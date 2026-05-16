# Day 7: FastMCP Middleware + Stats Dashboard

Implement a Python middleware SDK wrapper for FastMCP servers and create an offline stats viewer from the audit logs.

## User Review Required

> [!IMPORTANT]
> -   The middleware requires wrapping downstream operations of `FastMCP`. I propose a simple `wrap_fastmcp(mcp_instance)` function for developers to include `mcpguard` integration seamlessly.
> -   The stats dashboard will pull directly from the JSONL audit file trails statically.

## Proposed Changes

### [Component Name] FastMCP Middleware

#### [NEW] [middleware.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/middleware.py)
-   Implement `McpGuardMiddleware` class initializing with `PolicyEngine`, `AuditLogger`, and `ApprovalHandler`.
-   Implement `wrap_fastmcp(mcp_server)` wrapping the server's function decorators or overriding `.call_tool` triggers smoothly without breaking downstream routing.

### [Component Name] Audit Stats CLI

#### [MODIFY] [cli.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/cli.py)
-   Implement `mcpguard stats` parsing `audit.jsonl` buffers.
-   Print a structured `rich.Table` dashboard displaying:
    -   Total tool calls.
    -   Intercept count segmented by actions (`ALLOW`, `DENY`, `APPROVE`).
    -   Top blocked tools count.

## Verification Plan

### Automated Tests
-   Verify wrapping triggers evaluation accurate triggers of dummy context flows.

### Manual Verification
-   Run `mcpguard stats` verifying layout displays accurate counts offline accurately.
