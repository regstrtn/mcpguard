"""mcpguard.exceptions — Custom exception types."""


class McpGuardError(Exception):
    """Base exception for mcpguard."""


class McpGuardDenied(McpGuardError):
    """Raised when a tool call is denied by policy."""

    def __init__(self, tool: str, policy: str, reason: str):
        self.tool = tool
        self.policy = policy
        self.reason = reason
        super().__init__(f"Tool '{tool}' denied by policy '{policy}': {reason}")


class PolicyLoadError(McpGuardError):
    """Raised when a policy file cannot be loaded or parsed."""


class PolicyValidationError(McpGuardError):
    """Raised when a policy file has invalid structure or values."""
