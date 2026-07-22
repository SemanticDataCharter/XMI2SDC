"""Tests for xmi2sdc.toolsets.mapper."""

from __future__ import annotations

import pytest

from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.toolsets.mapper import (
    SdcMapperToolset,
    _map_multiplicity,
    _map_primitive_type,
    _normalize_type_name,
)

# --- Primitive type mapping ---


@pytest.mark.parametrize(
    "uml_type, expected_sdc4",
    [
        ("Boolean", "XdBoolean"),
        ("boolean", "XdBoolean"),
        ("bool", "XdBoolean"),
        ("String", "XdString"),
        ("string", "XdString"),
        ("char", "XdString"),
        ("text", "XdString"),
        ("Integer", "XdQuantity"),
        ("int", "XdQuantity"),
        ("long", "XdQuantity"),
        ("Real", "XdQuantity"),
        ("Float", "XdQuantity"),
        ("Double", "XdQuantity"),
        ("decimal", "XdQuantity"),
        ("Date", "XdTemporal"),
        ("DateTime", "XdTemporal"),
        ("Time", "XdTemporal"),
        ("timestamp", "XdTemporal"),
        ("URI", "XdString"),
        ("URL", "XdString"),
    ],
)
def test_map_primitive_type(uml_type, expected_sdc4):
    """Primitive types should map to correct SDC4 types."""
    result = _map_primitive_type(uml_type)
    assert result["sdc4_type"] == expected_sdc4


def test_map_unsigned_integer():
    """Non-negative integer types should map to XdCount."""
    result = _map_primitive_type("NonNegativeInteger")
    assert result["sdc4_type"] == "XdCount"

    result = _map_primitive_type("PositiveInteger")
    assert result["sdc4_type"] == "XdCount"

    result = _map_primitive_type("UnsignedInt")
    assert result["sdc4_type"] == "XdCount"


def test_map_integer_with_unsigned_flag():
    """Integer with is_unsigned flag should map to XdCount."""
    result = _map_primitive_type("Integer", is_unsigned=True)
    assert result["sdc4_type"] == "XdCount"


def test_map_signed_integer_has_restriction():
    """Signed integer should map to XdQuantity with integer restriction."""
    result = _map_primitive_type("Integer")
    assert result["sdc4_type"] == "XdQuantity"
    assert result.get("restriction") == "integer"


def test_map_unknown_type():
    """Unknown types should default to XdString with unmapped flag."""
    result = _map_primitive_type("CustomWidgetType")
    assert result["sdc4_type"] == "XdString"
    assert result["unmapped_source_type"] == "CustomWidgetType"


def test_normalize_type_name():
    """Type names should be normalized (lowercase, no spaces/underscores)."""
    assert _normalize_type_name("Non Negative Integer") == "nonnegativeinteger"
    assert _normalize_type_name("  String  ") == "string"
    assert _normalize_type_name("date_time") == "datetime"


# --- Multiplicity mapping ---


def test_map_multiplicity_required():
    """1..1 should be required, not a list."""
    result = _map_multiplicity(1, 1)
    assert result["minOccurs"] == 1
    assert result["maxOccurs"] == 1
    assert result["is_list"] is False


def test_map_multiplicity_optional():
    """0..1 should be optional, not a list."""
    result = _map_multiplicity(0, 1)
    assert result["minOccurs"] == 0
    assert result["maxOccurs"] == 1
    assert result["is_list"] is False


def test_map_multiplicity_unbounded():
    """0..* should be a list."""
    result = _map_multiplicity(0, -1)
    assert result["minOccurs"] == 0
    assert result["maxOccurs"] == 9999
    assert result["is_list"] is True


def test_map_multiplicity_one_or_more():
    """1..* should be required list."""
    result = _map_multiplicity(1, -1)
    assert result["minOccurs"] == 1
    assert result["maxOccurs"] == 9999
    assert result["is_list"] is True


def test_map_multiplicity_fixed_many():
    """0..5 should be a list."""
    result = _map_multiplicity(0, 5)
    assert result["minOccurs"] == 0
    assert result["maxOccurs"] == 5
    assert result["is_list"] is True


# --- Mapper Toolset ---


