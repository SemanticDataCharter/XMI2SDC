"""Tests for xmi2sdc.common.inheritance."""

from __future__ import annotations

import pytest

from xmi2sdc.common.inheritance import CyclicInheritanceError, flatten_inheritance


def _make_fish_model() -> dict:
    """Build a parsed model dict matching the Fish → Herring → DanubeHerring hierarchy."""
    return {
        "model_name": "fish_taxonomy",
        "dialect": "sparx_ea",
        "packages": [
            {
                "xmi_id": "PKG_001",
                "name": "Fish Taxonomy",
                "classes": [
                    {
                        "xmi_id": "CLASS_FISH",
                        "name": "Fish",
                        "parent_xmi_ids": [],
                        "attributes": [
                            {
                                "name": "head",
                                "type_name": "String",
                                "documentation": "Fish head — contains mouth, eyes, gills.",
                            },
                            {
                                "name": "scales",
                                "type_name": "String",
                                "documentation": "Scales — protective skin covering.",
                            },
                            {
                                "name": "fins",
                                "type_name": "String",
                                "documentation": "Fins — locomotion and stabilization organs.",
                            },
                            {
                                "name": "tail",
                                "type_name": "String",
                                "documentation": "Tail — primary propulsion organ.",
                            },
                        ],
                    },
                    {
                        "xmi_id": "CLASS_HERRING",
                        "name": "Herring",
                        "parent_xmi_ids": ["CLASS_FISH"],
                        "attributes": [
                            {
                                "name": "herringSmell",
                                "type_name": "String",
                                "documentation": (
                                    "Specific olfactory characteristic unique to herring."
                                ),
                            },
                        ],
                    },
                    {
                        "xmi_id": "CLASS_DANUBE_HERRING",
                        "name": "DanubeHerring",
                        "parent_xmi_ids": ["CLASS_HERRING"],
                        "attributes": [
                            {
                                "name": "iodineSmell",
                                "type_name": "String",
                                "documentation": (
                                    "Iodine-specific olfactory note unique to Danube Herring."
                                ),
                            },
                        ],
                    },
                ],
                "enumerations": [],
                "sub_packages": [],
            }
        ],
        "associations": [],
        "top_level_classes": [],
        "top_level_enumerations": [],
    }


