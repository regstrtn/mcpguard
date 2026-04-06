# Day 4: MCP Proxy — Policy Integration

Connect the Policy Engine to intercept incoming tool calls and block or forward messages accordingly.

## User Review Required

> [!NOTE]
> This is a plan for work already implemented in `mcpguard/proxy.py` containing interception checks.

## Proposed Changes

### [Component Name] Policy Engine Integration

#### [NEW] [proxy.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/proxy.py)
-   Wire `PolicyEngine` into proxy's `_handle_client_message` function.
-   Intercept `method == "tools/call"`, extract name and arguments accurately.
-   Evaluate against `self.policy_engine.evaluate(tool_name, arguments)`.
-   If `Action.DENY`, create JSON-RPC error mapping back downstream.
-   If `Action.ALLOW`, return `None` to transparently flow upstream.

## Verification Plan

### Automated Tests
-   Verify JSON-RPC error replies match standard diagnostics accurately.
-   Run standalone evaluation matches locally to confirm intercepts apply.

### Manual Verification
-   Run `mcpguard run` and manually pipe a `tools/call` dict structure. Verify it intercept triggers accurate actions.
