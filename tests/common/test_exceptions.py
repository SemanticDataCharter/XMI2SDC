"""Tests for xmi2sdc.common.exceptions — exception hierarchy."""

from __future__ import annotations

import pytest

from xmi2sdc.common.exceptions import (
    AssemblyApiError,
    AssemblyError,
    DialectDetectionError,
    InsufficientFundsError,
    MappingError,
    XmiParseError,
)


class TestExceptionInstantiation:
    """Each exception can be raised with a message."""

    def test_xmi_parse_error(self):
        exc = XmiParseError("bad xmi")
        assert str(exc) == "bad xmi"

    def test_dialect_detection_error(self):
        exc = DialectDetectionError("unknown dialect")
        assert str(exc) == "unknown dialect"

    def test_mapping_error(self):
        exc = MappingError("unmapped type")
        assert str(exc) == "unmapped type"

    def test_assembly_error(self):
        exc = AssemblyError("api failure")
        assert str(exc) == "api failure"

    def test_assembly_api_error(self):
        exc = AssemblyApiError("HTTP 500")
        assert str(exc) == "HTTP 500"

    def test_insufficient_funds_error(self):
        exc = InsufficientFundsError("HTTP 402")
        assert str(exc) == "HTTP 402"


class TestExceptionHierarchy:
    """Verify inheritance chains."""

    def test_dialect_detection_is_xmi_parse(self):
        with pytest.raises(XmiParseError):
            raise DialectDetectionError("child caught by parent")

    def test_assembly_api_is_assembly(self):
        with pytest.raises(AssemblyError):
            raise AssemblyApiError("child caught by parent")

    def test_insufficient_funds_is_assembly(self):
        with pytest.raises(AssemblyError):
            raise InsufficientFundsError("child caught by parent")


class TestExceptionIndependence:
    """MappingError is independent of XmiParseError and AssemblyError."""

    def test_mapping_not_xmi_parse(self):
        assert not issubclass(MappingError, XmiParseError)

    def test_mapping_not_assembly(self):
        assert not issubclass(MappingError, AssemblyError)
