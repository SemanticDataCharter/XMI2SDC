"""Pydantic models for parsed XMI elements.

All XMI dialects (Sparx EA, MagicDraw, generic XMI 2.x) normalize
into these structures. The ParsedXmiModel is the universal intermediate
representation consumed by downstream agents.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class XmiDialect(str, Enum):
    """Supported XMI dialect identifiers."""

    GENERIC = "generic_xmi21"
    SPARX_EA = "sparx_ea"
    MAGICDRAW = "magicdraw"


class Multiplicity(BaseModel):
    """UML multiplicity bounds."""

    lower: int = 1
    upper: int = 1  # -1 means unbounded (*)


class UmlAttribute(BaseModel):
    """A single attribute of a UML class."""

    name: str
    type_name: str = "String"
    multiplicity: Multiplicity = Field(default_factory=Multiplicity)
    is_id: bool = False
    default_value: Optional[str] = None
    visibility: str = "public"
    documentation: str = ""


class UmlEnumLiteral(BaseModel):
    """A single literal in a UML enumeration."""

    name: str
    documentation: str = ""


class UmlEnumeration(BaseModel):
    """A UML enumeration type."""

    xmi_id: str
    name: str
    literals: list[UmlEnumLiteral] = Field(default_factory=list)
    documentation: str = ""


class UmlAssociationEnd(BaseModel):
    """One end of a UML association."""

    role: str = ""
    type_name: str = ""
    type_xmi_id: str = ""
    multiplicity: Multiplicity = Field(default_factory=Multiplicity)
    aggregation: str = "none"  # none, shared, composite


class UmlAssociation(BaseModel):
    """A UML association between two classes."""

    xmi_id: str
    name: str = ""
    source: UmlAssociationEnd = Field(default_factory=UmlAssociationEnd)
    target: UmlAssociationEnd = Field(default_factory=UmlAssociationEnd)
    documentation: str = ""


class UmlClass(BaseModel):
    """A UML class extracted from XMI."""

    xmi_id: str
    name: str
    is_abstract: bool = False
    attributes: list[UmlAttribute] = Field(default_factory=list)
    parent_xmi_ids: list[str] = Field(default_factory=list)
    documentation: str = ""
    stereotype: str = ""


class UmlPackage(BaseModel):
    """A UML package (organizational container)."""

    xmi_id: str
    name: str
    classes: list[UmlClass] = Field(default_factory=list)
    enumerations: list[UmlEnumeration] = Field(default_factory=list)
    sub_packages: list[UmlPackage] = Field(default_factory=list)
    documentation: str = ""


class ParsedXmiModel(BaseModel):
    """Universal intermediate representation of a parsed XMI model.

    All dialect adapters produce this structure. Downstream agents
    (analyzer, mapper, assembler) consume only this model.
    """

    model_name: str
    dialect: XmiDialect
    xmi_version: str = "2.1"
    packages: list[UmlPackage] = Field(default_factory=list)
    associations: list[UmlAssociation] = Field(default_factory=list)
    top_level_classes: list[UmlClass] = Field(default_factory=list)
    top_level_enumerations: list[UmlEnumeration] = Field(default_factory=list)

    @property
    def all_classes(self) -> list[UmlClass]:
        """Flatten all classes from packages and top-level."""
        result = list(self.top_level_classes)
        for pkg in self.packages:
            result.extend(self._collect_classes(pkg))
        return result

    @property
    def all_enumerations(self) -> list[UmlEnumeration]:
        """Flatten all enumerations from packages and top-level."""
        result = list(self.top_level_enumerations)
        for pkg in self.packages:
            result.extend(self._collect_enumerations(pkg))
        return result

    def _collect_classes(self, pkg: UmlPackage) -> list[UmlClass]:
        """Recursively collect classes from a package tree."""
        result = list(pkg.classes)
        for sub in pkg.sub_packages:
            result.extend(self._collect_classes(sub))
        return result

    def _collect_enumerations(self, pkg: UmlPackage) -> list[UmlEnumeration]:
        """Recursively collect enumerations from a package tree."""
        result = list(pkg.enumerations)
        for sub in pkg.sub_packages:
            result.extend(self._collect_enumerations(sub))
        return result
