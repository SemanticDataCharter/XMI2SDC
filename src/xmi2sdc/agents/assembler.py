"""Assembler Agent factory — submits mapping plans to SDCStudio Assembly API."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.toolsets.assembler import SdcAssemblerToolset


def create_assembler_agent(
    config: XMI2SDCConfig,
    model: str = "ollama/qwen2.5:7b-instruct",
) -> LlmAgent:
    """Create an Assembler Agent for submitting mapping plans to SDCStudio.

    The agent transforms flat mapping plans into nested Assembly API trees,
    submits them, and polls until processing completes.

    Args:
        config: XMI2SDC configuration.
        model: LLM model identifier.

    Returns:
        Configured LlmAgent with SdcAssemblerToolset.
    """
    return LlmAgent(
        name="assembler_agent",
        model=model,
        description=(
            "Submits SDC4 mapping plans to the SDCStudio Assembly API. "
            "Transforms flat component/cluster lists into nested assembly trees, "
            "executes the API call, and polls until processing completes."
        ),
        instruction=(
            "You are the SDC Assembler Agent. Your job is to submit mapping "
            "plans to the SDCStudio Assembly API to create SDC4 data models.\n\n"
            "You can:\n"
            "- Build an assembly tree from a mapping plan (build_assembly_tree)\n"
            "- Submit the tree to the Assembly API (execute_assembly)\n"
            "- Poll for completion status (poll_status)\n\n"
            "Workflow:\n"
            "1. Call build_assembly_tree with the mapping plan\n"
            "2. Call execute_assembly with a title, description, and the tree\n"
            "3. If status is 'processing', call poll_status with the ct_id\n"
            "4. Report the final result to the user\n\n"
            "All components are new (mint mode). The API returns HTTP 202 for "
            "async processing. Poll every 5 seconds until completion."
        ),
        tools=[SdcAssemblerToolset(config=config)],
    )
