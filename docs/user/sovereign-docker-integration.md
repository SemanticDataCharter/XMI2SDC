# Sovereign Docker Integration Guide

Deploy XMI2SDC as part of the sovereign SDC stack alongside SDCStudioSov and SDC_AgentsSov.

## Overview

XMI2SDC converts UML models (XMI format from Sparx EA, MagicDraw, StarUML, etc.) into SDC4-compliant data models. It runs a three-agent pipeline:

1. **Parser** — Reads XMI files, detects the dialect, extracts classes, attributes, enumerations, and associations
2. **Mapper** — Maps parsed UML elements to SDC4 component types (XdString, XdQuantity, Cluster, etc.)
3. **Assembler** — Submits the mapping plan to the SDCStudioSov Assembly API to create the data model

Each agent can run as a standalone MCP server (for Claude Desktop/Code/Cursor) or be invoked via the CLI for scripted workflows.

## Prerequisites

| Requirement | Details |
|---|---|
| SDCStudioSov | Running at `http://localhost:8000` |
| Docker Compose V2 | `docker compose version` returns v2.x |
| API token | From SDCStudioSov — use `poc-eval-token-2026` for PoC evaluation |
| Wallet balance | Assembler calls the Assembly API ($0.50 per model). Ensure the wallet has funds. |

Ollama is **not required** — XMI2SDC agents use deterministic toolset logic, not LLM inference. The parser and mapper run entirely offline.

## Directory Layout

```
XMI2SDC/
├── docker-compose.xmi2sdc.yml   # Service definitions
├── Dockerfile                    # Multi-stage build
├── xmi2sdc.yaml                  # Your config (created from example)
├── xmi2sdc.example.yaml          # Committed template
├── data/                         # Place XMI files here (mounted read-only)
│   └── model.xmi
├── output/                       # Generated mapping plans and results
└── .xmi2sdc-cache/               # Parse cache and audit log
    └── audit.jsonl
```

## Configuration

### 1. Create your config file

```bash
cp xmi2sdc.example.yaml xmi2sdc.yaml
```

### 2. Set the API key

Choose one approach:

**Environment variable (recommended)**:
```bash
export SDC_API_KEY="poc-eval-token-2026"
```

The `${SDC_API_KEY}` placeholder in `xmi2sdc.yaml` is resolved at load time. If the variable is not set, XMI2SDC exits immediately with an error (fail-closed — no silent fallback).

**Inline replacement** (alternative):
Edit `xmi2sdc.yaml` and replace `"${SDC_API_KEY}"` with the token directly:
```yaml
sdcstudio:
  api_key: "poc-eval-token-2026"
```

### 3. Validate

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc validate-config
# Expected output: Config OK: /home/sdc/xmi2sdc.yaml
```

### Configuration reference

| Key | Default | Description |
|---|---|---|
| `sdcstudio.base_url` | `http://localhost:8000` | SDCStudioSov URL |
| `sdcstudio.api_key` | (none) | API token for Assembly API |
| `cache.root` | `.xmi2sdc-cache` | Parse cache directory |
| `cache.ttl_hours` | `24` | Cache time-to-live |
| `audit.path` | `.xmi2sdc-cache/audit.jsonl` | Audit log location |
| `audit.log_level` | `standard` | `standard` or `verbose` |
| `output.directory` | `./output` | Generated output directory |

## Build and Start Services

### MCP servers (persistent)

Start all three agent MCP servers for Claude Desktop/Code/Cursor:

```bash
docker compose -f docker-compose.xmi2sdc.yml up -d --build
```

This starts `xmi2sdc-parser`, `xmi2sdc-mapper`, and `xmi2sdc-assembler` as long-running MCP stdio servers. The `xmi2sdc` CLI service is **not** started (it uses the `cli` profile).

### CLI one-shot commands

Run any CLI command via the `cli` profile:

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc <command>
```

### Stop services

```bash
docker compose -f docker-compose.xmi2sdc.yml down
```

## CLI Quick Reference

All commands below use the Docker Compose `run --rm` pattern. Substitute your file paths as needed.

### `info` — Show configuration and agent inventory

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc info
```

Displays: config path, cache root, output directory, audit path, registered agents with tool counts, SDCStudioSov URL, API key status.

### `validate-config` — Check config file

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc validate-config
```

Exits 0 on success, exits 1 with a specific error if the config is missing, an env var is unset, or validation fails.

### `convert` — Parse XMI and generate mapping plan

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc convert /data/model.xmi
```

Options:
- `--model-name TEXT` — Override the model name (defaults to the filename)
- `--output/-o PATH` — Output JSON path (defaults to `{output.directory}/{model_name}_mapping.json`)

Output summary: dialect, class count, enumeration count, association count, component count, cluster count, unmapped count.

### `assemble` — Submit mapping plan to Assembly API

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc assemble /home/sdc/output/model_mapping.json \
  --title "My UML Model"
```

Options:
- `--title TEXT` (required) — Data model title
- `--description TEXT` — Data model description
- `--api-key TEXT` — Override API key from config
- `--base-url TEXT` — Override SDCStudioSov URL
- `--timeout INT` — Polling timeout in seconds (default: 300)

### `audit show` — View audit log

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc audit show --last 24h
```

Options:
- `--agent TEXT` — Filter by agent name
- `--tool TEXT` — Filter by tool name
- `--last DURATION` — Time window (e.g. `24h`, `7d`, `30m`)
- `--limit INT` — Max records (default: 50)

## MCP Client Configuration

For detailed MCP client setup (Claude Desktop, Claude Code, Cursor, generic stdio), see [mcp-integration.md](mcp-integration.md).

