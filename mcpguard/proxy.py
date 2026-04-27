"""mcpguard.proxy — MCP stdio proxy.

Sits between an MCP client and server, intercepting tools/call messages
and evaluating them against the policy engine.

Full implementation comes in Day 3-4. This is the skeleton.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from typing import Any

from mcpguard.approval import ApprovalHandler
from mcpguard.audit import AuditLogger
from mcpguard.policy import Action, PolicyEngine


class McpProxy:
    """Transparent MCP proxy that intercepts tools/call messages."""

    def __init__(
        self,
        upstream_command: list[str],
        policy_engine: PolicyEngine,
        audit_logger: AuditLogger,
        shadow_mode: bool = False,
    ):
        self.upstream_command = upstream_command
        self.policy_engine = policy_engine
        self.audit_logger = audit_logger
        self.shadow_mode = shadow_mode
        self._process: asyncio.subprocess.Process | None = None
        self.approval_handler = ApprovalHandler()
        # Regex patterns for secret detection in responses
        self._secret_patterns = [
            (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
            (r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private Key"),
            (r"ghp_[A-Za-z0-9_]{36}", "GitHub Token"),
            (r"sk-[A-Za-z0-9]{48}", "OpenAI API Key"),
            (r"xox[bpras]-[A-Za-z0-9-]+", "Slack Token"),
            (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "JWT Token"),
        ]

    async def start(self) -> None:
        """Start the upstream server and begin proxying."""
        # Start upstream MCP server as subprocess
        self._process = await asyncio.create_subprocess_exec(
            *self.upstream_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Run bidirectional proxy
        try:
            await asyncio.gather(
                self._client_to_server(),
                self._server_to_client(),
                self._forward_stderr(),
            )
        except asyncio.CancelledError:
            pass
        finally:
            if self._process and self._process.returncode is None:
                self._process.terminate()

    async def _client_to_server(self) -> None:
        """Read from stdin (client), evaluate, forward to upstream."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        while True:
            line = await reader.readline()
            if not line:
                break

            raw = line.decode("utf-8").strip()
            if not raw:
                continue

            result = await self._handle_client_message(raw)
            if result is None:
                # Forward to upstream
                assert self._process and self._process.stdin
                self._process.stdin.write(line)
                await self._process.stdin.drain()
            else:
                # Send response back to client (blocked call)
                sys.stdout.buffer.write((result + "\n").encode())
                sys.stdout.buffer.flush()

    async def _server_to_client(self) -> None:
        """Read from upstream stdout, forward to client stdout."""
        assert self._process and self._process.stdout
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            # Scan response for leaked secrets
            self._scan_response_for_secrets(line.decode("utf-8", errors="replace"))
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()

    async def _forward_stderr(self) -> None:
        """Forward upstream stderr to our stderr."""
        assert self._process and self._process.stderr
        while True:
            line = await self._process.stderr.readline()
            if not line:
                break
            sys.stderr.buffer.write(line)
            sys.stderr.buffer.flush()

    async def _handle_client_message(self, raw: str) -> str | None:
        """Process a client message.

        Returns None if the message should be forwarded.
        Returns a JSON-RPC error string if the message is blocked.
        """
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return None  # Not valid JSON, forward as-is

        # Only intercept tools/call
        if msg.get("method") != "tools/call":
            return None

        params = msg.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        request_id = msg.get("id")

        result = self.policy_engine.evaluate(tool_name, arguments)

        # Log the decision
        self.audit_logger.log(
            tool=tool_name,
            arguments=arguments,
            action=result.action.value,
            matched_policy=result.matched_policy,
            reason=result.reason,
        )

        if result.action == Action.DENY:
            if self.shadow_mode:
                # Shadow mode: log as SHADOW_DENY but forward anyway
                self.audit_logger.log(
                    tool=tool_name,
                    arguments=arguments,
                    action="SHADOW_DENY",
                    matched_policy=result.matched_policy,
                    reason=result.reason,
                )
                return None
            return json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32600,
                    "message": (
                        f"mcpguard: Blocked by policy '{result.matched_policy}': "
                        f"{result.reason}"
                    ),
                },
            })

        if result.action == Action.APPROVE:
            if self.shadow_mode:
                # Shadow mode: log as SHADOW_APPROVE but forward anyway
                self.audit_logger.log(
                    tool=tool_name,
                    arguments=arguments,
                    action="SHADOW_APPROVE",
                    matched_policy=result.matched_policy,
                    reason=result.reason,
                )
                return None
            approved = await self.approval_handler.request_approval(
                tool=tool_name, arguments=arguments, reason=result.reason
            )
            # Re-log the approval action
            self.audit_logger.log(
                tool=tool_name,
                arguments=arguments,
                action="APPROVE_YES" if approved else "APPROVE_NO",
                matched_policy=result.matched_policy,
                reason=result.reason,
            )
            if not approved:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32600,
                        "message": f"mcpguard: Human Denied '{result.matched_policy}'",
                    },
                })
            # If approved, return None to forward to upstream
            return None

        # ALLOW or LOG — forward to upstream
        return None

    def _scan_response_for_secrets(self, raw: str) -> None:
        """Scan a response string for leaked secrets and log warnings."""
        for pattern, label in self._secret_patterns:
            if re.search(pattern, raw):
                self.audit_logger.log(
                    tool="_response_scan",
                    arguments={"detected": label},
                    action="DENY",
                    matched_policy="response-secret-scan",
                    reason=f"Potential {label} detected in upstream response",
                )
