#!/bin/sh
set -e

# Docker entrypoint for XMI2SDC.
# Dispatches based on XMI2SDC_AGENT env var or passes args to the CLI.

if [ $# -gt 0 ]; then
    # Arguments provided — pass them directly to the CLI
    exec xmi2sdc --config "$XMI2SDC_CONFIG" "$@"
elif [ -n "$XMI2SDC_AGENT" ]; then
    # No args but XMI2SDC_AGENT is set — serve that agent as MCP
    exec xmi2sdc --config "$XMI2SDC_CONFIG" serve --mcp "$XMI2SDC_AGENT"
else
    echo "Usage: set XMI2SDC_AGENT env var or pass CLI arguments."
    echo ""
    echo "  XMI2SDC_AGENT mode (serve a single agent as MCP server):"
    echo "    docker run -e XMI2SDC_AGENT=parser -v ./config.yaml:/home/sdc/xmi2sdc.yaml:ro IMAGE"
    echo ""
    echo "  CLI mode (pass any xmi2sdc subcommand):"
    echo "    docker run -v ./config.yaml:/home/sdc/xmi2sdc.yaml:ro IMAGE info"
    echo "    docker run -v ./config.yaml:/home/sdc/xmi2sdc.yaml:ro IMAGE validate-config"
    echo ""
    echo "Available agents: assembler, mapper, parser"
    exit 1
fi
