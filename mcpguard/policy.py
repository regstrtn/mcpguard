"""mcpguard.policy — Core policy engine.

Parses YAML policy files and evaluates MCP tool calls against them.
First-match-wins semantics (like iptables). Higher priority evaluated first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from mcpguard.exceptions import PolicyLoadError, PolicyValidationError


class Action(str, Enum):
    """Policy actions."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVE = "APPROVE"
    LOG = "LOG"


@dataclass
class Rule:
    """A single argument inspection rule.

    Specifies conditions on a tool argument's value. All specified conditions
    must match for the rule to trigger (AND logic within a rule).
    """

    argument: str
    pattern: str | None = None
    not_pattern: str | None = None
    prefix: list[str] | None = None
    not_prefix: list[str] | None = None
    contains: list[str] | None = None
    not_contains: list[str] | None = None
    max_length: int | None = None
    message: str | None = None

    def evaluate(self, arguments: dict[str, Any]) -> bool:
        """Check if this rule matches against the given arguments.

        Returns True if the rule MATCHES (i.e., the condition is triggered).
        If the argument is not present in the call, the rule does NOT match.
        """
        value = arguments.get(self.argument)
        if value is None:
            return False

        value_str = str(value)

        # Pattern: regex match anywhere in value → rule matches
        if self.pattern is not None:
            if not re.search(self.pattern, value_str, re.IGNORECASE):
                return False

        # Not-pattern: if regex matches → rule does NOT match
        if self.not_pattern is not None:
            if re.search(self.not_pattern, value_str, re.IGNORECASE):
                return False

        # Prefix: value must start with at least one allowed prefix
        if self.prefix is not None:
            if not any(value_str.startswith(p) for p in self.prefix):
                return False

        # Not-prefix: value must NOT start with any blocked prefix
        if self.not_prefix is not None:
            if any(value_str.startswith(p) for p in self.not_prefix):
                return False

        # Contains: value must contain at least one of these
        if self.contains is not None:
            if not any(c.lower() in value_str.lower() for c in self.contains):
                return False

        # Not-contains: value must NOT contain any of these
        if self.not_contains is not None:
            if any(c.lower() in value_str.lower() for c in self.not_contains):
                return False

        # Max length: value must not exceed this length
        if self.max_length is not None:
            if len(value_str) > self.max_length:
                return False

        return True


