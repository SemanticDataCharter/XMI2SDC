"""Custom exceptions for XMI2SDC."""

from __future__ import annotations


class XmiParseError(Exception):
    """Raised when XMI parsing fails due to malformed or unsupported input."""


class DialectDetectionError(XmiParseError):
    """Raised when the XMI dialect cannot be determined."""


class MappingError(Exception):
    """Raised when UML-to-SDC4 type mapping fails."""


class AssemblyError(Exception):
    """Raised when SDCStudio Assembly API interaction fails."""


class AssemblyApiError(AssemblyError):
    """Raised when the Assembly API returns an error response."""


class InsufficientFundsError(AssemblyError):
    """Raised when the wallet has insufficient funds (HTTP 402)."""
