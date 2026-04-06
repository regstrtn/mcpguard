"""mcpguard.approval — Human approval handler.

Interactive CLI approval for tool calls requiring human review.
Reads from /dev/tty to avoid interfering with MCP stdio pipe.
"""

from __future__ import annotations

import json
import sys
from typing import Any


class ApprovalHandler:
    """Handles interactive approval requests from tool calls."""

    def __init__(self, tty_path: str = "/dev/tty"):
        self.tty_path = tty_path

    async def request_approval(
        self, tool: str, arguments: dict[str, Any], reason: str | None = None
    ) -> bool:
        """Prompt user for approval on /dev/tty.

        Returns True if approved, False otherwise.
        """
        # Print tool call details to stderr
        print(f"\n\033[93m⚠️  mcpguard: Approval Required\033[0m", file=sys.stderr)
        print(f"  Tool:   {tool}", file=sys.stderr)
        if reason:
            print(f"  Reason: {reason}", file=sys.stderr)
        print(f"  Args:   ", file=sys.stderr, end="")
        
        try:
            pretty_args = json.dumps(arguments, indent=2)
            # Indent each line
            indented = "\n".join("    " + l for l in pretty_args.splitlines())
            print(f"\n{indented}", file=sys.stderr)
        except (TypeError, ValueError):
            print(f" {arguments}", file=sys.stderr)

        print(f"\033[94mApprove for execution? (y/N):\033[0m ", file=sys.stderr, end="", flush=True)

        # Read from tty
        try:
            # open with "r" for reading only
            with open(self.tty_path, "r") as tty:
                response = tty.readline().strip().lower()
                approved = response == "y"
                if approved:
                    print("\033[92m✅ Approved\033[0m", file=sys.stderr)
                else:
                    print("\033[91m🚫 Denied\033[0m", file=sys.stderr)
                return approved
        except OSError as e:
            print(f"\n\033[91m❌ Error reading from {self.tty_path}: {e}\033[0m", file=sys.stderr)
            # Fall back to denying to be safe
            return False
