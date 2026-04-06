import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from mcpguard.middleware import McpGuardMiddleware, wrap_fastmcp
from mcpguard.policy import PolicyEngine, Action
from mcpguard.audit import AuditLogger

@pytest.fixture
def mock_policy_engine():
    engine = MagicMock(spec=PolicyEngine)
    engine.evaluate.return_value = MagicMock(
        action=Action.ALLOW, matched_policy=None, reason=None
    )
    return engine

@pytest.fixture
def mock_audit_logger():
    return MagicMock(spec=AuditLogger)

@pytest.fixture
def mock_middleware_context():
    # Mock FastMCP MiddlewareContext
    context = MagicMock()
    context.message = MagicMock()
    context.message.name = "test_tool"
    context.message.arguments = {"arg1": "value1"}
    return context

@pytest.mark.asyncio
async def test_mcp_guard_middleware_allow(mock_policy_engine, mock_audit_logger, mock_middleware_context):
    middleware = McpGuardMiddleware(mock_policy_engine, mock_audit_logger)
    call_next = AsyncMock(return_value="success")

    result = await middleware.on_call_tool(mock_middleware_context, call_next)

    # Assertions
    assert result == "success"
    mock_policy_engine.evaluate.assert_called_once_with("test_tool", {"arg1": "value1"})
    mock_audit_logger.log.assert_called_once()
    call_next.assert_called_once_with(mock_middleware_context)

@pytest.mark.asyncio
async def test_mcp_guard_middleware_deny(mock_policy_engine, mock_audit_logger, mock_middleware_context):
    from mcpguard.exceptions import McpGuardDenied

    # Configure mock to Deny
    mock_policy_engine.evaluate.return_value = MagicMock(
        action=Action.DENY, matched_policy="block-test", reason="Blocked for test"
    )
    
    middleware = McpGuardMiddleware(mock_policy_engine, mock_audit_logger)
    call_next = AsyncMock()

    with pytest.raises(McpGuardDenied) as exc_info:
        await middleware.on_call_tool(mock_middleware_context, call_next)

    # Assertions
    assert "Blocked by policy 'block-test'" in str(exc_info.value)
    mock_audit_logger.log.assert_called_once()
    call_next.assert_not_called()

@pytest.mark.asyncio
async def test_wrap_fastmcp_add_middleware(mock_policy_engine, mock_audit_logger):
    mcp_server = MagicMock()
    mcp_server.add_middleware = MagicMock()
    
    wrapped = wrap_fastmcp(mcp_server, mock_policy_engine, mock_audit_logger)
    
    # Assertions
    assert wrapped == mcp_server
    mcp_server.add_middleware.assert_called_once()

@pytest.mark.asyncio
async def test_wrap_fastmcp_monkeypatch(mock_policy_engine, mock_audit_logger):
    mcp_server = MagicMock()
    # Delete add_middleware if present on dict to trigger fallback
    if hasattr(mcp_server, "add_middleware"):
        del mcp_server.add_middleware
        
    original_call = AsyncMock(return_value="original_result")
    mcp_server.call_tool = original_call

    wrapped = wrap_fastmcp(mcp_server, mock_policy_engine, mock_audit_logger)

    # Test the patched call_tool
    result = await mcp_server.call_tool("patched_tool", {"patch": "yes"})
    
    # Assertions
    assert result == "original_result"
    mock_policy_engine.evaluate.assert_called_once_with("patched_tool", {"patch": "yes"})
    mock_audit_logger.log.assert_called_once()
    original_call.assert_called_once_with("patched_tool", {"patch": "yes"})
