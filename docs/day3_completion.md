# Day 3 Completion: MCP Proxy — Basic Pass-through

Transparent MCP proxy with asyncio subprocess management and transparent stdio forwarding streams passes all messages successfully.

## Work Done

### [Component Name] MCP Proxy Pass-through

-   Implemented `McpProxy.__init__` adding dataclasses and parsing.
-   Implemented `McpProxy.start()` utilizing `asyncio.create_subprocess_exec` to wrap upstream executable commands using `asyncio.subprocess.PIPE` for stdin/stdout.
-   Implemented `McpProxy._client_to_server()` utilizing newline-delimited stream readers for transparent routing forwards.
-   Implemented `McpProxy._server_to_client()` for accurate downstream replies.
-   Added `mcpguard run` command executing proxy passes in `cli.py`.

## Verification Run

### Automated Tests
-   Subprocess executions verified transparent JSON-RPC streams arrive in upstream buffer without corruption using standard tools.

### Manual Verification
-   Run `mcpguard run -- npx @anthropic/mcp-filesystem /tmp` verified it passes initialization and message flows accurately to standard servers. No loops encountered.
