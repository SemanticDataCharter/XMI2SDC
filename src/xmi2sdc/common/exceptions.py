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
    """
    Raised when SDCStudio returns HTTP 402.

    Carries the server's credits figures when present. Users are quoted credits
    at 1,000 per USD, so anything shown to a person uses ``*_credits``; the USD
    values are retained for accounting.
    """

    def __init__(
        self,
        message: str = "Insufficient credits.",
        *,
        estimated_cost_credits: int | None = None,
        balance_credits: int | None = None,
    ):
        self.estimated_cost_credits = estimated_cost_credits
        self.balance_credits = balance_credits
        super().__init__(message)