@pytest.fixture
def mapper(tmp_path):
    """Create a mapper toolset with tmp cache dir."""
    config = XMI2SDCConfig(
        cache={"root": str(tmp_path / "cache")},
        audit={"path": str(tmp_path / "cache" / "audit.jsonl")},
    )
    return SdcMapperToolset(config=config)


@pytest.mark.asyncio
async def test_map_type_tool(mapper):
    """map_type should return SDC4 type for a UML type name."""
    result = await mapper.map_type("Boolean")
    assert result["sdc4_type"] == "XdBoolean"


@pytest.mark.asyncio
async def test_map_class_with_attributes(mapper):
    """Should map class attributes to SDC4 components."""
    uml_class = {
        "xmi_id": "c1",
        "name": "Patient",
        "attributes": [
            {"name": "name", "type_name": "String", "multiplicity": {"lower": 1, "upper": 1}},
            {"name": "age", "type_name": "Integer", "multiplicity": {"lower": 0, "upper": 1}},
            {"name": "active", "type_name": "Boolean", "multiplicity": {"lower": 1, "upper": 1}},
        ],
    }
    result = await mapper.map_class(uml_class)

    components = result.get("components", [])
    assert len(components) == 3

    # Check type mappings
    type_map = {c["source_attribute"]: c["sdc4_type"] for c in components}
    assert type_map["name"] == "XdString"
    assert type_map["age"] == "XdQuantity"
    assert type_map["active"] == "XdBoolean"


@pytest.mark.asyncio
async def test_map_class_empty(mapper):
    """Empty class should become a cluster placeholder."""
    uml_class = {"xmi_id": "c1", "name": "EmptyClass", "attributes": []}
    result = await mapper.map_class(uml_class)
    assert result["is_cluster"] is True
    assert result["cluster_name"] == "EmptyClass"


@pytest.mark.asyncio
async def test_map_model_full(mapper, generic_xmi_path):
    """Should produce a complete mapping plan from parsed model."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    # First parse
    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(generic_xmi_path))

    # Then map
    mapping = await mapper.map_model(parsed)

    assert mapping["model_name"] == "generic_xmi21"
    assert len(mapping["components"]) > 0
    assert "summary" in mapping

    summary = mapping["summary"]
    assert summary["total_components"] > 0


@pytest.mark.asyncio
async def test_map_model_with_enumerations(mapper):
    """Enumeration types should produce XdString with enumerations."""
    parsed_model = {
        "model_name": "enum_test",
        "dialect": "generic_xmi21",
        "packages": [],
        "associations": [],
        "top_level_classes": [
            {
                "xmi_id": "c1",
                "name": "Record",
                "attributes": [
                    {
                        "name": "status",
                        "type_name": "Status",
                        "multiplicity": {"lower": 1, "upper": 1},
                    },
                ],
            }
        ],
        "top_level_enumerations": [
            {
                "xmi_id": "e1",
                "name": "Status",
                "literals": [
                    {"name": "Active"},
                    {"name": "Inactive"},
                    {"name": "Pending"},
                ],
            }
        ],
    }

    mapping = await mapper.map_model(parsed_model)
    components = mapping["components"]

    status_comp = next((c for c in components if c["source_attribute"] == "status"), None)
    assert status_comp is not None
    assert status_comp["sdc4_type"] == "XdString"
    assert status_comp["enumerations"] == ["Active", "Inactive", "Pending"]


@pytest.mark.asyncio
async def test_map_model_associations(mapper):
    """Composition associations should produce clusters."""
    parsed_model = {
        "model_name": "assoc_test",
        "dialect": "generic_xmi21",
        "packages": [],
        "top_level_classes": [],
        "top_level_enumerations": [],
        "associations": [
            {
                "xmi_id": "a1",
                "name": "owns",
                "source": {
                    "role": "owner",
                    "type_name": "Company",
                    "type_xmi_id": "c1",
                    "multiplicity": {"lower": 1, "upper": 1},
                    "aggregation": "composite",
                },
                "target": {
                    "role": "department",
                    "type_name": "Department",
                    "type_xmi_id": "c2",
                    "multiplicity": {"lower": 0, "upper": -1},
                    "aggregation": "none",
                },
            }
        ],
    }

    mapping = await mapper.map_model(parsed_model)
    clusters = mapping["clusters"]

    assert len(clusters) >= 1
    comp_cluster = next((c for c in clusters if c.get("containment_type") == "composition"), None)
    assert comp_cluster is not None
    assert comp_cluster["cluster_name"] == "Company"


@pytest.mark.asyncio
async def test_map_caches_result(mapper, tmp_path):
    """Mapping plan should be cached to disk."""
    parsed_model = {
        "model_name": "cache_test",
        "dialect": "generic_xmi21",
        "packages": [],
        "associations": [],
        "top_level_classes": [],
        "top_level_enumerations": [],
    }
    await mapper.map_model(parsed_model)
    cache_path = tmp_path / "cache" / "mappings" / "cache_test.json"
    assert cache_path.is_file()


@pytest.mark.asyncio
async def test_map_model_fish_herring(mapper, fish_herring_path):
    """Fish-Herring hierarchy should produce flattened component counts."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(fish_herring_path))
    mapping = await mapper.map_model(parsed)

    # Build cluster → component count map
    cluster_map = {}
    for cluster in mapping["clusters"]:
        name = cluster["cluster_name"]
        cluster_map[name] = len(cluster.get("component_refs", []))

    # Fish: 4 own attributes → 4 components
    assert cluster_map.get("Fish") == 4, f"Fish: expected 4, got {cluster_map.get('Fish')}"
    # Herring: 4 inherited + 1 own → 5 components
    assert (
        cluster_map.get("Herring") == 5
    ), f"Herring: expected 5, got {cluster_map.get('Herring')}"
    # DanubeHerring: 5 inherited + 1 own → 6 components
    assert (
        cluster_map.get("DanubeHerring") == 6
    ), f"DanubeHerring: expected 6, got {cluster_map.get('DanubeHerring')}"


