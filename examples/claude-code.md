# 🤖 Claude Code Integration

Wrap your existing MCP servers in `mcpguard run` to add security inspection.

---

## 📋 1. Setup Policy

Create a `mcpguard.yaml` with your standard rules (or run `mcpguard init` to generate one).

```yaml
version: "1"
default_action: ALLOW

policies:
  - name: verify-fs-writes
    tools: ["write_file", "edit_file"]
    action: APPROVE  # Require human y/n approval
    rules: []
```

---

## ⚙️ 2. Configure `~/.claude.json`

Claude Code configuration aggregates MCP server endpoints. Wrap the execution with `mcpguard`.

### 🔍 Standard Configuration

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
        "--config", "/path/to/mcpguard.yaml",
        "--log", "/path/to/audit.jsonl",
        "--",
        "npx", "@anthropic/mcp-filesystem", "/home/user/workspace"
      ]
    }
  }
}
```

---

## 🚨 3. Test verification

Invoke Claude Code:
```bash
claude
```

Ask it to perform an operation matching your policy rule (e.g., `Save text "hello world" to file debug.txt`).
You will see `mcpguard` prompt you on your `/dev/tty` screen (standard stderr overlay) for dynamic approval confirmation before forwarding execution back over standard routing protocols!
