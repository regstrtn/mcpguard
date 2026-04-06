"""Tests for mcpguard.policy — the core policy engine.

Tests cover: YAML loading, tool matching, rule evaluation, priority ordering,
edge cases, and validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcpguard.exceptions import PolicyLoadError, PolicyValidationError
from mcpguard.policy import Action, Policy, PolicyEngine, Rule


# ── YAML Loading ──────────────────────────────────────────────────────


class TestYamlLoading:
    """Tests for PolicyEngine.from_yaml()."""

    def test_load_valid_policy(self, tmp_policy_file):
        path = tmp_policy_file({
            "version": "1",
            "default_action": "ALLOW",
            "policies": [
                {
                    "name": "test-policy",
                    "tools": ["run_command"],
                    "action": "DENY",
                    "rules": [{"argument": "command", "pattern": "rm -rf"}],
                }
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        assert len(engine.policies) == 1
        assert engine.policies[0].name == "test-policy"

    def test_load_missing_file(self):
        with pytest.raises(PolicyLoadError, match="not found"):
            PolicyEngine.from_yaml("/nonexistent/path.yaml")

    def test_load_invalid_yaml(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("{{{{not yaml")
        with pytest.raises(PolicyLoadError, match="Invalid YAML"):
            PolicyEngine.from_yaml(path)

    def test_load_non_mapping(self, tmp_path):
        path = tmp_path / "list.yaml"
        path.write_text("- item1\n- item2")
        with pytest.raises(PolicyValidationError, match="mapping"):
            PolicyEngine.from_yaml(path)

    def test_load_invalid_default_action(self, tmp_policy_file):
        path = tmp_policy_file({
            "default_action": "EXPLODE",
            "policies": [],
        })
        with pytest.raises(PolicyValidationError, match="Invalid default_action"):
            PolicyEngine.from_yaml(path)

    def test_load_invalid_policy_action(self, tmp_policy_file):
        path = tmp_policy_file({
            "policies": [{"name": "bad", "tools": ["x"], "action": "NUKE"}],
        })
        with pytest.raises(PolicyValidationError, match="invalid action"):
            PolicyEngine.from_yaml(path)

    def test_load_default_action_defaults_to_allow(self, tmp_policy_file):
        path = tmp_policy_file({"policies": []})
        engine = PolicyEngine.from_yaml(path)
        assert engine.default_action == Action.ALLOW

    def test_load_default_policy_preset(self, default_policy_path):
        engine = PolicyEngine.from_yaml(default_policy_path)
        assert len(engine.policies) > 0

    def test_load_strict_policy_preset(self, strict_policy_path):
        engine = PolicyEngine.from_yaml(strict_policy_path)
        assert engine.default_action == Action.DENY


# ── Tool Matching ─────────────────────────────────────────────────────


class TestToolMatching:
    """Tests for Policy.matches_tool()."""

    def test_exact_match(self):
        policy = Policy(name="test", tools=["run_command"], action=Action.DENY)
        assert policy.matches_tool("run_command")

    def test_no_match(self):
        policy = Policy(name="test", tools=["run_command"], action=Action.DENY)
        assert not policy.matches_tool("read_file")

    def test_regex_wildcard(self):
        policy = Policy(name="test", tools=["shell_.*"], action=Action.DENY)
        assert policy.matches_tool("shell_exec")
        assert policy.matches_tool("shell_run")
        assert not policy.matches_tool("run_command")

    def test_multiple_tool_patterns(self):
        policy = Policy(
            name="test", tools=["run_command", "shell_.*"], action=Action.DENY
        )
        assert policy.matches_tool("run_command")
        assert policy.matches_tool("shell_exec")
        assert not policy.matches_tool("read_file")

    def test_case_insensitive(self):
        policy = Policy(name="test", tools=["Run_Command"], action=Action.DENY)
        assert policy.matches_tool("run_command")
        assert policy.matches_tool("RUN_COMMAND")

    def test_catch_all(self):
        policy = Policy(name="test", tools=[".*"], action=Action.LOG)
        assert policy.matches_tool("anything")
        assert policy.matches_tool("run_command")


# ── Rule Evaluation ───────────────────────────────────────────────────


class TestRuleEvaluation:
    """Tests for Rule.evaluate()."""

    def test_pattern_match(self):
        rule = Rule(argument="command", pattern="rm -rf")
        assert rule.evaluate({"command": "rm -rf /"})

    def test_pattern_no_match(self):
        rule = Rule(argument="command", pattern="rm -rf")
        assert not rule.evaluate({"command": "ls -la"})

    def test_pattern_case_insensitive(self):
        rule = Rule(argument="command", pattern="DELETE")
        assert rule.evaluate({"command": "delete everything"})

    def test_not_pattern_blocks(self):
        """not_pattern: if regex MATCHES, rule does NOT match."""
        rule = Rule(argument="command", not_pattern="^ls ")
        assert not rule.evaluate({"command": "ls -la"})

    def test_not_pattern_allows(self):
        rule = Rule(argument="command", not_pattern="^ls ")
        assert rule.evaluate({"command": "rm -rf /"})

    def test_prefix_match(self):
        rule = Rule(argument="path", prefix=["/home/user/project/"])
        assert rule.evaluate({"path": "/home/user/project/main.py"})

    def test_prefix_no_match(self):
        rule = Rule(argument="path", prefix=["/home/user/project/"])
        assert not rule.evaluate({"path": "/etc/passwd"})

    def test_not_prefix_blocks(self):
        rule = Rule(argument="path", not_prefix=["/etc/", "/root/"])
        assert not rule.evaluate({"path": "/etc/shadow"})

    def test_not_prefix_allows(self):
        rule = Rule(argument="path", not_prefix=["/etc/", "/root/"])
        assert rule.evaluate({"path": "/home/user/file.txt"})

    def test_contains_match(self):
        rule = Rule(argument="command", contains=["sudo", "su "])
        assert rule.evaluate({"command": "sudo rm -rf /"})

    def test_contains_no_match(self):
        rule = Rule(argument="command", contains=["sudo"])
        assert not rule.evaluate({"command": "ls -la"})

    def test_contains_case_insensitive(self):
        rule = Rule(argument="command", contains=["SUDO"])
        assert rule.evaluate({"command": "sudo whoami"})

    def test_not_contains_blocks(self):
        rule = Rule(argument="body", not_contains=["password", "secret"])
        assert not rule.evaluate({"body": "my password is 123"})

    def test_not_contains_allows(self):
        rule = Rule(argument="body", not_contains=["password"])
        assert rule.evaluate({"body": "hello world"})

    def test_max_length_ok(self):
        rule = Rule(argument="command", max_length=100)
        assert rule.evaluate({"command": "ls"})

    def test_max_length_exceeded(self):
        rule = Rule(argument="command", max_length=10)
        assert not rule.evaluate({"command": "a" * 11})

    def test_missing_argument_does_not_match(self):
        """If the argument isn't in the call, the rule doesn't match."""
        rule = Rule(argument="command", pattern="rm -rf")
        assert not rule.evaluate({"path": "/some/file"})

    def test_empty_arguments(self):
        rule = Rule(argument="command", pattern="rm -rf")
        assert not rule.evaluate({})

    def test_multiple_conditions_all_must_match(self):
        """AND logic: all conditions in a single rule must match."""
        rule = Rule(argument="command", pattern="curl", not_contains=["localhost"])
        # Has "curl" but also has "localhost" → not_contains fails
        assert not rule.evaluate({"command": "curl http://localhost"})
        # Has "curl" and no "localhost" → both conditions pass
        assert rule.evaluate({"command": "curl http://example.com"})


# ── Policy Engine Evaluation ──────────────────────────────────────────


class TestPolicyEngineEvaluation:
    """Tests for PolicyEngine.evaluate()."""

    def test_deny_destructive_command(self, default_engine):
        result = default_engine.evaluate("run_command", {"command": "rm -rf /"})
        assert result.action == Action.DENY
        assert result.matched_policy == "block-destructive-shell"

    def test_allow_safe_command(self, default_engine):
        result = default_engine.evaluate("run_command", {"command": "ls -la"})
        # Should either be ALLOW, or match LOG policy
        assert result.action in (Action.ALLOW, Action.LOG)

    def test_deny_sensitive_file_read(self, default_engine):
        result = default_engine.evaluate("read_file", {"path": "/home/user/.ssh/id_rsa"})
        assert result.action == Action.DENY

    def test_allow_normal_file_read(self, default_engine):
        result = default_engine.evaluate("read_file", {"path": "/home/user/project/main.py"})
        assert result.action == Action.ALLOW

    def test_deny_internal_network(self, default_engine):
        result = default_engine.evaluate(
            "http_request", {"url": "http://192.168.1.1/admin"}
        )
        assert result.action == Action.DENY

    def test_deny_exfiltration(self, default_engine):
        result = default_engine.evaluate(
            "http_request", {"url": "https://webhook.site/abc123"}
        )
        assert result.action == Action.DENY

    def test_no_policy_match_returns_default(self, tmp_policy_file):
        path = tmp_policy_file({
            "default_action": "DENY",
            "policies": [
                {"name": "allow-reads", "tools": ["read_file"], "action": "ALLOW"}
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        # This tool has no matching policy
        result = engine.evaluate("some_unknown_tool", {"arg": "val"})
        assert result.action == Action.DENY
        assert result.matched_policy is None

    def test_default_action_allow(self, tmp_policy_file):
        path = tmp_policy_file({"default_action": "ALLOW", "policies": []})
        engine = PolicyEngine.from_yaml(path)
        result = engine.evaluate("anything", {})
        assert result.action == Action.ALLOW

    def test_disabled_policy_skipped(self, tmp_policy_file):
        path = tmp_policy_file({
            "policies": [
                {
                    "name": "disabled-deny",
                    "tools": ["run_command"],
                    "action": "DENY",
                    "enabled": False,
                    "rules": [{"argument": "command", "pattern": "rm"}],
                }
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        result = engine.evaluate("run_command", {"command": "rm -rf /"})
        assert result.action == Action.ALLOW  # default, since policy is disabled

    def test_priority_ordering(self, tmp_policy_file):
        """Higher priority policy should win over lower priority."""
        path = tmp_policy_file({
            "policies": [
                {
                    "name": "low-deny",
                    "tools": ["run_command"],
                    "action": "DENY",
                    "priority": 1,
                },
                {
                    "name": "high-allow",
                    "tools": ["run_command"],
                    "action": "ALLOW",
                    "priority": 100,
                },
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        result = engine.evaluate("run_command", {"command": "anything"})
        assert result.action == Action.ALLOW
        assert result.matched_policy == "high-allow"

    def test_first_match_wins(self, tmp_policy_file):
        """Same priority: first in list wins."""
        path = tmp_policy_file({
            "policies": [
                {"name": "first", "tools": ["run_command"], "action": "DENY", "priority": 10},
                {"name": "second", "tools": ["run_command"], "action": "ALLOW", "priority": 10},
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        result = engine.evaluate("run_command", {})
        assert result.matched_policy == "first"

    def test_rules_must_all_match(self, tmp_policy_file):
        """Policy with rules: ALL rules must match for the policy to trigger."""
        path = tmp_policy_file({
            "policies": [
                {
                    "name": "multi-rule",
                    "tools": ["http_request"],
                    "action": "DENY",
                    "rules": [
                        {"argument": "url", "pattern": "internal"},
                        {"argument": "method", "pattern": "POST"},
                    ],
                }
            ],
        })
        engine = PolicyEngine.from_yaml(path)

        # Only one rule matches → policy doesn't trigger
        result = engine.evaluate("http_request", {"url": "http://internal", "method": "GET"})
        assert result.action == Action.ALLOW

        # Both rules match → policy triggers
        result = engine.evaluate(
            "http_request", {"url": "http://internal", "method": "POST"}
        )
        assert result.action == Action.DENY

    def test_no_rules_means_unconditional(self, tmp_policy_file):
        """Policy without rules: matches on tool name alone."""
        path = tmp_policy_file({
            "policies": [
                {"name": "block-all-shell", "tools": ["run_command"], "action": "DENY"}
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        result = engine.evaluate("run_command", {"command": "ls"})
        assert result.action == Action.DENY

    def test_result_includes_tool_and_args(self, default_engine):
        result = default_engine.evaluate("run_command", {"command": "rm -rf /"})
        assert result.tool_name == "run_command"
        assert result.arguments == {"command": "rm -rf /"}

    def test_result_includes_reason(self, default_engine):
        result = default_engine.evaluate("run_command", {"command": "rm -rf /"})
        assert result.reason is not None
        assert len(result.reason) > 0


# ── Validation ────────────────────────────────────────────────────────


class TestValidation:
    """Tests for PolicyEngine.validate()."""

    def test_valid_engine_no_warnings(self, default_engine):
        warnings = default_engine.validate()
        assert warnings == []

    def test_duplicate_names(self, tmp_policy_file):
        path = tmp_policy_file({
            "policies": [
                {"name": "dupe", "tools": ["x"], "action": "DENY"},
                {"name": "dupe", "tools": ["y"], "action": "ALLOW"},
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        warnings = engine.validate()
        assert any("Duplicate" in w for w in warnings)

    def test_invalid_regex(self, tmp_policy_file):
        path = tmp_policy_file({
            "policies": [
                {"name": "bad-regex", "tools": ["[invalid"], "action": "DENY"}
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        warnings = engine.validate()
        assert any("invalid tool regex" in w for w in warnings)


# ── Edge Cases ────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_policies_list(self, tmp_policy_file):
        path = tmp_policy_file({"policies": []})
        engine = PolicyEngine.from_yaml(path)
        result = engine.evaluate("anything", {"arg": "val"})
        assert result.action == Action.ALLOW

    def test_argument_value_is_not_string(self, tmp_policy_file):
        """Non-string argument values should be converted to str for matching."""
        path = tmp_policy_file({
            "policies": [
                {
                    "name": "block-big-numbers",
                    "tools": ["transfer"],
                    "action": "DENY",
                    "rules": [{"argument": "amount", "pattern": "^999"}],
                }
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        result = engine.evaluate("transfer", {"amount": 99999})
        assert result.action == Action.DENY

    def test_special_regex_characters_in_value(self):
        """Regex special chars in the VALUE shouldn't break matching."""
        rule = Rule(argument="path", pattern=r"\.env$")
        assert rule.evaluate({"path": "/project/.env"})
        assert not rule.evaluate({"path": "/project/env"})

    def test_very_long_argument_value(self, tmp_policy_file):
        path = tmp_policy_file({
            "policies": [
                {
                    "name": "length-limit",
                    "tools": ["run_command"],
                    "action": "DENY",
                    "rules": [{"argument": "command", "max_length": 100}],
                }
            ],
        })
        engine = PolicyEngine.from_yaml(path)
        # Short command: rule matches (length OK) → DENY
        result = engine.evaluate("run_command", {"command": "ls"})
        assert result.action == Action.DENY
        # Long command: rule doesn't match (length exceeded) → ALLOW (default)
        result = engine.evaluate("run_command", {"command": "x" * 200})
        assert result.action == Action.ALLOW