@pytest.mark.asyncio
async def test_get_tools(mapper):
    """get_tools should return 3 FunctionTools."""
    tools = await mapper.get_tools()
    assert len(tools) == 3
    tool_names = {t.name for t in tools}
    assert "map_model" in tool_names
    assert "map_class" in tool_names
    assert "map_type" in tool_names


# --- Association mapping (plain, shared, composition) ---


@pytest.mark.asyncio
async def test_map_model_it_employment(mapper, it_employment_path):
    """IT Employment: 4 clusters (2 class + 2 association), 4 components."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(it_employment_path))
    mapping = await mapper.map_model(parsed)

    # 2 empty class clusters + 2 association clusters
    assert len(mapping["clusters"]) == 4

    # Each association produces 2 role components → 4 total
    assert len(mapping["components"]) == 4

    # Association clusters should have association_type
    assoc_clusters = [c for c in mapping["clusters"] if "association_type" in c]
    assert len(assoc_clusters) == 2
    for ac in assoc_clusters:
        assert ac["association_type"] == "plain"


@pytest.mark.asyncio
async def test_map_plain_association_unit(mapper):
    """Plain association should produce a cluster with 2 role XdString components."""
    parsed_model = {
        "model_name": "plain_assoc_test",
        "dialect": "generic_xmi21",
        "packages": [],
        "top_level_classes": [],
        "top_level_enumerations": [],
        "associations": [
            {
                "xmi_id": "a1",
                "name": "worksFor",
                "documentation": "Employment link.",
                "source": {
                    "role": "worker",
                    "type_name": "Person",
                    "type_xmi_id": "c1",
                    "multiplicity": {"lower": 0, "upper": -1},
                    "aggregation": "none",
                },
                "target": {
                    "role": "employer",
                    "type_name": "Organization",
                    "type_xmi_id": "c2",
                    "multiplicity": {"lower": 1, "upper": 1},
                    "aggregation": "none",
                },
            }
        ],
    }

    mapping = await mapper.map_model(parsed_model)
    clusters = mapping["clusters"]
    components = mapping["components"]

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["cluster_name"] == "worksFor"
    assert cluster["association_type"] == "plain"
    assert cluster["description"] == "Employment link."
    assert len(cluster["component_refs"]) == 2

    assert len(components) == 2
    labels = {c["label"] for c in components}
    assert labels == {"worksFor.worker", "worksFor.employer"}

    # Both should be XdString
    for comp in components:
        assert comp["sdc4_type"] == "XdString"
        assert comp["referenced_type"] in ("Person", "Organization")


@pytest.mark.asyncio
async def test_map_shared_aggregation(mapper):
    """Shared aggregation should produce association cluster with type='shared'."""
    parsed_model = {
        "model_name": "shared_assoc_test",
        "dialect": "generic_xmi21",
        "packages": [],
        "top_level_classes": [],
        "top_level_enumerations": [],
        "associations": [
            {
                "xmi_id": "a1",
                "name": "usesLibrary",
                "documentation": "",
                "source": {
                    "role": "user",
                    "type_name": "Application",
                    "type_xmi_id": "c1",
                    "multiplicity": {"lower": 0, "upper": -1},
                    "aggregation": "none",
                },
                "target": {
                    "role": "library",
                    "type_name": "SharedLibrary",
                    "type_xmi_id": "c2",
                    "multiplicity": {"lower": 1, "upper": 1},
                    "aggregation": "shared",
                },
            }
        ],
    }

    mapping = await mapper.map_model(parsed_model)
    clusters = mapping["clusters"]
    assert len(clusters) == 1
    assert clusters[0]["association_type"] == "shared"
    assert len(mapping["components"]) == 2


@pytest.mark.asyncio
async def test_map_composition_regression(mapper):
    """Composition associations should still produce containment clusters (no regression)."""
    parsed_model = {
        "model_name": "comp_regression",
        "dialect": "generic_xmi21",
        "packages": [],
        "top_level_classes": [],
        "top_level_enumerations": [],
        "associations": [
            {
                "xmi_id": "a1",
                "name": "owns",
                "documentation": "",
                "source": {
                    "role": "owner",
                    "type_name": "Parent",
                    "type_xmi_id": "c1",
                    "multiplicity": {"lower": 1, "upper": 1},
                    "aggregation": "composite",
                },
                "target": {
                    "role": "child",
                    "type_name": "Child",
                    "type_xmi_id": "c2",
                    "multiplicity": {"lower": 0, "upper": -1},
                    "aggregation": "none",
                },
            }
        ],
    }

    mapping = await mapper.map_model(parsed_model)
    clusters = mapping["clusters"]
    assert len(clusters) == 1
    assert clusters[0]["containment_type"] == "composition"
    assert clusters[0]["cluster_name"] == "Parent"
    # Composition should NOT produce association components
    assert len(mapping["components"]) == 0


@pytest.mark.asyncio
async def test_map_ea_composition_cluster_direction(mapper, ea_composition_cat_tail_path):
    """EA composition: cluster should be named 'Cat' containing 'Tail'.

    After the EA adapter corrects aggregation direction, the mapper
    should produce a composition cluster owned by Cat (not Tail).
    """
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(ea_composition_cat_tail_path))
    mapping = await mapper.map_model(parsed)

    # Should have composition clusters (2 empty class clusters + 1 composition)
    comp_clusters = [c for c in mapping["clusters"] if c.get("containment_type") == "composition"]
    assert len(comp_clusters) == 1

    comp = comp_clusters[0]
    assert (
        comp["cluster_name"] == "Cat"
    ), f"Composition cluster should be 'Cat', got '{comp['cluster_name']}'"
    assert "Tail" in comp["component_refs"]


@pytest.mark.asyncio
async def test_map_ea_lawnmower_aggregation(mapper, ea_lawnmower_aggregation_path):
    """LawnMower aggregation: 2 shared association clusters + 3 empty class clusters."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(ea_lawnmower_aggregation_path))
    mapping = await mapper.map_model(parsed)

    assoc_clusters = [c for c in mapping["clusters"] if "association_type" in c]
    assert len(assoc_clusters) == 2
    for ac in assoc_clusters:
        assert ac["association_type"] == "shared"


