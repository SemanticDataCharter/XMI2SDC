"""Tests for agent factory functions — wiring, defaults, tools."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from xmi2sdc.agents.assembler import create_assembler_agent
from xmi2sdc.agents.mapper import create_mapper_agent
from xmi2sdc.agents.parser import create_parser_agent
from xmi2sdc.toolsets.assembler import SdcAssemblerToolset
from xmi2sdc.toolsets.mapper import SdcMapperToolset
from xmi2sdc.toolsets.parser import XmiParserToolset

DEFAULT_MODEL = "ollama/qwen2.5:7b-instruct"
CUSTOM_MODEL = "vertex_ai/gemini-2.5-flash"


class TestParserAgentFactory:
    """create_parser_agent wiring."""

    def test_returns_llm_agent(self, default_config):
        agent = create_parser_agent(default_config)
        assert isinstance(agent, LlmAgent)

    def test_agent_name(self, default_config):
        agent = create_parser_agent(default_config)
        assert agent.name == "parser_agent"

    def test_default_model(self, default_config):
        agent = create_parser_agent(default_config)
        assert agent.model == DEFAULT_MODEL

    def test_custom_model(self, default_config):
        agent = create_parser_agent(default_config, model=CUSTOM_MODEL)
        assert agent.model == CUSTOM_MODEL

    def test_instruction_non_empty(self, default_config):
        agent = create_parser_agent(default_config)
        assert agent.instruction and len(agent.instruction) > 10

    def test_toolset_type(self, default_config):
        agent = create_parser_agent(default_config)
        assert any(isinstance(t, XmiParserToolset) for t in agent.tools)


class TestMapperAgentFactory:
    """create_mapper_agent wiring."""

    def test_returns_llm_agent(self, default_config):
        agent = create_mapper_agent(default_config)
        assert isinstance(agent, LlmAgent)

    def test_agent_name(self, default_config):
        agent = create_mapper_agent(default_config)
        assert agent.name == "mapper_agent"

    def test_default_model(self, default_config):
        agent = create_mapper_agent(default_config)
        assert agent.model == DEFAULT_MODEL

    def test_custom_model(self, default_config):
        agent = create_mapper_agent(default_config, model=CUSTOM_MODEL)
        assert agent.model == CUSTOM_MODEL

    def test_instruction_non_empty(self, default_config):
        agent = create_mapper_agent(default_config)
        assert agent.instruction and len(agent.instruction) > 10

    def test_toolset_type(self, default_config):
        agent = create_mapper_agent(default_config)
        assert any(isinstance(t, SdcMapperToolset) for t in agent.tools)


class TestAssemblerAgentFactory:
    """create_assembler_agent wiring."""

    def test_returns_llm_agent(self, default_config):
        agent = create_assembler_agent(default_config)
        assert isinstance(agent, LlmAgent)

    def test_agent_name(self, default_config):
        agent = create_assembler_agent(default_config)
        assert agent.name == "assembler_agent"

    def test_default_model(self, default_config):
        agent = create_assembler_agent(default_config)
        assert agent.model == DEFAULT_MODEL

    def test_custom_model(self, default_config):
        agent = create_assembler_agent(default_config, model=CUSTOM_MODEL)
        assert agent.model == CUSTOM_MODEL

    def test_instruction_non_empty(self, default_config):
        agent = create_assembler_agent(default_config)
        assert agent.instruction and len(agent.instruction) > 10

    def test_toolset_type(self, default_config):
        agent = create_assembler_agent(default_config)
        assert any(isinstance(t, SdcAssemblerToolset) for t in agent.tools)
