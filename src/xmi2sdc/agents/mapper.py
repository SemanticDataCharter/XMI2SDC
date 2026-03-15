"""Mapper Agent factory — UML-to-SDC4 type mapping."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.toolsets.mapper import SdcMapperToolset


def create_mapper_agent(
    config: XMI2SDCConfig,
    model: str = "ollama/qwen2.5:7b-instruct",
) -> LlmAgent:
    """Create a Mapper Agent for UML-to-SDC4 type mapping.

    The agent applies deterministic type mapping rules to convert
    parsed UML classes and attributes into SDC4 component specifications.

    Args:
        config: XMI2SDC configuration.
        model: LLM model identifier.

    Returns:
        Configured LlmAgent with SdcMapperToolset.
    """
    return LlmAgent(
        name="mapper_agent",
        model=model,
        description=(
            "Maps UML model elements to SDC4 data types. "
            "Applies deterministic type mapping rules for primitives, "
            "enumerations, and associations. Produces JSON mapping plans."
        ),
        instruction=(
            "You are the SDC Mapper Agent. Your job is to convert UML model "
            "elements into SDC4 component specifications.\n\n"
            "You can:\n"
            "- Map an entire parsed model to an SDC4 mapping plan (map_model)\n"
            "- Map a single UML class (map_class)\n"
            "- Look up the SDC4 type for a UML type name (map_type)\n\n"
            "Type mapping rules:\n"
            "- Boolean → XdBoolean\n"
            "- Non-negative Integer → XdCount\n"
            "- Signed Integer → XdQuantity (integer restriction)\n"
            "- Real/Float/Double → XdQuantity\n"
            "- String → XdString\n"
            "- Enumeration → XdString with enumerations\n"
            "- Date/DateTime/Time → XdTemporal\n"
            "- Class (composite) → Cluster\n\n"
            "Report unmapped types and suggest SDC4 alternatives. "
            "Always include a mapping summary with counts."
        ),
        tools=[SdcMapperToolset(config=config)],
    )
