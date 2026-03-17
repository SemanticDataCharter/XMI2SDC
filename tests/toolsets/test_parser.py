"""Tests for xmi2sdc.toolsets.parser."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.common.exceptions import XmiParseError
from xmi2sdc.common.xmi_types import XmiDialect
from xmi2sdc.toolsets.parser import (
    XmiParserToolset,
    _detect_dialect,
    _detect_xmi_version,
    _extract_documentation,
    _parse_multiplicity_value,
)

# --- Dialect Detection ---


def test_detect_generic_dialect():
    """Generic XMI should be detected when no vendor namespaces present."""
    raw = '<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20131001" xmi:version="2.1"/>'
    root = ET.fromstring(raw)
    assert _detect_dialect(root, raw) == XmiDialect.GENERIC


def test_detect_sparx_ea_dialect():
    """Sparx EA namespace should trigger SPARX_EA dialect."""
    raw = (
        '<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20131001"'
        ' xmlns:sparx="http://www.sparxsystems.com/foo" xmi:version="2.1"/>'
    )
    root = ET.fromstring(raw)
    assert _detect_dialect(root, raw) == XmiDialect.SPARX_EA


def test_detect_magicdraw_dialect():
    """MagicDraw/NoMagic namespace should trigger MAGICDRAW dialect."""
    raw = (
        '<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20131001"'
        ' xmlns:md="http://www.nomagic.com/magicdraw" xmi:version="2.1"/>'
    )
    root = ET.fromstring(raw)
    assert _detect_dialect(root, raw) == XmiDialect.MAGICDRAW


def test_detect_xmi_version():
    """Should extract version attribute from root."""
    root = ET.fromstring(
        '<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20131001" xmi:version="2.5"/>'
    )
    assert _detect_xmi_version(root) == "2.5"


# --- Parser Toolset ---


@pytest.fixture
def parser(tmp_path):
    """Create a parser toolset with tmp cache dir."""
    config = XMI2SDCConfig(
        cache={"root": str(tmp_path / "cache")},
        audit={"path": str(tmp_path / "cache" / "audit.jsonl")},
    )
    return XmiParserToolset(config=config)


@pytest.mark.asyncio
async def test_parse_xmi_file_generic(parser, generic_xmi_path):
    """Should parse the generic XMI fixture successfully."""
    result = await parser.parse_xmi_file(str(generic_xmi_path))

    assert result["model_name"] == "generic_xmi21"
    assert result["dialect"] == "generic_xmi21"

    # Should have one package (Core)
    assert len(result["packages"]) == 1
    core_pkg = result["packages"][0]
    assert core_pkg["name"] == "Core"

    # Core package should have Person and Address classes
    class_names = {c["name"] for c in core_pkg["classes"]}
    assert "Person" in class_names
    assert "Address" in class_names

    # Should have Gender enumeration in Core package
    enum_names = {e["name"] for e in core_pkg["enumerations"]}
    assert "Gender" in enum_names

    # Should have top-level Organization class
    top_class_names = {c["name"] for c in result["top_level_classes"]}
    assert "Organization" in top_class_names

    # Should have top-level Status enumeration
    top_enum_names = {e["name"] for e in result["top_level_enumerations"]}
    assert "Status" in top_enum_names

    # Should have one association
    assert len(result["associations"]) == 1


@pytest.mark.asyncio
async def test_parse_xmi_file_sparx_ea(parser, sparx_ea_xmi_path):
    """Should detect Sparx EA dialect."""
    result = await parser.parse_xmi_file(str(sparx_ea_xmi_path))
    assert result["dialect"] == "sparx_ea"

    # Should find Customer class with 3 attributes
    all_classes = []
    for pkg in result["packages"]:
        all_classes.extend(pkg["classes"])
    all_classes.extend(result.get("top_level_classes", []))

    customer = next((c for c in all_classes if c["name"] == "Customer"), None)
    assert customer is not None
    assert len(customer["attributes"]) == 3

    # customerId should be marked as ID
    id_attr = next((a for a in customer["attributes"] if a["name"] == "customerId"), None)
    assert id_attr is not None
    assert id_attr["is_id"] is True


@pytest.mark.asyncio
async def test_parse_xmi_file_magicdraw(parser, magicdraw_xmi_path):
    """Should detect MagicDraw dialect."""
    result = await parser.parse_xmi_file(str(magicdraw_xmi_path))
    assert result["dialect"] == "magicdraw"

    # Should find Product class
    top_classes = result.get("top_level_classes", [])
    product = next((c for c in top_classes if c["name"] == "Product"), None)
    assert product is not None
    assert len(product["attributes"]) == 3


@pytest.mark.asyncio
async def test_parse_xmi_string(parser, generic_xmi_content):
    """Should parse XMI from string content."""
    result = await parser.parse_xmi_string(generic_xmi_content, "string_model")
    assert result["model_name"] == "string_model"
    assert len(result["packages"]) == 1


@pytest.mark.asyncio
async def test_parse_xmi_file_not_found(parser):
    """Should raise FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        await parser.parse_xmi_file("/nonexistent/model.xmi")


