# Onboarding Wizard & Sandbox Mode (DX Improvements)

To prepare `mcpguard` for a broader release (e.g., Hacker News, Reddit Product Post), we want to lower onboarding friction and solve absolute path safety natively.

---

## 1. 🧙 Automated Setup Wizard
To decouple manual `config.json` editing (brittle JSON framing arrays), we should expose commands that find and automatically wrap the proxy chain:

*   **Syntax**: `mcpguard add <server-name> --command "npx ..."`
*   **Target Files for Auto-Discovery**:
    *   **Claude Desktop**: `~/.config/Claude/claude_desktop_config.json`
    *   **Cursor**: Workspace setting layers.
*   **Logic Model**:
    1. Backup existing full `.json` structure safely.
    2. Read JSON structure, parse `"command"`, and shift it into `args: ["run", "--", "original_command", ...]`.
    3. Save maintaining backups correctly.

---

## 2. 📁 Native Workspace Sandbox Scope
Provide rigid guards for absolute locations that avoid relying purely on YAML regex variables.

*   **Flag Parameter**: `mcpguard run --sandbox /path/to/workspace -- ...`
*   **Logic Model**:
    *   In `McpProxy`, check whether the tool call includes argument keywords like `path` or `TargetFile`.
    *   If that absolute traverses outside the `--sandbox` scope (e.g., `/tmp` or `/etc`), throw an instant `Action.DENY` immediately without relying on downstream traversal regex matches.
    *   Treats workspace sandbox locks as strict deterministic fast-path overrides.

---

## 📅 Next Goals after Testing
1. Execute CLI setups inside `cli.py` or `.install` wrappers.
2. Verify absolute location rejection loops.
