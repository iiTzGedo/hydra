"""
MCP Tool Registry Module.

Provides a decorator-based registry pattern for defining MCP tools.
Each tool's schema and implementation are defined together, eliminating
the duplication between list_tools() and _execute_tool().

Usage:
    @tool(
        name="list_nodes",
        description="List infrastructure nodes",
        schema={...}
    )
    async def list_nodes(args: dict) -> str:
        ...

    # In server.py:
    tools = get_all_tools()  # Returns list of Tool objects
    result = await execute_tool("list_nodes", {...})
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import jsonschema
from mcp.types import Tool

from hydra_mcp.auth import SourceRestrictionError, check_permission, get_auth_context


class ToolValidationError(Exception):
    """Raised when tool input validation fails against the schema."""

    def __init__(self, tool_name: str, message: str, errors: list[str] | None = None):
        self.tool_name = tool_name
        self.errors = errors or []
        super().__init__(f"Validation failed for tool '{tool_name}': {message}")


@dataclass
class RegisteredTool:
    """A registered tool with its schema and implementation."""

    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[str]]
    required_permission: str | None = None
    internal_only: bool = False


# Global tool registry
_tool_registry: dict[str, RegisteredTool] = {}


def tool(
    name: str,
    description: str,
    schema: dict[str, Any],
    required_permission: str | None = None,
    internal_only: bool = False,
) -> Callable[[Callable[[dict[str, Any]], Awaitable[str]]], Callable[[dict[str, Any]], Awaitable[str]]]:
    """Decorator to register an MCP tool.

    Args:
        name: The tool name (must be unique).
        description: Human-readable description of the tool.
        schema: JSON Schema for the tool's input parameters.
        required_permission: Optional permission required to execute this tool.
        internal_only: If True, tool can only be called from internal (hydra-web) clients.

    Returns:
        Decorator function that registers the tool handler.

    Example:
        @tool(
            name="list_nodes",
            description="List infrastructure nodes with optional filters",
            schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 50}
                }
            },
            required_permission="nodes:read"
        )
        async def list_nodes(args: dict) -> str:
            nodes, _ = await client.list_nodes(limit=args.get("limit", 50))
            return format_response("nodes", nodes)
    """
    def decorator(handler: Callable[[dict[str, Any]], Awaitable[str]]) -> Callable[[dict[str, Any]], Awaitable[str]]:
        if name in _tool_registry:
            raise ValueError(f"Tool '{name}' is already registered")

        _tool_registry[name] = RegisteredTool(
            name=name,
            description=description,
            schema=schema,
            handler=handler,
            required_permission=required_permission,
            internal_only=internal_only,
        )
        return handler

    return decorator


def get_all_tools() -> list[Tool]:
    """Get all registered tools as MCP Tool objects.

    Returns:
        List of Tool objects for use in list_tools().
    """
    return [
        Tool(
            name=reg_tool.name,
            description=reg_tool.description,
            inputSchema=reg_tool.schema,
        )
        for reg_tool in _tool_registry.values()
    ]


def get_tool(name: str) -> RegisteredTool | None:
    """Get a registered tool by name.

    Args:
        name: The tool name.

    Returns:
        RegisteredTool if found, None otherwise.
    """
    return _tool_registry.get(name)


def validate_tool_args(name: str, args: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate tool arguments against the tool's JSON schema.

    Args:
        name: The tool name (for error messages).
        args: Tool arguments to validate.
        schema: JSON Schema to validate against.

    Raises:
        ToolValidationError: If validation fails.
    """
    try:
        jsonschema.validate(instance=args, schema=schema)
    except jsonschema.ValidationError as e:
        # Build list of all validation errors
        validator = jsonschema.Draft7Validator(schema)
        errors = [err.message for err in validator.iter_errors(args)]
        raise ToolValidationError(
            tool_name=name,
            message=e.message,
            errors=errors,
        ) from e


async def execute_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a registered tool with validation and authorization.

    This function validates arguments against the tool's schema, then
    checks permissions before executing the tool. If no authorization
    context is set (e.g., local development), authorization is bypassed.

    Args:
        name: The tool name.
        args: Tool arguments.

    Returns:
        Tool execution result as a string.

    Raises:
        ValueError: If the tool is not found.
        ToolValidationError: If arguments don't match the tool's schema.
        AuthorizationError: If the current context lacks required permissions.
    """
    reg_tool = _tool_registry.get(name)
    if not reg_tool:
        raise ValueError(f"Unknown tool: {name}")

    # Validate arguments against schema before executing
    validate_tool_args(name, args, reg_tool.schema)

    # Check authorization before executing
    check_permission(name, reg_tool.required_permission)

    # Check source restriction for internal-only tools
    if reg_tool.internal_only:
        ctx = get_auth_context()
        if ctx is None or ctx.source_type != "internal":
            action = args.get("action", "unknown")
            raise SourceRestrictionError(
                tool=name,
                action=action,
                context={
                    "requestedAction": action,
                    "guidance": (
                        "You can perform this action from the Hydra Command Center "
                        "or use the integrated chat in the Hydra web interface which "
                        "has full control permissions."
                    ),
                    "alternativeActions": [
                        "I can show you the current status of this resource",
                        "I can list recent commands executed on this resource",
                        "I can describe this resource based on its profile",
                    ],
                },
            )

    return await reg_tool.handler(args)


def get_tool_permission(name: str) -> str | None:
    """Get the required permission for a tool.

    Args:
        name: The tool name.

    Returns:
        The required permission string, or None if no permission is required.
    """
    reg_tool = _tool_registry.get(name)
    return reg_tool.required_permission if reg_tool else None


def list_tool_names() -> list[str]:
    """List all registered tool names.

    Returns:
        List of tool names.
    """
    return list(_tool_registry.keys())


def clear_registry() -> None:
    """Clear the tool registry (for testing)."""
    _tool_registry.clear()
