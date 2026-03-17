"""CLI entry point for xmi2sdc.

Provides subcommands for serving agents as MCP servers, inspecting
audit logs, displaying configuration info, and validating config files.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path

import click

AGENT_REGISTRY: dict[str, tuple[str, str]] = {
    "parser": ("xmi2sdc.toolsets.parser", "XmiParserToolset"),
    "mapper": ("xmi2sdc.toolsets.mapper", "SdcMapperToolset"),
    "assembler": ("xmi2sdc.toolsets.assembler", "SdcAssemblerToolset"),
}

_VALID_AGENTS = ", ".join(sorted(AGENT_REGISTRY))


def _load_toolset(agent_name: str, config):
    """Dynamically import and instantiate a toolset for the given agent."""
    module_path, class_name = AGENT_REGISTRY[agent_name]
    mod = import_module(module_path)
    cls = getattr(mod, class_name)
    return cls(config=config)


def _parse_duration(duration: str) -> timedelta:
    """Parse a duration string like '24h', '7d', '30m' into a timedelta."""
    match = re.fullmatch(r"(\d+)([hdm])", duration.strip().lower())
    if not match:
        raise click.BadParameter(
            f"Invalid duration '{duration}'. Use format like '24h', '7d', or '30m'."
        )
    value, unit = int(match.group(1)), match.group(2)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    return timedelta(minutes=value)


@click.group()
@click.option(
    "--config",
    default=None,
    envvar="XMI2SDC_CONFIG",
    type=click.Path(),
    help="Path to xmi2sdc.yaml config file.  [default: xmi2sdc.yaml]",
)
@click.pass_context
def main(ctx: click.Context, config: str | None) -> None:
    """XMI2SDC — agentic XMI/UML to SDC4 data model converter."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config or "xmi2sdc.yaml"


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--mcp",
    required=True,
    metavar="AGENT",
    help=f"Agent to serve as MCP server.  Valid: {_VALID_AGENTS}",
)
@click.pass_context
def serve(ctx: click.Context, mcp: str) -> None:
    """Start an agent toolset as an MCP stdio server."""
    if mcp not in AGENT_REGISTRY:
        raise click.ClickException(f"Unknown agent '{mcp}'. Valid agents: {_VALID_AGENTS}")

    from xmi2sdc.common.config import load_config

    try:
        config = load_config(ctx.obj["config_path"])
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    asyncio.run(_run_mcp_server(mcp, config))


