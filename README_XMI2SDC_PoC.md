# XMI2SDC — PoC Setup Guide

XMI2SDC converts enterprise **UML models** (XMI exports from Sparx Enterprise Architect, MagicDraw, and other tools) into SDC4-compliant data models. It uses a multi-agent pipeline to parse, analyze, map, and assemble models via the SDCStudio Assembly API — all running locally with no cloud dependencies.

---

## Prerequisites

| Requirement | Details |
|---|---|
| SDCStudioSov | Running at `http://localhost:8000` (Phase 1 PoC) |
| Docker Engine | 24+ with Compose V2 |

> **Note**: XMI2SDC's parsing and mapping stages are deterministic — no LLM is required for basic conversion. The analyzer and reviewer agents use an LLM for semantic analysis but are optional for the core pipeline.

---

## Quick Start

### 1. Extract the Tarball

```bash
tar xzf XMI2SDC-poc-4.0.0.tar.gz
cd XMI2SDC
```

### 2. Run the Init Script

```bash
./scripts/init-xmi2sdc.sh
```

This will:
- Verify SDCStudioSov is reachable at `localhost:8000`
- Generate `xmi2sdc.yaml` from the example (with the pre-baked API token)
- Create `data/` and `output/` directories
- Build the Docker image
- Run a config validation check

### 3. Verify

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc info
```

You should see the config summary and agent inventory (parser, analyzer, mapper, reviewer, assembler).

---

## Available Agents

| Agent | Tools | LLM | Purpose |
|---|---|---|---|
| **parser** | 3 | No | Parse XMI files, auto-detect dialect (Sparx EA, MagicDraw, generic XMI 2.x), normalize to intermediate model |
| **analyzer** | 3 | Yes | Semantic analysis of class intent, inheritance, associations |
| **mapper** | 3 | Edge cases | Apply UML-to-SDC4 type mapping rules, produce mapping plan |
| **reviewer** | 2 | Yes | Review mapping completeness, generate conversion report |
| **assembler** | 3 | No | Execute mapping plan via SDCStudio Assembly API |

---

## Usage Modes

### CLI Mode

```bash
# Show config summary and agent inventory
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc info

# Validate the config file
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc validate-config

# Convert an XMI file (parse + map, produces JSON mapping plan)
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc convert /data/model.xmi

# View recent audit log entries
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc audit show --last 24h
```

### MCP Server Mode

Start agents as MCP servers for LLM client integration (Claude Desktop, Cursor, etc.):

```bash
# Start the parser agent as an MCP server
docker compose -f docker-compose.xmi2sdc.yml up -d xmi2sdc-parser

# Start all agents
docker compose -f docker-compose.xmi2sdc.yml up -d xmi2sdc-parser xmi2sdc-mapper xmi2sdc-assembler

# View logs
docker compose -f docker-compose.xmi2sdc.yml logs -f xmi2sdc-parser

# Stop agents
docker compose -f docker-compose.xmi2sdc.yml down
```

---

## Demo Walkthrough

### Step 1: Place an XMI File

Place a UML model export (XMI format) in the `./data/` directory:

```bash
cp /path/to/your/model.xmi data/
```

XMI2SDC auto-detects the dialect (Sparx EA, MagicDraw, or generic XMI 2.x) from namespace declarations.

### Step 2: Convert

Run the conversion pipeline — this parses the XMI, maps UML types to SDC4 types, and produces a JSON mapping plan:

```bash
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc convert /data/model.xmi
```

The mapping plan is written to `./output/`.

### Step 3: Review Output

Inspect the mapping plan and audit log:

```bash
ls output/
docker compose -f docker-compose.xmi2sdc.yml run --rm xmi2sdc audit show --last 1h
```

The mapping plan shows how each UML class and attribute maps to SDC4 types (XdString, XdQuantity, XdTemporal, Cluster, etc.).

---

## Type Mapping

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

---

## Configuration

The `xmi2sdc.yaml` file controls all agent behavior. Key settings:

```yaml
sdcstudio:
  base_url: "http://localhost:8000"    # SDCStudioSov instance
  api_key: "poc-eval-token-2026"       # Pre-baked API token (from seed database)
```

For the PoC, the API token is pre-configured in both the seed database and the generated config file. No manual token creation is needed.

### Adding XMI Files

Place XMI exports in the `./data/` directory. They are mounted read-only into the agent container at `/home/sdc/data/`.

---

## Troubleshooting

**"Connection refused" to SDCStudioSov**
Verify Studio is running: `curl -s http://localhost:8000/accounts/login/ | head -1`. If not, run `./scripts/init-poc.sh` in the SDCStudioSov directory first.

**"401 Unauthorized" from API**
The pre-baked API token (`poc-eval-token-2026`) must exist in the database. Re-run `./scripts/init-poc.sh` in SDCStudioSov to restore the seed database with the token.

**HTTP 402 (insufficient funds)**
The PoC wallet has a pre-loaded balance. If depleted, add funds via Django Admin: http://localhost:8000/admin/billing/usdwallet/

**Config not found**
Ensure `xmi2sdc.yaml` exists in the project root. Re-run `./scripts/init-xmi2sdc.sh` to regenerate it.

**Docker build failures**
Ensure Docker has network access to pull the Python base image. For air-gapped environments, pre-load the image:
```bash
docker load -i python-3.12-slim.tar
```

**Output files not appearing**
Check that the `./output/` directory exists and is writable. The container runs as UID 1000 — ensure the host directory permissions match.

---

## Removing the XMI2SDC Container

```bash
# Stop and remove containers
docker compose -f docker-compose.xmi2sdc.yml down

# Also remove the built image
docker compose -f docker-compose.xmi2sdc.yml down --rmi all
```

---

## Further Reading

| Document | Description |
|---|---|
| [`README.md`](README.md) | Full XMI2SDC documentation |
| [`xmi2sdc.example.yaml`](xmi2sdc.example.yaml) | Complete configuration reference |
| [`docs/user/sovereign-docker-integration.md`](docs/user/sovereign-docker-integration.md) | Sovereign Docker integration guide |
| SDCStudioSov `README_PoC.md` | Platform setup and catalog walkthrough |
