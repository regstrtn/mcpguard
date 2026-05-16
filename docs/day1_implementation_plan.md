# Day 1: Scaffold + Policy Engine Core

Create the initial repository structure, dependencies, and implement core YAML policy parsing and evaluation.

## User Review Required

> [!NOTE]
> This is a retroactive plan for work already completed in the initial scaffold setup.

## Proposed Changes

### [Component Name] Policy Engine Core

#### [NEW] [policy.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/policy.py)
- Implement `Policy`, `Rule`, `PolicyResult` dataclasses.
- Implement `PolicyEngine.from_yaml()` for parsing.
- Implement `PolicyEngine.evaluate()` with support for absolute string equivalence and matching.

#### [NEW] [cli.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/cli.py)
- `mcpguard validate` command to check syntax.
- `mcpguard test` command for offline evaluation.

## Verification Plan

### Automated Tests
- Run `pytest tests/test_policy.py` verifying parsing and absolute equality rules match correctly.
- Verify that `mcpguard validate` handles correct/incorrect cases correctly.
