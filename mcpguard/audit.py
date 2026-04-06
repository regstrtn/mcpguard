"""mcpguard.audit — Structured JSON-lines audit logging.

Every policy decision is logged as a single JSON line, enabling
grep, jq, and programmatic analysis of agent behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    """A single audit log entry."""

    timestamp: str
    session_id: str
    tool: str
    arguments: dict[str, Any]
    action: str  # ALLOW, DENY, APPROVE_YES, APPROVE_NO, LOG
    matched_policy: str | None = None
    reason: str | None = None
    response_time_ms: float | None = None
    # DPR chain: hash of previous entry for tamper-evidence
    prev_hash: str | None = None
    entry_hash: str | None = None


class AuditLogger:
    """Append-only JSON-lines audit logger with optional DPR hash chain.

    Each log line is a JSON object. If hash_chain=True, each entry includes
    a SHA256 hash of the previous entry, making the log tamper-evident.
    """

    def __init__(
        self,
        path: str | Path = "mcpguard_audit.jsonl",
        also_stderr: bool = True,
        hash_chain: bool = True,
    ):
        self.path = Path(path)
        self.also_stderr = also_stderr
        self.hash_chain = hash_chain
        self.session_id = uuid.uuid4().hex[:12]
        self._prev_hash: str | None = None

        # If file exists and has entries, read the last hash for chain continuity
        if self.hash_chain and self.path.exists():
            self._prev_hash = self._read_last_hash()

    def log(
        self,
        tool: str,
        arguments: dict[str, Any],
        action: str,
        matched_policy: str | None = None,
        reason: str | None = None,
        response_time_ms: float | None = None,
    ) -> AuditEvent:
        """Create and write an audit event. Returns the event."""
        event = AuditEvent(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            session_id=self.session_id,
            tool=tool,
            arguments=self._redact_sensitive(arguments),
            action=action,
            matched_policy=matched_policy,
            reason=reason,
            response_time_ms=response_time_ms,
            prev_hash=self._prev_hash,
        )

        # Compute entry hash for DPR chain
        if self.hash_chain:
            event_dict = asdict(event)
            event_dict.pop("entry_hash", None)
            event.entry_hash = hashlib.sha256(
                json.dumps(event_dict, sort_keys=True).encode()
            ).hexdigest()[:16]
            self._prev_hash = event.entry_hash

        # Write to file
        line = json.dumps(asdict(event), default=str)
        with open(self.path, "a") as f:
            f.write(line + "\n")

        # Also print to stderr for visibility
        if self.also_stderr:
            icon = {"ALLOW": "✅", "DENY": "🚫", "LOG": "📝"}.get(
                action, "❓"
            )
            print(
                f"{icon} [{action}] {tool}({self._summarize_args(arguments)})"
                + (f" — {reason}" if reason else ""),
                file=sys.stderr,
            )

        return event

    def get_stats(self) -> dict[str, Any]:
        """Read the audit log and compute summary statistics."""
        if not self.path.exists():
            return {"total": 0, "by_action": {}, "by_tool": {}, "by_policy": {}}

        events = []
        for line in self.path.read_text().splitlines():
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        by_action: dict[str, int] = {}
        by_tool: dict[str, int] = {}
        by_policy: dict[str, int] = {}

        for e in events:
            action = e.get("action", "UNKNOWN")
            by_action[action] = by_action.get(action, 0) + 1
            tool = e.get("tool", "unknown")
            by_tool[tool] = by_tool.get(tool, 0) + 1
            policy = e.get("matched_policy") or "(none)"
            by_policy[policy] = by_policy.get(policy, 0) + 1

        return {
            "total": len(events),
            "by_action": by_action,
            "by_tool": by_tool,
            "by_policy": by_policy,
        }

    def verify_chain(self) -> tuple[bool, int]:
        """Verify the hash chain integrity.

        Returns (is_valid, num_entries_checked).
        """
        if not self.path.exists():
            return True, 0

        entries = []
        for line in self.path.read_text().splitlines():
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    return False, len(entries)

        prev_hash = None
        for i, entry in enumerate(entries):
            if entry.get("prev_hash") != prev_hash:
                return False, i

            # Recompute hash
            check = dict(entry)
            stored_hash = check.pop("entry_hash", None)
            computed = hashlib.sha256(
                json.dumps(check, sort_keys=True).encode()
            ).hexdigest()[:16]
            if stored_hash != computed:
                return False, i

            prev_hash = stored_hash

        return True, len(entries)

    def _read_last_hash(self) -> str | None:
        """Read the entry_hash from the last line of the log file."""
        try:
            lines = self.path.read_text().strip().splitlines()
            if lines:
                last = json.loads(lines[-1])
                return last.get("entry_hash")
        except (json.JSONDecodeError, OSError):
            pass
        return None

    @staticmethod
    def _redact_sensitive(args: dict[str, Any]) -> dict[str, Any]:
        """Redact obviously sensitive argument values."""
        sensitive_keys = {"password", "secret", "token", "api_key", "apikey", "credential"}
        redacted = {}
        for k, v in args.items():
            if k.lower() in sensitive_keys:
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = v
        return redacted

    @staticmethod
    def _summarize_args(args: dict[str, Any], max_len: int = 60) -> str:
        """Create a short summary of arguments for stderr output."""
        parts = []
        for k, v in args.items():
            v_str = str(v)
            if len(v_str) > max_len:
                v_str = v_str[: max_len - 3] + "..."
            parts.append(f"{k}={v_str!r}")
        return ", ".join(parts)
