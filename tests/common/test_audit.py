"""Tests for xmi2sdc.common.audit — AuditLogger JSONL output, redaction, levels."""

from __future__ import annotations

import json
import time
from datetime import datetime

from xmi2sdc.common.audit import AuditLogger


class TestAuditLogBasics:
    """Core logging behaviour."""

    def test_log_creates_file_and_parents(self, tmp_path):
        log_path = tmp_path / "deep" / "nested" / "audit.jsonl"
        logger = AuditLogger(log_path)
        logger.log(
            agent="test_agent",
            tool="test_tool",
            inputs={"a": 1},
            outputs="ok",
            start_time=time.monotonic() - 0.05,
        )
        assert log_path.exists()

    def test_log_writes_jsonl_line(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        logger.log(agent="p", tool="t", inputs={}, outputs="x", start_time=time.monotonic())
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert set(record.keys()) == {
            "timestamp",
            "agent",
            "tool",
            "inputs",
            "outputs",
            "duration_ms",
        }

    def test_timestamp_is_utc_iso(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        logger.log(agent="a", tool="t", inputs={}, outputs="", start_time=time.monotonic())
        record = json.loads(log_path.read_text().strip())
        ts = datetime.fromisoformat(record["timestamp"])
        assert ts.tzinfo is not None  # timezone-aware

    def test_duration_ms_positive(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        logger.log(
            agent="a",
            tool="t",
            inputs={},
            outputs="",
            start_time=time.monotonic() - 0.05,
        )
        record = json.loads(log_path.read_text().strip())
        assert record["duration_ms"] > 0

    def test_multiple_logs_produce_multiple_lines(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        for i in range(3):
            logger.log(
                agent="a",
                tool=f"t{i}",
                inputs={},
                outputs="",
                start_time=time.monotonic(),
            )
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 3


class TestRedaction:
    """Sensitive key redaction in inputs."""

    def test_redacts_token_key(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        logger.log(
            agent="a",
            tool="t",
            inputs={"api_token": "secret123", "name": "safe"},
            outputs="",
            start_time=time.monotonic(),
        )
        record = json.loads(log_path.read_text().strip())
        assert record["inputs"]["api_token"] == "***REDACTED***"
        assert record["inputs"]["name"] == "safe"

    def test_redacts_nested_sensitive_keys(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        logger.log(
            agent="a",
            tool="t",
            inputs={"config": {"password": "pw", "host": "localhost"}},
            outputs="",
            start_time=time.monotonic(),
        )
        record = json.loads(log_path.read_text().strip())
        assert record["inputs"]["config"]["password"] == "***REDACTED***"
        assert record["inputs"]["config"]["host"] == "localhost"

    def test_redacts_connection_secret_key(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path)
        logger.log(
            agent="a",
            tool="t",
            inputs={"connection_string": "pg://...", "secret_value": "abc"},
            outputs="",
            start_time=time.monotonic(),
        )
        record = json.loads(log_path.read_text().strip())
        assert record["inputs"]["connection_string"] == "***REDACTED***"
        assert record["inputs"]["secret_value"] == "***REDACTED***"


class TestLogLevels:
    """Standard vs verbose output processing."""

    def test_standard_summarises_list_outputs(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, log_level="standard")
        logger.log(
            agent="a",
            tool="t",
            inputs={},
            outputs=[1, 2, 3],
            start_time=time.monotonic(),
        )
        record = json.loads(log_path.read_text().strip())
        assert record["outputs"] == {"_type": "list", "_count": 3}

    def test_verbose_preserves_list_outputs(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, log_level="verbose")
        logger.log(
            agent="a",
            tool="t",
            inputs={},
            outputs=[1, 2, 3],
            start_time=time.monotonic(),
        )
        record = json.loads(log_path.read_text().strip())
        assert record["outputs"] == [1, 2, 3]