@pytest.mark.asyncio
async def test_map_ea_lawnmower_complex(mapper, ea_lawnmower_complex_path):
    """LawnMower complex: 2 composition + 3 shared + 5 class clusters."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(ea_lawnmower_complex_path))
    mapping = await mapper.map_model(parsed)

    comp_clusters = [c for c in mapping["clusters"] if c.get("containment_type") == "composition"]
    assert len(comp_clusters) == 2
    comp_owners = sorted(c["cluster_name"] for c in comp_clusters)
    assert comp_owners == ["LawnMower", "LawnMower"]

    # Composition components should be CuttingDeck and Transmission
    comp_components = sorted(ref for c in comp_clusters for ref in c["component_refs"])
    assert comp_components == ["CuttingDeck", "Transmission"]

    assoc_clusters = [c for c in mapping["clusters"] if c.get("association_type") == "shared"]
    assert len(assoc_clusters) == 3


@pytest.mark.asyncio
async def test_map_ea_tea_sugar_glass_complex(mapper, ea_tea_sugar_glass_complex_path):
    """Tea-Sugar-Glass: 1 composition + 1 shared + 3 class clusters."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(ea_tea_sugar_glass_complex_path))
    mapping = await mapper.map_model(parsed)

    comp_clusters = [c for c in mapping["clusters"] if c.get("containment_type") == "composition"]
    assert len(comp_clusters) == 1
    assert comp_clusters[0]["cluster_name"] == "TeaPortion"
    assert "SugarPortion" in comp_clusters[0]["component_refs"]

    assoc_clusters = [c for c in mapping["clusters"] if c.get("association_type") == "shared"]
    assert len(assoc_clusters) == 1


