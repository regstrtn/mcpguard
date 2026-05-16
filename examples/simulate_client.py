#!/usr/bin/env python3
"""Simulate an MCP client session through mcpguard.

Starts mcpguard proxy with `cat` as a loopback server, sends a
safe and a malicious tool call, and prints the results.
"""

import json
import subprocess
import sys
import time


def simulate_mcp_session():
    print("🚀 [Simulating MCP Client Session]")
    print("---")

    # Start mcpguard proxy wrapping `cat` as a loopback echo server
    process = subprocess.Popen(
        [sys.executable, "-m", "mcpguard", "run", "--config", "mcpguard.yaml", "--", "cat"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Give the proxy a moment to start
    time.sleep(0.5)

    # 1. Send an initialize handshake (passes through untouched)
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TestRunner", "version": "1.0"},
        },
    }

    # 2. Send a malicious tool call (should be DENIED)
    malicious_call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "read_file",
            "arguments": {"path": "/home/user/.ssh/id_rsa"},
        },
    }

    # 3. Send a safe tool call (should be forwarded)
    safe_call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "read_file",
            "arguments": {"path": "/tmp/notes.txt"},
        },
    }

    print("📤 Sending 'initialize' handshake...")
    process.stdin.write(json.dumps(init_msg) + "\n")
    process.stdin.flush()
    time.sleep(0.3)

    print("📤 Sending malicious tool call (reading ~/.ssh/id_rsa)...")
    process.stdin.write(json.dumps(malicious_call) + "\n")
    process.stdin.flush()
    time.sleep(0.3)

    print("📤 Sending safe tool call (reading /tmp/notes.txt)...")
    process.stdin.write(json.dumps(safe_call) + "\n")
    process.stdin.flush()
    time.sleep(0.3)

    print("\n📩 [Responses]:")
    print("---")

    # Read available responses
    for _ in range(3):
        output = process.stdout.readline()
        if not output:
            break
        parsed = json.loads(output.strip())
        req_id = parsed.get("id")
        if "error" in parsed:
            print(f"  ❌ Request #{req_id}: BLOCKED — {parsed['error']['message']}")
        else:
            print(f"  ✅ Request #{req_id}: Forwarded")

    process.terminate()
    print("\n🏁 Simulation complete. Check mcpguard_audit.jsonl for the audit trail.")


if __name__ == "__main__":
    simulate_mcp_session()
