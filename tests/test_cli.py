"""Tests for xmi2sdc.cli — Click commands via CliRunner."""

from __future__ import annotations

import json
import time
from pathlib import Path

from click.testing import CliRunner

from xmi2sdc.cli import main
from xmi2sdc.common.audit import AuditLogger

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CONFIG = str(FIXTURES_DIR / "sample_config.yaml")
GENERIC_XMI = str(FIXTURES_DIR / "xmi_samples" / "generic_xmi21.xmi")


class TestInfoCommand:
    """xmi2sdc info."""

    def test_exit_zero(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", SAMPLE_CONFIG, "info"])
        assert result.exit_code == 0

    def test_shows_agent_count(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", SAMPLE_CONFIG, "info"])
        assert "Agents (3)" in result.output

    def test_shows_tool_counts(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", SAMPLE_CONFIG, "info"])
        assert "3 tools" in result.output


class TestValidateConfigCommand:
    """xmi2sdc validate-config."""

    def test_valid_config_ok(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", SAMPLE_CONFIG, "validate-config"])
        assert result.exit_code == 0
        assert "Config OK" in result.output

    def test_missing_file_error(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", "/nonexistent/path.yaml", "validate-config"])
        assert result.exit_code != 0

    def test_missing_env_var_error(self, tmp_path):
        cfg = tmp_path / "bad.yaml"
        cfg.write_text('sdcstudio:\n  api_key: "${NEVER_SET_XYZ_ABC_123}"\n')
        runner = CliRunner()
        result = runner.invoke(main, ["--config", str(cfg), "validate-config"])
        assert result.exit_code != 0


class TestConvertCommand:
    """xmi2sdc convert."""

    def test_exit_zero_with_output(self, tmp_path):
        out_file = tmp_path / "out.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--config",
                SAMPLE_CONFIG,
                "convert",
                GENERIC_XMI,
                "-o",
                str(out_file),
            ],
        )
        assert result.exit_code == 0
        assert out_file.exists()

    def test_output_contains_dialect(self, tmp_path):
        out_file = tmp_path / "out.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--config",
                SAMPLE_CONFIG,
                "convert",
                GENERIC_XMI,
                "-o",
                str(out_file),
            ],
        )
        assert "Dialect:" in result.output

    def test_output_is_valid_json(self, tmp_path):
        out_file = tmp_path / "out.json"
        runner = CliRunner()
        runner.invoke(
            main,
            [
                "--config",
                SAMPLE_CONFIG,
                "convert",
                GENERIC_XMI,
                "-o",
                str(out_file),
            ],
        )
        data = json.loads(out_file.read_text())
        assert "components" in data


class TestAuditShowCommand:
    """xmi2sdc audit show."""

    def test_nonexistent_audit_path(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--config",
                SAMPLE_CONFIG,
                "audit",
                "show",
                "--audit-path",
                str(tmp_path / "nope.jsonl"),
            ],
        )
        assert result.exit_code == 0
        assert "No audit log found" in result.output

    def test_populated_audit_shows_records(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        logger.log(
            agent="parser_agent",
            tool="parse_xmi_file",
            inputs={"file": "test.xmi"},
            outputs="ok",
            start_time=time.monotonic() - 0.01,
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--config",
                SAMPLE_CONFIG,
                "audit",
                "show",
                "--audit-path",
                str(log_path),
            ],
        )
        assert "parser_agent" in result.output
        assert "parse_xmi_file" in result.output

    def test_agent_filter(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        for agent_name in ("parser_agent", "mapper_agent"):
            logger.log(
                agent=agent_name,
                tool="some_tool",
                inputs={},
                outputs="",
                start_time=time.monotonic(),
            )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--config",
                SAMPLE_CONFIG,
                "audit",
                "show",
                "--audit-path",
                str(log_path),
                "--agent",
                "parser_agent",
            ],
        )
        assert "parser_agent" in result.output
        assert "mapper_agent" not in result.output
