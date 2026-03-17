# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

XMI2SDC is an **agentic XMI/UML to SDC4 data model converter**. It uses a multi-agent pipeline built on the Google Agent Development Kit (ADK) to parse UML models exported from Sparx Enterprise Architect, MagicDraw, and other tools, then convert them into SDC4-compliant data models via the SDCStudio Assembly API.

**Version**: 4.0.0
**License**: Proprietary (Axius SDC, Inc.)

Built for **air-gapped, self-hosted** environments. No cloud dependencies required.

## SDC4 Context

XMI2SDC is part of the SDC4 ecosystem. Key principles:
- **XML instances are self-describing** — root element name and `xsi:schemaLocation` identify the schema
- **Schemas are never versioned** — each schema is identified by its `ct_id` (CUID2)
- **`xsd:restriction` only, never `xsd:extension`** — constraint-based specialization
- **Semantic versioning**: MAJOR = SDC Reference Model version (4), MINOR = features, PATCH = fixes

## Architecture

### Agent Pipeline

```
XMI File --> Parser Agent --> ParsedXmiModel --> Mapper Agent --> Mapping Plan JSON
                                                                        |
                                                                        v
                                                  Conversion Report <-- Assembler --> SDCStudio API
```

### Agents

| Agent | Tools | LLM | Description |
|---|---|---|---|
| parser | 3 | No | Parse XMI files, auto-detect dialect, normalize to intermediate model |
| mapper | 3 | Edge cases | Apply UML-to-SDC4 type mapping rules, produce mapping plan |
| assembler | 3 | No | Execute mapping plan via SDCStudio Assembly API |

**Key design**: Deterministic operations (parsing, type mapping) are separated from LLM-assisted operations (edge-case resolution). Failed stages can resume from cache.

### Supported Dialects

- **Generic XMI 2.x** — Standard OMG XMI exports
- **Sparx Enterprise Architect** — Auto-detected via `sparxsystems.com` namespace
- **MagicDraw / Cameo** — Auto-detected via `nomagic.com` namespace

## Development Workflow

### Branch Strategy

- **`main`**: Production code, protected branch (PR required)
- **`dev`**: Active development, all work happens here

**Flow**: Work on `dev` → Test → PR to `main` → Merge

### Environment Setup

```bash
# Activate conda environment
conda activate SDCStudio

# Install in development mode
pip install -e ".[dev]"
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=xmi2sdc --cov-report=term-missing

# Specific test file
pytest tests/toolsets/test_parser_tools.py

# Specific test
pytest tests/toolsets/test_parser_tools.py::test_function_name
```

### Linting

```bash
# Check style
ruff check src/ tests/

# Check formatting
black --check src/ tests/

# Auto-fix formatting
black src/ tests/
```

## Project Structure

```
xmi2sdc/
├── src/xmi2sdc/
│   ├── agents/           # ADK agent definitions
│   │   ├── parser.py     # Parser agent
│   │   ├── mapper.py     # Mapper agent
│   │   └── ...
│   ├── toolsets/          # Agent tool implementations
│   │   ├── parser.py     # Parser tools (parse_xmi, detect_dialect, etc.)
│   │   ├── mapper.py     # Mapper tools (map_types, resolve_associations, etc.)
│   │   └── ...
│   ├── common/            # Shared utilities
│   │   ├── xmi_types.py   # Pydantic models for XMI/UML types
│   │   ├── config.py      # YAML configuration loader
│   │   ├── audit.py       # Structured audit logging
│   │   ├── cache.py       # .xmi2sdc-cache management
│   │   ├── inheritance.py # UML inheritance resolution
│   │   └── exceptions.py  # Custom exceptions
│   └── cli.py             # Click CLI entry point
├── tests/
│   ├── common/            # Tests for shared utilities
│   ├── toolsets/          # Tests for agent tools
│   ├── fixtures/          # Test XMI files and data
│   └── conftest.py        # Shared pytest fixtures
├── scripts/               # Docker entrypoint and utilities
├── xmi2sdc.example.yaml   # Configuration template
├── Dockerfile             # Multi-stage Docker build
└── pyproject.toml         # Project metadata and tool config
```

## Code Style and Conventions

- **PEP 8** for all Python code
- **Google style docstrings**
- **Type hints** required for all public functions
- **Line length**: 99 characters (ruff + black)
- **Linters**: ruff (E, F, I, W rules) and black
- **Target**: Python 3.11+

### Agent Isolation Rules

1. No agent imports another agent's code — each agent has its own toolset
2. Tool inputs come from function signatures only — no raw file paths as tool input
3. Network access is explicit — only specific agents may make HTTP calls
4. File writes are scoped to designated directories
5. Credentials come from configuration, never from tool parameters

### ADK Tool Definitions

Each tool is a Python `async def` function wrapped in `FunctionTool`:
- Clear name following `{agent}_{action}` convention
- Type-hinted parameters with Google-style docstring descriptions
- Return type annotation and documented return structure
- Side effects documented in the docstring

## Configuration

Configuration lives in `xmi2sdc.yaml` with environment variable substitution (`${VAR}` syntax). Missing variables cause an immediate error (fail closed).

```yaml
sdcstudio:
  base_url: "http://localhost:8000"
  api_key: "${SDC_API_KEY}"

cache:
  root: ".xmi2sdc-cache"

audit:
  path: ".xmi2sdc-cache/audit.jsonl"
  log_level: "standard"

output:
  directory: "./output"
```

## CLI Commands

```bash
xmi2sdc convert FILE       # Parse XMI and produce SDC4 mapping plan
xmi2sdc assemble FILE      # Submit mapping plan to SDCStudio Assembly API
xmi2sdc serve --mcp AGENT  # Start MCP stdio server for an agent toolset
xmi2sdc info               # Display config summary and agent inventory
xmi2sdc validate-config    # Validate configuration file
xmi2sdc audit show         # Display audit log with filters
```

## Docker

```bash
# Build
docker build -t xmi2sdc .

# MCP server mode
docker run -v $(pwd)/xmi2sdc.yaml:/home/sdc/xmi2sdc.yaml:ro \
    -e XMI2SDC_AGENT=parser xmi2sdc

# CLI mode
docker run -v $(pwd)/xmi2sdc.yaml:/home/sdc/xmi2sdc.yaml:ro \
    xmi2sdc info
```

## Type Mapping Reference

| UML Type | SDC4 Type | Notes |
|---|---|---|
| Boolean | XdBoolean | |
| Integer (non-negative) | XdCount | |
| Integer (signed) | XdQuantity | Integer restriction |
| Real / Float / Double | XdQuantity | |
| String | XdString | |
| Enumeration | XdString | Literals become enumerations |
| Date / DateTime / Time | XdTemporal | |
| Class (composite) | Cluster | |
| Composition association | Cluster containment | |

## Important Notes

- **Never commit** `xmi2sdc.yaml` with real credentials — use `xmi2sdc.example.yaml` as template
- Follow PEP 8 for all Python code
- Use Google style docstrings
- All pull requests should include tests
- `.xmi2sdc-cache/` is gitignored — it contains runtime state only
