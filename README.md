# 🛡️ mcpguard

> **"iptables for AI agents"** — A YAML-configurable firewall between AI agents and their tools.

`mcpguard` intercepts every tool call between an MCP client (Claude Code, Cursor, Windsurf) and an MCP server, evaluating each call against YAML-defined security policies. It can **allow**, **deny**, or require **human approval**.

---

## 🚀 Quick Start

### 1. Install

```bash
pip install mcpguard
```

### 2. Generate configuration

Generate a robust `mcpguard.yaml` with sensible defaults:

```bash
mcpguard init
```

### 3. Wrap your MCP Server

To secure any MCP server over `stdio`, wrap its command line executable using `mcpguard run`:

```bash
mcpguard run --config mcpguard.yaml -- npx @anthropic/mcp-filesystem /home/user/workspace
```

---

## ⚙️ Features

- 🔌 **Framework Agnostic:** Sits between any stdout/stdin pipe securely. No code changes needed.
- 📜 **YAML Policies:** Define fine-grained inspection rules on tool execution arguments.
- ✅ **Human Approval Screen:** Intercepts high-risk actions and waits on a `/dev/tty` check for approval.
- 📊 **Audit Analytics:** Automatic DPR linked-list hash chain audit logging with standalone dashboard renderer analytics.
- ⚡ **FastMCP Middleware:** Direct programmatic drop-in support if building custom workflows in Python directly.

---

## 📊 Dashboard & Stats

View simple traffic statistics or export to beautiful dynamic chart viewers:

```bash
# Print static table inside terminal
mcpguard stats --log mcpguard_audit.jsonl

# Generate visual HTML dashboard report template 
mcpguard stats --log mcpguard_audit.jsonl --html dashboard.html
```

---

## 📖 Documentation

- [Policy Language Reference](docs/policy-reference.md)
- [Claude Code Integration](examples/claude-code.md)
- [Cursor Integration](examples/cursor-md)

---

## ⚖️ License

MIT License. Standalone, auditable infrastructure proxy wrapper stack setup!
