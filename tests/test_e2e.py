import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

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
            # Simple echo server with tool calling support
            if req.get("method") == "tools/call":
                name = req["params"]["name"]
                args = req["params"]["arguments"]
                
                # Echo tool execution result
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
                # Generic pass-through echo
                res = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "result": {"echo": req}
                }
            print(json.dumps(res), flush=True)
        except Exception as e:
            # error trace back to stderr
            print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
"""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(script_content)
        path = f.name
    
    os.chmod(path, 0o755)  # Make executable
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

@pytest.mark.asyncio
async def test_e2e_proxy_allows_and_blocks(mock_upstream_server, policy_file):
    audit_log = tempfile.NamedTemporaryFile(delete=False).name
    
    # Start mcpguard run command in background using subprocess
    # We pipe stdin & stdout to interact with it just like an MCP client
    process = await asyncio.create_subprocess_exec(
        "python3", "-m", "mcpguard.cli", "run",
        "--config", policy_file,
        "--log", audit_log,
        "--", "python3", mock_upstream_server,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # 1. Send an allowed tool call
    allowed_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "shell",
            "arguments": {"command": "ls -la"}
        }
    }
    
    process.stdin.write((json.dumps(allowed_req) + "\n").encode())
    await process.stdin.drain()
    
    line = await process.stdout.readline()
    res = json.loads(line.decode().strip())
    
    assert res.get("id") == 1
    assert "result" in res
    assert "Executed shell" in res["result"]["content"][0]["text"]

    # 2. Send a denied tool call
    denied_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "shell",
            "arguments": {"command": "rm -rf /"}
        }
    }
    
    process.stdin.write((json.dumps(denied_req) + "\n").encode())
    await process.stdin.drain()
    
    line = await process.stdout.readline()
    res = json.loads(line.decode().strip())
    
    assert res.get("id") == 2
    assert "error" in res
    assert "Blocked by policy" in res["error"]["message"]

    # 3. Verify non-tool message passes through
    init_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "initialize",
        "params": {}
    }
    process.stdin.write((json.dumps(init_req) + "\n").encode())
    await process.stdin.drain()
    
    line = await process.stdout.readline()
    res = json.loads(line.decode().strip())
    assert res.get("id") == 3
    assert "result" in res
    assert "echo" in res["result"]

    # Cleanup
    process.kill()
    await process.wait()
    
    # Verify audit log exists and contains both ALLOW and DENY
    audit_content = Path(audit_log).read_text()
    assert '"action": "ALLOW"' in audit_content
    assert '"action": "DENY"' in audit_content
    
    try:
        os.unlink(audit_log)
    except FileNotFoundError:
        pass
