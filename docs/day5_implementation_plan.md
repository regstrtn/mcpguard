# Day 5: Audit Logger

Implement structured logging for all intercepted tool calls into a JSON-Lines audit trail.

## User Review Required

> [!NOTE]
> This is a plan for work already implemented in `mcpguard/audit.py` containing audit trails.

## Proposed Changes

### [Component Name] Audit Logger

#### [NEW] [audit.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/audit.py)
-   Implement `AuditLogger` supporting append loops to local file paths.
-   Include JSON serialisation payloads: `timestamp`, `tool`, `arguments`, `action`, `matched_policy`, `reason`.

#### [NEW] [proxy.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/proxy.py)
-   Wire `AuditLogger` call buffers to log evaluate answers before triggers.

#### [NEW] [cli.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/cli.py)
-   Add `--log` configuration option to standalone execute pass-throughs.

## Verification Plan

### Automated Tests
-   Verify JSON payload appending structure reads correctly correctly.
-   Ensure read triggers append accurately back downstream.

### Manual Verification
-   Run `mcpguard run --log audit.jsonl` and verify output loads correctly on updates.
