"""Shared test fixtures for mcpguard tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from mcpguard.policy import PolicyEngine


@pytest.fixture
def tmp_policy_file(tmp_path: Path):
    """Factory fixture: write a policy dict to a temp YAML file, return path."""

    def _make(policy_dict: dict) -> Path:
        path = tmp_path / "test_policy.yaml"
        path.write_text(yaml.dump(policy_dict))
        return path

    return _make


@pytest.fixture
def default_policy_path() -> Path:
    """Path to the default.yaml policy preset."""
    return Path(__file__).parent.parent / "policies" / "default.yaml"


@pytest.fixture
def strict_policy_path() -> Path:
    """Path to the strict.yaml policy preset."""
    return Path(__file__).parent.parent / "policies" / "strict.yaml"


@pytest.fixture
def default_engine(default_policy_path: Path) -> PolicyEngine:
    """PolicyEngine loaded from default.yaml."""
    return PolicyEngine.from_yaml(default_policy_path)
