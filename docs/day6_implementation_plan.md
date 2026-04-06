# Day 6: Human Approval + Polish

Implement an interactive human approval handler using `/dev/tty` for non-blocking confirmation prompts.

## User Review Required

> [!NOTE]
> This is a retroactive plan for work already implemented in `mcpguard/approval.py` and `mcpguard/proxy.py`.

## Proposed Changes

### [Component Name] Human Approval handler

#### [NEW] [approval.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/approval.py)
-   Implement `ApprovalHandler` using prompt streams reading `/dev/tty`.
-   Implement `ApprovalHandler.request_approval(tool_name, arguments, reason)` suspending loop prompts.

#### [NEW] [proxy.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/proxy.py)
-   Wire `ApprovalHandler` `Action.APPROVE` triggers into call intercepts.

#### [NEW] [cli.py](file:///usr/local/google/home/moluqman/Projects/vibecoded/mcpguard/mcpguard/cli.py)
-   Implement `mcpguard init` creating starter `policies/default.yaml` configs.

## Verification Plan

### Automated Tests
-   Standalone evaluation testing prompts triggers accurate intercepts locally.

### Manual Verification
-   Run `mcpguard run` loading `Action.APPROVE` rules. Confirm prompt blocks accurately and forwards on approval matches.
