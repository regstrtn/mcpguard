import asyncio
import logging
from typing import Callable, Any

try:
    from fastmcp.server.middleware import Middleware, MiddlewareContext  # type: ignore
except ImportError:
    # Fallback for optional dependency
    class Middleware:  # type: ignore
        pass
    class MiddlewareContext:  # type: ignore
        pass

from mcpguard.policy import PolicyEngine, Action
from mcpguard.audit import AuditLogger, AuditEvent
from mcpguard.exceptions import McpGuardDenied

logger = logging.getLogger(__name__)

class McpGuardMiddleware(Middleware):
    """
    FastMCP Middleware utilizing mcpguard policies.
    
    Intercepts tools/call inside FastMCP servers to enforce security rules.
    """
    def __init__(self, policy_engine: PolicyEngine, audit_logger: AuditLogger | None = None):
        self.policy_engine = policy_engine
        self.audit_logger = audit_logger

    @classmethod
    def from_yaml(cls, path: str, audit_log_path: str | None = None) -> "McpGuardMiddleware":
        """Load middleware using a YAML policy configuration."""
        engine = PolicyEngine.from_yaml(path)
        logger = AuditLogger(audit_log_path) if audit_log_path else None
        return cls(engine, logger)

    async def on_call_tool(self, context: MiddlewareContext, call_next: Callable) -> Any:
        """
        Intercept tool calls in FastMCP.
        
        Args:
            context: FastMCP MiddlewareContext containing request details.
            call_next: The next middleware or handler chain executor.
        """
        tool_name = getattr(context.message, "name", None)
        arguments = getattr(context.message, "arguments", {}) or {}

        if not tool_name:
            return await call_next(context)

        # Evaluate policy
        result = self.policy_engine.evaluate(tool_name, arguments)

        if self.audit_logger:
            self.audit_logger.log(
                tool=tool_name,
                arguments=arguments,
                action=result.action.name,
                matched_policy=result.matched_policy,
                reason=result.reason
            )

        if result.action == Action.DENY:
            raise McpGuardDenied(
                tool=tool_name,
                policy=result.matched_policy or "unknown",
                reason=result.reason or "Denied by policy",
            )

        if result.action == Action.APPROVE:
            # For FastMCP, interactive TTY prompts might hijack the server stream if running on a terminal,
            # but usually FastMCP apps run in background. We attempt approval via ApprovalHandler if TTY is available.
            from mcpguard.approval import ApprovalHandler
            handler = ApprovalHandler()
            try:
                approved = await handler.request_approval(tool_name, arguments, result.reason or "")
                if not approved:
                    if self.audit_logger:
                         self.audit_logger.log(
                             tool=tool_name, arguments=arguments, action="APPROVE_NO",
                             matched_policy=result.matched_policy, reason="User denied approval"
                         )
                    raise McpGuardDenied(
                        tool=tool_name,
                        policy=result.matched_policy or "unknown",
                        reason="User denied approval",
                    )
            except Exception as e:
                # Fallback to deny if prompt fails
                logger.error(f"Approval prompt failed: {e}")
                raise McpGuardDenied(
                    tool=tool_name,
                    policy=result.matched_policy or "unknown",
                    reason=f"Approval prompt failed: {e}",
                )

        return await call_next(context)

def wrap_fastmcp(mcp_server: Any, policy_engine: PolicyEngine, audit_logger: AuditLogger | None = None) -> Any:
    """
    A helper to wrap an existing FastMCP server programmatically if Middleware is not supported.
    
    This overrides the `call_tool` method dynamically.
    """
    if hasattr(mcp_server, "add_middleware") and callable(mcp_server.add_middleware):
         mcp_server.add_middleware(McpGuardMiddleware(policy_engine, audit_logger))
         return mcp_server

    # Fallback to monkeypatching `call_tool` if add_middleware is missing
    original_call_tool = getattr(mcp_server, "call_tool", None)
    if not original_call_tool:
         logger.warning("mcp_server does not have call_tool method. Skipping wrap.")
         return mcp_server

    async def secure_call_tool(name: str, arguments: dict | None = None) -> Any:
         args = arguments or {}
         result = policy_engine.evaluate(name, args)

         if audit_logger:
              audit_logger.log(
                   tool=name, arguments=args, action=result.action.name,
                   matched_policy=result.matched_policy, reason=result.reason
              )

         if result.action == Action.DENY:
              raise ValueError(f"McpGuard: Blocked tool '{name}'")
         
         if result.action == Action.APPROVE:
              from mcpguard.approval import ApprovalHandler
              handler = ApprovalHandler()
              approved = await handler.request_approval(name, args, result.reason or "")
              if not approved:
                   raise ValueError(f"McpGuard: User denied approval for '{name}'")

         return await original_call_tool(name, arguments)

    setattr(mcp_server, "call_tool", secure_call_tool)
    return mcp_server
