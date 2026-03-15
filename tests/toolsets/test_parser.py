"""Tests for xmi2sdc.toolsets.parser."""

from __future__ import annotations

import pytest

from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.common.exceptions import XmiParseError
from xmi2sdc.toolsets.parser import (
    XmiParserToolset,
    _detect_dialect,
    _detect_xmi_version,
    _parse_generic_xmi,
)
from xmi2sdc.common.xmi_types import XmiDialect
import xml.etree.ElementTree as ET


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
    result = await parser.parse_xmi_file(str(generic_xmi_path))
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
