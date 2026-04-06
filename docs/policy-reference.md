# Policy Reference

`mcpguard` enables you to define firewall policies for AI tool calls using a structured YAML format.

---

## 📋 Full YAML Schema

```yaml
version: "1"                    # Schema version
default_action: ALLOW           # ALLOW or DENY. What happens when no policy matches.

policies:
  - name: string                # Required. Unique identifier.
    description: string         # Optional. Human-readable description.
    enabled: true               # Optional. Default true.
    priority: 0                 # Optional. Higher = evaluated first. Default 0.
    tools:                      # Required. List of tool name patterns (regex).
      - "run_command"
    action: DENY                # Required. DENY | ALLOW | APPROVE | LOG
    
    # Argument inspection rules. ALL rules must match for the policy to trigger.
    rules:
      - argument: "command"     # Which argument key to inspect
        pattern: "rm -rf|mkfs"  # Regex. If matches → rule triggers.
        not_pattern: "^ls "     # Regex. If matches → rule does NOT trigger.
        prefix:                 # Allowed prefixes. Value must start with one.
          - "/safe/path/"
        not_prefix:             # Blocked prefixes. Value must NOT start with any.
          - "/etc/"
        contains:               # Value must contain at least one of these.
          - "sudo"
        not_contains:           # Value must NOT contain any of these.
          - "password"
        max_length: 1000        # Max character length of argument string.
```

---

## ⚙️ Actions

| Action | Description |
| :--- | :--- |
| `ALLOW` | Proceed with forwarding tool call to upstream server. |
| `DENY` | Immediately return standard JSON-RPC error. Do not forward. |
| `APPROVE` | Block and prompt user on dashboard/Tty buffer for y/n response interactively. |
| `LOG` | Record in audit trail but continue allowing execution otherwise. |

---

## 🛠️ Matching logic

1. Sorted by **priority** (highest first).
2. Filtered by **tool name** regex list.
3. Logical **AND** is applied to multiple `rules:` inside the block. All must match to evaluated action constraint on policy tier!
4. Default fallback condition defaults to `ALLOW` unless overridden inside the header of document definition setups explicitly.
