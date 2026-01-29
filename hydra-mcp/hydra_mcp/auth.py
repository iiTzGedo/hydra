"""MCP Authorization Module.

Provides permission checking for MCP tool execution.

Permissions follow the format: resource:action
Examples:
    - nodes:read
    - services:write
    - commands:execute
    - *:* (full access)

The authorization context can be set per-request to enforce RBAC.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


class AuthorizationError(Exception):
    """Raised when a tool execution is not authorized.

    This exception is caught by the MCP server and returned as an error
    result to the client.
    """

    def __init__(self, tool: str, required_permission: str, message: str | None = None):
        self.tool = tool
        self.required_permission = required_permission
        self.message = message or f"Permission '{required_permission}' required for tool '{tool}'"
        super().__init__(self.message)


@dataclass
class AuthContext:
    """Authorization context for MCP requests.

    Attributes:
        user_id: The authenticated user identifier (if any).
        permissions: List of granted permissions (e.g., ["nodes:read", "services:*"]).
        role: The user's role (e.g., "admin", "operator", "viewer").
        metadata: Additional context metadata.
    """

    user_id: str | None = None
    permissions: list[str] = field(default_factory=list)
    role: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_permission(self, required: str) -> bool:
        """Check if this context has the required permission.

        Supports wildcard matching:
        - "*:*" matches everything
        - "nodes:*" matches any action on nodes
        - "*:read" matches read action on any resource

        Args:
            required: The permission string to check (e.g., "nodes:read").

        Returns:
            True if permission is granted, False otherwise.
        """
        if not required:
            return True

        if "*:*" in self.permissions:
            return True

        # Split into resource and action
        req_parts = required.split(":", 1)
        if len(req_parts) != 2:
            # Invalid permission format
            return False

        req_resource, req_action = req_parts

        for perm in self.permissions:
            perm_parts = perm.split(":", 1)
            if len(perm_parts) != 2:
                continue

            perm_resource, perm_action = perm_parts

            # Check resource match (exact or wildcard)
            resource_match = perm_resource == "*" or perm_resource == req_resource
            # Check action match (exact or wildcard)
            action_match = perm_action == "*" or perm_action == req_action

            if resource_match and action_match:
                return True

        return False


# Context variable for per-request authorization
_auth_context: ContextVar[AuthContext | None] = ContextVar("auth_context", default=None)


def get_auth_context() -> AuthContext | None:
    """Get the current authorization context.

    Returns:
        The current AuthContext, or None if not set.
    """
    return _auth_context.get()


def set_auth_context(ctx: AuthContext | None) -> None:
    """Set the authorization context for the current request.

    Args:
        ctx: The AuthContext to set, or None to clear.
    """
    _auth_context.set(ctx)


def check_permission(tool_name: str, required_permission: str | None) -> None:
    """Check if the current context has permission to execute a tool.

    This function checks the current authorization context against the
    required permission. If no context is set (unauthenticated), authorization
    is bypassed (permissive mode for local/dev use).

    Args:
        tool_name: The name of the tool being executed.
        required_permission: The permission required, or None if no auth needed.

    Raises:
        AuthorizationError: If permission is denied.
    """
    if not required_permission:
        # Tool doesn't require any permission
        return

    ctx = get_auth_context()

    if ctx is None:
        # No auth context set - permissive mode (e.g., local development)
        # In production, middleware should always set a context
        return

    if not ctx.has_permission(required_permission):
        raise AuthorizationError(
            tool=tool_name,
            required_permission=required_permission,
        )


def create_context_from_api_key(api_key_data: dict[str, Any]) -> AuthContext:
    """Create an AuthContext from API key data.

    This helper creates an AuthContext from the API key metadata
    returned by the Hydra API during authentication.

    Args:
        api_key_data: Dictionary containing API key info with fields:
            - userId: The owner user ID
            - permissions: List of permission strings
            - role: The associated role

    Returns:
        An AuthContext configured from the API key data.
    """
    return AuthContext(
        user_id=api_key_data.get("userId"),
        permissions=api_key_data.get("permissions", []),
        role=api_key_data.get("role"),
        metadata={"source": "api_key", "keyId": api_key_data.get("keyId")},
    )


# Predefined permission sets for common roles
ADMIN_PERMISSIONS = ["*:*"]
OPERATOR_PERMISSIONS = [
    "nodes:read",
    "nodes:write",
    "profiles:read",
    "services:read",
    "services:write",
    "services:control",
    "groups:read",
    "groups:write",
    "networks:read",
    "networks:write",
    "topologies:read",
    "commands:read",
    "commands:execute",
    "iot:read",
    "iot:control",
]
VIEWER_PERMISSIONS = [
    "nodes:read",
    "profiles:read",
    "services:read",
    "groups:read",
    "networks:read",
    "topologies:read",
]
FAMILY_PERMISSIONS = [
    "iot:read",
    "iot:control",
]
