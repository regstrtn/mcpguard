# Day 3: MCP Proxy — Basic Pass-through

Implement a transparent MCP proxy that manages upstream server subprocesses and forwards stdio messages correctly.

## User Review Required

> [!NOTE]
> This is a plan for work already implemented in `mcpguard/proxy.py` containing standalone process forwarding.

## Proposed Changes

### [Component Name] MCP Proxy Pass-through

#### [NEW] [proxy.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/proxy.py)
-   Implement `McpProxy` utilizing `asyncio.create_subprocess_exec` to wrap upstream executable commands.
-   Implement line-by-line reading with standard asyncio Streams.
-   Implement `_client_to_server` and `_server_to_client` transparent pass-through mechanism (forwarding raw stdio streams accurately).

#### [NEW] [cli.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/cli.py)
-   Add `mcpguard run` command executing proxy passes to evaluate commands downstream.

## Verification Plan

### Automated Tests
-   Verify transparent JSON-RPC streams arrive in upstream buffer without corruption using standard tools.

### Manual Verification
-   Run `mcpguard run -- npx @anthropic/mcp-filesystem /tmp` to verify it passes all message flows into standard upstream listeners correctly.
