"""Tests for MCP authorization module."""

import pytest

from hydra_mcp.auth import (
    AuthContext,
    AuthorizationError,
    check_permission,
    get_auth_context,
    set_auth_context,
    create_context_from_api_key,
    ADMIN_PERMISSIONS,
    OPERATOR_PERMISSIONS,
    VIEWER_PERMISSIONS,
    FAMILY_PERMISSIONS,
)


class TestAuthContext:
    """Tests for AuthContext permission checking."""

    def test_empty_permissions_denies_all(self):
        """Test that empty permissions list denies everything."""
        ctx = AuthContext(permissions=[])
        assert ctx.has_permission("nodes:read") is False
        assert ctx.has_permission("services:write") is False

    def test_wildcard_grants_all(self):
        """Test that *:* grants all permissions."""
        ctx = AuthContext(permissions=["*:*"])
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("services:write") is True
        assert ctx.has_permission("anything:action") is True

    def test_exact_match(self):
        """Test exact permission matching."""
        ctx = AuthContext(permissions=["nodes:read"])
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("nodes:write") is False
        assert ctx.has_permission("services:read") is False

    def test_resource_wildcard(self):
        """Test resource wildcard matching (e.g., nodes:*)."""
        ctx = AuthContext(permissions=["nodes:*"])
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("nodes:write") is True
        assert ctx.has_permission("nodes:delete") is True
        assert ctx.has_permission("services:read") is False

    def test_action_wildcard(self):
        """Test action wildcard matching (e.g., *:read)."""
        ctx = AuthContext(permissions=["*:read"])
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("services:read") is True
        assert ctx.has_permission("nodes:write") is False

    def test_multiple_permissions(self):
        """Test multiple permission grants."""
        ctx = AuthContext(permissions=["nodes:read", "services:read", "services:write"])
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("services:read") is True
        assert ctx.has_permission("services:write") is True
        assert ctx.has_permission("nodes:write") is False
        assert ctx.has_permission("groups:read") is False

    def test_empty_required_permission_always_grants(self):
        """Test that empty/None required permission is always granted."""
        ctx = AuthContext(permissions=[])
        assert ctx.has_permission("") is True
        assert ctx.has_permission(None) is True

    def test_invalid_permission_format_denied(self):
        """Test that malformed permissions are denied."""
        ctx = AuthContext(permissions=["nodes:read"])
        # Required permission without colon
        assert ctx.has_permission("invalid") is False

    def test_invalid_granted_permission_ignored(self):
        """Test that malformed granted permissions are ignored."""
        ctx = AuthContext(permissions=["invalid", "nodes:read"])
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("invalid:action") is False


class TestContextVar:
    """Tests for context variable management."""

    def test_get_context_default_none(self):
        """Test that default context is None."""
        set_auth_context(None)
        assert get_auth_context() is None

    def test_set_and_get_context(self):
        """Test setting and retrieving context."""
        ctx = AuthContext(user_id="user_123", permissions=["nodes:read"])
        set_auth_context(ctx)

        retrieved = get_auth_context()
        assert retrieved is not None
        assert retrieved.user_id == "user_123"
        assert retrieved.permissions == ["nodes:read"]

        # Clean up
        set_auth_context(None)

    def test_clear_context(self):
        """Test clearing context by setting None."""
        ctx = AuthContext(user_id="user_123")
        set_auth_context(ctx)
        assert get_auth_context() is not None

        set_auth_context(None)
        assert get_auth_context() is None


