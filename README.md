# mcpguard 🛡️

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-93%20passing-brightgreen.svg)]()
[![PyPI](https://img.shields.io/badge/pypi-mcpguard-orange.svg)](https://pypi.org/project/mcpguard/)

**A firewall for MCP-based AI agents** — intercepts and evaluates tool calls against YAML policies before they reach your servers.

```
  AI Agent ─── mcpguard ──→ MCP Server
                  │
              Policy Engine
              Audit Logger
```

Stop your AI agent from running `rm -rf /`, reading your `.ssh` keys, or exfiltrating data to `webhook.site`.

## Features

- **YAML Policies** — Simple rules with regex, prefix, and contains matching. No DSL to learn.
- **Stdio Proxy** — Transparent man-in-the-middle for any MCP server. Zero code changes.
- **Shadow Mode** — Log everything without blocking. See what *would* be blocked before enforcing.
- **FastMCP Middleware** — Native integration for FastMCP servers via `McpGuardMiddleware`.
- **Tamper-Evident Audit Log** — JSON-lines with hash chain. Every tool call recorded.
- **Human Approval** — Interactive `APPROVE` action via `/dev/tty` (doesn't interfere with MCP stdio).
- **Response Scanning** — Detects leaked secrets (AWS keys, private keys, tokens) in upstream responses.
- **Stats Dashboard** — Rich terminal tables + HTML export with Chart.js visualizations.

## Quick Start

```bash
# Install
pip install mcpguard

# Generate starter config
mcpguard init

# Run in front of any MCP server
mcpguard run -- npx @anthropic/mcp-filesystem /tmp

# Or start in shadow mode first (log only, no blocking)
mcpguard run --shadow -- npx @anthropic/mcp-filesystem /tmp
```

## Usage

### Proxy Mode (stdio)

Works with any MCP-compatible client (Claude Code, Cursor, Jetski):

```bash
# Enforce policies
mcpguard run --config mcpguard.yaml -- npx @anthropic/mcp-filesystem /home/user/project

# Shadow mode: log everything, block nothing
mcpguard run --shadow -- npx @anthropic/mcp-filesystem /home/user/project
```

Configure in Claude Code's `.claude.json`:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "mcpguard",
      "args": ["run", "--config", "mcpguard.yaml", "--", "npx", "@anthropic/mcp-filesystem", "/tmp"]
    }
  }
}
```

### Shadow Mode

Start in shadow mode to see what mcpguard *would* block without actually blocking anything. Tool calls that would be denied are logged as `SHADOW_DENY` instead — your agent keeps working normally.

```bash
# Watch what would happen
mcpguard run --shadow -- python my_server.py

# Review the log
mcpguard stats --log mcpguard_audit.jsonl

# When satisfied, switch to enforcement
mcpguard run -- python my_server.py
```

### FastMCP Middleware

For servers built with FastMCP:

```python
from fastmcp import FastMCP
from mcpguard.middleware import McpGuardMiddleware

mcp = FastMCP("my-server")
guard = McpGuardMiddleware.from_yaml("mcpguard.yaml")
mcp.add_middleware(guard)
```

### Test a Policy

```bash
# Test a deny case
mcpguard test --tool run_command --args '{"command": "rm -rf /"}'
# → DENIED by policy 'block-destructive-commands'

# Test an allow case
mcpguard test --tool run_command --args '{"command": "ls -la"}'
# → LOG (logged, not blocked)
```

### Validate & Stats

```bash
mcpguard validate                          # Validate default mcpguard.yaml
mcpguard stats --log mcpguard_audit.jsonl  # Terminal dashboard
mcpguard stats --log audit.jsonl --html report.html  # HTML export
```

## Writing Policies

Policies are a single YAML file — `mcpguard.yaml`:

```yaml
version: "1"
default_action: ALLOW

policies:
  - name: block-destructive-commands
    description: "Block rm -rf, mkfs, etc."
    priority: 100
    tools: ["run_command", "shell_.*"]
    action: DENY
    rules:
      - argument: command
        pattern: "rm\\s+-rf|mkfs|dd\\s+if="
        message: "Destructive command blocked"

  - name: log-file-writes
    description: "Log all file modifications"
    priority: 10
    tools: ["write_file", "create_file"]
    action: LOG
```

### Rule Types

| Rule | Description | Example |
|------|-------------|---------|
| `pattern` | Regex match | `pattern: "\\.ssh/"` |
| `not_pattern` | Must NOT match regex | `not_pattern: "rm\\s+-r"` |
| `prefix` | String starts with | `prefix: ["/home/user/"]` |
| `not_prefix` | Must NOT start with | `not_prefix: ["/etc/"]` |
| `contains` | Substring match | `contains: ["password"]` |
| `not_contains` | Must NOT contain | `not_contains: [".env"]` |
| `max_length` | Max argument length | `max_length: 500` |

### Actions

| Action | Behavior |
|--------|----------|
| `ALLOW` | Forward to upstream server |
| `DENY` | Block with JSON-RPC error |
| `APPROVE` | Interactive human approval via `/dev/tty` |
| `LOG` | Forward but log the call |

Rules sorted by `priority` (highest first). First match wins. If nothing matches, `default_action` applies.

See [docs/policy-reference.md](docs/policy-reference.md) for the full language reference.

## Architecture

```
┌─────────────────────────────────────────┐
│            AI Agent / Client            │
│        (Claude, Cursor, Jetski)         │
└──────────────────┬──────────────────────┘
                   │ JSON-RPC over stdio
                   ▼
┌─────────────────────────────────────────┐
│             mcpguard proxy              │
│  ┌──────────┐  ┌───────────────────┐    │
│  │ Policy   │  │  Audit Logger     │    │
│  │ Engine   │  │  (hash-chained)   │    │
│  └──────────┘  └───────────────────┘    │
│  ┌──────────┐  ┌───────────────────┐    │
│  │ Response │  │  Approval Handler │    │
│  │ Scanner  │  │  (/dev/tty)       │    │
│  └──────────┘  └───────────────────┘    │
└──────────────────┬──────────────────────┘
                   │ JSON-RPC over stdio
                   ▼
┌─────────────────────────────────────────┐
│          MCP Server (upstream)          │
│     (filesystem, shell, API, etc.)      │
└─────────────────────────────────────────┘
```

## Development

```bash
git clone https://github.com/regstrtn/mcpguard.git
cd mcpguard

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Roadmap

- [ ] Expression language (`when: 'args["amount"] > 500'`)
- [ ] ML-based anomaly detection
- [ ] `mcpguard suggest` — auto-generate policies from audit logs

## License

MIT
