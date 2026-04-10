"""Additional coverage tests for hydra_mcp.auth module."""

from types import SimpleNamespace
from unittest.mock import patch

from hydra_mcp.auth import (
    AuthContext,
    AuthorizationError,
    SourceRestrictionError,
    allow_missing_auth_context,
    create_context_from_user_info,
    get_forward_auth_headers,
    push_auth_context,
    reset_auth_context,
    set_auth_context,
)


class TestAuthContextDataclass:
    """Tests for AuthContext dataclass field defaults and construction."""

    def test_default_fields(self):
        ctx = AuthContext()
        assert ctx.user_id is None
        assert ctx.permissions == []
        assert ctx.role is None
        assert ctx.source_type == "internal"
        assert ctx.client_id is None
        assert ctx.metadata == {}

    def test_full_construction(self):
        ctx = AuthContext(
            user_id="u1",
            permissions=["nodes:read"],
            role="viewer",
            source_type="external",
            client_id="client-1",
            metadata={"key": "val"},
        )
        assert ctx.user_id == "u1"
        assert ctx.source_type == "external"
        assert ctx.client_id == "client-1"


class TestCreateContextFromUserInfo:
    """Tests for create_context_from_user_info with various source types."""

    def test_internal_source(self):
        info = {"userId": "u1", "role": "admin", "permissions": ["*:*"], "type": "agent"}
        ctx = create_context_from_user_info(info, source_type="internal", client_id="hydra-api")
        assert ctx.user_id == "u1"
        assert ctx.role == "admin"
        assert ctx.source_type == "internal"
        assert ctx.client_id == "hydra-api"
        assert ctx.metadata["source"] == "agent"

    def test_external_source(self):
        info = {"userId": "u2", "role": "viewer", "permissions": ["nodes:read"]}
        ctx = create_context_from_user_info(info, source_type="external")
        assert ctx.source_type == "external"
        assert ctx.metadata["source"] == "user"

    def test_with_metadata(self):
        info = {"userId": "u3"}
        ctx = create_context_from_user_info(
            info,
            source_type="internal",
            metadata={"forward_auth": {"Authorization": "Bearer tok"}},
        )
        assert ctx.metadata["forward_auth"]["Authorization"] == "Bearer tok"

    def test_user_id_fallback(self):
        info = {"user_id": "u4"}
        ctx = create_context_from_user_info(info, source_type="external")
        assert ctx.user_id == "u4"


class TestPushResetAuthContext:
    """Tests for push_auth_context / reset_auth_context lifecycle."""

    def test_push_and_reset(self):
        set_auth_context(None)
        ctx = AuthContext(user_id="temp")
        token = push_auth_context(ctx)
        from hydra_mcp.auth import get_auth_context
        assert get_auth_context() is not None
        assert get_auth_context().user_id == "temp"
        reset_auth_context(token)
        assert get_auth_context() is None

    def test_push_none(self):
        set_auth_context(AuthContext(user_id="original"))
        token = push_auth_context(None)
        from hydra_mcp.auth import get_auth_context
        assert get_auth_context() is None
        reset_auth_context(token)
        assert get_auth_context().user_id == "original"
        set_auth_context(None)


class TestGetForwardAuthHeaders:
    """Tests for get_forward_auth_headers with explicit context argument."""

    def test_with_explicit_context(self):
        ctx = AuthContext(
            metadata={"forward_auth": {"X-API-Key": "key123"}}
        )
        headers = get_forward_auth_headers(ctx)
        assert headers == {"X-API-Key": "key123"}

    def test_empty_forward_auth(self):
        ctx = AuthContext(metadata={"forward_auth": {}})
        assert get_forward_auth_headers(ctx) is None

    def test_no_forward_auth_key(self):
        ctx = AuthContext(metadata={"other": "data"})
        assert get_forward_auth_headers(ctx) is None

    def test_non_dict_forward_auth(self):
        ctx = AuthContext(metadata={"forward_auth": "not-a-dict"})
        assert get_forward_auth_headers(ctx) is None


class TestAllowMissingAuthContext:
    """Tests for allow_missing_auth_context."""

    def test_stdio_always_allowed(self):
        with patch(
            "hydra_mcp.auth.get_settings",
            return_value=SimpleNamespace(transport="stdio", allow_unauthenticated=False),
        ):
            assert allow_missing_auth_context() is True

    def test_http_denied(self):
        with patch(
            "hydra_mcp.auth.get_settings",
            return_value=SimpleNamespace(transport="http", allow_unauthenticated=False),
        ):
            assert allow_missing_auth_context() is False

    def test_http_with_allow_unauth_still_denied_with_warning(self):
        with patch(
            "hydra_mcp.auth.get_settings",
            return_value=SimpleNamespace(transport="http", allow_unauthenticated=True),
        ):
            assert allow_missing_auth_context() is False


class TestExceptionClasses:
    """Tests for AuthorizationError and SourceRestrictionError."""

    def test_authorization_error_default_message(self):
        err = AuthorizationError("tool1", "res:act")
        assert err.tool == "tool1"
        assert err.required_permission == "res:act"
        assert "res:act" in err.message
        assert "tool1" in err.message

    def test_authorization_error_custom_message(self):
        err = AuthorizationError("tool1", "res:act", "Custom msg")
        assert err.message == "Custom msg"

    def test_source_restriction_error_defaults(self):
        err = SourceRestrictionError("control_service")
        assert err.tool == "control_service"
        assert err.action is None
        assert err.context == {}
        assert "web interface" in err.message

    def test_source_restriction_error_with_context(self):
        err = SourceRestrictionError(
            "control_node", "reboot",
            {"guidance": "Use web UI"},
        )
        assert err.action == "reboot"
        assert err.context["guidance"] == "Use web UI"