@pytest.mark.asyncio
async def test_parse_invalid_xml(parser):
    """Should raise XmiParseError for invalid XML."""
    with pytest.raises(XmiParseError):
        await parser.parse_xmi_string("<not>valid<xml", "bad")


@pytest.mark.asyncio
async def test_detect_dialect_tool(parser, generic_xmi_path):
    """detect_dialect tool should return dialect info."""
    result = await parser.detect_dialect(str(generic_xmi_path))
    assert result["dialect"] == "generic_xmi21"
    assert result["xmi_version"] == "2.1"
    assert "root_tag" in result


@pytest.mark.asyncio
async def test_parse_caches_result(parser, generic_xmi_path, tmp_path):
    """Parsed result should be cached to disk."""
    await parser.parse_xmi_file(str(generic_xmi_path))
    cache_path = tmp_path / "cache" / "parsed" / "generic_xmi21.json"
    assert cache_path.is_file()


@pytest.mark.asyncio
async def test_parse_person_attributes(parser, generic_xmi_path):
    """Person class should have correct attribute types."""
    result = await parser.parse_xmi_file(str(generic_xmi_path))
    core_pkg = result["packages"][0]
    person = next(c for c in core_pkg["classes"] if c["name"] == "Person")

    attrs = {a["name"]: a for a in person["attributes"]}
    assert "name" in attrs
    assert "age" in attrs
    assert "email" in attrs
    assert "isActive" in attrs
    assert "dateOfBirth" in attrs
    assert "weight" in attrs

    # Check type resolution
    assert attrs["name"]["type_name"] == "String"
    assert attrs["age"]["type_name"] == "Integer"
    assert attrs["isActive"]["type_name"] == "Boolean"
    assert attrs["dateOfBirth"]["type_name"] == "Date"
    assert attrs["weight"]["type_name"] == "Float"

    # Check multiplicity on email (0..*)
    assert attrs["email"]["multiplicity"]["lower"] == 0
    assert attrs["email"]["multiplicity"]["upper"] == -1

    # Check multiplicity on age (0..1)
    assert attrs["age"]["multiplicity"]["lower"] == 0
    assert attrs["age"]["multiplicity"]["upper"] == 1


@pytest.mark.asyncio
async def test_parse_enumeration_literals(parser, generic_xmi_path):
    """Gender enumeration should have Male/Female/Other literals."""
    result = await parser.parse_xmi_file(str(generic_xmi_path))
    core_pkg = result["packages"][0]
    gender = next(e for e in core_pkg["enumerations"] if e["name"] == "Gender")

    literal_names = [lit["name"] for lit in gender["literals"]]
    assert literal_names == ["Male", "Female", "Other"]


