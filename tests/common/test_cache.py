"""Tests for xmi2sdc.common.cache."""

from __future__ import annotations

from xmi2sdc.common.cache import CacheManager


def test_cache_subdirs(tmp_path):
    """ensure_dirs should create all standard subdirectories."""
    cache = CacheManager(tmp_path / "test-cache")
    cache.ensure_dirs()

    for subdir in CacheManager.SUBDIRS:
        assert (cache.root / subdir).is_dir()


def test_parsed_path(tmp_path):
    """parsed_path should return correct path."""
    cache = CacheManager(tmp_path / "cache")
    assert cache.parsed_path("my_model") == cache.root / "parsed" / "my_model.json"


def test_analysis_path(tmp_path):
    """analysis_path should return correct path."""
    cache = CacheManager(tmp_path / "cache")
    assert cache.analysis_path("my_model") == cache.root / "analyses" / "my_model.json"


def test_mapping_path(tmp_path):
    """mapping_path should return correct path."""
    cache = CacheManager(tmp_path / "cache")
    assert cache.mapping_path("my_model") == cache.root / "mappings" / "my_model.json"


def test_assembly_path(tmp_path):
    """assembly_path should return correct path."""
    cache = CacheManager(tmp_path / "cache")
    assert cache.assembly_path("my_model") == cache.root / "assemblies" / "my_model.json"


def test_report_path(tmp_path):
    """report_path should return correct path."""
    cache = CacheManager(tmp_path / "cache")
    assert cache.report_path("my_model") == cache.root / "reports" / "my_model.json"


def test_is_cached_false(tmp_path):
    """is_cached should return False for non-existent file."""
    cache = CacheManager(tmp_path / "cache")
    assert not cache.is_cached(cache.parsed_path("nope"))


def test_is_cached_true(tmp_path):
    """is_cached should return True for existing non-empty file."""
    cache = CacheManager(tmp_path / "cache")
    cache.ensure_dirs()
    path = cache.parsed_path("test")
    path.write_text('{"data": true}')
    assert cache.is_cached(path)


def test_is_cached_empty(tmp_path):
    """is_cached should return False for empty file."""
    cache = CacheManager(tmp_path / "cache")
    cache.ensure_dirs()
    path = cache.parsed_path("empty")
    path.write_text("")
    assert not cache.is_cached(path)
