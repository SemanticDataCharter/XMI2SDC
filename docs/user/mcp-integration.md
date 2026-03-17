# MCP Integration

All three XMI2SDC agents can be served as [MCP](https://modelcontextprotocol.io/) stdio servers, allowing non-ADK clients to use the tools. The `xmi2sdc serve --mcp <agent>` command converts ADK `FunctionTool` instances to MCP tool types and serves them over stdio.

---

## Claude Desktop

### pip install variant

1. Install XMI2SDC:

   ```bash
   pip install xmi2sdc
   ```

2. Create your config file at `~/xmi2sdc.yaml` (see `xmi2sdc.example.yaml`).

3. Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

   ```json
   {
     "mcpServers": {
       "xmi2sdc-parser": {
         "command": "xmi2sdc",
         "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "parser"]
       },
       "xmi2sdc-mapper": {
         "command": "xmi2sdc",
         "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "mapper"]
       },
       "xmi2sdc-assembler": {
         "command": "xmi2sdc",
         "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "assembler"]
       }
     }
   }
   ```

4. Restart Claude Desktop. The agent's tools appear in the tool list.

### Docker variant

```json
{
  "mcpServers": {
    "xmi2sdc-parser": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/xmi2sdc.yaml:/home/sdc/xmi2sdc.yaml:ro",
        "-v", "/path/to/xmi-files:/home/sdc/data:ro",
        "-e", "XMI2SDC_AGENT=parser",
        "xmi2sdc"
      ]
    },
    "xmi2sdc-mapper": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/xmi2sdc.yaml:/home/sdc/xmi2sdc.yaml:ro",
        "-v", "/path/to/xmi-files:/home/sdc/data:ro",
        "-e", "XMI2SDC_AGENT=mapper",
        "xmi2sdc"
      ]
    },
    "xmi2sdc-assembler": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "host",
        "-v", "/path/to/xmi2sdc.yaml:/home/sdc/xmi2sdc.yaml:ro",
        "-e", "XMI2SDC_AGENT=assembler",
        "xmi2sdc"
      ]
    }
  }
}
```

> **Note:** The assembler needs `--network host` to reach SDCStudio at `localhost:8000`. Parser and mapper do not make network calls.

---

## Claude Code

Add to `.claude/settings.json` in the XMI2SDC project root:

```json
{
  "mcpServers": {
    "xmi2sdc-parser": {
      "command": "xmi2sdc",
      "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "parser"]
    },
    "xmi2sdc-mapper": {
      "command": "xmi2sdc",
      "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "mapper"]
    },
    "xmi2sdc-assembler": {
      "command": "xmi2sdc",
      "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "assembler"]
    }
  }
}
```

---

## Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "xmi2sdc-parser": {
      "command": "xmi2sdc",
      "args": ["serve", "--mcp", "parser"]
    },
    "xmi2sdc-mapper": {
      "command": "xmi2sdc",
      "args": ["serve", "--mcp", "mapper"]
    },
    "xmi2sdc-assembler": {
      "command": "xmi2sdc",
      "args": ["serve", "--mcp", "assembler"]
    }
  }
}
```

If your config file is not in the current directory, add `"--config", "/path/to/xmi2sdc.yaml"` before `"serve"` in each `args` array.

---

## Generic stdio Client

Any MCP client that supports stdio transport can connect:

```bash
# Start a single agent as an MCP server
xmi2sdc serve --mcp parser

# With explicit config path
xmi2sdc --config /path/to/xmi2sdc.yaml serve --mcp mapper
```

The server communicates via stdin/stdout using the MCP protocol. Stderr is used for status messages.

---

## Tool Availability per Agent

When you connect an MCP server, the client sees only that agent's tools:

| MCP Server | Tools Exposed |
|---|---|
| `xmi2sdc-parser` | `parse_xmi_file`, `detect_dialect`, `list_classes` |
| `xmi2sdc-mapper` | `map_model`, `resolve_associations`, `generate_mapping_report` |
| `xmi2sdc-assembler` | `build_assembly_tree`, `execute_assembly`, `poll_status` |

---

## Use-Case Matrix

Which agents to configure for common workflows:

| Workflow | XMI2SDC Agents | SDC Agents (optional) |
|---|---|---|
| Parse XMI and inspect | `parser` | -- |
| Full XMI-to-mapping | `parser` + `mapper` | -- |
| Full XMI-to-SDC4 | `parser` + `mapper` + `assembler` | -- |
| XMI-to-SDC4 + validate | all 3 | `validation` |
| XMI-to-SDC4 + distribute | all 3 | `validation` + `distribution` |

---

## Running alongside SDC Agents

XMI2SDC's 3 MCP servers coexist with SDC Agents' 8 MCP servers in the same client. This gives you 11 total MCP servers for the full SDC4 pipeline: XMI parsing, conversion, assembly, catalog browsing, validation, and distribution.

### Claude Desktop: Combined Configuration

```json
{
  "mcpServers": {
    "xmi2sdc-parser": {
      "command": "xmi2sdc",
      "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "parser"]
    },
    "xmi2sdc-mapper": {
      "command": "xmi2sdc",
      "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "mapper"]
    },
    "xmi2sdc-assembler": {
      "command": "xmi2sdc",
      "args": ["--config", "/path/to/xmi2sdc.yaml", "serve", "--mcp", "assembler"]
    },
    "sdc-catalog": {
      "command": "sdc-agents",
      "args": ["--config", "/path/to/sdc-agents.yaml", "serve", "--mcp", "catalog"]
    },
    "sdc-introspect": {
      "command": "sdc-agents",
      "args": ["--config", "/path/to/sdc-agents.yaml", "serve", "--mcp", "introspect"]
    },
    "sdc-mapping": {
      "command": "sdc-agents",
      "args": ["--config", "/path/to/sdc-agents.yaml", "serve", "--mcp", "mapping"]
    },
    "sdc-generator": {
      "command": "sdc-agents",
      "args": ["--config", "/path/to/sdc-agents.yaml", "serve", "--mcp", "generator"]
    },
    "sdc-validation": {
      "command": "sdc-agents",
      "args": ["--config", "/path/to/sdc-agents.yaml", "serve", "--mcp", "validation"]
    },
    "sdc-distribution": {
      "command": "sdc-agents",
      "args": ["--config", "/path/to/sdc-agents.yaml", "serve", "--mcp", "distribution"]
    },
    "sdc-knowledge": {
      "command": "sdc-agents",
      "args": ["--config", "/path/to/sdc-agents.yaml", "serve", "--mcp", "knowledge"]
    },
    "sdc-assembly": {
      "command": "sdc-agents",
      "args": ["--config", "/path/to/sdc-agents.yaml", "serve", "--mcp", "assembly"]
    }
  }
}
```

With this configuration, a typical XMI-to-SDC4 session might look like:

1. Use `parse_xmi_file` to parse a Sparx EA export
2. Use `list_classes` to inspect the UML model
3. Use `map_model` to generate the SDC4 mapping plan
4. Use `execute_assembly` to submit to SDCStudio Assembly API
5. Use `validate_instance` (SDC Agents) to validate the generated artifacts
6. Use `distribute_package` (SDC Agents) to deliver to destinations