@pytest.mark.asyncio
async def test_parse_association_composition(parser, generic_xmi_path):
    """Composition association should be detected."""
    result = await parser.parse_xmi_file(str(generic_xmi_path))
    assoc = result["associations"][0]
    assert assoc["name"] == "orgAddresses"

    # One end should have composite aggregation
    source_agg = assoc["source"]["aggregation"]
    target_agg = assoc["target"]["aggregation"]
    assert source_agg == "composite" or target_agg == "composite"


@pytest.mark.asyncio
async def test_get_tools(parser):
    """get_tools should return 3 FunctionTools."""
    tools = await parser.get_tools()
    assert len(tools) == 3
    tool_names = {t.name for t in tools}
    assert "parse_xmi_file" in tool_names
    assert "parse_xmi_string" in tool_names
    assert "detect_dialect" in tool_names


# --- Sparx EA Taxonomy (deep composition hierarchy) ---


@pytest.mark.asyncio
async def test_parse_ea_taxonomy_dialect(parser, sparx_ea_taxonomy_path):
    """Sparx EA taxonomy should be detected as SPARX_EA dialect."""
    result = await parser.parse_xmi_file(str(sparx_ea_taxonomy_path))
    assert result["dialect"] == "sparx_ea"


@pytest.mark.asyncio
async def test_parse_ea_taxonomy_classes(parser, sparx_ea_taxonomy_path):
    """Should find all 5 taxonomy classes across all levels."""
    result = await parser.parse_xmi_file(str(sparx_ea_taxonomy_path))

    # All classes should be inside the APQC_PCF_Retail package
    assert len(result["packages"]) == 1
    pkg = result["packages"][0]
    assert pkg["name"] == "APQC_PCF_Retail"

    class_names = {c["name"] for c in pkg["classes"]}
    assert "1.0 Develop Vision and Strategy" in class_names
    assert "1.1 Define the business concept and long-term vision" in class_names
    assert "1.2 Develop business strategy" in class_names
    assert "1.1.1 Assess the external environment" in class_names
    assert "1.1.2 Survey market and determine customer needs" in class_names
    assert len(class_names) == 5


@pytest.mark.asyncio
async def test_parse_ea_taxonomy_associations(parser, sparx_ea_taxonomy_path):
    """Should find all 4 composition associations via memberEnd resolution."""
    result = await parser.parse_xmi_file(str(sparx_ea_taxonomy_path))
    associations = result["associations"]
    assert len(associations) == 4

    # All should be composition (one end has aggregation=composite)
    for assoc in associations:
        src_agg = assoc["source"]["aggregation"]
        tgt_agg = assoc["target"]["aggregation"]
        assert (
            src_agg == "composite" or tgt_agg == "composite"
        ), f"Association should be composition: {assoc}"


@pytest.mark.asyncio
async def test_parse_ea_taxonomy_composition_hierarchy(parser, sparx_ea_taxonomy_path):
    """Composition hierarchy should reflect correct parent-child relationships."""
    result = await parser.parse_xmi_file(str(sparx_ea_taxonomy_path))
    associations = result["associations"]

    # Build parent->children map from composition associations
    hierarchy: dict[str, list[str]] = {}
    for assoc in associations:
        src = assoc["source"]
        tgt = assoc["target"]
        if src["aggregation"] == "composite":
            parent = src["type_name"]
            child = tgt["type_name"]
        else:
            parent = tgt["type_name"]
            child = src["type_name"]
        hierarchy.setdefault(parent, []).append(child)

    # Verify: 1.0 -> [1.1, 1.2]  and  1.1 -> [1.1.1, 1.1.2]
    # type_name might be the xmi_id if name not resolved, so check via type_map
    # The type_map should resolve EAID_CAT_01 -> "1.0 Develop Vision and Strategy" etc.
    cat_children = None
    pg_children = None
    for parent, children in hierarchy.items():
        if "1.0" in parent:
            cat_children = children
        elif "1.1 Define" in parent:
            pg_children = children

    assert cat_children is not None, f"Category 1.0 not found as parent. Hierarchy: {hierarchy}"
    assert len(cat_children) == 2
    assert (
        pg_children is not None
    ), f"Process Group 1.1 not found as parent. Hierarchy: {hierarchy}"
    assert len(pg_children) == 2


