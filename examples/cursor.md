# 🖱️ Cursor Integration

Wrap your existing MCP servers with `mcpguard run` to evaluate tool calls before forwarding them to the server inside Cursor.

---

## 📋 1. Setup Policy File

Create a standard policy file first:

```yaml
version: "1"
default_action: ALLOW

policies:
  - name: restrict-shell
    tools: ["shell_command", "run_command"]
    action: DENY
    rules:
      - argument: "command"
        not_contains: ["ls", "cat", "pwd"]
```

---

## ⚙️ 2. Configure Settings in Cursor

Cursor offers an interface under **Features > MCP**.

1. Choose **Stdio** transport type.
2. Fill in the interface form fields with the wrapping `mcpguard` variables:

| Field | Value |
| :--- | :--- |
| **Name** | `secured-server-everything` |
| **Command** | `mcpguard` |
| **Args** | `run --config /path/to/mcpguard.yaml -- npx @modelcontextprotocol/server-everything` |

---

## 🚨 3. Verifying Results

When Cursor triggers any tool over that server proxy (e.g. asking it to read a prohibited path), `mcpguard` returns a standard description feedback stream reported that it was blocked by policy:

```json
{
  "code": -32600,
  "message": "Blocked by policy 'restrict-shell': Forbidden command blocked"
}
```

Audit stats can immediately be viewed using `mcpguard stats --log audit.jsonl` over those interactions!