async def _run_mcp_server(agent_name: str, config) -> None:
    """Set up and run an MCP stdio server for the given agent toolset."""
    from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent

    toolset = _load_toolset(agent_name, config)
    adk_tools = await toolset.get_tools()

    # Build lookup: MCP tool name → ADK FunctionTool
    adk_by_name = {t.name: t for t in adk_tools}
    mcp_tools = [adk_to_mcp_tool_type(t) for t in adk_tools]

    server = Server(f"xmi2sdc-{agent_name}")

    @server.list_tools()
    async def list_tools():
        return mcp_tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name not in adk_by_name:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        func = adk_by_name[name]
        result = await func.run_async(args=arguments, tool_context=None)
        text = json.dumps(result, default=str) if not isinstance(result, str) else result
        return [TextContent(type="text", text=text)]

    click.echo(f"Serving {agent_name} agent via MCP stdio ({len(adk_tools)} tools)...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


@main.group()
def audit() -> None:
    """Inspect the structured audit log."""


@audit.command("show")
@click.option("--agent", default=None, help="Filter by agent name.")
@click.option("--tool", default=None, help="Filter by tool name.")
@click.option(
    "--last", default=None, metavar="DURATION", help="Show records within duration (e.g. 24h, 7d)."
)
@click.option("--limit", default=50, show_default=True, help="Maximum records to display.")
@click.option(
    "--audit-path", default=None, type=click.Path(), help="Audit log path (overrides config)."
)
@click.pass_context
def audit_show(
    ctx: click.Context,
    agent: str | None,
    tool: str | None,
    last: str | None,
    limit: int,
    audit_path: str | None,
) -> None:
    """Display audit log records with optional filters."""
    log_path: str | None = audit_path
    if log_path is None:
        from xmi2sdc.common.config import load_config

        try:
            config = load_config(ctx.obj["config_path"])
            log_path = config.audit.path
        except (FileNotFoundError, KeyError):
            log_path = ".xmi2sdc-cache/audit.jsonl"

    path = Path(log_path)
    if not path.exists():
        click.echo(f"No audit log found at {path}")
        return

    cutoff: datetime | None = None
    if last is not None:
        try:
            delta = _parse_duration(last)
        except click.BadParameter as exc:
            raise click.ClickException(str(exc)) from exc
        cutoff = datetime.now(timezone.utc) - delta

    records: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if agent and record.get("agent") != agent:
            continue
        if tool and record.get("tool") != tool:
            continue
        if cutoff:
            ts_str = record.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                continue

        records.append(record)

    if not records:
        click.echo("No matching audit records.")
        return

    for rec in records[-limit:]:
        click.echo("---")
        click.echo(f"  timestamp : {rec.get('timestamp', '?')}")
        click.echo(f"  agent     : {rec.get('agent', '?')}")
        click.echo(f"  tool      : {rec.get('tool', '?')}")
        click.echo(f"  duration  : {rec.get('duration_ms', '?')} ms")
        inputs = rec.get("inputs", {})
        if isinstance(inputs, dict):
            click.echo(f"  inputs    : {', '.join(inputs.keys()) or '(none)'}")
        else:
            click.echo(f"  inputs    : {inputs}")


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


@main.command()
@click.argument("xmi_file", type=click.Path(exists=True))
@click.option("--model-name", default=None, help="Name for the model (defaults to filename).")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path.")
@click.pass_context
def convert(ctx: click.Context, xmi_file: str, model_name: str | None, output: str | None) -> None:
    """Parse an XMI file and produce an SDC4 mapping plan."""
    from xmi2sdc.common.config import load_config

    try:
        config = load_config(ctx.obj["config_path"])
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    asyncio.run(_run_convert(config, xmi_file, model_name, output))


async def _run_convert(config, xmi_file: str, model_name: str | None, output: str | None) -> None:
    """Run the parse → map pipeline."""
    from xmi2sdc.toolsets.mapper import SdcMapperToolset
    from xmi2sdc.toolsets.parser import XmiParserToolset

    parser = XmiParserToolset(config=config)
    mapper = SdcMapperToolset(config=config)

    # Parse
    click.echo(f"Parsing {xmi_file}...")
    parsed = await parser.parse_xmi_file(xmi_file, model_name or "")
    class_count = len(parsed.get("top_level_classes", []))
    for pkg in parsed.get("packages", []):
        class_count += len(pkg.get("classes", []))
    click.echo(f"  Dialect: {parsed.get('dialect', '?')}")
    click.echo(f"  Classes: {class_count}")
    click.echo(f"  Enumerations: {len(parsed.get('top_level_enumerations', []))}")
    click.echo(f"  Associations: {len(parsed.get('associations', []))}")

    # Map
    click.echo("Mapping to SDC4 types...")
    mapping = await mapper.map_model(parsed)
    summary = mapping.get("summary", {})
    click.echo(f"  Components: {summary.get('total_components', 0)}")
    click.echo(f"  Clusters: {summary.get('total_clusters', 0)}")
    click.echo(f"  Unmapped: {summary.get('total_unmapped', 0)}")

    # Output
    if output:
        out_path = Path(output)
    else:
        model_name = parsed.get("model_name", "model")
        out_path = Path(config.output.directory) / f"{model_name}_mapping.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_text(json.dumps(mapping, indent=2))
    click.echo(f"Mapping plan written to {out_path}")


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------


@main.command()
@click.argument("mapping_json", type=click.Path(exists=True))
@click.option("--title", required=True, help="Title for the new data model.")
@click.option("--description", default="", help="Description for the data model.")
@click.option(
    "--api-key",
    default=None,
    envvar="SDCSTUDIO_API_KEY",
    help="SDCStudio API key.  [env: SDCSTUDIO_API_KEY]",
)
@click.option(
    "--base-url",
    default=None,
    help="SDCStudio base URL (overrides config).",
)
@click.option(
    "--timeout",
    default=300,
    show_default=True,
    help="Polling timeout in seconds.",
)
@click.pass_context
def assemble(
    ctx: click.Context,
    mapping_json: str,
    title: str,
    description: str,
    api_key: str | None,
    base_url: str | None,
    timeout: int,
) -> None:
    """Submit a mapping plan to the SDCStudio Assembly API."""
    from xmi2sdc.common.config import load_config

    try:
        config = load_config(ctx.obj["config_path"])
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    # CLI overrides
    if api_key:
        config.sdcstudio.api_key = api_key
    if base_url:
        config.sdcstudio.base_url = base_url

    if not config.sdcstudio.api_key:
        raise click.ClickException(
            "API key required. Use --api-key or set SDCSTUDIO_API_KEY env var."
        )

    asyncio.run(_run_assemble(config, mapping_json, title, description, timeout))


async def _run_assemble(
    config,
    mapping_json: str,
    title: str,
    description: str,
    timeout: int,
) -> None:
    """Run the build → assemble → poll pipeline."""
    from xmi2sdc.toolsets.assembler import SdcAssemblerToolset

    mapping_plan = json.loads(Path(mapping_json).read_text())
    assembler = SdcAssemblerToolset(config=config)

    # Build assembly tree
    click.echo(f"Building assembly tree from {mapping_json}...")
    tree = await assembler.build_assembly_tree(mapping_plan)
    cluster_count = len(tree.get("clusters", []))
    comp_count = len(tree.get("components", []))
    click.echo(f"  Root: {tree.get('label', '?')}")
    click.echo(f"  Top-level clusters: {cluster_count}")
    click.echo(f"  Top-level components: {comp_count}")

    # Submit to Assembly API
    click.echo(f"Submitting to {config.sdcstudio.base_url}...")
    result = await assembler.execute_assembly(title, description, tree)
    ct_id = result.get("data_source_ct_id", "")
    status = result.get("status", "")
    click.echo(f"  Status: {status}")
    click.echo(f"  Data source ct_id: {ct_id}")

    # Poll if async
    if status == "processing" and ct_id:
        click.echo(f"Polling for completion (timeout: {timeout}s)...")
        final = await assembler.poll_status(ct_id, timeout_seconds=timeout)
        click.echo(f"  Final status: {final.get('status', '?')}")
        if final.get("analysis_results"):
            click.echo(f"  Analysis: {json.dumps(final['analysis_results'], indent=2)}")
    elif status == "completed":
        click.echo("Assembly completed synchronously.")

    click.echo("Done.")


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


@main.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Display configuration summary and agent inventory."""
    from xmi2sdc.common.config import load_config

    config_path = ctx.obj["config_path"]
    try:
        config = load_config(config_path)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(f"Cannot load config: {exc}") from exc

    click.echo(f"Config      : {config_path}")
    click.echo(f"Cache root  : {config.cache.root}")
    click.echo(f"Output dir  : {config.output.directory}")
    click.echo(f"Audit path  : {config.audit.path}")
    click.echo()

    click.echo(f"Agents ({len(AGENT_REGISTRY)}):")
    tool_counts = {
        "parser": 3,
        "mapper": 3,
        "assembler": 3,
    }
    for name in sorted(AGENT_REGISTRY):
        count = tool_counts.get(name, "?")
        click.echo(f"  {name:16s} {count} tools")
    click.echo()

    click.echo(f"SDCStudio   : {config.sdcstudio.base_url}")
    click.echo(f"API key     : {'configured' if config.sdcstudio.api_key else 'not set'}")


# ---------------------------------------------------------------------------
# validate-config
# ---------------------------------------------------------------------------


@main.command("validate-config")
@click.pass_context
def validate_config(ctx: click.Context) -> None:
    """Validate the configuration file and report errors."""
    from pydantic import ValidationError

    from xmi2sdc.common.config import load_config

    config_path = ctx.obj["config_path"]
    try:
        load_config(config_path)
    except FileNotFoundError:
        click.echo(f"Error: config file not found: {config_path}", err=True)
        sys.exit(1)
    except KeyError as exc:
        click.echo(f"Error: missing environment variable: {exc}", err=True)
        sys.exit(1)
    except ValidationError as exc:
        click.echo(f"Error: config validation failed:\n{exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Config OK: {config_path}")
