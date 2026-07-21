"""SDC Mapper Toolset — deterministic UML-to-SDC4 type mapping.

Phase 1: Pure rules-based mapping, no LLM. Applies the type mapping
table to produce a JSON mapping plan that the Assembler can execute.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from google.adk.tools import FunctionTool
from google.adk.tools.base_toolset import BaseToolset

from xmi2sdc.common.audit import AuditLogger
from xmi2sdc.common.cache import CacheManager
from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.common.inheritance import flatten_inheritance

# Canonical UML primitive type names (case-insensitive matching)
_BOOLEAN_TYPES = {"boolean", "bool"}
_INTEGER_TYPES = {"integer", "int", "long", "short", "byte", "unsignedint", "positiveinteger"}
_UNSIGNED_INTEGER_TYPES = {
    "unsignedint",
    "unsignedlong",
    "unsignedshort",
    "unsignedbyte",
    "nonnegativeinteger",
    "positiveinteger",
    "natural",
}
_REAL_TYPES = {"real", "float", "double", "decimal", "number"}
_STRING_TYPES = {"string", "char", "text", "name", "token", "uri", "url", "id"}
_TEMPORAL_TYPES = {
    "date",
    "datetime",
    "time",
    "timestamp",
    "instant",
    "duration",
    "localdate",
    "localtime",
    "localdatetime",
}


def _normalize_type_name(type_name: str) -> str:
    """Normalize a UML type name for matching (lowercase, strip whitespace)."""
    return type_name.strip().lower().replace(" ", "").replace("_", "")


def _map_primitive_type(type_name: str, is_unsigned: bool = False) -> dict:
    """Map a UML primitive type to an SDC4 type specification.

    Args:
        type_name: The UML type name.
        is_unsigned: Whether the integer type is known to be non-negative.

    Returns:
        Dict with sdc4_type and any additional configuration.
    """
    normalized = _normalize_type_name(type_name)

    if normalized in _BOOLEAN_TYPES:
        return {"sdc4_type": "XdBoolean"}

    if normalized in _UNSIGNED_INTEGER_TYPES:
        return {"sdc4_type": "XdCount"}

    if normalized in _INTEGER_TYPES:
        if is_unsigned:
            return {"sdc4_type": "XdCount"}
        return {"sdc4_type": "XdQuantity", "restriction": "integer"}

    if normalized in _REAL_TYPES:
        return {"sdc4_type": "XdQuantity"}

    if normalized in _TEMPORAL_TYPES:
        return {"sdc4_type": "XdTemporal"}

    if normalized in _STRING_TYPES:
        return {"sdc4_type": "XdString"}

    # Unknown primitive — default to XdString
    return {"sdc4_type": "XdString", "unmapped_source_type": type_name}


def _map_multiplicity(lower: int, upper: int) -> dict:
    """Map UML multiplicity to SDC4 occurrence constraints.

    Args:
        lower: Lower bound (0 or positive integer).
        upper: Upper bound (-1 for unbounded, or positive integer).

    Returns:
        Dict with minOccurs, maxOccurs, and is_list flag.
    """
    min_occurs = max(0, lower)
    max_occurs = upper if upper > 0 else 9999  # SDC4 uses high number for unbounded
    is_list = upper == -1 or upper > 1

    return {
        "minOccurs": min_occurs,
        "maxOccurs": max_occurs,
        "is_list": is_list,
    }


# Vocabularies used by the inheritance-provenance semantic links (see the
# "namespaces" block emitted in the mapping plan). Both are ratified and
# already part of the SDC stack; no predicate is invented here.
PROVENANCE_NAMESPACES = {
    "prov": "http://www.w3.org/ns/prov#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}

# Stable, greppable fence for the human-readable provenance note appended to an
# inherited component's description. Lets a reader (and a tool) find or strip it.
_PROVENANCE_FENCE = "[XMI2SDC provenance]"


def _append_provenance_note(description: str, introduced_by: str) -> str:
    """Append a fenced provenance note for an inherited (materialized) attribute.

    The note tells the human-in-the-loop where the attribute came from and how
    to contain it if reconstructing the original hierarchy. It guides the
    containment decision without dictating it: in SDC any component may be
    placed in any Cluster, and that call belongs to the human.

    Args:
        description: The component's existing description (may be empty).
        introduced_by: Name of the ancestor class that introduced the attribute.

    Returns:
        The description with the fenced provenance note appended.
    """
    note = (
        f"{_PROVENANCE_FENCE} Inherited from UML class {introduced_by}. "
        f"In the source model this attribute belonged to {introduced_by}; "
        f"if reconstructing the original hierarchy, contain it accordingly."
    )
    return f"{description}\n\n{note}" if description else note


class SdcMapperToolset(BaseToolset):
    """Deterministic UML-to-SDC4 type mapper — no LLM in Phase 1.

    Applies the type mapping rules to a ParsedXmiModel and produces
    a JSON mapping plan for downstream Assembly API calls.
    """

    def __init__(self, config: XMI2SDCConfig, **kwargs):
        super().__init__(**kwargs)
        self._config = config
        self._cache = CacheManager(config.cache.root)
        self._cache.ensure_dirs()
        self._audit = AuditLogger(config.audit.path, config.audit.log_level)

    async def get_tools(self, readonly_context=None) -> list:
        """Return the mapper tools as FunctionTool instances."""
        tools = [
            FunctionTool(self.map_model),
            FunctionTool(self.map_class),
            FunctionTool(self.map_type),
        ]
        if readonly_context and self.tool_filter:
            return [t for t in tools if self._is_tool_selected(t, readonly_context)]
        return tools

    async def map_model(self, parsed_model: dict) -> dict:
        """Map an entire ParsedXmiModel to an SDC4 mapping plan.

        Takes the output of parse_xmi_file/parse_xmi_string and produces
        a complete mapping plan with SDC4 type assignments for all classes,
        attributes, and associations.

        Args:
            parsed_model: Dict representation of ParsedXmiModel (from parser).

        Returns:
            Dict with model_name, components (list of SDC4 component specs),
            clusters, and unmapped items.
        """
        start = time.monotonic()
        model_name = parsed_model.get("model_name", "unknown")

        components: list[dict] = []
        clusters: list[dict] = []
        unmapped: list[dict] = []

        # Flatten inheritance before mapping
        flatten_inheritance(parsed_model)

        # Build class lookup for association resolution
        all_classes = self._collect_all_classes(parsed_model)
        class_name_by_id = {c.get("xmi_id", ""): c.get("name", "") for c in all_classes}
        enum_map = self._build_enum_map(parsed_model)

        # Map each class
        for cls in all_classes:
            class_result = self._map_single_class(cls, enum_map)
            # Always extract components and unmapped items
            components.extend(class_result.get("components", []))
            unmapped.extend(class_result.get("unmapped", []))
            # Add cluster definition if class has components
            if class_result.get("is_cluster") and class_result.get("cluster_name"):
                cluster_def = {
                    "cluster_name": class_result["cluster_name"],
                    "source_xmi_id": class_result.get("source_xmi_id", ""),
                    "description": class_result.get("description", ""),
                    "component_refs": class_result.get("component_refs", []),
                }
                # Record the generalization edges as rdfs:subClassOf links so the
                # class hierarchy is reconstructable from the flat model.
                subclass_links = [
                    {"predicate": "rdfs:subClassOf", "object": class_name_by_id[pid]}
                    for pid in cls.get("parent_xmi_ids", [])
                    if class_name_by_id.get(pid)
                ]
                if subclass_links:
                    cluster_def["semantic_links"] = subclass_links
                clusters.append(cluster_def)

        # Map associations to cluster containment or association clusters
        for assoc in parsed_model.get("associations", []):
            assoc_mapping = self._map_association(assoc, all_classes)
            if assoc_mapping:
                assoc_components = assoc_mapping.pop("components", [])
                components.extend(assoc_components)
                clusters.append(assoc_mapping)

        result = {
            "model_name": model_name,
            "dialect": parsed_model.get("dialect", "generic_xmi21"),
            "namespaces": PROVENANCE_NAMESPACES,
            "components": components,
            "clusters": clusters,
            "unmapped": unmapped,
            "summary": {
                "total_classes": len(all_classes),
                "total_components": len(components),
                "total_clusters": len(clusters),
                "total_unmapped": len(unmapped),
            },
        }

        # Cache the mapping plan
        cache_path = self._cache.mapping_path(model_name)
        cache_path.write_text(json.dumps(result, indent=2))

        self._audit.log(
            agent="mapper",
            tool="map_model",
            inputs={"model_name": model_name},
            outputs=result,
            start_time=start,
        )
        return result

    async def map_class(self, uml_class: dict) -> dict:
        """Map a single UML class to SDC4 components.

        Args:
            uml_class: Dict representation of a UmlClass.

        Returns:
            Dict with components list and/or cluster definition.
        """
        start = time.monotonic()
        result = self._map_single_class(uml_class, {})

        self._audit.log(
            agent="mapper",
            tool="map_class",
            inputs={"class_name": uml_class.get("name", "unknown")},
            outputs=result,
            start_time=start,
        )
        return result

    async def map_type(self, uml_type_name: str) -> dict:
        """Map a single UML type name to an SDC4 type.

        Useful for quick lookups and testing.

        Args:
            uml_type_name: UML type name (e.g., "String", "Integer", "Boolean").

        Returns:
            Dict with sdc4_type and any configuration.
        """
        start = time.monotonic()
        result = _map_primitive_type(uml_type_name)

        self._audit.log(
            agent="mapper",
            tool="map_type",
            inputs={"uml_type_name": uml_type_name},
            outputs=result,
            start_time=start,
        )
        return result

    def _collect_all_classes(self, parsed_model: dict) -> list[dict]:
        """Flatten all classes from packages and top-level."""
        result = list(parsed_model.get("top_level_classes", []))
        for pkg in parsed_model.get("packages", []):
            result.extend(self._collect_classes_from_package(pkg))
        return result

    def _collect_classes_from_package(self, pkg: dict) -> list[dict]:
        """Recursively collect classes from a package dict."""
        result = list(pkg.get("classes", []))
        for sub in pkg.get("sub_packages", []):
            result.extend(self._collect_classes_from_package(sub))
        return result

    def _build_enum_map(self, parsed_model: dict) -> dict[str, list[str]]:
        """Build a map of enumeration xmi_id → list of literal names."""
        enum_map: dict[str, list[str]] = {}
        for enum in parsed_model.get("top_level_enumerations", []):
            xmi_id = enum.get("xmi_id", "")
            literals = [lit.get("name", "") for lit in enum.get("literals", [])]
            if xmi_id:
                enum_map[xmi_id] = literals
            # Also map by name for type_name references
            name = enum.get("name", "")
            if name:
                enum_map[name] = literals
        for pkg in parsed_model.get("packages", []):
            self._collect_enums_from_package(pkg, enum_map)
        return enum_map

    def _collect_enums_from_package(self, pkg: dict, enum_map: dict) -> None:
        """Recursively collect enumerations from packages."""
        for enum in pkg.get("enumerations", []):
            xmi_id = enum.get("xmi_id", "")
            literals = [lit.get("name", "") for lit in enum.get("literals", [])]
            if xmi_id:
                enum_map[xmi_id] = literals
            name = enum.get("name", "")
            if name:
                enum_map[name] = literals
        for sub in pkg.get("sub_packages", []):
            self._collect_enums_from_package(sub, enum_map)

    def _map_single_class(self, cls: dict, enum_map: dict) -> dict:
        """Map a single class to SDC4 components or a cluster."""
        class_name = cls.get("name", "unknown")
        # Use flattened attributes when available, fall back to own attributes
        all_attrs = cls.get("all_attributes", [])
        attributes = all_attrs if all_attrs else cls.get("attributes", [])

        # A class with attributes maps to individual SDC4 components
        # grouped in a Cluster
        if not attributes:
            # Empty class — becomes a Cluster placeholder
            return {
                "is_cluster": True,
                "cluster_name": class_name,
                "source_xmi_id": cls.get("xmi_id", ""),
                "description": cls.get("documentation", ""),
                "component_refs": [],
            }

        components: list[dict] = []
        unmapped: list[dict] = []

        for attr in attributes:
            attr_name = attr.get("name", "")
            type_name = attr.get("type_name", "String")
            mult = attr.get("multiplicity", {"lower": 1, "upper": 1})

            doc = attr.get("documentation", "")

            # Inheritance provenance. If this attribute was introduced by an
            # ancestor (flatten stamped introduced_by_*), record where it came
            # from: a prov:wasDerivedFrom link for machines, and a fenced note
            # in the description for the human doing containment. Own attributes
            # carry no link and no note, so their output is unchanged.
            introduced_by = attr.get("introduced_by_name", "")
            is_inherited = bool(introduced_by) and introduced_by != class_name
            sem_links: list[dict] = []
            if is_inherited:
                sem_links = [
                    {
                        "predicate": "prov:wasDerivedFrom",
                        "object": f"{introduced_by}.{attr_name}",
                    }
                ]
                doc = _append_provenance_note(doc, introduced_by)

            # Check if type is an enumeration
            if type_name in enum_map:
                comp = {
                    "source_class": class_name,
                    "source_attribute": attr_name,
                    "source_type": type_name,
                    "sdc4_type": "XdString",
                    "enumerations": enum_map[type_name],
                    "description": doc,
                    "label": f"{class_name}.{attr_name}",
                    **_map_multiplicity(mult.get("lower", 1), mult.get("upper", 1)),
                }
                if sem_links:
                    comp["semantic_links"] = sem_links
                components.append(comp)
                continue

            # Map primitive type
            type_mapping = _map_primitive_type(type_name)
            comp = {
                "source_class": class_name,
                "source_attribute": attr_name,
                "source_type": type_name,
                "description": doc,
                "label": f"{class_name}.{attr_name}",
                **type_mapping,
                **_map_multiplicity(mult.get("lower", 1), mult.get("upper", 1)),
            }
            if sem_links:
                comp["semantic_links"] = sem_links

            if "unmapped_source_type" in type_mapping:
                unmapped.append(comp)
            else:
                components.append(comp)

        # Create a cluster for this class if it has components
        result: dict = {
            "is_cluster": len(components) > 0,
            "components": components,
            "unmapped": unmapped,
        }

        if components:
            result["cluster_name"] = class_name
            result["source_xmi_id"] = cls.get("xmi_id", "")
            result["description"] = cls.get("documentation", "")
            result["component_refs"] = [c["label"] for c in components]

        return result

    @staticmethod
    def _format_multiplicity_str(mult: dict) -> str:
        """Format a multiplicity dict as a human-readable string (e.g., '0..*')."""
        lower = mult.get("lower", 1)
        upper = mult.get("upper", 1)
        lower_str = str(lower)
        upper_str = "*" if upper == -1 else str(upper)
        return f"{lower_str}..{upper_str}"

    def _build_association_cluster(self, assoc: dict, association_type: str) -> dict:
        """Build a Cluster with XdString role components for a non-composition association.

        Each association end becomes an XdString component capturing the role
        name, type reference, and multiplicity.

        Args:
            assoc: Dict representation of a UmlAssociation.
            association_type: Either 'plain' or 'shared'.

        Returns:
            Cluster dict with embedded components list.
        """
        assoc_name = assoc.get("name", "") or "unnamed_association"
        documentation = assoc.get("documentation", "")

        components: list[dict] = []
        component_refs: list[str] = []

        for end in (assoc.get("source", {}), assoc.get("target", {})):
            role = end.get("role", "")
            type_name = end.get("type_name", "")
            mult = end.get("multiplicity", {"lower": 1, "upper": 1})
            mult_str = self._format_multiplicity_str(mult)

            label = f"{assoc_name}.{role}" if role else f"{assoc_name}.{type_name}"
            description = f"Role '{role}' referencing {type_name} [{mult_str}]"

            comp = {
                "source_class": assoc_name,
                "source_attribute": role or type_name,
                "source_type": type_name,
                "sdc4_type": "XdString",
                "description": description,
                "label": label,
                "minOccurs": max(0, mult.get("lower", 1)),
                "maxOccurs": mult.get("upper", 1) if mult.get("upper", 1) > 0 else 9999,
                "is_list": mult.get("upper", 1) == -1 or mult.get("upper", 1) > 1,
                "role_name": role,
                "referenced_type": type_name,
            }
            components.append(comp)
            component_refs.append(label)

        return {
            "is_cluster": True,
            "cluster_name": assoc_name,
            "source_xmi_id": assoc.get("xmi_id", ""),
            "description": documentation,
            "component_refs": component_refs,
            "association_type": association_type,
            "components": components,
        }

    def _map_association(self, assoc: dict, all_classes: list[dict]) -> Optional[dict]:
        """Map a UML association to an SDC4 cluster.

        Three aggregation paths:
        - composite → cluster containment (existing behavior)
        - shared → association cluster with role components
        - none (plain) → association cluster with role components
        """
        source = assoc.get("source", {})
        target = assoc.get("target", {})

        source_agg = source.get("aggregation", "none")
        target_agg = target.get("aggregation", "none")

        # Composition → cluster containment
        if source_agg == "composite" or target_agg == "composite":
            if source_agg == "composite":
                owner_name = source.get("type_name", "")
                contained_name = target.get("type_name", "")
            else:
                owner_name = target.get("type_name", "")
                contained_name = source.get("type_name", "")

            return {
                "is_cluster": True,
                "cluster_name": owner_name,
                "source_xmi_id": assoc.get("xmi_id", ""),
                "description": assoc.get("documentation", ""),
                "component_refs": [contained_name],
                "containment_type": "composition",
            }

        # Shared aggregation → association cluster
        if source_agg == "shared" or target_agg == "shared":
            return self._build_association_cluster(assoc, "shared")

        # Plain association (aggregation=none on both ends)
        return self._build_association_cluster(assoc, "plain")
