# 🚀 Jetski / Antigravity Integration

`mcpguard` works natively with Google's **Jetski** internal assistant and the **Antigravity SDK**, because they adhere to standard Model Context Protocol (MCP) clientside hosting schemas (`mcp_config.json`).

---

## 📋 1. Setup Policy File

Create your target safety rule set (`mcpguard.yaml`):

```yaml
version: "1"
default_action: ALLOW

policies:
  - name: restrict-shell
    tools: ["run_command", "shell_exec"]
    action: DENY
    rules:
      - argument: "command"
        not_contains: ["ls", "cat"]
```

---

## ⚙️ 2. Configure Jetski Settings

Jetski / Antigravity looks for local configurations inside your home profile config store:
`~/.codeium/antigravity/mcp_config.json`

Add/Wrap your server entry leveraging `mcpguard run`:

```json
{
  "mcpServers": {
    "my-secure-server": {
      "command": "mcpguard",
      "args": [
        "run",
        "--config", "/path/to/mcpguard.yaml",
        "--log", "/path/to/audit.jsonl",
        "--",
        "npx", "@modelcontextprotocol/server-everything"
      ]
    }
  }
}
```

---

## 🐍 3. Programmatic Antigravity SDK Integration

If you are invoking agents using the **Python Antigravity SDK**, you can spawn `mcpguard` directly around custom endpoints by passing them on config setup.

```python
from google3.learning.gemini.agents.clis.antigravity_sdk import antigravity_sdk_lib

# Standard Agentic configuration hooks
result = antigravity_sdk_lib.run_coder_agent(
    prompt="Investigate this workspace",
    mcp_servers_to_launch=[
        {
            "name": "wrapped-mcp",
            "command": "mcpguard",
            "args": ["run", "--", "my_custom_server_bin"]
        }
    ]
)
```

---

## 📊 4. Interactive Approvals

If your rule includes an `APPROVE` buffer logic lock on tool execution, `mcpguard` overlays standard buffer confirmation streams allowing you to approve execution runs safely directly matching your security dashboard layout checkpoints manually without changing how Jetski models run tool-cases internally.
