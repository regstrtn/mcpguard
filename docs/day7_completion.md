# Day 7 Completion: FastMCP Middleware + Stats Dashboard

FastMCP middleware integration and audit stats dashboard with rich tables and HTML export are complete.

## Work Done

### FastMCP Middleware

-   Implemented `McpGuardMiddleware` class in `mcpguard/middleware.py` extending FastMCP's `Middleware` base class.
-   Implements `on_call_tool()` interceptor that evaluates tool calls against `PolicyEngine` before forwarding.
-   Handles DENY (raises `McpGuardDenied`), APPROVE (interactive TTY prompt), and ALLOW (pass-through) actions.
-   Implemented `wrap_fastmcp()` helper that auto-detects `add_middleware` support or falls back to monkeypatching `call_tool`.
-   `from_yaml()` classmethod for easy one-line initialization from YAML policy files.
-   Fixed `McpGuardDenied` constructor calls to match the `(tool, policy, reason)` signature.

### Stats Dashboard

-   Implemented `mcpguard stats --log <path>` CLI command with rich table output showing:
    -   By Action breakdown (ALLOW, DENY, LOG counts)
    -   By Tool breakdown (sorted by count)
    -   By Policy breakdown (which policies triggered most)
    -   Hash chain verification status
-   Implemented `generate_html_dashboard()` in `mcpguard/dashboard.py` with Chart.js pie/bar charts and responsive CSS.
-   Added `--html` flag to export stats as standalone HTML dashboard.

### Bug Fixes

-   Created missing `strict.yaml` policy preset (referenced by tests/CLI but not previously existing).
-   Fixed `McpGuardDenied` constructor calls in middleware to use `(tool, policy, reason)` instead of single string.
-   Created `mcpguard/__main__.py` so `python -m mcpguard` works correctly.

## Verification Run

### Automated Tests
-   4 middleware tests pass: allow flow, deny flow, add_middleware path, monkeypatch fallback.
-   All 92 tests pass across test_policy.py, test_middleware.py, test_e2e.py, test_audit.py.

### Manual Verification
-   `mcpguard stats --log mcpguard_audit.jsonl` displays formatted tables correctly.
-   `mcpguard validate --config policies/strict.yaml` validates the new strict preset.