class TestFlattenInheritance:
    """Test inheritance flattening with the Fish hierarchy."""

    def test_fish_has_4_attributes(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        fish = model["packages"][0]["classes"][0]
        assert fish["name"] == "Fish"
        assert len(fish["all_attributes"]) == 4
        assert [a["name"] for a in fish["all_attributes"]] == [
            "head",
            "scales",
            "fins",
            "tail",
        ]

    def test_fish_has_no_ancestors(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        fish = model["packages"][0]["classes"][0]
        assert fish["ancestor_xmi_ids"] == []

    def test_herring_has_5_attributes(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        herring = model["packages"][0]["classes"][1]
        assert herring["name"] == "Herring"
        assert len(herring["all_attributes"]) == 5
        names = [a["name"] for a in herring["all_attributes"]]
        # Inherited first (root order), then own
        assert names == ["head", "scales", "fins", "tail", "herringSmell"]

    def test_herring_ancestors(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        herring = model["packages"][0]["classes"][1]
        assert herring["ancestor_xmi_ids"] == ["CLASS_FISH"]

    def test_danube_herring_has_6_attributes(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        danube = model["packages"][0]["classes"][2]
        assert danube["name"] == "DanubeHerring"
        assert len(danube["all_attributes"]) == 6
        names = [a["name"] for a in danube["all_attributes"]]
        assert names == [
            "head",
            "scales",
            "fins",
            "tail",
            "herringSmell",
            "iodineSmell",
        ]

    def test_danube_herring_ancestors(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        danube = model["packages"][0]["classes"][2]
        assert danube["ancestor_xmi_ids"] == ["CLASS_FISH", "CLASS_HERRING"]

    def test_documentation_preserved(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        danube = model["packages"][0]["classes"][2]
        attr_map = {a["name"]: a for a in danube["all_attributes"]}
        # Inherited attribute keeps parent's doc
        assert "mouth, eyes, gills" in attr_map["head"]["documentation"]
        # Own attribute keeps its doc
        assert "iodine" in attr_map["iodineSmell"]["documentation"].lower()

    def test_attribute_override(self):
        """Child redefining a parent attribute should win."""
        model = {
            "model_name": "override_test",
            "packages": [],
            "associations": [],
            "top_level_classes": [
                {
                    "xmi_id": "PARENT",
                    "name": "Parent",
                    "parent_xmi_ids": [],
                    "attributes": [
                        {"name": "color", "type_name": "String", "documentation": "parent color"},
                        {"name": "size", "type_name": "Integer", "documentation": "parent size"},
                    ],
                },
                {
                    "xmi_id": "CHILD",
                    "name": "Child",
                    "parent_xmi_ids": ["PARENT"],
                    "attributes": [
                        {
                            "name": "color",
                            "type_name": "String",
                            "documentation": "child color override",
                        },
                    ],
                },
            ],
            "top_level_enumerations": [],
        }
        flatten_inheritance(model)
        child = model["top_level_classes"][1]
        assert len(child["all_attributes"]) == 2
        attr_map = {a["name"]: a for a in child["all_attributes"]}
        # Child's override wins
        assert attr_map["color"]["documentation"] == "child color override"
        # Parent's non-overridden attr is inherited
        assert attr_map["size"]["documentation"] == "parent size"

    def test_cycle_detection(self):
        """Circular inheritance should raise CyclicInheritanceError."""
        model = {
            "model_name": "cycle_test",
            "packages": [],
            "associations": [],
            "top_level_classes": [
                {
                    "xmi_id": "A",
                    "name": "ClassA",
                    "parent_xmi_ids": ["B"],
                    "attributes": [{"name": "a1", "type_name": "String"}],
                },
                {
                    "xmi_id": "B",
                    "name": "ClassB",
                    "parent_xmi_ids": ["A"],
                    "attributes": [{"name": "b1", "type_name": "String"}],
                },
            ],
            "top_level_enumerations": [],
        }
        with pytest.raises(CyclicInheritanceError, match="Circular inheritance"):
            flatten_inheritance(model)

    def test_no_parents_leaves_all_attributes_as_own(self):
        """A class with no parents gets all_attributes == attributes."""
        model = {
            "model_name": "no_parent",
            "packages": [],
            "associations": [],
            "top_level_classes": [
                {
                    "xmi_id": "SOLO",
                    "name": "Solo",
                    "parent_xmi_ids": [],
                    "attributes": [
                        {"name": "x", "type_name": "String"},
                    ],
                },
            ],
            "top_level_enumerations": [],
        }
        flatten_inheritance(model)
        solo = model["top_level_classes"][0]
        assert len(solo["all_attributes"]) == 1
        assert solo["all_attributes"][0]["name"] == "x"

    def test_missing_parent_gracefully_skipped(self):
        """If a parent_xmi_id references a non-existent class, skip it."""
        model = {
            "model_name": "missing_parent",
            "packages": [],
            "associations": [],
            "top_level_classes": [
                {
                    "xmi_id": "ORPHAN",
                    "name": "Orphan",
                    "parent_xmi_ids": ["NONEXISTENT"],
                    "attributes": [
                        {"name": "lonely", "type_name": "String"},
                    ],
                },
            ],
            "top_level_enumerations": [],
        }
        # Should not raise
        flatten_inheritance(model)
        orphan = model["top_level_classes"][0]
        assert len(orphan["all_attributes"]) == 1

    def test_returns_same_dict(self):
        """flatten_inheritance returns the same dict reference."""
        model = _make_fish_model()
        result = flatten_inheritance(model)
        assert result is model


class TestInheritanceProvenance:
    """Each attribute is tagged with the class that introduced it (origin)."""

    def test_own_attributes_tagged_with_owner(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        classes = model["packages"][0]["classes"]
        fish, herring, danube = classes[0], classes[1], classes[2]
        # Own attrs carry their own class as origin
        assert all(a["introduced_by_name"] == "Fish" for a in fish["attributes"])
        assert herring["attributes"][0]["introduced_by_name"] == "Herring"
        assert danube["attributes"][0]["introduced_by_name"] == "DanubeHerring"

    def test_inherited_attribute_keeps_true_origin(self):
        model = _make_fish_model()
        flatten_inheritance(model)
        danube = model["packages"][0]["classes"][2]
        origin = {a["name"]: a["introduced_by_name"] for a in danube["all_attributes"]}
        # head came from Fish (not Herring, not DanubeHerring); the chain is preserved
        assert origin["head"] == "Fish"
        assert origin["herringSmell"] == "Herring"
        assert origin["iodineSmell"] == "DanubeHerring"

    def test_override_origin_is_the_overriding_class(self):
        model = {
            "model_name": "override",
            "packages": [],
            "associations": [],
            "top_level_classes": [
                {
                    "xmi_id": "P",
                    "name": "Parent",
                    "parent_xmi_ids": [],
                    "attributes": [{"name": "color", "type_name": "String"}],
                },
                {
                    "xmi_id": "C",
                    "name": "Child",
                    "parent_xmi_ids": ["P"],
                    "attributes": [{"name": "color", "type_name": "String"}],
                },
            ],
            "top_level_enumerations": [],
        }
        flatten_inheritance(model)
        child = model["top_level_classes"][1]
        color = {a["name"]: a for a in child["all_attributes"]}["color"]
        # The child redefines color, so origin is the child
        assert color["introduced_by_name"] == "Child"
