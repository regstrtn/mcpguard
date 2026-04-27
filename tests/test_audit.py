"""Tests for mcpguard.audit — audit logger and hash chain."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from mcpguard.audit import AuditEvent, AuditLogger


@pytest.fixture
def audit_log_path():
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestAuditLogger:
    """Tests for AuditLogger basic operations."""

    def test_log_creates_file(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        logger.log(tool="test", arguments={"key": "val"}, action="ALLOW")
        assert Path(audit_log_path).exists()

    def test_log_writes_json_line(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        logger.log(tool="test_tool", arguments={"cmd": "ls"}, action="ALLOW")

        lines = Path(audit_log_path).read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["tool"] == "test_tool"
        assert entry["action"] == "ALLOW"
        assert entry["arguments"]["cmd"] == "ls"

    def test_log_appends_multiple_entries(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        logger.log(tool="a", arguments={}, action="ALLOW")
        logger.log(tool="b", arguments={}, action="DENY")
        logger.log(tool="c", arguments={}, action="LOG")

        lines = Path(audit_log_path).read_text().strip().splitlines()
        assert len(lines) == 3

    def test_log_returns_audit_event(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        event = logger.log(tool="test", arguments={}, action="ALLOW")
        assert isinstance(event, AuditEvent)
        assert event.tool == "test"
        assert event.action == "ALLOW"

    def test_log_includes_session_id(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        e1 = logger.log(tool="a", arguments={}, action="ALLOW")
        e2 = logger.log(tool="b", arguments={}, action="DENY")
        assert e1.session_id == e2.session_id
        assert len(e1.session_id) == 12

    def test_log_includes_timestamp(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        event = logger.log(tool="test", arguments={}, action="ALLOW")
        assert event.timestamp is not None
        assert "T" in event.timestamp  # ISO 8601

    def test_log_with_matched_policy(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        event = logger.log(
            tool="shell", arguments={"cmd": "rm"}, action="DENY",
            matched_policy="block-rm", reason="Destructive"
        )
        assert event.matched_policy == "block-rm"
        assert event.reason == "Destructive"


class TestSensitiveRedaction:
    """Tests for sensitive argument redaction."""

    def test_redact_password(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        event = logger.log(
            tool="login", arguments={"password": "secret123"}, action="ALLOW"
        )
        assert event.arguments["password"] == "***REDACTED***"

    def test_redact_api_key(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        event = logger.log(
            tool="api", arguments={"api_key": "sk-abc123"}, action="ALLOW"
        )
        assert event.arguments["api_key"] == "***REDACTED***"

    def test_redact_token(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        event = logger.log(
            tool="auth", arguments={"token": "xyz", "name": "test"}, action="ALLOW"
        )
        assert event.arguments["token"] == "***REDACTED***"
        assert event.arguments["name"] == "test"  # Non-sensitive preserved

    def test_no_redaction_for_safe_keys(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        event = logger.log(
            tool="cmd", arguments={"command": "ls", "path": "/tmp"}, action="ALLOW"
        )
        assert event.arguments["command"] == "ls"
        assert event.arguments["path"] == "/tmp"


class TestHashChain:
    """Tests for DPR hash chain integrity."""

    def test_hash_chain_entries_have_hashes(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        e1 = logger.log(tool="a", arguments={}, action="ALLOW")
        e2 = logger.log(tool="b", arguments={}, action="DENY")
        assert e1.entry_hash is not None
        assert e2.entry_hash is not None
        assert e1.prev_hash is None  # First entry
        assert e2.prev_hash == e1.entry_hash  # Linked

    def test_verify_chain_valid(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        for i in range(5):
            logger.log(tool=f"tool_{i}", arguments={}, action="ALLOW")
        is_valid, count = logger.verify_chain()
        assert is_valid
        assert count == 5

    def test_verify_chain_detects_tampering(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        logger.log(tool="a", arguments={}, action="ALLOW")
        logger.log(tool="b", arguments={}, action="DENY")
        logger.log(tool="c", arguments={}, action="LOG")

        # Tamper with the middle entry
        lines = Path(audit_log_path).read_text().strip().splitlines()
        entry = json.loads(lines[1])
        entry["action"] = "ALLOW"  # Change DENY to ALLOW
        lines[1] = json.dumps(entry)
        Path(audit_log_path).write_text("\n".join(lines) + "\n")

        is_valid, at = logger.verify_chain()
        assert not is_valid

    def test_verify_empty_log(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        is_valid, count = logger.verify_chain()
        assert is_valid
        assert count == 0

    def test_chain_continuity_across_sessions(self, audit_log_path):
        """New logger instance should continue the hash chain."""
        logger1 = AuditLogger(path=audit_log_path, also_stderr=False)
        logger1.log(tool="a", arguments={}, action="ALLOW")

        # New instance should pick up the last hash
        logger2 = AuditLogger(path=audit_log_path, also_stderr=False)
        logger2.log(tool="b", arguments={}, action="DENY")

        is_valid, count = logger2.verify_chain()
        assert is_valid
        assert count == 2

    def test_no_hash_chain_when_disabled(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False, hash_chain=False)
        event = logger.log(tool="test", arguments={}, action="ALLOW")
        assert event.entry_hash is None
        assert event.prev_hash is None


class TestGetStats:
    """Tests for audit log statistics."""

    def test_empty_stats(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        stats = logger.get_stats()
        assert stats["total"] == 0

    def test_stats_by_action(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        logger.log(tool="a", arguments={}, action="ALLOW")
        logger.log(tool="b", arguments={}, action="ALLOW")
        logger.log(tool="c", arguments={}, action="DENY")

        stats = logger.get_stats()
        assert stats["total"] == 3
        assert stats["by_action"]["ALLOW"] == 2
        assert stats["by_action"]["DENY"] == 1

    def test_stats_by_tool(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        logger.log(tool="shell", arguments={}, action="ALLOW")
        logger.log(tool="shell", arguments={}, action="DENY")
        logger.log(tool="read_file", arguments={}, action="ALLOW")

        stats = logger.get_stats()
        assert stats["by_tool"]["shell"] == 2
        assert stats["by_tool"]["read_file"] == 1

    def test_stats_by_policy(self, audit_log_path):
        logger = AuditLogger(path=audit_log_path, also_stderr=False)
        logger.log(tool="a", arguments={}, action="DENY", matched_policy="block-x")
        logger.log(tool="b", arguments={}, action="DENY", matched_policy="block-x")
        logger.log(tool="c", arguments={}, action="ALLOW")

        stats = logger.get_stats()
        assert stats["by_policy"]["block-x"] == 2
        assert stats["by_policy"]["(none)"] == 1
