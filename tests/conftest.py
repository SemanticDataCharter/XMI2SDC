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
def generic_xmi_content(generic_xmi_path: Path) -> str:
    return generic_xmi_path.read_text()
