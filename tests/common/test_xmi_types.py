"""Tests for xmi2sdc.common.xmi_types."""

from __future__ import annotations

from xmi2sdc.common.xmi_types import (
    Multiplicity,
    ParsedXmiModel,
    UmlAttribute,
    UmlClass,
    UmlEnumeration,
    UmlEnumLiteral,
    UmlPackage,
    XmiDialect,
)


def test_multiplicity_defaults():
    """Default multiplicity should be 1..1."""
    m = Multiplicity()
    assert m.lower == 1
    assert m.upper == 1


def test_uml_attribute_defaults():
    """UmlAttribute should have sensible defaults."""
    attr = UmlAttribute(name="test")
    assert attr.type_name == "String"
    assert attr.visibility == "public"
    assert not attr.is_id
    assert attr.default_value is None


def test_uml_class_basics():
    """UmlClass should store attributes and parent refs."""
    cls = UmlClass(
        xmi_id="id1",
        name="MyClass",
        is_abstract=True,
        attributes=[UmlAttribute(name="field1", type_name="Integer")],
        parent_xmi_ids=["parent_id"],
    )
    assert cls.name == "MyClass"
    assert cls.is_abstract
    assert len(cls.attributes) == 1
    assert cls.attributes[0].type_name == "Integer"
    assert cls.parent_xmi_ids == ["parent_id"]


def test_uml_enumeration():
    """UmlEnumeration should store literals."""
    enum = UmlEnumeration(
        xmi_id="enum1",
        name="Color",
        literals=[
            UmlEnumLiteral(name="Red"),
            UmlEnumLiteral(name="Green"),
            UmlEnumLiteral(name="Blue"),
        ],
    )
    assert enum.name == "Color"
    assert len(enum.literals) == 3
    assert enum.literals[0].name == "Red"


def test_uml_package_with_classes():
    """UmlPackage should contain classes and enumerations."""
    pkg = UmlPackage(
        xmi_id="pkg1",
        name="MyPackage",
        classes=[UmlClass(xmi_id="c1", name="ClassA")],
        enumerations=[UmlEnumeration(xmi_id="e1", name="EnumA")],
    )
    assert len(pkg.classes) == 1
    assert len(pkg.enumerations) == 1


def test_parsed_xmi_model_all_classes():
    """all_classes should flatten from packages and top-level."""
    model = ParsedXmiModel(
        model_name="test",
        dialect=XmiDialect.GENERIC,
        top_level_classes=[UmlClass(xmi_id="c1", name="TopClass")],
        packages=[
            UmlPackage(
                xmi_id="p1",
                name="Pkg",
                classes=[UmlClass(xmi_id="c2", name="PkgClass")],
                sub_packages=[
                    UmlPackage(
                        xmi_id="p2",
                        name="SubPkg",
                        classes=[UmlClass(xmi_id="c3", name="SubPkgClass")],
                    )
                ],
            )
        ],
    )
    all_cls = model.all_classes
    assert len(all_cls) == 3
    names = {c.name for c in all_cls}
    assert names == {"TopClass", "PkgClass", "SubPkgClass"}


def test_parsed_xmi_model_all_enumerations():
    """all_enumerations should flatten from packages and top-level."""
    model = ParsedXmiModel(
        model_name="test",
        dialect=XmiDialect.GENERIC,
        top_level_enumerations=[UmlEnumeration(xmi_id="e1", name="TopEnum")],
        packages=[
            UmlPackage(
                xmi_id="p1",
                name="Pkg",
                enumerations=[UmlEnumeration(xmi_id="e2", name="PkgEnum")],
            )
        ],
    )
    all_enums = model.all_enumerations
    assert len(all_enums) == 2


def test_model_serialization():
    """ParsedXmiModel should round-trip through dict serialization."""
    model = ParsedXmiModel(
        model_name="roundtrip",
        dialect=XmiDialect.SPARX_EA,
        xmi_version="2.1",
        top_level_classes=[
            UmlClass(
                xmi_id="c1",
                name="TestClass",
                attributes=[UmlAttribute(name="field", type_name="Boolean")],
            )
        ],
    )
    data = model.model_dump()
    restored = ParsedXmiModel.model_validate(data)
    assert restored.model_name == "roundtrip"
    assert restored.dialect == XmiDialect.SPARX_EA
    assert len(restored.top_level_classes) == 1
    assert restored.top_level_classes[0].attributes[0].type_name == "Boolean"


def test_xmi_dialect_values():
    """XmiDialect enum should have expected values."""
    assert XmiDialect.GENERIC == "generic_xmi21"
    assert XmiDialect.SPARX_EA == "sparx_ea"
    assert XmiDialect.MAGICDRAW == "magicdraw"
