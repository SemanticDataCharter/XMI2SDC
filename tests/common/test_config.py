"""Tests for xmi2sdc.common.config."""

from __future__ import annotations

import pytest
import yaml

from xmi2sdc.common.config import (
    XMI2SDCConfig,
    _substitute_env_vars,
    _walk_and_substitute,
    load_config,
)


def test_load_sample_config(sample_config_path):
    """Load the sample config fixture and verify defaults."""
    config = load_config(sample_config_path)
    assert config.sdcstudio.base_url == "http://localhost:8000"
    assert config.cache.root == ".xmi2sdc-cache"
    assert config.audit.log_level == "standard"
    assert config.output.directory == "./output"


def test_default_config():
    """All fields should have sensible defaults."""
    config = XMI2SDCConfig()
    assert config.sdcstudio.base_url == "http://localhost:8000"
    assert config.sdcstudio.api_key is None
    assert config.cache.root == ".xmi2sdc-cache"
    assert config.cache.ttl_hours == 24
    assert config.audit.path == ".xmi2sdc-cache/audit.jsonl"
    assert config.output.directory == "./output"


def test_env_var_substitution(monkeypatch):
    """${VAR} placeholders should be replaced with env values."""
    monkeypatch.setenv("TEST_URL", "http://example.com:9000")
    result = _substitute_env_vars("${TEST_URL}/api")
    assert result == "http://example.com:9000/api"


def test_env_var_missing_raises():
    """Missing env var should raise KeyError (fail closed)."""
    with pytest.raises(KeyError):
        _substitute_env_vars("${DEFINITELY_NOT_SET_12345}")


def test_walk_and_substitute(monkeypatch):
    """Recursive substitution across nested structures."""
    monkeypatch.setenv("MY_HOST", "prod.example.com")
    data = {"url": "http://${MY_HOST}", "nested": {"key": "${MY_HOST}"}, "list": ["${MY_HOST}"]}
    result = _walk_and_substitute(data)
    assert result["url"] == "http://prod.example.com"
    assert result["nested"]["key"] == "prod.example.com"
    assert result["list"][0] == "prod.example.com"


def test_load_config_with_env_vars(tmp_path, monkeypatch):
    """Config file with env vars should load correctly."""
    monkeypatch.setenv("SDC_BASE_URL", "http://myserver:8000")
    config_data = {
        "sdcstudio": {"base_url": "${SDC_BASE_URL}"},
    }
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(yaml.dump(config_data))

    config = load_config(config_file)
    assert config.sdcstudio.base_url == "http://myserver:8000"


def test_load_config_file_not_found():
    """Missing config file should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.yaml")