# --- Generic Inheritance (Vehicle hierarchy) ---


@pytest.mark.asyncio
async def test_map_generic_inheritance_flattening(mapper, generic_inheritance_path):
    """Vehicle=5, Car=6, ElectricCar=7 components after inheritance flattening."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(generic_inheritance_path))
    mapping = await mapper.map_model(parsed)

    cluster_map = {}
    for cluster in mapping["clusters"]:
        name = cluster["cluster_name"]
        cluster_map[name] = len(cluster.get("component_refs", []))

    assert (
        cluster_map.get("Vehicle") == 5
    ), f"Vehicle: expected 5, got {cluster_map.get('Vehicle')}"
    assert cluster_map.get("Car") == 6, f"Car: expected 6, got {cluster_map.get('Car')}"
    assert (
        cluster_map.get("ElectricCar") == 7
    ), f"ElectricCar: expected 7, got {cluster_map.get('ElectricCar')}"


@pytest.mark.asyncio
async def test_map_generic_enum_typed_attribute(mapper, generic_inheritance_path):
    """fuelType should map to XdString with enumerations list."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(generic_inheritance_path))
    mapping = await mapper.map_model(parsed)

    fuel_comp = next(
        (c for c in mapping["components"] if c["source_attribute"] == "fuelType"),
        None,
    )
    assert fuel_comp is not None, "fuelType component not found"
    assert fuel_comp["sdc4_type"] == "XdString"
    assert fuel_comp["enumerations"] == ["Gasoline", "Diesel", "Electric", "Hybrid"]


# --- Generic Associations (University course system) ---


@pytest.mark.asyncio
async def test_map_generic_university_associations(mapper, generic_associations_path):
    """University model: 1 composition + 1 shared + 1 plain association cluster."""
    from xmi2sdc.toolsets.parser import XmiParserToolset

    config = mapper._config
    parser = XmiParserToolset(config=config)
    parsed = await parser.parse_xmi_file(str(generic_associations_path))
    mapping = await mapper.map_model(parsed)

    comp_clusters = [c for c in mapping["clusters"] if c.get("containment_type") == "composition"]
    assert len(comp_clusters) == 1
    assert comp_clusters[0]["cluster_name"] == "Course"

    shared_clusters = [c for c in mapping["clusters"] if c.get("association_type") == "shared"]
    assert len(shared_clusters) == 1

    plain_clusters = [c for c in mapping["clusters"] if c.get("association_type") == "plain"]
    assert len(plain_clusters) == 1


# --- Inheritance provenance + lossless round-trip (issue #11) ---


