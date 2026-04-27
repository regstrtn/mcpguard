# mcpguard 🛡️

**A firewall for MCP-based AI agents** — intercepts and evaluates tool calls against YAML policies before they reach your servers.

```
  AI Agent ─── mcpguard ──→ MCP Server
                  │
              Policy Engine
              Audit Logger
```

Stop your AI agent from running `rm -rf /`, reading your `.ssh` keys, or exfiltrating data to `webhook.site`.

## Features

- **Policy Engine** — YAML-defined rules with regex, prefix, and contains matching. First-match-wins priority.
- **Stdio Proxy** — Transparent man-in-the-middle for any MCP server. Zero code changes needed.
- **FastMCP Middleware** — Native integration for FastMCP servers via `McpGuardMiddleware`.
- **Tamper-Evident Audit Log** — JSON-lines with DPR hash chain. Every tool call recorded.
- **Human Approval** — Interactive `APPROVE` action via `/dev/tty` (doesn't interfere with MCP stdio).
- **Response Scanning** — Detects leaked secrets (AWS keys, private keys, tokens) in upstream responses.
- **Stats Dashboard** — Rich terminal tables + HTML export with Chart.js visualizations.
- **Policy Presets** — `default`, `strict`, and `permissive` built-in policies.

## Quick Start

```bash
# Install
pip install mcpguard

# Generate a starter config
mcpguard init

# Run in front of any MCP server
mcpguard run --config mcpguard.yaml -- npx @anthropic/mcp-filesystem /tmp
```

## Usage

### Proxy Mode (stdio)

Works with any MCP-compatible client (Claude Code, Cursor, Jetski):

```bash
# Claude Code filesystem server
mcpguard run --config mcpguard.yaml -- npx @anthropic/mcp-filesystem /home/user/project

# Any custom MCP server
mcpguard run --config policy.yaml --log audit.jsonl -- python my_server.py
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

### FastMCP Middleware

For servers built with FastMCP:

```python
from fastmcp import FastMCP
from mcpguard.middleware import McpGuardMiddleware

mcp = FastMCP("my-server")
guard = McpGuardMiddleware.from_yaml("mcpguard.yaml")
mcp.add_middleware(guard)
```

Or wrap an existing server:

```python
from mcpguard.middleware import wrap_fastmcp
wrap_fastmcp(mcp, policy_path="mcpguard.yaml")
```

### Test a Policy

```bash
# Test a deny case
mcpguard test --config mcpguard.yaml --tool run_command --args '{"command": "rm -rf /"}'
# → DENIED by policy 'block-destructive-shell'

# Test an allow case
mcpguard test --config mcpguard.yaml --tool run_command --args '{"command": "ls -la"}'
# → ALLOWED (no matching deny policy)
```

### Validate Policies

```bash
mcpguard validate --config mcpguard.yaml
# ✅ Valid! 9 policies loaded
```

### View Audit Stats

```bash
# Terminal dashboard
mcpguard stats --log mcpguard_audit.jsonl

# HTML export
mcpguard stats --log mcpguard_audit.jsonl --html report.html
```

## Writing Policies

Policies are YAML files with a simple structure:

```yaml
version: "1"
default_action: ALLOW  # ALLOW, DENY, APPROVE, or LOG

policies:
  - name: block-destructive-shell
    description: "Block rm -rf, mkfs, etc."
    priority: 100
    tools:
      - "run_command"
      - "shell_.*"    # regex patterns supported
    action: DENY
    rules:
      - argument: command
        pattern: "rm\\s+-rf|mkfs|dd\\s+if="
        message: "Destructive command blocked"
```

### Rule Types

| Rule | Description | Example |
|------|-------------|---------|
| `pattern` | Regex match | `pattern: "\\.ssh/"` |
| `not_pattern` | Regex must NOT match | `not_pattern: "rm\\s+-r"` |
| `prefix` | String prefix match | `prefix: ["/home/user/"]` |
| `not_prefix` | String must NOT start with | `not_prefix: ["/etc/"]` |
| `contains` | Substring match | `contains: ["password"]` |
| `not_contains` | Must NOT contain substring | `not_contains: [".env"]` |
| `max_length` | Maximum argument length | `max_length: 500` |

### Actions

| Action | Behavior |
|--------|----------|
| `ALLOW` | Forward to upstream server |
| `DENY` | Block with JSON-RPC error |
| `APPROVE` | Interactive human approval via `/dev/tty` |
| `LOG` | Forward but log the call |

### Priority

Rules are sorted by `priority` (highest first). First matching rule wins.
If no rule matches, `default_action` is used.

## Built-in Policy Presets

| Preset | Default Action | Description |
|--------|---------------|-------------|
| `default.yaml` | ALLOW | Block known-dangerous patterns, log writes and shell |
| `strict.yaml` | DENY | Deny everything by default, require explicit allows/approvals |
| `permissive.yaml` | ALLOW | Log-only mode, no blocking |

## Architecture

```
┌────────────────────────────────────────┐
│             AI Agent / Client          │
│         (Claude, Cursor, etc.)         │
└─────────────────┬──────────────────────┘
                  │ JSON-RPC over stdio
                  ▼
┌────────────────────────────────────────┐
│              mcpguard proxy            │
│  ┌──────────┐  ┌──────────────────┐    │
│  │ Policy   │  │  Audit Logger    │    │
│  │ Engine   │  │  (hash-chained)  │    │
│  └──────────┘  └──────────────────┘    │
│  ┌──────────┐  ┌──────────────────┐    │
│  │ Response │  │  Approval        │    │
│  │ Scanner  │  │  Handler (/tty)  │    │
│  └──────────┘  └──────────────────┘    │
└─────────────────┬──────────────────────┘
                  │ JSON-RPC over stdio
                  ▼
┌────────────────────────────────────────┐
│           MCP Server (upstream)        │
│      (filesystem, shell, API, etc.)    │
└────────────────────────────────────────┘
```

## Project Structure

```
mcpguard/
├── mcpguard/
│   ├── __init__.py          # Package metadata
│   ├── __main__.py          # python -m mcpguard entry point
│   ├── cli.py               # Click CLI (run, validate, test, init, stats)
│   ├── policy.py            # PolicyEngine with first-match-wins evaluation
│   ├── proxy.py             # Stdio proxy with response scanning
│   ├── middleware.py         # FastMCP middleware integration
│   ├── audit.py             # JSON-lines logger with DPR hash chain
│   ├── approval.py          # Interactive TTY approval handler
│   ├── dashboard.py         # HTML stats dashboard (Chart.js)
│   └── exceptions.py        # Custom exceptions
├── policies/
│   ├── default.yaml          # Sensible defaults
│   ├── strict.yaml           # Deny-by-default
│   └── permissive.yaml       # Log-only
├── tests/
│   ├── test_policy.py        # 57 policy engine tests
│   ├── test_middleware.py     # 4 FastMCP middleware tests
│   ├── test_audit.py          # 21 audit logger tests
│   └── test_e2e.py            # 10 E2E integration tests
├── examples/
│   ├── claude-code.md         # Claude Code integration guide
│   ├── cursor.md              # Cursor integration guide
│   ├── antigravity.md         # Antigravity/Jetski integration guide
│   └── simulate_client.py     # Test client simulator
├── docs/
│   ├── mcpguard_build_spec.md # Full project specification
│   └── policy-reference.md    # Policy language reference
└── pyproject.toml
```

## Development

```bash
# Clone
git clone https://github.com/regstrtn/mcpguard.git
cd mcpguard

# Create venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check .
```

## Roadmap

- [ ] Rate limiting (`RATE_LIMIT` action with `max_calls` / `per_seconds`)
- [ ] Expression language (`when: 'args["amount"] > 500'`) via expr-lang
- [ ] ML-based anomaly detection for unusual tool call patterns
- [ ] Async approval (`DEFER` action with file-based pending queue)
- [ ] Multi-agent governance policies

## License

MIT
