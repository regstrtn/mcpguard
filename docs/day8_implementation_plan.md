# Day 8-9: End-to-End Testing + Response Scanning

Comprehensive E2E testing, response scanning for leaked secrets, and missing test coverage for audit, proxy, and CLI modules.

## Proposed Changes

### E2E Test Suite

#### [NEW] [test_e2e.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/tests/test_e2e.py)
-   Rewrite E2E tests to use direct proxy integration (instantiate `McpProxy` directly) rather than brittle subprocess invocation.
-   Test proxy blocking denied calls, forwarding allowed calls, passing non-tool messages, and full upstream communication.
-   Add audit log E2E tests verifying both ALLOW and DENY events are recorded with correct hash chain.
-   Add CLI command tests: `validate`, `test`, `stats`, `init` via subprocess.

### Audit Test Suite

#### [NEW] [test_audit.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/tests/test_audit.py)
-   Test basic logging: file creation, JSON-line format, multiple entries, session IDs, timestamps.
-   Test sensitive value redaction: password, api_key, token fields redacted while safe keys preserved.
-   Test DPR hash chain: entries linked, verify_chain() works, tampering detected, cross-session continuity, disable option.
-   Test get_stats(): empty log, by_action, by_tool, by_policy breakdowns.

### Response Scanning (Day 4 TODO)

#### [MODIFY] [proxy.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/proxy.py)
-   Implement response scanning in `_server_to_client()` to detect leaked secrets in upstream responses.
-   Scan for: AWS keys, private keys, tokens, API keys, passwords using regex patterns.
-   Log warnings to audit trail when secrets detected in responses.

### Dead Code Cleanup

#### [MODIFY] [proxy.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/proxy.py)
-   Remove unreachable `return None` at line 178 (after line 175's `return None`).

## Verification Plan

### Automated Tests
-   Run full test suite: `pytest tests/ -v`
-   Target: 90+ tests passing with 0 failures.