### Sovereign Docker variant

When running the MCP servers via Docker Compose (as described above), configure your MCP client to connect to the running containers. Example for Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "xmi2sdc-parser": {
      "command": "docker",
      "args": ["exec", "-i", "xmi2sdc-parser", "xmi2sdc", "--config", "/home/sdc/xmi2sdc.yaml", "serve", "--mcp", "parser"]
    },
    "xmi2sdc-mapper": {
      "command": "docker",
      "args": ["exec", "-i", "xmi2sdc-mapper", "xmi2sdc", "--config", "/home/sdc/xmi2sdc.yaml", "serve", "--mcp", "mapper"]
    },
    "xmi2sdc-assembler": {
      "command": "docker",
      "args": ["exec", "-i", "xmi2sdc-assembler", "xmi2sdc", "--config", "/home/sdc/xmi2sdc.yaml", "serve", "--mcp", "assembler"]
    }
  }
}
```

## Running Alongside SDC_AgentsSov

The full sovereign stack exposes **11 MCP servers**:

| Source | Servers | Tools |
|---|---|---|
| XMI2SDC | 3 (parser, mapper, assembler) | `parse_xmi_file`, `detect_dialect`, `list_classes`, `map_model`, `resolve_associations`, `generate_mapping_report`, `build_assembly_tree`, `execute_assembly`, `poll_status` |
| SDC_AgentsSov | 8 (catalog, validation, assembly, minting, semantic_discovery, knowledge, schema, export) | 32 tools across agents |

### End-to-end pipeline walkthrough

1. **Parse**: `xmi2sdc convert model.xmi` — extracts UML structure into a mapping plan JSON
2. **Map**: (runs automatically within `convert`) — maps UML types to SDC4 component types
3. **Assemble**: `xmi2sdc assemble output/model_mapping.json --title "Model"` — submits to SDCStudioSov Assembly API, which mints new components and assembles the data model
4. **Validate**: Use SDC_AgentsSov's validation agent to validate generated instances against the new schema
5. **Distribute**: Use SDC_AgentsSov's export agent to generate XSD, XML, JSON-LD, HTML, SHACL, GQL outputs

## Network Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Host Machine                       │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ xmi2sdc-    │  │ xmi2sdc-    │  │ xmi2sdc-    │ │
│  │ parser      │  │ mapper      │  │ assembler   │ │
│  │ (offline)   │  │ (offline)   │  │ ──────────► │─┼──┐
│  └─────────────┘  └─────────────┘  └─────────────┘ │  │
│                                                     │  │
│  network_mode: host (all containers)                │  │
│                                                     │  │
│  ┌─────────────────────────────────────────────────┐ │  │
│  │ SDCStudioSov (localhost:8000)                   │◄┼──┘
│  │  ├── Assembly API  (/api/assembly/...)          │ │
│  │  ├── Catalog API   (/api/catalog/...)           │ │
│  │  └── VaaS API      (/api/vaas/...)              │ │
│  └─────────────────────────────────────────────────┘ │
│                                                     │
│  ┌─────────────────────────────────────────────────┐ │
│  │ SDC_AgentsSov MCP servers (8 agents)            │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

- All XMI2SDC containers use `network_mode: host` — they reach SDCStudioSov directly at `localhost:8000`
- **Parser** and **mapper** are fully offline — they read XMI files from the mounted `data/` volume and write to cache/output. No network calls.
- **Assembler** is the only container that makes HTTP calls (to the Assembly API)
- All telemetry is suppressed (`OTEL_SDK_DISABLED=true`) — no data leaves the host

## Troubleshooting

### Config not found

```
Error: Config file not found: /home/sdc/xmi2sdc.yaml
```

Ensure `xmi2sdc.yaml` exists in the XMI2SDC directory. The Docker Compose file mounts it at `/home/sdc/xmi2sdc.yaml:ro`.

```bash
cp xmi2sdc.example.yaml xmi2sdc.yaml
```

### API key not set

```
KeyError: 'SDC_API_KEY'
```

The `${SDC_API_KEY}` placeholder in `xmi2sdc.yaml` could not be resolved. Either:
- Set the environment variable: `export SDC_API_KEY="poc-eval-token-2026"`
- Or replace the placeholder with the token directly in `xmi2sdc.yaml`

Note: pass the env var into Docker with `-e SDC_API_KEY` or add it to your compose environment:

```yaml
environment:
  SDC_API_KEY: "poc-eval-token-2026"
```

### SDCStudioSov unreachable

```
ConnectionError: http://localhost:8000
```

The assembler cannot reach SDCStudioSov. Verify:
1. SDCStudioSov is running: `curl http://localhost:8000/api/catalog/`
2. The container uses `network_mode: host` (default in the compose file)
3. `sdcstudio.base_url` in `xmi2sdc.yaml` is `http://localhost:8000`

### HTTP 402 — Insufficient wallet balance

```
HTTP 402: Payment Required
```

The wallet does not have enough funds for the assembly operation ($0.50 per model). Add funds via the SDCStudioSov wallet dashboard or API.

### Docker build issues

```bash
# Rebuild from scratch
docker compose -f docker-compose.xmi2sdc.yml build --no-cache

# Check build logs
docker compose -f docker-compose.xmi2sdc.yml build 2>&1 | tail -50
```

### Viewing container logs

```bash
# All services
docker compose -f docker-compose.xmi2sdc.yml logs

# Specific service
docker compose -f docker-compose.xmi2sdc.yml logs xmi2sdc-assembler

# Follow logs
docker compose -f docker-compose.xmi2sdc.yml logs -f
```
