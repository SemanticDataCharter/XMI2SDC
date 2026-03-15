"""Parser Agent factory — deterministic XMI parsing."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.toolsets.parser import XmiParserToolset


def create_parser_agent(
    config: XMI2SDCConfig,
    model: str = "ollama/qwen2.5:7b-instruct",
) -> LlmAgent:
    """Create a Parser Agent for XMI file parsing and dialect detection.

    The agent parses XMI files into the universal ParsedXmiModel
    intermediate representation. Deterministic — no LLM calls for
    actual parsing, but the agent can explain results.

    Args:
        config: XMI2SDC configuration.
        model: LLM model identifier.

    Returns:
        Configured LlmAgent with XmiParserToolset.
    """
    return LlmAgent(
        name="parser_agent",
        model=model,
        description=(
            "Parses XMI/UML model files into normalized structures. "
            "Supports generic XMI 2.x, Sparx EA, and MagicDraw formats. "
            "Deterministic parsing — no LLM used for structural extraction."
        ),
        instruction=(
            "You are the XMI Parser Agent. Your job is to parse XMI model files "
            "and produce normalized ParsedXmiModel structures.\n\n"
            "You can:\n"
            "- Parse XMI files from disk (parse_xmi_file)\n"
            "- Parse XMI content from strings (parse_xmi_string)\n"
            "- Detect XMI dialect without full parsing (detect_dialect)\n\n"
            "You CANNOT:\n"
            "- Modify files on disk\n"
            "- Access the SDCStudio API\n"
            "- Make network calls\n\n"
            "When parsing, report the detected dialect, number of classes, "
            "enumerations, and associations found. Flag any elements that "
            "could not be parsed."
        ),
        tools=[XmiParserToolset(config=config)],
    )
