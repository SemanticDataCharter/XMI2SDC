"""Cache manager for XMI2SDC.

Provides path helpers and existence checks for cached artifacts
stored under the .xmi2sdc-cache/ directory tree.
"""

from __future__ import annotations

from pathlib import Path


class CacheManager:
    """Manages the .xmi2sdc-cache directory structure and file lookups."""

    SUBDIRS = ("parsed", "analyses", "mappings", "assemblies", "reports")

    def __init__(self, root: str | Path = ".xmi2sdc-cache"):
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def ensure_dirs(self) -> None:
        """Create the cache root and all standard subdirectories."""
        for subdir in self.SUBDIRS:
            (self._root / subdir).mkdir(parents=True, exist_ok=True)

    def parsed_path(self, model_name: str) -> Path:
        """Path where a parsed XMI model JSON would be cached."""
        return self._root / "parsed" / f"{model_name}.json"

    def analysis_path(self, model_name: str) -> Path:
        """Path where a UML analysis result would be cached."""
        return self._root / "analyses" / f"{model_name}.json"

    def mapping_path(self, model_name: str) -> Path:
        """Path where a mapping plan JSON would be cached."""
        return self._root / "mappings" / f"{model_name}.json"

    def assembly_path(self, model_name: str) -> Path:
        """Path where an assembly result would be cached."""
        return self._root / "assemblies" / f"{model_name}.json"

    def report_path(self, model_name: str) -> Path:
        """Path where a conversion report would be cached."""
        return self._root / "reports" / f"{model_name}.json"

    def is_cached(self, path: Path) -> bool:
        """Check whether a cached file exists and is non-empty."""
        return path.is_file() and path.stat().st_size > 0
