"""Shared test fixtures for XMI2SDC."""

from __future__ import annotations

from pathlib import Path

import pytest

from xmi2sdc.common.config import XMI2SDCConfig, load_config

FIXTURES_DIR = Path(__file__).parent / "fixtures"
XMI_SAMPLES_DIR = FIXTURES_DIR / "xmi_samples"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def xmi_samples_dir() -> Path:
    return XMI_SAMPLES_DIR


@pytest.fixture
def sample_config_path() -> Path:
    return FIXTURES_DIR / "sample_config.yaml"


@pytest.fixture
def config(sample_config_path: Path) -> XMI2SDCConfig:
    return load_config(sample_config_path)


@pytest.fixture
def default_config() -> XMI2SDCConfig:
    """Config with all defaults (no file needed)."""
    return XMI2SDCConfig()


@pytest.fixture
def generic_xmi_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "generic_xmi21.xmi"


@pytest.fixture
def sparx_ea_xmi_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "sparx_ea_simple.xmi"


@pytest.fixture
def magicdraw_xmi_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "magicdraw_simple.xmi"


@pytest.fixture
def sparx_ea_taxonomy_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "sparx_ea_taxonomy.xmi"


@pytest.fixture
def fish_herring_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "fish_herring.xmi"


@pytest.fixture
def it_employment_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "it_employment.xmi"


@pytest.fixture
def ea_composition_cat_tail_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "ea_composition_cat_tail.xmi"


@pytest.fixture
def ea_composition_tea_sugar_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "ea_composition_tea_sugar.xmi"


@pytest.fixture
def ea_lawnmower_aggregation_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "ea_lawnmower_aggregation.xmi"


@pytest.fixture
def ea_lawnmower_complex_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "ea_lawnmower_complex.xmi"


@pytest.fixture
def ea_tea_sugar_glass_complex_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "ea_tea_sugar_glass_complex.xmi"


@pytest.fixture
def generic_inheritance_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "generic_inheritance.xmi"


@pytest.fixture
def generic_associations_path(xmi_samples_dir: Path) -> Path:
    return xmi_samples_dir / "generic_associations.xmi"


@pytest.fixture
def generic_xmi_content(generic_xmi_path: Path) -> str:
    return generic_xmi_path.read_text()


@pytest.fixture
def vehicle_mapping_plan() -> dict:
    """Mapping plan for a Vehicle model with composition and attributes."""
    return {
        "model_name": "VehicleModel",
        "dialect": "generic_xmi21",
        "components": [
            {
                "source_class": "Vehicle",
                "label": "Vehicle.make",
                "sdc4_type": "XdString",
                "description": "Vehicle manufacturer",
            },
            {
                "source_class": "Vehicle",
                "label": "Vehicle.year",
                "sdc4_type": "XdCount",
                "description": "Model year",
            },
            {
                "source_class": "Vehicle",
                "label": "Vehicle.weight",
                "sdc4_type": "XdQuantity",
                "description": "Vehicle weight in kg",
            },
            {
                "source_class": "Engine",
                "label": "Engine.horsepower",
                "sdc4_type": "XdQuantity",
                "description": "Engine horsepower",
            },
            {
                "source_class": "Engine",
                "label": "Engine.electric",
                "sdc4_type": "XdBoolean",
                "description": "Whether engine is electric",
            },
            {
                "source_class": "Wheel",
                "label": "Wheel.diameter",
                "sdc4_type": "XdQuantity",
                "description": "Wheel diameter in inches",
            },
        ],
        "clusters": [
            {
                "cluster_name": "Vehicle",
                "source_xmi_id": "v1",
                "description": "A motor vehicle",
                "component_refs": ["Vehicle.make", "Vehicle.year", "Vehicle.weight"],
            },
            {
                "cluster_name": "Engine",
                "source_xmi_id": "e1",
                "description": "Propulsion unit",
                "component_refs": ["Engine.horsepower", "Engine.electric"],
            },
            {
                "cluster_name": "Wheel",
                "source_xmi_id": "w1",
                "description": "A wheel assembly",
                "component_refs": ["Wheel.diameter"],
            },
            {
                "is_cluster": True,
                "cluster_name": "Vehicle",
                "source_xmi_id": "comp1",
                "description": "Engine is part of Vehicle",
                "component_refs": ["Engine"],
                "containment_type": "composition",
            },
            {
                "is_cluster": True,
                "cluster_name": "Vehicle",
                "source_xmi_id": "comp2",
                "description": "Wheels are part of Vehicle",
                "component_refs": ["Wheel"],
                "containment_type": "composition",
            },
        ],
        "unmapped": [],
        "summary": {
            "total_classes": 3,
            "total_components": 6,
            "total_clusters": 5,
            "total_unmapped": 0,
        },
    }


@pytest.fixture
def simple_mapping_plan() -> dict:
    """Minimal mapping plan with a single class and components."""
    return {
        "model_name": "SimpleModel",
        "dialect": "generic_xmi21",
        "components": [
            {
                "source_class": "Person",
                "label": "Person.name",
                "sdc4_type": "XdString",
                "description": "Full name",
            },
            {
                "source_class": "Person",
                "label": "Person.birthDate",
                "sdc4_type": "XdTemporal",
                "description": "Date of birth",
            },
        ],
        "clusters": [
            {
                "cluster_name": "Person",
                "source_xmi_id": "p1",
                "description": "A person",
                "component_refs": ["Person.name", "Person.birthDate"],
            },
        ],
        "unmapped": [],
        "summary": {
            "total_classes": 1,
            "total_components": 2,
            "total_clusters": 1,
            "total_unmapped": 0,
        },
    }
