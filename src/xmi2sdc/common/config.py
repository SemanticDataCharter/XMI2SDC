"""Configuration loading and validation for XMI2SDC.

Loads YAML config with ${VAR} environment variable substitution.
Fails closed: missing env vars raise KeyError immediately.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values.

    Raises KeyError if an environment variable is not set (fail closed).
    """

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ[var_name]  # KeyError if missing — intentional

    return _ENV_VAR_PATTERN.sub(_replace, value)


def _walk_and_substitute(obj: object) -> object:
    """Recursively substitute env vars in strings within nested dicts/lists."""
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _walk_and_substitute(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_and_substitute(item) for item in obj]
    return obj


class SDCStudioConfig(BaseModel):
    """SDCStudio API connection settings for Assembly API calls."""

    base_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    token: Optional[str] = None


class CacheConfig(BaseModel):
    """Local cache settings."""

    root: str = ".xmi2sdc-cache"
    ttl_hours: int = 24


class AuditConfig(BaseModel):
    """Audit logging settings."""

    path: str = ".xmi2sdc-cache/audit.jsonl"
    log_level: Literal["standard", "verbose"] = "standard"


class OutputConfig(BaseModel):
    """Output generation settings."""

    directory: str = "./output"


class XMI2SDCConfig(BaseModel):
    """Top-level configuration for XMI2SDC."""

    sdcstudio: SDCStudioConfig = Field(default_factory=SDCStudioConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_config(path: str | Path) -> XMI2SDCConfig:
    """Load and validate configuration from a YAML file.

    Environment variables in ${VAR} syntax are substituted before validation.
    Missing environment variables cause an immediate KeyError (fail closed).

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Validated XMI2SDCConfig instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        KeyError: If a referenced environment variable is not set.
    """
    raw = Path(path).read_text()
    data = yaml.safe_load(raw)
    substituted = _walk_and_substitute(data)
    return XMI2SDCConfig.model_validate(substituted)