@pytest.mark.asyncio
async def test_parse_ea_taxonomy_skips_extension(parser, sparx_ea_taxonomy_path):
    """xmi:Extension block should not produce spurious classes or packages."""
    result = await parser.parse_xmi_file(str(sparx_ea_taxonomy_path))

    # Should only have classes from the UML model, not from xmi:Extension
    pkg = result["packages"][0]
    # No class should have EA extension element names
    for cls in pkg["classes"]:
        assert cls["name"] != "EA_PrimitiveTypes_Package"


# --- Multiplicity edge cases ---


def test_parse_multiplicity_value_star():
    """'*' should map to -1 (unbounded)."""
    assert _parse_multiplicity_value("*", 1) == -1


def test_parse_multiplicity_value_negative_one():
    """'-1' (EA convention) should map to -1 (unbounded)."""
    assert _parse_multiplicity_value("-1", 1) == -1


def test_parse_multiplicity_value_digit():
    """Normal digit should be returned as int."""
    assert _parse_multiplicity_value("5", 1) == 5


def test_parse_multiplicity_value_default():
    """Non-numeric value should return default."""
    assert _parse_multiplicity_value("abc", 42) == 42


# --- Fish-Herring model (documentation + generalization) ---


@pytest.mark.asyncio
async def test_fish_herring_dialect(parser, fish_herring_path):
    """Fish-Herring XMI should be detected as Sparx EA dialect."""
    result = await parser.detect_dialect(str(fish_herring_path))
    assert result["dialect"] == "sparx_ea"


@pytest.mark.asyncio
async def test_fish_herring_classes(parser, fish_herring_path):
    """Should find 3 classes: Fish, Herring, DanubeHerring."""
    result = await parser.parse_xmi_file(str(fish_herring_path))
    pkg = result["packages"][0]
    class_names = [c["name"] for c in pkg["classes"]]
    assert sorted(class_names) == ["DanubeHerring", "Fish", "Herring"]


@pytest.mark.asyncio
async def test_fish_herring_attributes(parser, fish_herring_path):
    """Each class should have its own (non-inherited) attributes."""
    result = await parser.parse_xmi_file(str(fish_herring_path))
    pkg = result["packages"][0]
    by_name = {c["name"]: c for c in pkg["classes"]}

    fish_attrs = [a["name"] for a in by_name["Fish"]["attributes"]]
    assert sorted(fish_attrs) == ["fins", "head", "scales", "tail"]

    herring_attrs = [a["name"] for a in by_name["Herring"]["attributes"]]
    assert herring_attrs == ["herringSmell"]

    danube_attrs = [a["name"] for a in by_name["DanubeHerring"]["attributes"]]
    assert danube_attrs == ["iodineSmell"]


@pytest.mark.asyncio
async def test_fish_herring_generalization(parser, fish_herring_path):
    """Generalization chain: DanubeHerring -> Herring -> Fish."""
    result = await parser.parse_xmi_file(str(fish_herring_path))
    pkg = result["packages"][0]
    by_name = {c["name"]: c for c in pkg["classes"]}

    assert by_name["Fish"]["parent_xmi_ids"] == []
    assert by_name["Herring"]["parent_xmi_ids"] == ["CLASS_FISH"]
    assert by_name["DanubeHerring"]["parent_xmi_ids"] == ["CLASS_HERRING"]


