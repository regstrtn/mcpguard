# Day 2: Policy Engine Completeness

Add advanced operators to match rule arguments and integrate priority sorting & offline evaluation.

## User Review Required

> [!NOTE]
> This is a plan for work already implemented and verified as complete in `mcpguard/policy.py` and `mcpguard/cli.py`.

## Proposed Changes

### [Component Name] Policy Engine Completeness

#### [NEW] [policy.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/policy.py)
-   Add support for `prefix`, `not_prefix`, `contains`, `not_contains`, and `max_length` constraints in the `Rule.evaluate()` method.
-   Add prioritisation to sorting list in `PolicyEngine.__init__()` and iterate highest priority first in `evaluate`.
-   Add support for the `enabled` field. Skip disabled policies in `evaluate()`.

#### [NEW] [cli.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/cli.py)
-   Implement the `mcpguard test --tool X --args '{}'` command to test single evaluations offline offline.

## Verification Plan

### Automated Tests
-   Verify updated pattern matching passes all 15 edge case unit tests in `test_policy.py`.
-   Run offline test command: `mcpguard test` to confirm evaluation triggers.

### Manual Verification
-   Run `mcpguard test --config policies/default.yaml --tool run_command --args '{"command": "rm -f file"}'` or similar commands offline.