def _fish_parsed_model() -> dict:
    """Fish -> Herring -> DanubeHerring, as a parsed-model dict for map_model."""
    return {
        "model_name": "fish_taxonomy",
        "dialect": "sparx_ea",
        "packages": [
            {
                "xmi_id": "PKG",
                "name": "Fish Taxonomy",
                "sub_packages": [],
                "enumerations": [],
                "classes": [
                    {
                        "xmi_id": "FISH",
                        "name": "Fish",
                        "parent_xmi_ids": [],
                        "attributes": [
                            {"name": "head", "type_name": "String", "documentation": "d"},
                            {"name": "scales", "type_name": "String", "documentation": "d"},
                            {"name": "fins", "type_name": "String", "documentation": "d"},
                            {"name": "tail", "type_name": "String", "documentation": "d"},
                        ],
                    },
                    {
                        "xmi_id": "HERRING",
                        "name": "Herring",
                        "parent_xmi_ids": ["FISH"],
                        "attributes": [
                            {"name": "herringSmell", "type_name": "String", "documentation": "d"}
                        ],
                    },
                    {
                        "xmi_id": "DANUBE",
                        "name": "DanubeHerring",
                        "parent_xmi_ids": ["HERRING"],
                        "attributes": [
                            {"name": "iodineSmell", "type_name": "String", "documentation": "d"}
                        ],
                    },
                ],
            }
        ],
        "associations": [],
        "top_level_classes": [],
        "top_level_enumerations": [],
    }


@pytest.mark.asyncio
async def test_inherited_component_carries_wasderivedfrom(mapper):
    plan = await mapper.map_model(_fish_parsed_model())
    by_label = {c["label"]: c for c in plan["components"]}
    # DanubeHerring.head came from Fish, not Herring
    links = by_label["DanubeHerring.head"]["semantic_links"]
    assert links == [{"predicate": "prov:wasDerivedFrom", "object": "Fish.head"}]
    # and the human-facing note is in the description
    assert (
        "[XMI2SDC provenance] Inherited from UML class Fish"
        in by_label["DanubeHerring.head"]["description"]
    )


@pytest.mark.asyncio
async def test_own_component_has_no_semantic_links(mapper):
    """Backward-compatible: non-inherited components are unchanged (no links key)."""
    plan = await mapper.map_model(_fish_parsed_model())
    by_label = {c["label"]: c for c in plan["components"]}
    assert "semantic_links" not in by_label["Fish.head"]
    assert "semantic_links" not in by_label["DanubeHerring.iodineSmell"]


@pytest.mark.asyncio
async def test_cluster_subclassof_edges(mapper):
    plan = await mapper.map_model(_fish_parsed_model())
    edges = {}
    for cl in plan["clusters"]:
        for link in cl.get("semantic_links", []):
            if link["predicate"] == "rdfs:subClassOf":
                edges.setdefault(cl["cluster_name"], []).append(link["object"])
    assert edges == {"Herring": ["Fish"], "DanubeHerring": ["Herring"]}
    assert plan["namespaces"] == {
        "prov": "http://www.w3.org/ns/prov#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }


@pytest.mark.asyncio
async def test_lossless_class_diagram_reconstruction(mapper):
    """The whole point: rebuild the original class diagram from the flat plan,
    with no name-guessing, purely from prov:wasDerivedFrom + rdfs:subClassOf."""
    plan = await mapper.map_model(_fish_parsed_model())

    # Own attrs of a class = its components with no wasDerivedFrom link
    own: dict[str, list[str]] = {}
    for c in plan["components"]:
        cls_name = c["label"].split(".", 1)[0]
        inherited = any(
            link["predicate"] == "prov:wasDerivedFrom" for link in c.get("semantic_links", [])
        )
        if not inherited:
            own.setdefault(cls_name, []).append(c["source_attribute"])

    parents: dict[str, list[str]] = {}
    for cl in plan["clusters"]:
        for link in cl.get("semantic_links", []):
            if link["predicate"] == "rdfs:subClassOf":
                parents.setdefault(cl["cluster_name"], []).append(link["object"])

    # Reconstructed diagram matches the original exactly
    assert own["Fish"] == ["head", "scales", "fins", "tail"]
    assert own["Herring"] == ["herringSmell"]
    assert own["DanubeHerring"] == ["iodineSmell"]
    assert parents.get("Fish", []) == []
    assert parents["Herring"] == ["Fish"]
    assert parents["DanubeHerring"] == ["Herring"]
