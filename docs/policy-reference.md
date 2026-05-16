# mcpguard Policy Reference

This document describes the full policy language supported by mcpguard.

## File Format

Policy files are YAML documents with the following top-level structure:

```yaml
version: "1"
default_action: ALLOW
policies:
  - name: policy-name
    # ... policy definition
```

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | No | Policy format version (currently `"1"`) |
| `default_action` | string | No | Action when no policy matches. Default: `ALLOW` |
| `policies` | list | Yes | Ordered list of policy definitions |

## Policy Definition

Each policy in the `policies` list has the following fields:

```yaml
- name: block-destructive-shell
  description: "Block dangerous shell commands"
  priority: 100
  enabled: true
  tools:
    - "run_command"
    - "shell_.*"
  action: DENY
  rules:
    - argument: command
      pattern: "rm\\s+-rf"
      message: "Destructive command blocked"
```

### Policy Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier for the policy |
| `description` | string | No | Human-readable description |
| `priority` | integer | No | Higher values evaluate first. Default: `0` |
| `enabled` | boolean | No | Set to `false` to skip this policy. Default: `true` |
| `tools` | list[string] | Yes | Tool name patterns to match (regex supported) |
| `action` | string | Yes | Action to take: `ALLOW`, `DENY`, `APPROVE`, or `LOG` |
| `rules` | list[Rule] | No | Argument inspection rules. If absent, matches unconditionally |

## Tool Matching

The `tools` field is a list of patterns that match against tool names. Each pattern is treated as a **regex**:

```yaml
tools:
  - "run_command"          # Exact match
  - "shell_.*"             # Matches shell_exec, shell_run, etc.
  - ".*"                   # Catch-all: matches any tool
  - "read_file|view_file"  # Multiple tools via regex alternation
```

Matching is **case-insensitive**.

## Rule Types

Rules inspect the **arguments** of a tool call. All rules within a policy must match for the policy to trigger (AND logic).

### `pattern` — Regex Match

Matches if the argument value matches the regex pattern.

```yaml
rules:
  - argument: command
    pattern: "rm\\s+-rf|mkfs|dd\\s+if="
```

### `not_pattern` — Negative Regex Match

Matches if the argument value does NOT match the regex pattern. Use to create allowlists.

```yaml
rules:
  - argument: command
    not_pattern: "rm\\s+-r|shutdown|reboot"
```

### `prefix` — String Prefix Match

Matches if the argument value starts with any of the given prefixes.

```yaml
rules:
  - argument: path
    prefix:
      - "/home/user/workspace/"
      - "/tmp/"
```

### `not_prefix` — Negative Prefix Match

Matches if the argument value does NOT start with any of the given prefixes.

```yaml
rules:
  - argument: path
    not_prefix:
      - "/etc/"
      - "/root/"
      - "/sys/"
```

### `contains` — Substring Match

Matches if the argument value contains any of the given substrings. Case-insensitive.

```yaml
rules:
  - argument: command
    contains:
      - "chmod 777"
      - "chown root"
      - "passwd"
```

### `not_contains` — Negative Substring Match

Matches if the argument value does NOT contain any of the given substrings. Case-insensitive.

```yaml
rules:
  - argument: url
    not_contains:
      - "webhook.site"
      - "ngrok"
      - "burpcollaborator"
```

### `max_length` — Maximum Length

Matches if the argument value exceeds the given character length. Use to prevent command injection via very long arguments.

```yaml
rules:
  - argument: command
    max_length: 500
```

### `message` — Custom Denial Message

Attached to the policy result when the rule matches. Shows in error responses and audit logs.

```yaml
rules:
  - argument: command
    pattern: "rm\\s+-rf"
    message: "Destructive command blocked by security policy"
```

## Actions

### `ALLOW`

Forward the tool call to the upstream MCP server without modification.

### `DENY`

Block the tool call and return a JSON-RPC error response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "Blocked by policy 'block-destructive-shell': Destructive command blocked"
  }
}
```

### `APPROVE`

Prompt the user for interactive approval via `/dev/tty`. This avoids interfering with the MCP stdio channel.

```
⚠️  APPROVE required for tool call:
  Tool: run_command
  Arguments: {"command": "pip install requests"}
  Policy: approve-installs
Allow? [y/N]:
```

If denied, behaves like `DENY`. If approved, behaves like `ALLOW`.

### `LOG`

Forward the tool call but record it in the audit log. Useful for monitoring without blocking.

## Evaluation Order

1. Policies are sorted by `priority` (descending — highest first).
2. For each policy, check if any `tools` pattern matches the tool name.
3. If tools match, evaluate all `rules`. All rules must match (AND logic).
4. **First matching policy wins** — no further policies are evaluated.
5. If no policy matches, `default_action` is used.

## Multiple Rules (AND Logic)

When a policy has multiple rules, ALL must match:

```yaml
- name: approve-large-writes
  tools: ["write_file"]
  action: APPROVE
  rules:
    # Both must match:
    - argument: path
      prefix: ["/production/"]
    - argument: content
      max_length: 10000
```

## Examples

### Block Secret Exfiltration

```yaml
- name: block-data-exfiltration
  description: "Block common data exfiltration endpoints"
  priority: 80
  tools: ["http_request", "fetch", "curl"]
  action: DENY
  rules:
    - argument: url
      pattern: "webhook\\.site|requestbin|pipedream|ngrok|burpcollaborator"
      message: "Potential data exfiltration blocked"
```

### Approve All File Writes in Production

```yaml
- name: approve-production-writes
  description: "Require human approval for production writes"
  priority: 90
  tools: ["write_file", "create_file"]
  action: APPROVE
  rules:
    - argument: path
      prefix: ["/production/", "/live/"]
```

### Log Everything (Permissive Mode)

```yaml
default_action: ALLOW
policies:
  - name: log-all
    tools: [".*"]
    action: LOG
    priority: 1
```

### Deny by Default (Strict Mode)

```yaml
default_action: DENY
policies:
  - name: allow-safe-reads
    tools: ["read_file"]
    action: APPROVE
    priority: 100
    rules:
      - argument: path
        not_contains: [".ssh", ".env", "credentials"]
```
