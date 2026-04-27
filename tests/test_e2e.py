"""End-to-end tests for mcpguard.

Tests the full proxy pipeline: client → mcpguard → upstream server → client.
Also tests the audit log output and CLI commands.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mcpguard.audit import AuditLogger
from mcpguard.policy import Action, PolicyEngine


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_upstream_server():
    """Create a temporary executable that acts as an MCP server over stdio."""
    script_content = """#!/usr/bin/env python3
import sys
import json

def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            if req.get("method") == "tools/call":
                name = req["params"]["name"]
                args = req["params"]["arguments"]
                res = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Executed {name} with {json.dumps(args)}"}
                        ]
                    }
                }
            else:
                res = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "result": {"echo": req}
                }
            print(json.dumps(res), flush=True)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".py") as f:
        f.write(script_content)
        path = f.name

    os.chmod(path, 0o755)
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def policy_file():
    content = """---
default_action: ALLOW
policies:
  - name: block-rm
    description: Block rm commands
    tools: ["shell"]
    action: DENY
    rules:
      - argument: "command"
        contains: ["rm"]
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as f:
        f.write(content)
        path = f.name
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


# ── Proxy integration tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_proxy_blocks_denied_call(mock_upstream_server, policy_file):
    """Test that the proxy correctly blocks a denied tool call."""
    from mcpguard.proxy import McpProxy

    audit_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    engine = PolicyEngine.from_yaml(policy_file)
    audit_logger = AuditLogger(path=audit_log, also_stderr=False)

    proxy = McpProxy(
        upstream_command=[sys.executable, mock_upstream_server],
        policy_engine=engine,
        audit_logger=audit_logger,
    )

    # Start the upstream process manually
    proxy._process = await asyncio.create_subprocess_exec(
        *proxy.upstream_command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Test denied call
    raw = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "shell", "arguments": {"command": "rm -rf /"}}
    })

    result = await proxy._handle_client_message(raw)
    assert result is not None
    response = json.loads(result)
    assert response["id"] == 1
    assert "error" in response
    assert "Blocked by policy" in response["error"]["message"]

    # Cleanup
    proxy._process.terminate()
    await proxy._process.wait()
    os.unlink(audit_log)


@pytest.mark.asyncio
async def test_proxy_allows_safe_call(mock_upstream_server, policy_file):
    """Test that the proxy forwards allowed tool calls."""
    from mcpguard.proxy import McpProxy

    audit_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    engine = PolicyEngine.from_yaml(policy_file)
    audit_logger = AuditLogger(path=audit_log, also_stderr=False)

    proxy = McpProxy(
        upstream_command=[sys.executable, mock_upstream_server],
        policy_engine=engine,
        audit_logger=audit_logger,
    )

    proxy._process = await asyncio.create_subprocess_exec(
        *proxy.upstream_command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Test allowed call (no "rm" in command)
    raw = json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "shell", "arguments": {"command": "ls -la"}}
    })

    result = await proxy._handle_client_message(raw)
    assert result is None  # None means forward to upstream

    # Cleanup
    proxy._process.terminate()
    await proxy._process.wait()
    os.unlink(audit_log)


@pytest.mark.asyncio
async def test_proxy_passes_non_tool_messages(mock_upstream_server, policy_file):
    """Non tools/call messages should pass through unchanged."""
    from mcpguard.proxy import McpProxy

    audit_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    engine = PolicyEngine.from_yaml(policy_file)
    audit_logger = AuditLogger(path=audit_log, also_stderr=False)

    proxy = McpProxy(
        upstream_command=[sys.executable, mock_upstream_server],
        policy_engine=engine,
        audit_logger=audit_logger,
    )

    proxy._process = await asyncio.create_subprocess_exec(
        *proxy.upstream_command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Test non-tool message
    raw = json.dumps({
        "jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}
    })

    result = await proxy._handle_client_message(raw)
    assert result is None  # Should forward

    # Test tools/list
    raw = json.dumps({
        "jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}
    })
    result = await proxy._handle_client_message(raw)
    assert result is None

    # Test invalid JSON
    result = await proxy._handle_client_message("not json at all")
    assert result is None

    # Cleanup
    proxy._process.terminate()
    await proxy._process.wait()
    os.unlink(audit_log)


@pytest.mark.asyncio
async def test_proxy_upstream_communication(mock_upstream_server, policy_file):
    """Test full upstream communication: forward + receive response."""
    from mcpguard.proxy import McpProxy

    audit_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    engine = PolicyEngine.from_yaml(policy_file)
    audit_logger = AuditLogger(path=audit_log, also_stderr=False)

    proxy = McpProxy(
        upstream_command=[sys.executable, mock_upstream_server],
        policy_engine=engine,
        audit_logger=audit_logger,
    )

    proxy._process = await asyncio.create_subprocess_exec(
        *proxy.upstream_command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Send an allowed call directly to upstream
    req = json.dumps({
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "shell", "arguments": {"command": "echo hello"}}
    })

    # Verify handle returns None (= forward)
    result = await proxy._handle_client_message(req)
    assert result is None

    # Actually write to upstream and read response
    proxy._process.stdin.write((req + "\n").encode())
    await proxy._process.stdin.drain()

    line = await asyncio.wait_for(proxy._process.stdout.readline(), timeout=5.0)
    response = json.loads(line.decode().strip())
    assert response["id"] == 5
    assert "result" in response
    assert "Executed shell" in response["result"]["content"][0]["text"]

    # Cleanup
    proxy._process.terminate()
    await proxy._process.wait()
    os.unlink(audit_log)


# ── Audit log E2E tests ──────────────────────────────────────────────


def test_audit_log_records_allow_and_deny(policy_file):
    """Verify audit log captures both ALLOW and DENY events."""
    audit_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    engine = PolicyEngine.from_yaml(policy_file)
    audit_logger = AuditLogger(path=audit_log, also_stderr=False)

    # Simulate ALLOW
    result = engine.evaluate("shell", {"command": "ls -la"})
    audit_logger.log(
        tool="shell", arguments={"command": "ls -la"},
        action=result.action.value,
        matched_policy=result.matched_policy,
        reason=result.reason,
    )

    # Simulate DENY
    result = engine.evaluate("shell", {"command": "rm -rf /"})
    audit_logger.log(
        tool="shell", arguments={"command": "rm -rf /"},
        action=result.action.value,
        matched_policy=result.matched_policy,
        reason=result.reason,
    )

    # Verify log contents
    content = Path(audit_log).read_text()
    assert '"action": "ALLOW"' in content
    assert '"action": "DENY"' in content

    # Verify hash chain
    is_valid, count = audit_logger.verify_chain()
    assert is_valid
    assert count == 2

    os.unlink(audit_log)


def test_audit_stats_computation(policy_file):
    """Verify get_stats returns correct counts."""
    audit_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    engine = PolicyEngine.from_yaml(policy_file)
    audit_logger = AuditLogger(path=audit_log, also_stderr=False)

    # Log several events
    for _ in range(3):
        audit_logger.log(tool="shell", arguments={"command": "ls"}, action="ALLOW")
    for _ in range(2):
        audit_logger.log(tool="shell", arguments={"command": "rm"}, action="DENY",
                         matched_policy="block-rm")
    audit_logger.log(tool="read_file", arguments={"path": "/tmp/x"}, action="LOG")

    stats = audit_logger.get_stats()
    assert stats["total"] == 6
    assert stats["by_action"]["ALLOW"] == 3
    assert stats["by_action"]["DENY"] == 2
    assert stats["by_action"]["LOG"] == 1
    assert stats["by_tool"]["shell"] == 5
    assert stats["by_tool"]["read_file"] == 1

    os.unlink(audit_log)


# ── CLI E2E tests ────────────────────────────────────────────────────


def test_cli_validate(policy_file):
    """Test mcpguard validate command."""
    project_root = str(Path(__file__).parent.parent)
    result = subprocess.run(
        [sys.executable, "-m", "mcpguard", "validate", "--config", policy_file],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": project_root},
    )
    assert result.returncode == 0


def test_cli_test_deny():
    """Test mcpguard test command with a deny result."""
    project_root = str(Path(__file__).parent.parent)
    policy_path = str(Path(__file__).parent.parent / "mcpguard.yaml")
    result = subprocess.run(
        [sys.executable, "-m", "mcpguard", "test",
         "--config", policy_path,
         "--tool", "run_command",
         "--args", '{"command": "rm -rf /"}'],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": project_root},
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "DENY" in combined


def test_cli_test_allow():
    """Test mcpguard test command with an allow result."""
    project_root = str(Path(__file__).parent.parent)
    policy_path = str(Path(__file__).parent.parent / "mcpguard.yaml")
    result = subprocess.run(
        [sys.executable, "-m", "mcpguard", "test",
         "--config", policy_path,
         "--tool", "run_command",
         "--args", '{"command": "ls -la"}'],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": project_root},
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    # Should be either ALLOW or LOG (log-shell-commands catches it)
    assert ("ALLOW" in combined or "LOG" in combined)


def test_cli_stats():
    """Test mcpguard stats command."""
    project_root = str(Path(__file__).parent.parent)
    audit_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name

    # Create some audit entries
    logger = AuditLogger(path=audit_log, also_stderr=False)
    logger.log(tool="test_tool", arguments={}, action="ALLOW")
    logger.log(tool="test_tool", arguments={}, action="DENY", matched_policy="test-policy")

    result = subprocess.run(
        [sys.executable, "-m", "mcpguard", "stats", "--log", audit_log],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": project_root},
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "2 events" in combined

    os.unlink(audit_log)


def test_cli_init():
    """Test mcpguard init creates a config file."""
    project_root = str(Path(__file__).parent.parent)
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "mcpguard.yaml")
        result = subprocess.run(
            [sys.executable, "-m", "mcpguard", "init", "--output", output],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": project_root},
            input="y\n",  # Confirm overwrite if prompted
        )
        # Check the file was created (or the command ran without crashing)
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "Created" in combined or os.path.exists(output)


# ── Shadow mode tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shadow_mode_logs_but_does_not_block(mock_upstream_server, policy_file):
    """Shadow mode should log DENY as SHADOW_DENY but forward the call."""
    from mcpguard.proxy import McpProxy

    audit_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl").name
    engine = PolicyEngine.from_yaml(policy_file)
    audit_logger = AuditLogger(path=audit_log, also_stderr=False)

    proxy = McpProxy(
        upstream_command=[sys.executable, mock_upstream_server],
        policy_engine=engine,
        audit_logger=audit_logger,
        shadow_mode=True,
    )

    proxy._process = await asyncio.create_subprocess_exec(
        *proxy.upstream_command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # This call would be DENIED in normal mode
    raw = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "shell", "arguments": {"command": "rm -rf /"}}
    })

    result = await proxy._handle_client_message(raw)
    # Shadow mode: should NOT block (return None = forward)
    assert result is None

    # But it should be logged as SHADOW_DENY
    content = Path(audit_log).read_text()
    assert "SHADOW_DENY" in content

    # Cleanup
    proxy._process.terminate()
    await proxy._process.wait()
    os.unlink(audit_log)
