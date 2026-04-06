# mcpguard — Build Specification

> "iptables for AI agents" — A YAML-configurable firewall between AI agents and their tools.

---

## Work Culture & Coding Principles

### Work Culture
1. **Be brief, skip pleasantries.** Speak less, do more.
2. **Use Mercurial (hg).** Do not create new commits using `hg commit` in the middle of a task; always amend onto existing commits unless working off of `p4head`.
3. **No magic.** Prefer explicit, boring code that is easy to maintain.

### Coding Principles
1. **Code must be easily readable.** If a reviewer can't understand what a function does in 30 seconds, rewrite it.
2. **Optimize for readability and understandability, not cleverness.** Do not over-optimize for performance. There is value in simpler, readable, and maintainable code. Boring code is good code.
3. **No magic.** Prefer explicit over implicit. Name things clearly. Add comments for *why*, not *what*.
4. **Small functions.** Each function does one thing. If it needs a paragraph to explain, split it.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Key Research Findings](#2-key-research-findings)
3. [Architecture](#3-architecture)
4. [MCP Protocol Primer](#4-mcp-protocol-primer)
5. [Module-by-Module Specification](#5-module-by-module-specification)
6. [Policy Language Specification](#6-policy-language-specification)
7. [File Structure](#7-file-structure)
8. [Dependencies](#8-dependencies)
9. [Build Plan (Day-by-Day)](#9-build-plan-day-by-day)
10. [Testing Strategy](#10-testing-strategy)
11. [Distribution & Launch](#11-distribution--launch)
12. [Publication Strategy](#12-publication-strategy)

---

## 1. Overview

### What

mcpguard is a lightweight Python tool that intercepts every tool call between an MCP client (Claude, LangChain, Cursor, any agent) and an MCP server (filesystem, shell, database, API). It evaluates each call against YAML-defined security policies and allows, blocks, rate-limits, or requires human approval.

### Why this specific thing

| Alternative | Why it's not enough |
|---|---|
| FastMCP middleware | Tied to FastMCP framework. Only works if YOUR server uses FastMCP. Doesn't protect against 3rd-party MCP servers. |
| faramesh-core | Vague, early-stage, uses Go+Python, no clear docs or adoption |
| Lilith-zero | Rust, not Python, Feb 2026 |
| Golf Firewall | Commercial, not launched yet |
| Solo.io agentgateway | Enterprise-grade, complex infra required |
| LangChain Interceptors | Tied to LangChain MCP Adapters only |
| Permit.io middleware | AuthZ only (who can call), not content inspection (what they pass) |

**mcpguard's niche:** Framework-agnostic, standalone, pip-installable, YAML-configured, inspects tool call ARGUMENTS (not just tool names), works with ANY MCP server.

### Two integration modes

1. **Standalone proxy** — sits between any MCP client and server. Zero code changes.
2. **FastMCP middleware** — for people already using FastMCP, drop-in middleware class.

---

## 2. Key Research Findings

### MCP Protocol (as of March 2026)

- **Transport:** JSON-RPC 2.0 over stdio (local) or Streamable HTTP (remote)
- **Tool call method:** `tools/call` with params `{name: string, arguments: object}`
- **Tool discovery:** `tools/list` returns available tools + their input schemas
- **SDK:** `mcp` pip package (v1.26.0, Jan 2026), maintained by Anthropic → Linux Foundation
- **FastMCP:** High-level Python SDK (v2.9+), has middleware system with `on_call_tool`

### Wire Format — What We Intercept

**Tool call request (client → server):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run_command",
    "arguments": {
      "command": "rm -rf /",
      "cwd": "/home/user"
    }
  }
}
```

**Tool call response (server → client):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {"type": "text", "text": "Command output..."}
    ]
  }
}
```

**What mcpguard does:** Intercepts the request JSON, inspects `params.name` and `params.arguments`, evaluates policies, then either forwards or blocks.

### Competitive landscape

| Project | Stars | Lang | Framework-agnostic? | Arg inspection? | YAML policies? |
|---|---|---|---|---|---|
| LLM Guard | 4k+ | Python | Yes | No (prompt only) | No |
| NeMo Guardrails | 4k+ | Python | No (NeMo) | No | Colang |
| FastMCP middleware | N/A | Python | No (FastMCP) | Yes | No (code) |
| Permit.io MCP | ~200 | Python | No (FastMCP) | No (authZ only) | No |
| faramesh-core | ~14 | Go+Py | Partial (adapters) | Yes (expr-lang) | YAML | Elastic License, complex multi-adapter arch |
| **mcpguard** | 0 | Python | **Yes** | **Yes** | **Yes** | MIT, standalone, pip-installable |

---

## 3. Architecture

### Standalone proxy mode

```
┌─────────────┐     stdio      ┌──────────────────┐     stdio      ┌─────────────┐
│  MCP Client │ ◄────────────► │    mcpguard       │ ◄────────────► │  MCP Server  │
│  (Claude,   │                │                   │                │  (filesystem,│
│   Cursor,   │                │  ┌─────────────┐  │                │   shell,     │
│   agent)    │                │  │ Policy      │  │                │   DB, API)   │
│             │                │  │ Engine      │  │                │              │
│             │                │  └─────────────┘  │                │              │
│             │                │  ┌─────────────┐  │                │              │
│             │                │  │ Audit Log   │  │                │              │
│             │                │  └─────────────┘  │                │              │
└─────────────┘                └──────────────────┘                └─────────────┘
```

**How it works:**
1. mcpguard starts the upstream MCP server as a subprocess
2. mcpguard itself acts as an MCP server (the client connects to it)
3. It passes through all messages EXCEPT `tools/call` requests
4. For `tools/call`: parse → evaluate policies → allow/deny → forward or return error
5. All decisions are logged to audit log

### FastMCP middleware mode

```python
from mcpguard import McpGuardMiddleware

server = FastMCP("my-server")
server.add_middleware(McpGuardMiddleware.from_yaml("mcpguard.yaml"))
```

---

## 4. MCP Protocol Primer

### Messages we care about

| Method | Direction | What it does | mcpguard action |
|---|---|---|---|
| `initialize` | client→server | Handshake | **Pass through** |
| `tools/list` | client→server | Discover tools | **Pass through** (optionally filter) |
| `tools/call` | client→server | Execute a tool | **🔥 INTERCEPT AND EVALUATE** |
| `notifications/*` | either | Progress updates | **Pass through** |
| `resources/*` | client→server | Read resources | **Pass through** (future: intercept) |
| `prompts/*` | client→server | Get prompts | **Pass through** |

### stdio transport details

MCP over stdio works like this:
- Client writes JSON-RPC messages to server's **stdin**, separated by newlines
- Server writes JSON-RPC messages to **stdout**, separated by newlines
- Server can write debug info to **stderr** (not part of protocol)

mcpguard acts as a **man-in-the-middle**:
- Reads from ITS stdin (client's messages)
- Parses JSON-RPC
- If `method == "tools/call"`: evaluate policies
- Forwards allowed messages to upstream server's stdin
- Reads upstream server's stdout, forwards to ITS stdout

---

## 5. Module-by-Module Specification

### 5.1 `mcpguard/policy.py` — Policy Engine

The core brain. Parses YAML policies and evaluates tool calls against them.

```python
"""
Classes:
  - Policy: A single policy rule
  - PolicyEngine: Collection of policies, evaluates tool calls
  - PolicyResult: ALLOW | DENY | APPROVE
  - RuleMatch: Details of which policy matched and why
"""

@dataclass
class Policy:
    name: str                    # e.g. "block-destructive-shell"
    description: str             # Human-readable
    tools: list[str]             # Tool name patterns (regex). e.g. ["run_command", "shell_.*"]
    action: str                  # "DENY" | "ALLOW" | "APPROVE" | "LOG"
    rules: list[Rule]            # Argument inspection rules
    priority: int                # Higher = evaluated first. Default 0.
    enabled: bool                # Can disable without removing

@dataclass
class Rule:
    argument: str                # Which argument to inspect. e.g. "command", "path", "url"
    # Match conditions (at least one required):
    pattern: str | None          # Regex pattern to DENY. e.g. "rm -rf|mkfs"
    not_pattern: str | None      # Regex pattern that MUST NOT match
    prefix: list[str] | None     # Allowed prefixes. e.g. ["/home/user/project/"]
    not_prefix: list[str] | None # Denied prefixes
    contains: list[str] | None   # Must contain one of these
    not_contains: list[str] | None  # Must not contain any of these
    max_length: int | None       # Argument value max length

@dataclass 
class PolicyResult:
    action: str                  # "ALLOW" | "DENY" | "APPROVE"
    matched_policy: str | None   # Name of the policy that matched
    reason: str | None           # Human-readable reason
    tool_name: str
    arguments: dict

class PolicyEngine:
    def __init__(self, policies: list[Policy], default_action: str = "ALLOW"):
        ...
    
    @classmethod
    def from_yaml(cls, path: str) -> "PolicyEngine":
        """Load policies from YAML file."""
        ...
    
    def evaluate(self, tool_name: str, arguments: dict) -> PolicyResult:
        """
        Evaluate a tool call against all policies.
        
        Algorithm:
        1. Sort policies by priority (descending)
        2. For each policy:
           a. Check if tool_name matches any pattern in policy.tools
           b. If yes, evaluate all rules against arguments
           c. If all rules match → return policy's action
        3. If no policy matches → return default_action
        """
        ...
```

**Key design decisions:**
- First-match wins (like iptables). Higher priority evaluated first.
- Default action is ALLOW (fail-open). Users can set to DENY (fail-closed).
- Regex uses `re.search` (not `re.match`) — matches anywhere in string.
- All matching is case-insensitive by default.

### 5.2 `mcpguard/proxy.py` — MCP Proxy

The transport layer. Handles stdio communication.

```python
"""
McpProxy: Transparent MCP proxy that intercepts tools/call messages.

Architecture:
- Starts upstream MCP server as subprocess
- Reads JSON-RPC from stdin (from client)
- For tools/call: evaluates via PolicyEngine
- Forwards allowed messages to upstream subprocess stdin
- Reads upstream subprocess stdout, forwards to own stdout
- Logs everything via AuditLogger
"""

class McpProxy:
    def __init__(
        self,
        upstream_command: list[str],   # e.g. ["npx", "@anthropic/mcp-filesystem", "/home"]
        policy_engine: PolicyEngine,
        audit_logger: AuditLogger,
        on_deny: Callable | None = None,      # Custom deny handler
        on_approve: Callable | None = None,    # Human approval handler
    ):
        ...
    
    async def start(self):
        """
        1. Start upstream server as asyncio subprocess
        2. Start two tasks:
           a. client_to_server: read stdin → process → write to upstream stdin
           b. server_to_client: read upstream stdout → write to stdout
        3. Wait for either side to close
        """
        ...
    
    async def _handle_client_message(self, raw: str) -> str | None:
        """
        Parse JSON-RPC message from client.
        If method == "tools/call":
            Extract tool name + arguments
            Evaluate against policy engine
            If DENY: return error response JSON, don't forward
            If APPROVE: prompt user, wait for y/n
            If ALLOW: forward to upstream
        Else:
            Forward as-is
        """
        ...
    
    async def _read_stream(self, stream) -> AsyncIterator[str]:
        """Read newline-delimited JSON-RPC messages from a stream."""
        ...
```

**Critical implementation details:**

1. **Message framing:** MCP stdio uses newline-delimited JSON. Each message is one line. Read line-by-line from stdin/stdout.

2. **Async I/O:** Use `asyncio.create_subprocess_exec` for upstream. Use `asyncio.StreamReader` for reading. This prevents blocking.

3. **Error responses:** When blocking a tool call, return a valid JSON-RPC error:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "mcpguard: Blocked by policy 'block-destructive-shell': Destructive command blocked"
  }
}
```

4. **Request ID tracking:** Must preserve the `id` field from the client's request when returning deny responses.

### 5.3 `mcpguard/audit.py` — Audit Logger

```python
class AuditLogger:
    def __init__(self, path: str = "mcpguard_audit.jsonl", also_stderr: bool = True, hash_chain: bool = True):
        ...
    
    def log(self, event: AuditEvent):
        """Append JSON line to audit file. Optionally print to stderr."""
        ...
    
    def verify_chain(self) -> tuple[bool, int]:
        """Verify hash chain integrity. Returns (is_valid, entries_checked)."""
        ...
    
    def get_stats(self) -> dict:
        """Read audit log and compute summary statistics."""
        ...

@dataclass
class AuditEvent:
    timestamp: str           # ISO 8601
    session_id: str          # Unique per mcpguard run
    tool: str                # Tool name
    arguments: dict          # Tool arguments (sensitive values auto-redacted)
    action: str              # "ALLOW" | "DENY" | "APPROVE_YES" | "APPROVE_NO" | "LOG"
    matched_policy: str | None
    reason: str | None
    response_time_ms: float | None  # How long the upstream took (if allowed)
    prev_hash: str | None    # SHA256 hash of previous entry (DPR chain)
    entry_hash: str | None   # SHA256 hash of this entry
```

**DPR hash chain (tamper-evident audit trail):**
Each audit entry includes a `prev_hash` (hash of the previous entry) and `entry_hash` (hash of itself). This creates a linked chain — if any entry is modified or deleted, `verify_chain()` detects it. Inspired by faramesh-core's DPR concept but implemented simply (~15 lines). The `mcpguard stats` command automatically verifies chain integrity.

**Sensitive value redaction:**
Arguments with keys like `password`, `secret`, `token`, `api_key` are automatically replaced with `***REDACTED***` before logging.

### 5.4 `mcpguard/approval.py` — Human Approval

```python
class ApprovalHandler:
    """Interactive CLI approval for tool calls requiring human review."""
    
    async def request_approval(self, tool: str, arguments: dict, reason: str) -> bool:
        """
        Print tool call details to stderr.
        Prompt user for y/n on stderr.
        Read response from /dev/tty (NOT stdin — stdin is MCP protocol).
        Returns True if approved.
        
        IMPORTANT: Cannot use stdin because that's the MCP transport.
        Must read from /dev/tty directly for interactive approval.
        """
        ...
```

**Critical gotcha:** Since stdin/stdout are used for MCP communication, interactive approval must use `/dev/tty` for input and stderr for output. This is the same approach `sudo` uses.

### 5.5 `mcpguard/cli.py` — CLI Interface

```python
"""
Commands:
  mcpguard run --config policy.yaml -- <upstream_command>
    Start proxy with given upstream command.
    
  mcpguard validate --config policy.yaml
    Validate policy file syntax and semantics.
    
  mcpguard stats --log mcpguard_audit.jsonl
    Show summary statistics from audit log.
    
  mcpguard init
    Generate a starter mcpguard.yaml with sensible defaults.
    
  mcpguard test --config policy.yaml --tool <name> --args '{"key": "value"}'
    Test a single tool call against policies without running a server.
"""
```

### 5.6 `mcpguard/middleware.py` — FastMCP Integration

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext

class McpGuardMiddleware(Middleware):
    """Drop-in FastMCP middleware using mcpguard policies."""
    
    def __init__(self, policy_engine: PolicyEngine, audit_logger: AuditLogger | None = None):
        ...
    
    @classmethod
    def from_yaml(cls, path: str) -> "McpGuardMiddleware":
        ...
    
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        arguments = context.message.arguments or {}
        result = self.policy_engine.evaluate(tool_name, arguments)
        
        if result.action == "APPROVE":
            # approval logic
            pass
        
        # Log and forward
        self.audit_logger.log(...)
        return await call_next(context)
```

---

## 6. Policy Language Specification

### Full YAML schema

```yaml
# mcpguard.yaml
version: "1"                    # Schema version
default_action: ALLOW           # ALLOW or DENY. What happens when no policy matches.

policies:
  - name: string                # Required. Unique identifier.
    description: string         # Optional. Human-readable.
    enabled: true               # Optional. Default true.
    priority: 0                 # Optional. Higher = evaluated first. Default 0.
    tools:                      # Required. List of tool name patterns (regex).
      - "run_command"
      - "shell_.*"
    action: DENY                # Required. DENY | ALLOW | APPROVE | LOG
    
    # Argument inspection rules. ALL must match for policy to trigger.
    rules:
      - argument: "command"     # Which argument key to inspect
        # String matching (pick one or more):
        pattern: "rm -rf|mkfs"  # Regex. If matches → rule triggers.
        not_pattern: "^ls "     # Regex. If matches → rule does NOT trigger.
        prefix:                 # Allowed prefixes. Value must start with one.
          - "/safe/path/"
        not_prefix:             # Blocked prefixes. Value must NOT start with any.
          - "/etc/"
          - "/root/"
        contains:               # Value must contain at least one.
          - "sudo"
        not_contains:           # Value must NOT contain any.
          - "password"
        max_length: 1000        # Max character length
        
        message: "Custom deny message"  # Optional. Shown when rule triggers.
```

### Built-in policy presets

**`default.yaml`** — sensible defaults for any development environment:
- Block destructive shell commands (rm -rf, mkfs, dd, shutdown)
- Block reading sensitive files (.ssh, .env, .aws, credentials)
- Block network access to internal IPs (10.x, 172.16-31.x, 192.168.x)
- Log all file writes
**`permissive.yaml`** — log-only mode:
- Default action: ALLOW
- LOG action on everything (no blocking)
- Good for auditing before enforcing

---

## 7. File Structure

```
mcpguard/
├── README.md                   # Full docs, quick start, examples
├── LICENSE                     # MIT
├── pyproject.toml              # Package config, dependencies
├── mcpguard/
│   ├── __init__.py             # Version, public API exports
│   ├── cli.py                  # Click/Typer CLI (run, validate, stats, init, test)
│   ├── proxy.py                # MCP stdio proxy (asyncio subprocess)
│   ├── policy.py               # YAML policy engine (parse, evaluate)
│   ├── audit.py                # Structured JSON-lines audit logging
│   ├── rate_limiter.py         # Token bucket rate limiter
│   ├── approval.py             # Interactive /dev/tty human approval
│   ├── middleware.py           # FastMCP middleware adapter
│   └── exceptions.py           # McpGuardDenied, McpGuardRateLimited
├── policies/
│   ├── default.yaml            # Sensible defaults
│   ├── strict.yaml             # Maximum security
│   └── permissive.yaml         # Log-only
├── tests/
│   ├── conftest.py             # Shared fixtures
│   ├── test_policy.py          # Policy engine unit tests (~30 tests)
│   ├── test_proxy.py           # Proxy integration tests (~15 tests)
│   ├── test_audit.py           # Audit logger tests (~10 tests)
│   ├── test_rate_limiter.py    # Rate limiter tests (~10 tests)
│   ├── test_cli.py             # CLI tests (~10 tests)
│   ├── test_middleware.py      # FastMCP middleware tests (~10 tests)
│   └── test_e2e.py             # End-to-end with real MCP server (~5 tests)
├── examples/
│   ├── claude-code.md          # How to use with Claude Code
│   ├── cursor.md               # How to use with Cursor
│   ├── langchain.md            # How to use with LangChain
│   └── custom-agent.md         # How to use programmatically
└── docs/
    ├── policy-reference.md     # Full policy language docs
    └── architecture.md         # Design decisions
```

---

## 8. Dependencies

### Runtime
```toml
[project]
dependencies = [
    "pyyaml>=6.0",      # YAML parsing
    "click>=8.0",        # CLI framework
    "rich>=13.0",        # Pretty terminal output (stats, tables)
]

[project.optional-dependencies]
fastmcp = ["fastmcp>=2.9"]  # Optional: FastMCP middleware support
```

### Dev
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.3",         # Linting
    "mypy>=1.8",         # Type checking
]
```

**Note:** Zero ML dependencies. Zero LLM dependencies. This is a security tool — it should be lightweight and auditable.

---

## 9. Build Plan (Day-by-Day)

> **Important Instruction**: After every milestone (or day), you MUST review your work. Make sure your milestone output builds. Make sure there are tests and they run successfully. Make sure the milestone is completely fulfilled by comparing against the spec.
> **Documentation Instruction**: You MUST save the implementation planning files tagged as "day1_implementation_plan.md", "day2_..." etc. explicitly to the `docs/` folder for every passing milestone.

### Day 1: Scaffold + Policy Engine Core
- [ ] Create repo, pyproject.toml, CI (GitHub Actions)
- [ ] Implement `Policy`, `Rule`, `PolicyResult` dataclasses
- [ ] Implement `PolicyEngine.from_yaml()` — parse YAML into Policy objects
- [ ] Implement `PolicyEngine.evaluate()` — pattern matching logic
- [ ] Write 15+ unit tests for policy evaluation (test_policy.py)
- [ ] Deliverable: `mcpguard validate --config test.yaml` works

### Day 2: Policy Engine Completeness
- [ ] Add `prefix`, `not_prefix`, `contains`, `not_contains`, `max_length` rules
- [ ] Add priority sorting (first-match-wins)
- [ ] Add `enabled` field support
- [ ] Implement `mcpguard test --tool X --args '{}'` CLI command
- [ ] Write 15 more tests covering edge cases
- [ ] Deliverable: Can test any policy offline

### Day 3: MCP Proxy — Basic Pass-through
- [ ] Implement `McpProxy` with asyncio subprocess management
- [ ] Implement stdio message reading (newline-delimited JSON-RPC)
- [ ] Implement transparent pass-through (no policy evaluation yet)
- [ ] Test with a real MCP server (use `npx @anthropic/mcp-filesystem`)
- [ ] Deliverable: `mcpguard run -- npx @anthropic/mcp-filesystem /tmp` passes all messages

### Day 4: MCP Proxy — Policy Integration
- [ ] Wire PolicyEngine into proxy's `_handle_client_message`
- [ ] Intercept `tools/call` method, extract name + arguments
- [ ] Return JSON-RPC error for DENY'd calls
- [ ] Forward ALLOW'd calls to upstream
- [ ] Write integration tests (test_proxy.py)
- [ ] Deliverable: Can actually block dangerous commands

### Day 5: Audit Logger
- [ ] Implement AuditLogger with JSON-lines output
- [ ] Wire into proxy
- [ ] Add `--log` flag to CLI
- [ ] Write tests (test_audit.py)
- [ ] Deliverable: Every tool call securely logged

### Day 6: Human Approval + Polish
- [ ] Implement ApprovalHandler using /dev/tty
- [ ] Wire APPROVE action into proxy
- [ ] Create `default.yaml` and `permissive.yaml` presets
- [ ] Implement `mcpguard init` command
- [ ] Deliverable: Full policy action set working

### Day 7: FastMCP Middleware + Stats
- [ ] Implement McpGuardMiddleware for FastMCP
- [ ] Implement `mcpguard stats` dashboard using rich tables
- [ ] Write middleware tests (test_middleware.py)
- [ ] Deliverable: Both proxy and middleware modes complete

### Day 8-9: End-to-End Testing
- [ ] Write E2E tests with real MCP servers
- [ ] Test with Claude Code configuration (document in examples/)
- [ ] Test with Cursor configuration
- [ ] Fix all bugs found
- [ ] Deliverable: Battle-tested

### Day 10: README + Docs
- [ ] Write comprehensive README with quick start
- [ ] Write policy-reference.md
- [ ] Write example docs (claude-code.md, cursor.md, langchain.md)
- [ ] Add ASCII architecture diagrams
- [ ] Deliverable: Someone can use it from README alone

### Day 11: PyPI + GitHub Actions
- [ ] Set up PyPI publishing
- [ ] Set up GitHub Actions CI (lint, test, type-check)
- [ ] Add badges to README
- [ ] `pip install mcpguard` works
- [ ] Deliverable: Published on PyPI

### Day 12: Launch
- [ ] Post to Hacker News ("Show HN: mcpguard — iptables for AI agents")
- [ ] Post to Reddit r/MachineLearning, r/LocalLLaMA, r/artificial
- [ ] Tweet thread with demo GIF
- [ ] Deliverable: Public launch

### Day 13-14: Article + Paper
- [ ] Write Medium article: "Why Your AI Agent Needs a Firewall"
- [ ] Draft arXiv paper: "mcpguard: Policy Enforcement for MCP-Based AI Agents"
- [ ] Deliverable: Publication pipeline started

---

## 10. Testing Strategy

### Unit tests (test_policy.py) — ~30 tests

```python
# Pattern matching
def test_deny_destructive_command():
    engine = PolicyEngine.from_yaml("policies/default.yaml")
    result = engine.evaluate("run_command", {"command": "rm -rf /"})
    assert result.action == "DENY"

def test_allow_safe_command():
    result = engine.evaluate("run_command", {"command": "ls -la"})
    assert result.action == "ALLOW"

def test_deny_sensitive_file_read():
    result = engine.evaluate("read_file", {"path": "/home/user/.ssh/id_rsa"})
    assert result.action == "DENY"

def test_allow_project_file_read():
    result = engine.evaluate("read_file", {"path": "/home/user/project/main.py"})
    assert result.action == "ALLOW"

# Prefix rules
def test_not_prefix_blocks_outside_project():
    ...

# Priority
def test_higher_priority_wins():
    ...

# Edge cases
def test_missing_argument_passes():
    """If policy checks 'command' but tool call has no 'command' arg, skip."""
    ...

def test_empty_arguments():
    ...

def test_regex_special_characters():
    ...

def test_case_insensitive_matching():
    ...
```

### Integration tests (test_proxy.py) — ~15 tests

```python
@pytest.mark.asyncio
async def test_proxy_blocks_denied_call():
    """Start proxy with deny policy, send tools/call, expect error response."""
    ...

@pytest.mark.asyncio
async def test_proxy_forwards_allowed_call():
    """Start proxy with allow policy, send tools/call, expect upstream response."""
    ...

@pytest.mark.asyncio
async def test_proxy_passes_non_tool_messages():
    """tools/list, initialize, etc. should pass through unchanged."""
    ...
```

### E2E tests (test_e2e.py) — ~5 tests

```python
@pytest.mark.asyncio
async def test_e2e_with_echo_server():
    """
    1. Start a simple echo MCP server (fixture)
    2. Start mcpguard proxy in front of it
    3. Send tool calls
    4. Verify blocked calls get error
    5. Verify allowed calls get echo response
    6. Verify audit log has correct entries
    """
    ...
```

---

## 11. Distribution & Launch

### PyPI

```toml
# pyproject.toml
[project]
name = "mcpguard"
version = "0.1.0"
description = "A firewall for MCP-based AI agents — intercepts and evaluates tool calls against YAML policies"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
keywords = ["mcp", "ai", "security", "firewall", "agents", "llm", "tool-calls"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Topic :: Security",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

[project.scripts]
mcpguard = "mcpguard.cli:main"

[project.urls]
Homepage = "https://github.com/moluqman/mcpguard"
Documentation = "https://github.com/moluqman/mcpguard#readme"
Issues = "https://github.com/moluqman/mcpguard/issues"
```

### Usage examples for README

```bash
# Install
pip install mcpguard

# Generate starter config
mcpguard init

# Run with Claude Code's filesystem server
mcpguard run --config mcpguard.yaml -- npx @anthropic/mcp-filesystem /home/user/project

# Test a policy without running a server
mcpguard test --config mcpguard.yaml --tool run_command --args '{"command": "rm -rf /"}'
# Output: DENIED by policy 'block-destructive-shell': Destructive command blocked

# View audit stats
mcpguard stats --log mcpguard_audit.jsonl
```

---

## 12. Publication Strategy

### Medium article (Day 13)
**Title:** "Why Your AI Agent Needs a Firewall (And How to Build One)"
- Hook: July 2025 database deletion incident
- Problem: no enforcement layer between agent and tools
- Solution: mcpguard
- Demo with screenshots
- Link to GitHub

### arXiv paper (Day 14 draft, submit within month)
**Title:** "mcpguard: A Policy Enforcement Architecture for MCP-Based AI Agents"
- Abstract: Growing attack surface of agentic AI at tool call layer
- Related work: LLM Guard, NeMo, FastMCP middleware, Golf, agentgateway
- Architecture: proxy pattern, policy language, audit trail
- Evaluation: latency overhead (<1ms per call), policy expressiveness
- Case studies: blocking exfiltration, preventing destructive commands
- Discussion: limitations, future work (ML-based anomaly detection)

### Conference targets
1. **USENIX Security 2027** (submit by Feb 2027)
2. **IEEE S&P Workshop on AI Security** (varies)
3. **NeurIPS 2026 Workshop** (if framed as safety research)

---

## Appendix A: Example Policy Files

### default.yaml

```yaml
version: "1"
default_action: ALLOW

policies:
  - name: block-destructive-shell
    description: Block dangerous shell commands
    tools: ["run_command", "shell_exec", "execute_command", "bash"]
    action: DENY
    priority: 100
    rules:
      - argument: command
        pattern: "rm\\s+-r|rm\\s+-f|rmdir|mkfs|dd\\s+if=|:(\\)\\{\\s+:|shutdown|reboot|halt|init\\s+0|kill\\s+-9\\s+1|format\\s+c:"
        message: "Destructive command blocked"

  - name: block-sensitive-file-read
    description: Block reading sensitive files
    tools: ["read_file", "view_file", "cat", "open"]
    action: DENY
    priority: 90
    rules:
      - argument: path
        pattern: "\\.ssh/|\\.env$|\\.aws/|credentials|secret|private_key|\\.gnupg/|\\.kube/config"
        message: "Reading sensitive file blocked"

  - name: block-exfiltration
    description: Block sending data to external endpoints
    tools: ["http_request", "fetch", "curl", "wget"]
    action: DENY
    priority: 80
    rules:
      - argument: url
        pattern: "10\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|192\\.168\\.|localhost|127\\.0\\.0\\.1|metadata\\.google|169\\.254\\."
        message: "Access to internal/metadata network blocked"

  - name: rate-limit-http
    description: Rate limit outbound HTTP requests
    tools: ["http_request", "fetch", "curl"]
    action: RATE_LIMIT
    priority: 50
    max_calls: 20
    per_seconds: 60

  - name: log-file-writes
    description: Log all file modifications
    tools: ["write_file", "edit_file", "create_file", "delete_file", "replace_file"]
    action: LOG
    priority: 10
```

---

## 13. Design Decisions Log

Decisions made during development, recorded for traceability.

| Decision | Choice | Rationale |
|---|---|---|
| **DPR hash chain** | ✅ Included | ~15 lines of code, makes audit trail tamper-evident. Big credibility boost for a security tool. Taken from faramesh-core concept. |
| **Kill switch** | ✅ Included (Day 6) | File-based kill switch (`mcpguard.kill`) that immediately blocks ALL tool calls. Trivial to implement, huge safety value. |
| **Post-execution response scanning** | ✅ Included (Day 4) | After forwarding an allowed call, scan the RESPONSE for leaked secrets (AWS keys, private keys, tokens). ~20 lines of regex patterns. |
| **DEFER action (async approval)** | ❌ Skipped for v1 | Would write pending approvals to a file for another process to approve. Adds complexity. APPROVE stays CLI-only (`/dev/tty`) for now. Revisit in v2. |
| **WAL-first logging** | ❌ Skipped | Write audit BEFORE returning decision is theoretically better for forensics, but adds complexity. We log after the decision for simplicity. |
| **expr-lang expressions** | ❌ v2 roadmap | `when: 'args["amount"] > 500'` would be more powerful than regex rules, but adds a dependency. Keep regex for v1. |
| **Multi-agent governance** | ❌ Skipped | Too complex for MVP. |
| **eBPF / SPIFFE / K8s** | ❌ Skipped | Enterprise bloat, not our niche. |
| **Elastic License** | ❌ Kept MIT | Max adoption for NIW case. |
| **faramesh-core duplication** | ✅ Intentional | faramesh-core is Go+Python, Elastic License, complex. If an idea is sound, we implement it in our simpler pure-Python MIT tool regardless of whether faramesh has it. |
| **Project location** | `~/Projects/vibecoded/mcpguard/` | Lives alongside other vibecoded projects. |

---

*Last updated: March 2026*
*Author: Mohammad Luqman*