@pytest.mark.asyncio
async def test_fish_herring_class_documentation(parser, fish_herring_path):
    """Class-level ownedComment documentation should be extracted."""
    result = await parser.parse_xmi_file(str(fish_herring_path))
    pkg = result["packages"][0]
    by_name = {c["name"]: c for c in pkg["classes"]}

    assert "Base class for all fish" in by_name["Fish"]["documentation"]
    assert "not every fish is a herring" in by_name["Herring"]["documentation"]
    assert "Danube river basin" in by_name["DanubeHerring"]["documentation"]


@pytest.mark.asyncio
async def test_fish_herring_attribute_documentation(parser, fish_herring_path):
    """Attribute-level ownedComment documentation should be extracted."""
    result = await parser.parse_xmi_file(str(fish_herring_path))
    pkg = result["packages"][0]
    by_name = {c["name"]: c for c in pkg["classes"]}

    # Fish attributes
    fish_attrs = {a["name"]: a for a in by_name["Fish"]["attributes"]}
    assert "mouth, eyes, gills" in fish_attrs["head"]["documentation"]
    assert "protective skin" in fish_attrs["scales"]["documentation"]
    assert "locomotion" in fish_attrs["fins"]["documentation"]
    assert "propulsion" in fish_attrs["tail"]["documentation"]

    # Herring attribute
    herring_attrs = {a["name"]: a for a in by_name["Herring"]["attributes"]}
    assert "olfactory" in herring_attrs["herringSmell"]["documentation"]

    # DanubeHerring attribute
    danube_attrs = {a["name"]: a for a in by_name["DanubeHerring"]["attributes"]}
    assert "iodine" in danube_attrs["iodineSmell"]["documentation"]


@pytest.mark.asyncio
async def test_fish_herring_type_resolution(parser, fish_herring_path):
    """Attribute types using pathmap href should resolve to 'String'."""
    result = await parser.parse_xmi_file(str(fish_herring_path))
    pkg = result["packages"][0]
    for cls in pkg["classes"]:
        for attr in cls["attributes"]:
            assert attr["type_name"] == "String"


def test_extract_documentation_present():
    """_extract_documentation should find body text from ownedComment."""
    xml = '<cls><ownedComment body="Test docs."><annotatedElement/></ownedComment></cls>'
    elem = ET.fromstring(xml)
    assert _extract_documentation(elem) == "Test docs."


def test_extract_documentation_absent():
    """_extract_documentation should return empty string when no ownedComment."""
    xml = '<cls><ownedAttribute name="x"/></cls>'
    elem = ET.fromstring(xml)
    assert _extract_documentation(elem) == ""


# --- IT Employment model (plain associations + documentation) ---


@pytest.mark.asyncio
async def test_it_employment_associations_count(parser, it_employment_path):
    """Should parse 2 associations from IT Employment model."""
    result = await parser.parse_xmi_file(str(it_employment_path))
    assert len(result["associations"]) == 2


@pytest.mark.asyncio
async def test_it_employment_associations_aggregation(parser, it_employment_path):
    """Both associations should have aggregation='none' (plain)."""
    result = await parser.parse_xmi_file(str(it_employment_path))
    for assoc in result["associations"]:
        assert assoc["source"]["aggregation"] == "none"
        assert assoc["target"]["aggregation"] == "none"


@pytest.mark.asyncio
async def test_it_employment_association_documentation(parser, it_employment_path):
    """Association-level documentation should be extracted."""
    result = await parser.parse_xmi_file(str(it_employment_path))
    assoc_by_name = {a["name"]: a for a in result["associations"]}

    assert "employs" in assoc_by_name
    assert "Employment relationship" in assoc_by_name["employs"]["documentation"]

    # contractsWith has no ownedComment
    assert "contractsWith" in assoc_by_name
    assert assoc_by_name["contractsWith"]["documentation"] == ""


