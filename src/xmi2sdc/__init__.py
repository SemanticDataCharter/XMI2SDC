"""XMI2SDC — Agentic XMI/UML to SDC4 data model converter."""

from importlib.metadata import PackageNotFoundError, version

# Derived from the installed distribution so it cannot drift from
# pyproject.toml. It already had: this file said 4.1.0 after the bump.
try:
    __version__ = version("xmi2sdc")
except PackageNotFoundError:  # source tree that was never installed
    __version__ = "0.0.0+unknown"
