"""XMI Parser Toolset — deterministic XMI parsing, no LLM.

Parses XMI 2.x files using stdlib xml.etree.ElementTree.
Auto-detects dialect (Sparx EA, MagicDraw, generic) via namespace URIs.
Normalizes all dialects into ParsedXmiModel.
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from google.adk.tools import FunctionTool
from google.adk.tools.base_toolset import BaseToolset

from xmi2sdc.common.audit import AuditLogger
from xmi2sdc.common.cache import CacheManager
from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.common.exceptions import XmiParseError
from xmi2sdc.common.xmi_types import (
    Multiplicity,
    ParsedXmiModel,
    UmlAssociation,
    UmlAssociationEnd,
    UmlAttribute,
    UmlClass,
    UmlEnumeration,
    UmlEnumLiteral,
    UmlPackage,
    XmiDialect,
)

# Common XMI/UML namespace URIs
NS_XMI = "http://www.omg.org/spec/XMI/20131001"
NS_XMI_20 = "http://schema.omg.org/spec/XMI/2.1"
NS_UML = "http://www.omg.org/spec/UML/20131001"
NS_UML_20 = "http://schema.omg.org/spec/UML/2.1"

# Sparx EA namespace markers
NS_EA = "http://www.sparxsystems.com"

# MagicDraw namespace markers
NS_MD = "http://www.nomagic.com"


def _detect_dialect(root: ET.Element, raw_xml: str = "") -> XmiDialect:
    """Detect XMI dialect from namespace declarations and element content.

    ElementTree strips unused xmlns declarations, so we also scan the
    raw XML text for vendor namespace URIs when available.

    Args:
        root: Parsed XML root element.
        raw_xml: Optional raw XML string for namespace URI scanning.
    """
    # Scan raw XML for xmlns declarations (most reliable)
    search_text = raw_xml.lower() if raw_xml else ""

    # Also collect namespace URIs from parsed element tags
    for elem in root.iter():
        tag = elem.tag
        if "{" in tag:
            search_text += " " + tag.split("}")[0].lstrip("{").lower()
        for attr_name in elem.attrib:
            if "{" in attr_name:
                search_text += " " + attr_name.split("}")[0].lstrip("{").lower()

    if "sparxsystems.com" in search_text or "sparx" in search_text:
        return XmiDialect.SPARX_EA
    if "nomagic.com" in search_text or "magicdraw" in search_text:
        return XmiDialect.MAGICDRAW

    return XmiDialect.GENERIC


def _detect_xmi_version(root: ET.Element) -> str:
    """Extract XMI version from root element attributes."""
    for attr_name, attr_val in root.attrib.items():
        if attr_name.endswith("version") or attr_name == "version":
            if attr_val.startswith("2"):
                return attr_val
    return "2.1"


def _build_ns_map(root: ET.Element) -> dict[str, str]:
    """Build namespace prefix map from the root element.

    Returns a dict mapping short prefixes to full URIs for use with
    ElementTree's namespace-aware find methods.
    """
    ns_map: dict[str, str] = {}

    # Scan root attributes for xmlns declarations
    for attr_name, attr_val in root.attrib.items():
        if attr_name.startswith("{"):
            continue
        if ":" in attr_name:
            prefix = attr_name.split(":")[-1]
            ns_map[prefix] = attr_val

    # Ensure we have xmi and uml namespaces
    if "xmi" not in ns_map:
        # Try common XMI namespaces
        for ns in [NS_XMI, NS_XMI_20]:
            ns_map["xmi"] = ns
            break
    if "uml" not in ns_map:
        for ns in [NS_UML, NS_UML_20]:
            ns_map["uml"] = ns
            break

    return ns_map


def _get_attr(elem: ET.Element, local_name: str) -> str:
    """Get an attribute value by local name, ignoring namespace prefixes."""
    # Try plain attribute first
    val = elem.get(local_name, "")
    if val:
        return val

    # Try with common namespace prefixes
    for attr_name, attr_val in elem.attrib.items():
        if attr_name.endswith(f"}}{local_name}") or attr_name.endswith(f":{local_name}"):
            return attr_val
    return ""


def _get_xmi_id(elem: ET.Element) -> str:
    """Extract xmi:id from an element."""
    return _get_attr(elem, "id") or _get_attr(elem, "xmi.id") or ""


def _get_xmi_type(elem: ET.Element) -> str:
    """Extract xmi:type from an element."""
    return _get_attr(elem, "type") or _get_attr(elem, "xmi.type") or ""


def _parse_multiplicity_value(val: str, default: int) -> int:
    """Parse a single multiplicity bound value.

    Handles: "0", "1", "*", "-1" (EA convention for unbounded), digits.
    """
    if val in ("*",):
        return -1
    if val.lstrip("-").isdigit():
        return int(val)
    return default


def _parse_multiplicity(elem: ET.Element) -> Multiplicity:
    """Parse multiplicity from lowerValue/upperValue child elements or attributes."""
    lower = 1
    upper = 1

    # Check for lowerValue/upperValue child elements
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "lowerValue":
            lower = _parse_multiplicity_value(child.get("value", "1"), 1)
            if lower == -1:
                lower = 0  # lower bound can't be unbounded
        elif tag == "upperValue":
            upper = _parse_multiplicity_value(child.get("value", "1"), 1)

    # Check for direct attributes
    if "lower" in elem.attrib:
        lower = _parse_multiplicity_value(elem.get("lower", "1"), 1)
        if lower == -1:
            lower = 0
    if "upper" in elem.attrib:
        upper = _parse_multiplicity_value(elem.get("upper", "1"), 1)

    return Multiplicity(lower=lower, upper=upper)


def _extract_documentation(elem: ET.Element) -> str:
    """Extract documentation from ownedComment child elements.

    Handles both UML model ownedComment (body attribute) and
    EA Extension documentation (value attribute).
    """
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "ownedComment":
            body = child.get("body", "")
            if body:
                return body
    return ""


def _parse_attribute(elem: ET.Element, type_map: dict[str, str]) -> UmlAttribute:
    """Parse a UML attribute (ownedAttribute with no association)."""
    name = elem.get("name", "")
    visibility = elem.get("visibility", "public")

    # Determine type name
    type_name = "String"
    type_ref = elem.get("type", "")
    if type_ref and type_ref in type_map:
        type_name = type_map[type_ref]
    elif type_ref:
        type_name = type_ref

    # Check for type child element (multiple patterns)
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "type":
            # Pattern 1: href attribute (generic XMI)
            href = child.get("href", "")
            if href:
                type_name = href.split("#")[-1] if "#" in href else href
            # Pattern 2: xmi:idref attribute (Sparx EA)
            elif _get_attr(child, "idref"):
                idref = _get_attr(child, "idref")
                if idref in type_map:
                    type_name = type_map[idref]
                else:
                    type_name = idref  # Preserve ref for downstream
            elif child.get("name"):
                type_name = child.get("name", type_name)

    multiplicity = _parse_multiplicity(elem)
    default_value = elem.get("default", None)

    # Check for defaultValue child
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "defaultValue":
            default_value = child.get("value", default_value)

    # Check isID
    is_id = elem.get("isID", "false").lower() == "true"

    # Extract documentation from ownedComment
    documentation = _extract_documentation(elem)

    return UmlAttribute(
        name=name,
        type_name=type_name,
        multiplicity=multiplicity,
        is_id=is_id,
        default_value=default_value,
        visibility=visibility,
        documentation=documentation,
    )


def _parse_enum(elem: ET.Element) -> UmlEnumeration:
    """Parse a UML enumeration from an element."""
    xmi_id = _get_xmi_id(elem)
    name = elem.get("name", "")
    documentation = _extract_documentation(elem)

    literals: list[UmlEnumLiteral] = []
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "ownedLiteral":
            lit_name = child.get("name", "")
            if lit_name:
                lit_doc = _extract_documentation(child)
                literals.append(UmlEnumLiteral(name=lit_name, documentation=lit_doc))

    return UmlEnumeration(xmi_id=xmi_id, name=name, literals=literals, documentation=documentation)


def _build_type_map(root: ET.Element) -> dict[str, str]:
    """Build a map of xmi:id → type name for resolving attribute type references."""
    type_map: dict[str, str] = {}
    for elem in root.iter():
        xmi_id = _get_xmi_id(elem)
        name = elem.get("name", "")
        if xmi_id and name:
            type_map[xmi_id] = name
    return type_map


def _is_class_like(xmi_type: str) -> bool:
    """Check if an xmi:type represents a class-like element.

    Includes uml:Class and uml:Activity (used by BPMN models in Sparx EA).
    Excludes AssociationClass.
    """
    if xmi_type.endswith("AssociationClass"):
        return False
    return xmi_type.endswith("Class") or xmi_type.endswith("Activity")


def _parse_class(elem: ET.Element, type_map: dict[str, str]) -> UmlClass:
    """Parse a UML class (or Activity) from an element."""
    xmi_id = _get_xmi_id(elem)
    name = elem.get("name", "")
    is_abstract = elem.get("isAbstract", "false").lower() == "true"

    attributes: list[UmlAttribute] = []
    parent_xmi_ids: list[str] = []

    # Extract class-level documentation
    documentation = _extract_documentation(elem)

    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "ownedAttribute":
            # Skip association-owned attributes (navigable ends)
            if child.get("association"):
                continue
            attributes.append(_parse_attribute(child, type_map))

        elif tag == "generalization":
            general_ref = child.get("general", "")
            if general_ref:
                parent_xmi_ids.append(general_ref)

    return UmlClass(
        xmi_id=xmi_id,
        name=name,
        is_abstract=is_abstract,
        attributes=attributes,
        parent_xmi_ids=parent_xmi_ids,
        documentation=documentation,
    )


def _build_element_index(root: ET.Element) -> dict[str, ET.Element]:
    """Build a map of xmi:id → Element for resolving cross-references.

    This is essential for Sparx EA exports where memberEnd references
    point to ownedAttribute elements on other classes.
    """
    index: dict[str, ET.Element] = {}
    for elem in root.iter():
        xmi_id = _get_xmi_id(elem)
        if xmi_id:
            index[xmi_id] = elem
    return index


def _parse_association_end(elem: ET.Element, type_map: dict[str, str]) -> UmlAssociationEnd:
    """Parse a single association end from an element (ownedEnd or ownedAttribute)."""
    role = elem.get("name", "")
    aggregation = elem.get("aggregation", "none")
    multiplicity = _parse_multiplicity(elem)

    # Resolve type — could be type= attribute or <type xmi:idref="..."/> child
    type_ref = elem.get("type", "")
    type_name = type_map.get(type_ref, type_ref) if type_ref else ""

    if not type_name:
        for child in elem:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "type":
                idref = _get_attr(child, "idref")
                if idref:
                    type_name = type_map.get(idref, idref)
                    type_ref = idref
                    break

    return UmlAssociationEnd(
        role=role,
        type_name=type_name,
        type_xmi_id=type_ref,
        multiplicity=multiplicity,
        aggregation=aggregation,
    )


def _parse_association(
    elem: ET.Element,
    type_map: dict[str, str],
    element_index: dict[str, ET.Element] | None = None,
) -> UmlAssociation | None:
    """Parse a UML association from an element.

    Handles two patterns:
    1. Generic XMI: both ends as ownedEnd children of the Association.
    2. Sparx EA: one ownedEnd on the Association + one ownedAttribute on a
       class (referenced via memberEnd idref).
    """
    xmi_id = _get_xmi_id(elem)
    name = elem.get("name", "")
    element_index = element_index or {}

    ends: list[UmlAssociationEnd] = []
    member_end_refs: list[str] = []

    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "ownedEnd":
            ends.append(_parse_association_end(child, type_map))

        elif tag == "memberEnd":
            # EA pattern: memberEnd references an element elsewhere
            idref = _get_attr(child, "idref")
            if idref:
                member_end_refs.append(idref)

    # If we have fewer than 2 inline ends, resolve memberEnd references
    if len(ends) < 2 and member_end_refs and element_index:
        # Collect IDs of ends we already have
        existing_ids = set()
        for child in elem:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "ownedEnd":
                existing_ids.add(_get_xmi_id(child))

        for ref_id in member_end_refs:
            if ref_id not in existing_ids and ref_id in element_index:
                ref_elem = element_index[ref_id]
                ends.append(_parse_association_end(ref_elem, type_map))

    if len(ends) < 2:
        return None

    documentation = _extract_documentation(elem)

    return UmlAssociation(
        xmi_id=xmi_id,
        name=name,
        source=ends[0],
        target=ends[1],
        documentation=documentation,
    )


def _collect_nested_classes(
    elem: ET.Element,
    type_map: dict[str, str],
    classes_out: list[UmlClass],
    element_index: dict[str, ET.Element] | None = None,
    associations_out: list[UmlAssociation] | None = None,
) -> None:
    """Recursively collect class-like elements nested inside another element.

    Sparx EA BPMN models nest Activity elements inside parent Activities
    (rather than using packages). This flattens them into the classes list
    while preserving association collection.
    """
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        xmi_type = _get_xmi_type(child)

        if tag == "packagedElement" or tag == "ownedMember":
            if _is_class_like(xmi_type):
                cls = _parse_class(child, type_map)
                classes_out.append(cls)
                # Recurse into nested elements
                _collect_nested_classes(
                    child, type_map, classes_out, element_index, associations_out
                )
            elif xmi_type.endswith("Association") and associations_out is not None:
                assoc = _parse_association(child, type_map, element_index)
                if assoc:
                    associations_out.append(assoc)


def _parse_package(
    elem: ET.Element,
    type_map: dict[str, str],
    element_index: dict[str, ET.Element] | None = None,
    associations_out: list[UmlAssociation] | None = None,
) -> UmlPackage:
    """Parse a UML package from an element, recursively handling sub-packages.

    Args:
        elem: Package XML element.
        type_map: ID-to-name mapping for type resolution.
        element_index: Optional element index for resolving memberEnd refs.
        associations_out: Optional list to collect associations found inside
            packages (EA puts associations inside the same package as classes).
    """
    xmi_id = _get_xmi_id(elem)
    name = elem.get("name", "")

    classes: list[UmlClass] = []
    enumerations: list[UmlEnumeration] = []
    sub_packages: list[UmlPackage] = []

    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        xmi_type = _get_xmi_type(child)

        if tag == "packagedElement" or tag == "ownedMember":
            if _is_class_like(xmi_type):
                cls = _parse_class(child, type_map)
                classes.append(cls)
                # Recursively collect nested class-like elements
                # (EA BPMN models nest Activities inside Activities)
                _collect_nested_classes(child, type_map, classes, element_index, associations_out)
            elif xmi_type.endswith("Enumeration"):
                enumerations.append(_parse_enum(child))
            elif xmi_type.endswith("Package"):
                sub_packages.append(
                    _parse_package(child, type_map, element_index, associations_out)
                )
            elif xmi_type.endswith("Association") and associations_out is not None:
                assoc = _parse_association(child, type_map, element_index)
                if assoc:
                    associations_out.append(assoc)

    return UmlPackage(
        xmi_id=xmi_id,
        name=name,
        classes=classes,
        enumerations=enumerations,
        sub_packages=sub_packages,
    )


def _is_extension_or_documentation(tag: str) -> bool:
    """Check if a tag is an xmi:Extension or xmi:Documentation element to skip."""
    local = tag.split("}")[-1] if "}" in tag else tag
    return local in ("Extension", "Documentation")


def _parse_generic_xmi(root: ET.Element, model_name: str) -> ParsedXmiModel:
    """Parse a generic XMI 2.x document into ParsedXmiModel.

    Also handles Sparx EA patterns (memberEnd references, split association
    ends, xmi:Extension skipping) since EA exports are structurally valid
    XMI 2.x with vendor extensions.
    """
    type_map = _build_type_map(root)
    element_index = _build_element_index(root)
    xmi_version = _detect_xmi_version(root)

    packages: list[UmlPackage] = []
    associations: list[UmlAssociation] = []
    top_classes: list[UmlClass] = []
    top_enums: list[UmlEnumeration] = []

    # Find the UML Model element — could be direct child or nested
    model_elem = None
    for child in root:
        # Skip xmi:Extension and xmi:Documentation (EA-specific)
        if _is_extension_or_documentation(child.tag):
            continue
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        xmi_type = _get_xmi_type(child)
        if tag == "Model" or xmi_type.endswith("Model") or tag.endswith(":Model"):
            model_elem = child
            break

    # If no Model wrapper, treat root as the container
    container = model_elem if model_elem is not None else root

    for child in container:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        xmi_type = _get_xmi_type(child)

        # Skip extension/documentation elements that may appear inside Model
        if _is_extension_or_documentation(child.tag):
            continue

        if tag == "packagedElement" or tag == "ownedMember":
            if xmi_type.endswith("Package"):
                packages.append(_parse_package(child, type_map, element_index, associations))
            elif _is_class_like(xmi_type):
                top_classes.append(_parse_class(child, type_map))
                # Collect nested class-like elements (BPMN Activities)
                _collect_nested_classes(child, type_map, top_classes, element_index, associations)
            elif xmi_type.endswith("Enumeration"):
                top_enums.append(_parse_enum(child))
            elif xmi_type.endswith("Association"):
                assoc = _parse_association(child, type_map, element_index)
                if assoc:
                    associations.append(assoc)

    return ParsedXmiModel(
        model_name=model_name,
        dialect=XmiDialect.GENERIC,
        xmi_version=xmi_version,
        packages=packages,
        associations=associations,
        top_level_classes=top_classes,
        top_level_enumerations=top_enums,
    )


class XmiParserToolset(BaseToolset):
    """Deterministic XMI parser — no LLM calls.

    Parses XMI files into the universal ParsedXmiModel intermediate
    representation. Auto-detects dialect and normalizes structure.
    """

    def __init__(self, config: XMI2SDCConfig, **kwargs):
        super().__init__(**kwargs)
        self._config = config
        self._cache = CacheManager(config.cache.root)
        self._cache.ensure_dirs()
        self._audit = AuditLogger(config.audit.path, config.audit.log_level)

    async def get_tools(self, readonly_context=None) -> list:
        """Return the parser tools as FunctionTool instances."""
        tools = [
            FunctionTool(self.parse_xmi_file),
            FunctionTool(self.parse_xmi_string),
            FunctionTool(self.detect_dialect),
        ]
        if readonly_context and self.tool_filter:
            return [t for t in tools if self._is_tool_selected(t, readonly_context)]
        return tools

    async def parse_xmi_file(self, file_path: str, model_name: str = "") -> dict:
        """Parse an XMI file into a normalized model structure.

        Reads the XMI file, auto-detects dialect, and produces a
        ParsedXmiModel as a JSON-serializable dict.

        Args:
            file_path: Path to the XMI file.
            model_name: Optional name for the model. Defaults to filename stem.

        Returns:
            Dict representation of ParsedXmiModel.
        """
        start = time.monotonic()
        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(f"XMI file not found: {file_path}")

        if not model_name:
            model_name = path.stem

        xmi_content = self._read_xmi_file(path)
        result = self._parse(xmi_content, model_name)

        # Cache the result
        cache_path = self._cache.parsed_path(model_name)
        cache_path.write_text(json.dumps(result, indent=2))

        self._audit.log(
            agent="parser",
            tool="parse_xmi_file",
            inputs={"file_path": file_path, "model_name": model_name},
            outputs=result,
            start_time=start,
        )
        return result

    async def parse_xmi_string(self, xmi_content: str, model_name: str) -> dict:
        """Parse an XMI string into a normalized model structure.

        Args:
            xmi_content: Raw XMI/XML string content.
            model_name: Name for the model.

        Returns:
            Dict representation of ParsedXmiModel.
        """
        start = time.monotonic()
        result = self._parse(xmi_content, model_name)

        # Cache the result
        cache_path = self._cache.parsed_path(model_name)
        cache_path.write_text(json.dumps(result, indent=2))

        self._audit.log(
            agent="parser",
            tool="parse_xmi_string",
            inputs={"model_name": model_name, "xmi_content_length": len(xmi_content)},
            outputs=result,
            start_time=start,
        )
        return result

    async def detect_dialect(self, file_path: str) -> dict:
        """Detect the XMI dialect of a file without full parsing.

        Args:
            file_path: Path to the XMI file.

        Returns:
            Dict with dialect, xmi_version, and root element info.
        """
        start = time.monotonic()
        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(f"XMI file not found: {file_path}")

        raw_xml = self._read_xmi_file(path)
        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            raise XmiParseError(f"Invalid XML in {file_path}: {exc}") from exc

        dialect = _detect_dialect(root, raw_xml)
        xmi_version = _detect_xmi_version(root)

        result = {
            "file": file_path,
            "dialect": dialect.value,
            "xmi_version": xmi_version,
            "root_tag": root.tag,
            "root_attribs": dict(root.attrib),
        }

        self._audit.log(
            agent="parser",
            tool="detect_dialect",
            inputs={"file_path": file_path},
            outputs=result,
            start_time=start,
        )
        return result

    @staticmethod
    def _read_xmi_file(path: Path) -> str:
        """Read an XMI file, handling encoding detection.

        Sparx EA exports use windows-1252 encoding. We try UTF-8 first,
        then fall back to windows-1252, then latin-1 (which never fails).
        """
        for encoding in ("utf-8", "windows-1252", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except (UnicodeDecodeError, ValueError):
                continue
        # latin-1 should never fail, but just in case
        return path.read_bytes().decode("latin-1")

    def _parse(self, xmi_content: str, model_name: str) -> dict:
        """Internal parse method — dialect dispatch."""
        try:
            root = ET.fromstring(xmi_content)
        except ET.ParseError as exc:
            raise XmiParseError(f"Invalid XML: {exc}") from exc

        dialect = _detect_dialect(root, xmi_content)

        # Phase 1: generic XMI 2.x only
        # Phase 2 will add Sparx EA and MagicDraw adapters
        if dialect == XmiDialect.SPARX_EA:
            # For now, fall through to generic parser
            parsed = _parse_generic_xmi(root, model_name)
            parsed.dialect = XmiDialect.SPARX_EA
        elif dialect == XmiDialect.MAGICDRAW:
            parsed = _parse_generic_xmi(root, model_name)
            parsed.dialect = XmiDialect.MAGICDRAW
        else:
            parsed = _parse_generic_xmi(root, model_name)

        return parsed.model_dump(mode="json")