@pytest.mark.asyncio
async def test_it_employment_association_roles(parser, it_employment_path):
    """Association role names and type references should be captured."""
    result = await parser.parse_xmi_file(str(it_employment_path))
    employs = next(a for a in result["associations"] if a["name"] == "employs")

    roles = {employs["source"]["role"], employs["target"]["role"]}
    assert roles == {"employer", "employee"}

    type_names = {employs["source"]["type_name"], employs["target"]["type_name"]}
    assert type_names == {"Company", "ITProfessional"}


@pytest.mark.asyncio
async def test_it_employment_association_multiplicities(parser, it_employment_path):
    """Association multiplicities should be parsed correctly."""
    result = await parser.parse_xmi_file(str(it_employment_path))
    contracts = next(a for a in result["associations"] if a["name"] == "contractsWith")

    # contractor end: 0..1
    contractor = next(
        e for e in (contracts["source"], contracts["target"]) if e["role"] == "contractor"
    )
    assert contractor["multiplicity"]["lower"] == 0
    assert contractor["multiplicity"]["upper"] == 1

    # client end: 0..*
    client = next(e for e in (contracts["source"], contracts["target"]) if e["role"] == "client")
    assert client["multiplicity"]["lower"] == 0
    assert client["multiplicity"]["upper"] == -1


# --- EA Composition Correction (Cat-Tail, Tea-Sugar) ---


@pytest.mark.asyncio
async def test_parse_ea_composition_direction(parser, ea_composition_cat_tail_path):
    """Cat should be composite owner, Tail should be component (not inverted).

    Sparx EA places aggregation="composite" on the component end in
    uml:Model ownedEnd elements. The EA adapter corrects this using
    Extension/connectors metadata.
    """
    result = await parser.parse_xmi_file(str(ea_composition_cat_tail_path))
    assert result["dialect"] == "sparx_ea"
    assert len(result["associations"]) == 1

    assoc = result["associations"][0]
    src = assoc["source"]
    tgt = assoc["target"]

    # Find which end points to Cat and which to Tail
    if src["type_name"] == "Cat":
        cat_end, tail_end = src, tgt
    else:
        cat_end, tail_end = tgt, src

    # Cat (the owner) should have aggregation=composite
    assert (
        cat_end["aggregation"] == "composite"
    ), f"Cat should be composite, got {cat_end['aggregation']}"
    # Tail (the component) should have aggregation=none
    assert tail_end["aggregation"] == "none", f"Tail should be none, got {tail_end['aggregation']}"


@pytest.mark.asyncio
async def test_parse_ea_composition_aggregation_field(parser, ea_composition_tea_sugar_path):
    """TeaPortion should be composite owner, SugarPortion the component."""
    result = await parser.parse_xmi_file(str(ea_composition_tea_sugar_path))
    assert result["dialect"] == "sparx_ea"
    assert len(result["associations"]) == 1

    assoc = result["associations"][0]
    src = assoc["source"]
    tgt = assoc["target"]

    if src["type_name"] == "TeaPortion":
        tea_end, sugar_end = src, tgt
    else:
        tea_end, sugar_end = tgt, src

    assert tea_end["aggregation"] == "composite"
    assert sugar_end["aggregation"] == "none"


@pytest.mark.asyncio
async def test_parse_ea_composition_documentation(parser, ea_composition_cat_tail_path):
    """Rich Extension documentation should be captured on the association."""
    result = await parser.parse_xmi_file(str(ea_composition_cat_tail_path))
    assoc = result["associations"][0]

    # Extension connector has rich documentation about composition semantics
    assert "composite aggregation" in assoc["documentation"]
    assert "Cat" in assoc["documentation"]


@pytest.mark.asyncio
async def test_parse_ea_plain_associations_unchanged(parser, it_employment_path):
    """IT Employment plain associations should be unchanged by EA adapter.

    Plain associations (aggregation=none on both ends) are unaffected
    by the EA composition correction.
    """
    result = await parser.parse_xmi_file(str(it_employment_path))
    for assoc in result["associations"]:
        assert assoc["source"]["aggregation"] == "none"
        assert assoc["target"]["aggregation"] == "none"
