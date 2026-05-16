# integrating mcpguard

`mcpguard` sits between your AI agent client (Claude Code, Cursor, Windsurf, etc.) and your MCP server, filtering tool calls over the `stdio` stream in real-time.

---

## 🚀 General Usage

To guard an MCP server, wrap its command with `mcpguard run`:

```bash
mcpguard run --config policy.yaml -- <upstream_mcp_command>
```

---

## 🤖 Claude Code (Anthropic)

Claude Code loads MCP servers from `~/.claude.json` or equivalent configurations.

1. Create a `policy.yaml` (e.g., denying `rm` commands in shell or restricted files).
2. Update your config to wrap the executable:

**Before:**
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["@anthropic/mcp-filesystem", "/home/user/workspace"]
    }
  }
}
```

**After:**
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "mcpguard",
      "args": [
        "run",
        "--config", "/path/to/policy.yaml",
        "--log", "/path/to/audit.jsonl",
        "--",
        "npx", "@anthropic/mcp-filesystem", "/home/user/workspace"
      ]
    }
  }
}
```

---

## 🖱️ Cursor

Cursor configures MCP servers inside **Settings > Features > MCP**.

1. Choose **Stdio** type.
2. Provide the following setup:

| Field | Value |
| :--- | :--- |
| **Name** | `filesystem-secured` |
| **Command** | `mcpguard run --config /path/to/policy.yaml -- npx @anthropic/mcp-filesystem /workspace` |

> [!NOTE]
> Ensure `mcpguard` is available in your `$PATH` globally (e.g., installed via `pip install mcpguard` inside a global environment or system-wide).

---

## 🌪️ Windsurf / Cascade

Windsurf has a similar setup in `~/.codeium/windsurf/mcp_config.json`.

```json
{
  "mcpServers": {
    "everything": {
      "command": "mcpguard",
      "args": [
        "run", "--", "npx", "@modelcontextprotocol/server-everything"
      ]
    }
  }
}
```

---

## 🔍 Verifying Setup

After configuring your client, ask it to run a tool that you know should be blocked.

1. **Ask your agent:** `Can you run shell command 'rm -rf /tmp/test'`?
2. **Result:** The client should report `McpGuard: Blocked tool 'shell' by policy 'block-dangerous'`.
3. **Verify log:** Check that it is recorded in your local `mcpguard_audit.jsonl` log audit stream.