class TestCheckPermission:
    """Tests for check_permission function."""

    def test_no_required_permission_always_passes(self):
        """Test that no required permission always passes."""
        set_auth_context(AuthContext(permissions=[]))
        check_permission("any_tool", None)  # Should not raise
        check_permission("any_tool", "")  # Should not raise
        set_auth_context(None)

    def test_no_context_permissive_mode(self):
        """Test that no auth context allows everything (permissive mode)."""
        set_auth_context(None)
        check_permission("list_nodes", "nodes:read")  # Should not raise

    def test_permission_granted(self):
        """Test that granted permission passes check."""
        ctx = AuthContext(permissions=["nodes:read"])
        set_auth_context(ctx)
        check_permission("list_nodes", "nodes:read")  # Should not raise
        set_auth_context(None)

    def test_permission_denied_raises(self):
        """Test that missing permission raises AuthorizationError."""
        ctx = AuthContext(permissions=["nodes:read"])
        set_auth_context(ctx)

        with pytest.raises(AuthorizationError) as exc_info:
            check_permission("control_service", "services:control")

        assert exc_info.value.tool == "control_service"
        assert exc_info.value.required_permission == "services:control"
        assert "services:control" in exc_info.value.message

        set_auth_context(None)

    def test_admin_permissions_grant_all(self):
        """Test that admin permissions grant all tools."""
        ctx = AuthContext(permissions=ADMIN_PERMISSIONS)
        set_auth_context(ctx)

        check_permission("list_nodes", "nodes:read")
        check_permission("control_service", "services:control")
        check_permission("control_device", "iot:control")
        check_permission("execute_command", "commands:execute")

        set_auth_context(None)


class TestCreateContextFromApiKey:
    """Tests for API key context creation."""

    def test_creates_context_from_full_data(self):
        """Test creating context from complete API key data."""
        api_key_data = {
            "userId": "user_123",
            "permissions": ["nodes:read", "services:read"],
            "role": "operator",
            "keyId": "key_abc",
        }

        ctx = create_context_from_api_key(api_key_data)

        assert ctx.user_id == "user_123"
        assert ctx.permissions == ["nodes:read", "services:read"]
        assert ctx.role == "operator"
        assert ctx.metadata["source"] == "api_key"
        assert ctx.metadata["keyId"] == "key_abc"

    def test_creates_context_from_minimal_data(self):
        """Test creating context from minimal API key data."""
        api_key_data = {}

        ctx = create_context_from_api_key(api_key_data)

        assert ctx.user_id is None
        assert ctx.permissions == []
        assert ctx.role is None
        assert ctx.metadata["source"] == "api_key"

    def test_context_has_correct_permissions(self):
        """Test that created context has working permission checking."""
        api_key_data = {
            "userId": "user_123",
            "permissions": ["nodes:*", "services:read"],
        }

        ctx = create_context_from_api_key(api_key_data)

        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("nodes:write") is True
        assert ctx.has_permission("services:read") is True
        assert ctx.has_permission("services:write") is False


class TestPredefinedPermissions:
    """Tests for predefined role permission sets."""

    def test_admin_has_full_access(self):
        """Test that admin permissions grant full access."""
        ctx = AuthContext(permissions=ADMIN_PERMISSIONS)
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("users:delete") is True
        assert ctx.has_permission("anything:anything") is True

    def test_operator_permissions(self):
        """Test operator permission set."""
        ctx = AuthContext(permissions=OPERATOR_PERMISSIONS)
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("nodes:write") is True
        assert ctx.has_permission("services:control") is True
        assert ctx.has_permission("commands:execute") is True
        # Operator shouldn't have user management
        assert ctx.has_permission("users:delete") is False

    def test_viewer_permissions(self):
        """Test viewer permission set (read-only)."""
        ctx = AuthContext(permissions=VIEWER_PERMISSIONS)
        assert ctx.has_permission("nodes:read") is True
        assert ctx.has_permission("services:read") is True
        # Viewer shouldn't have write access
        assert ctx.has_permission("nodes:write") is False
        assert ctx.has_permission("services:control") is False

    def test_family_permissions(self):
        """Test family permission set (IoT only)."""
        ctx = AuthContext(permissions=FAMILY_PERMISSIONS)
        assert ctx.has_permission("iot:read") is True
        assert ctx.has_permission("iot:control") is True
        # Family shouldn't have infrastructure access
        assert ctx.has_permission("nodes:read") is False
        assert ctx.has_permission("services:read") is False


class TestAuthorizationError:
    """Tests for AuthorizationError exception."""

    def test_error_properties(self):
        """Test AuthorizationError has correct properties."""
        error = AuthorizationError("list_nodes", "nodes:read")

        assert error.tool == "list_nodes"
        assert error.required_permission == "nodes:read"
        assert "nodes:read" in str(error)
        assert "list_nodes" in str(error)

    def test_custom_message(self):
        """Test AuthorizationError with custom message."""
        error = AuthorizationError("list_nodes", "nodes:read", "Custom error message")

        assert error.message == "Custom error message"
        assert str(error) == "Custom error message"