@dataclass
class Policy:
    """A single named policy with tool matching and argument rules."""

    name: str
    tools: list[str]
    action: Action
    description: str = ""
    rules: list[Rule] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True

    def matches_tool(self, tool_name: str) -> bool:
        """Check if this policy applies to the given tool name.

        Each entry in self.tools is treated as a regex pattern.
        """
        for pattern in self.tools:
            if re.fullmatch(pattern, tool_name, re.IGNORECASE):
                return True
        return False

    def evaluate_rules(self, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        """Evaluate all argument rules against given arguments.

        All rules must match for the policy to trigger (AND logic).
        Returns (matched: bool, message: str | None).
        """
        if not self.rules:
            # No rules = unconditional match on tool name alone
            return True, self.description or None

        for rule in self.rules:
            if not rule.evaluate(arguments):
                return False, None

        # All rules matched — find the first rule with a custom message
        message = next(
            (r.message for r in self.rules if r.message),
            self.description or None,
        )
        return True, message


@dataclass
class PolicyResult:
    """Result of evaluating a tool call against all policies."""

    action: Action
    matched_policy: str | None
    reason: str | None
    tool_name: str
    arguments: dict[str, Any]


class PolicyEngine:
    """Evaluates tool calls against a collection of policies.

    Policies are sorted by priority (descending). First match wins.
    If no policy matches, the default_action is returned.
    """

    def __init__(
        self,
        policies: list[Policy],
        default_action: Action = Action.ALLOW,
    ):
        self.policies = sorted(policies, key=lambda p: p.priority, reverse=True)
        self.default_action = default_action

    @classmethod
    def from_yaml(cls, path: str | Path) -> PolicyEngine:
        """Load policies from a YAML file.

        Raises PolicyLoadError if the file can't be read.
        Raises PolicyValidationError if the YAML structure is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise PolicyLoadError(f"Policy file not found: {path}")

        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise PolicyLoadError(f"Invalid YAML in {path}: {e}") from e

        if not isinstance(raw, dict):
            raise PolicyValidationError(f"Policy file must be a YAML mapping, got {type(raw)}")

        default_action_str = raw.get("default_action", "ALLOW")
        try:
            default_action = Action(default_action_str.upper())
        except ValueError:
            raise PolicyValidationError(
                f"Invalid default_action '{default_action_str}'. "
                f"Must be one of: {[a.value for a in Action]}"
            )

        raw_policies = raw.get("policies", [])
        if not isinstance(raw_policies, list):
            raise PolicyValidationError("'policies' must be a list")

        policies = []
        for i, rp in enumerate(raw_policies):
            try:
                policies.append(_parse_policy(rp))
            except (KeyError, ValueError, TypeError) as e:
                raise PolicyValidationError(f"Error in policy #{i + 1}: {e}") from e

        return cls(policies=policies, default_action=default_action)

    def evaluate(self, tool_name: str, arguments: dict[str, Any]) -> PolicyResult:
        """Evaluate a tool call against all policies.

        Algorithm:
        1. Iterate policies in priority order (highest first)
        2. Skip disabled policies
        3. Check if tool_name matches policy's tool patterns
        4. If yes, evaluate argument rules
        5. If all rules match → return that policy's action
        6. If no policy matches → return default_action
        """
        for policy in self.policies:
            if not policy.enabled:
                continue

            if not policy.matches_tool(tool_name):
                continue

            matched, reason = policy.evaluate_rules(arguments)
            if matched:
                return PolicyResult(
                    action=policy.action,
                    matched_policy=policy.name,
                    reason=reason,
                    tool_name=tool_name,
                    arguments=arguments,
                )

        return PolicyResult(
            action=self.default_action,
            matched_policy=None,
            reason=f"No policy matched. Default action: {self.default_action.value}",
            tool_name=tool_name,
            arguments=arguments,
        )

    def validate(self) -> list[str]:
        """Validate all policies and return a list of warnings (empty = valid).

        Checks:
        - Duplicate policy names
        - Invalid regex patterns in tools/rules
        """
        warnings: list[str] = []
        seen_names: set[str] = set()

        for policy in self.policies:
            # Duplicate names
            if policy.name in seen_names:
                warnings.append(f"Duplicate policy name: '{policy.name}'")
            seen_names.add(policy.name)

            # Validate tool patterns are valid regex
            for pattern in policy.tools:
                try:
                    re.compile(pattern)
                except re.error as e:
                    warnings.append(
                        f"Policy '{policy.name}': invalid tool regex '{pattern}': {e}"
                    )

            # Validate rule patterns
            for rule in policy.rules:
                if rule.pattern:
                    try:
                        re.compile(rule.pattern)
                    except re.error as e:
                        warnings.append(
                            f"Policy '{policy.name}': invalid rule pattern "
                            f"'{rule.pattern}': {e}"
                        )
                if rule.not_pattern:
                    try:
                        re.compile(rule.not_pattern)
                    except re.error as e:
                        warnings.append(
                            f"Policy '{policy.name}': invalid rule not_pattern "
                            f"'{rule.not_pattern}': {e}"
                        )




        return warnings


def _parse_policy(raw: dict[str, Any]) -> Policy:
    """Parse a single policy dict from YAML into a Policy object."""
    name = raw["name"]
    tools = raw["tools"]
    action_str = raw["action"]

    if not isinstance(tools, list) or not tools:
        raise ValueError(f"Policy '{name}': 'tools' must be a non-empty list")

    try:
        action = Action(action_str.upper())
    except ValueError:
        raise ValueError(
            f"Policy '{name}': invalid action '{action_str}'. "
            f"Must be one of: {[a.value for a in Action]}"
        )

    rules = []
    for raw_rule in raw.get("rules", []):
        rules.append(
            Rule(
                argument=raw_rule["argument"],
                pattern=raw_rule.get("pattern"),
                not_pattern=raw_rule.get("not_pattern"),
                prefix=raw_rule.get("prefix"),
                not_prefix=raw_rule.get("not_prefix"),
                contains=raw_rule.get("contains"),
                not_contains=raw_rule.get("not_contains"),
                max_length=raw_rule.get("max_length"),
                message=raw_rule.get("message"),
            )
        )

    return Policy(
        name=name,
        description=raw.get("description", ""),
        tools=tools,
        action=action,
        rules=rules,
        priority=raw.get("priority", 0),
        enabled=raw.get("enabled", True),
    )
