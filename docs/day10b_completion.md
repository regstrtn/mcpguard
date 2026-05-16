# Day 10b Completion: Shadow Mode + Policy Consolidation + DX Polish

Post-Day 10 improvements: shadow mode, policy consolidation, and developer experience polish.

## Work Done

### Single Policy File (Policy Consolidation)

- Created `mcpguard.yaml` at project root as the **single source of truth** for policies.
- Permissive-leaning default: only blocks genuinely dangerous operations (filesystem destruction, credential theft, data exfiltration). Everything else is logged, not blocked.
- `mcpguard init` now copies the root `mcpguard.yaml` instead of choosing from presets.
- Removed `--preset` flag from `init` command — no more decision fatigue.
- Kept `policies/` directory as an examples gallery (default.yaml, strict.yaml, permissive.yaml remain as reference templates).

### Shadow Mode

- Added `--shadow` flag to `mcpguard run` CLI command.
- In shadow mode: all tool calls are forwarded to upstream, nothing is blocked.
- DENY decisions are logged as `SHADOW_DENY` instead of blocking.
- APPROVE decisions are logged as `SHADOW_APPROVE` instead of prompting.
- Use case: deploy mcpguard in front of your MCP server to see what *would* be blocked before switching to enforcement mode.

### CONTRIBUTING.md

- Created standard contributing guide covering:
  - Development setup (clone, venv, install)
  - Coding principles
  - Project structure overview
  - How to add new rule types and CLI commands
  - Style and testing guidelines

### README.md (Updated)

- Added shields.io badges: MIT License, Python 3.10+, Tests, PyPI.
- Added shadow mode documentation and examples.
- Simplified policy story to single file.
- Added CONTRIBUTING.md link.

## Test Results

```
93 passed in 1.51s
```

New test: `test_shadow_mode_logs_but_does_not_block` — verifies that shadow mode forwards denied calls and logs them as `SHADOW_DENY`.

## Build Spec Updates

Added 6 new decision log entries:
- Single policy file, Shadow mode, Permissive-leaning default, Policy packs (skipped), CONTRIBUTING.md, Test coverage update.
