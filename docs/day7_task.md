# Day 7 Checklist: FastMCP Middleware + Stats

- [ ] Create `mcpguard/middleware.py`
    - [ ] Implement `McpGuardMiddleware` class
    - [ ] Implement `wrap_fastmcp(mcp_server)` decorator/wrapper
- [ ] Implement `mcpguard stats` in `mcpguard/cli.py`
    - [ ] Parse `audit.jsonl`
    - [ ] Print summary table
- [ ] Verify both components locally
