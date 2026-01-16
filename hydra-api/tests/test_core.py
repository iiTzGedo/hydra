"""Tests for core utilities (crypto, email, deps, exceptions, validators)."""

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from hydra.api.v1.core.crypto import encrypt_value, decrypt_value, mask_api_key
from hydra.api.v1.core.security import (
    create_access_token,
    create_token_pair,
    hash_password,
    verify_password,
    decode_token,
)
from hydra.api.v1.core.validators import (
    validate_node_id,
    validate_node_id_strict,
    validate_node_id_lenient,
    validate_tag,
    validate_network_id,
    validate_ipv4,
    validate_cidr,
    validate_profile_version,
    validate_service_id,
    validate_agent_username,
)
from hydra.api.v1.core.exceptions import (
    HydraError,
    NotFoundError,
    NodeNotFoundError,
    AuthenticationError,
    InvalidTokenError,
    AuthorizationError,
    ValidationError,
    ConflictError,
    NodeAlreadyRegisteredError,
    ServiceUnavailableError,
)
from hydra.core.config import get_settings


class TestCrypto:
    """Tests for cryptographic utilities."""

    def test_encrypt_decrypt_value(self):
        """Test encryption and decryption of values."""
        plaintext = "test_secret_value_123"
        encrypted = encrypt_value(plaintext)
        assert encrypted is not None
        assert encrypted != plaintext
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext

    def test_mask_api_key(self):
        """Test API key masking."""
        api_key = "hyk_node_abc123def456"
        masked = mask_api_key(api_key)
        assert masked.endswith("f456")
        assert "..." in masked

    def test_mask_api_key_short(self):
        """Test masking of short API key."""
        api_key = "abc"
        masked = mask_api_key(api_key)
        assert masked == "***"

    def test_generate_api_key_pattern(self):
        """Test API key generation pattern (as used in auth service)."""
        api_key = f"hyk_node_{secrets.token_urlsafe(32)}"
        assert api_key.startswith("hyk_node_")
        assert len(api_key) > 20


class TestSecurity:
    """Tests for security utilities."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "test_password_123"
        hashed = hash_password(password)
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 20

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "test_password_123"
        hashed = hash_password(password)
        assert verify_password("wrong_password", hashed) is False

    def test_create_access_token(self):
        """Test access token creation."""
        settings = get_settings()
        token = create_access_token(
            subject="user_test123",
            token_type="access",
            additional_claims={"role": "admin"},
            settings=settings,
        )
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50

    def test_create_token_pair(self):
        """Test access/refresh token pair creation."""
        settings = get_settings()
        access_token, refresh_token = create_token_pair(
            subject="user_test123",
            additional_claims={"sub_type": "user", "role": "admin"},
            settings=settings,
        )
        assert access_token is not None
        assert refresh_token is not None
        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)

    def test_decode_token(self):
        """Test token decoding."""
        settings = get_settings()
        token = create_access_token(
            subject="user_test123",
            token_type="access",
            additional_claims={"role": "admin"},
            settings=settings,
        )
        decoded = decode_token(token, settings)
        assert decoded["sub"] == "user_test123"
        assert decoded["role"] == "admin"


class TestValidators:
    """Tests for input validators."""

    def test_validate_node_id_valid_strict(self):
        """Test valid node IDs with strict pattern."""
        # New strict pattern: ^[a-z]+([._-][a-z0-9]+){0,2}$
        valid_ids = [
            "server",
            "proxmox",
            "server-01",
            "server_01",
            "server.lan",
        ]
        for node_id in valid_ids:
            is_valid, _ = validate_node_id(node_id, strict=True)
            assert is_valid is True, f"Expected '{node_id}' to be valid"

    def test_validate_node_id_invalid_strict(self):
        """Test invalid node IDs with strict pattern."""
        # Pattern: ^[a-z]+([._-][a-z0-9]+){0,2}$
        # Single letters like "a" are valid under this pattern
        invalid_ids = [
            "Server-01",  # uppercase
            "-server",  # starts with dash
            "01server",  # starts with number
            "server@01",  # invalid character
            "server_01_02_03",  # too many segments (max 2 separators)
        ]
        for node_id in invalid_ids:
            is_valid, _ = validate_node_id(node_id, strict=True)
            assert is_valid is False, f"Expected '{node_id}' to be invalid"

    def test_validate_node_id_lenient(self):
        """Test node IDs with lenient validation (legacy pattern)."""
        # Legacy pattern: ^[a-z0-9][a-z0-9.-]{2,63}$
        valid_legacy_ids = [
            "server-01",
            "proxmox-01",
            "opnsense.gw",
            "ha-core",
            "a1b2c3",
        ]
        for node_id in valid_legacy_ids:
            assert validate_node_id_lenient(node_id) is True, f"Expected '{node_id}' to be valid"

    def test_validate_tag_valid(self):
        """Test valid tags."""
        # Pattern: ^[a-z]+[_:]?[a-z]+$
        valid_tags = [
            "production",
            "web_server",
            "env:prod",
            "testenv",
        ]
        for tag in valid_tags:
            assert validate_tag(tag) is True, f"Expected '{tag}' to be valid"

    def test_validate_tag_invalid(self):
        """Test invalid tags."""
        invalid_tags = ["", "a", "Tag With Spaces", "tag@invalid", "v1.0"]
        for tag in invalid_tags:
            assert validate_tag(tag) is False, f"Expected '{tag}' to be invalid"

    def test_validate_network_id_valid(self):
        """Test valid network IDs."""
        # Pattern: ^[a-z]{1,}[0-9a-z]*([-]?net)$
        valid_ids = ["lan-net", "vlan100-net", "mainnet"]
        for net_id in valid_ids:
            assert validate_network_id(net_id) is True, f"Expected '{net_id}' to be valid"

    def test_validate_network_id_invalid(self):
        """Test invalid network IDs."""
        invalid_ids = ["192.168.1.0/24", "network-01", "NET-LAN", "net-192-168-1"]
        for net_id in invalid_ids:
            assert validate_network_id(net_id) is False, f"Expected '{net_id}' to be invalid"

    def test_validate_ipv4_valid(self):
        """Test valid IPv4 addresses."""
        valid_ips = ["192.168.1.1", "10.0.0.1", "255.255.255.255", "0.0.0.0"]
        for ip in valid_ips:
            assert validate_ipv4(ip) is True

    def test_validate_ipv4_invalid(self):
        """Test invalid IPv4 addresses."""
        invalid_ips = ["256.1.1.1", "192.168.1", "192.168.1.1.1", "not-an-ip"]
        for ip in invalid_ips:
            assert validate_ipv4(ip) is False

    def test_validate_cidr_valid(self):
        """Test valid CIDR notations."""
        valid_cidrs = ["192.168.1.0/24", "10.0.0.0/8", "172.16.0.0/16"]
        for cidr in valid_cidrs:
            assert validate_cidr(cidr) is True

    def test_validate_cidr_invalid(self):
        """Test invalid CIDR notations."""
        invalid_cidrs = ["192.168.1.0", "192.168.1.0/33", "not-a-cidr"]
        for cidr in invalid_cidrs:
            assert validate_cidr(cidr) is False

    def test_validate_profile_version_valid(self):
        """Test valid profile versions."""
        # Pattern: ^E([0-9]|[1-9][0-9]+)-([0-9A-F]\.){3}[0-9A-F]$
        valid_versions = ["E0-0.0.0.1", "E1-1.2.3.4", "E0-0.0.1.5", "E0-A.B.C.D"]
        for version in valid_versions:
            assert validate_profile_version(version) is True, f"Expected '{version}' to be valid"

    def test_validate_profile_version_invalid(self):
        """Test invalid profile versions."""
        invalid_versions = ["0.0.0.1", "E0-1.2.3", "v1.0.0"]
        for version in invalid_versions:
            assert validate_profile_version(version) is False

    def test_validate_service_id_valid(self):
        """Test valid service IDs."""
        # Pattern: ^svc-[a-z0-9-_]+-[a-zA-Z0-9]{4}$
        valid_ids = ["svc-nginx-a1b2", "svc-mongodb-c3D4", "svc-api-gateway-e5f6"]
        for svc_id in valid_ids:
            assert validate_service_id(svc_id) is True, f"Expected '{svc_id}' to be valid"

    def test_validate_service_id_invalid(self):
        """Test invalid service IDs."""
        invalid_ids = ["nginx", "svc-nginx", "service-nginx-a1b2"]
        for svc_id in invalid_ids:
            assert validate_service_id(svc_id) is False

    def test_validate_agent_username_valid(self):
        """Test valid agent usernames."""
        # Pattern: ^agent-[0-9A-Z]{8}$
        valid_usernames = ["agent-ABC12345", "agent-XYZ78901", "agent-A1B2C3D4"]
        for username in valid_usernames:
            assert validate_agent_username(username) is True, f"Expected '{username}' to be valid"

    def test_validate_agent_username_invalid(self):
        """Test invalid agent usernames."""
        # Must be agent- followed by exactly 8 uppercase alphanumeric
        invalid_usernames = ["user-abc", "agent", "Agent-ABC123", "agent-abc123", "agent-server01"]
        for username in invalid_usernames:
            assert validate_agent_username(username) is False, f"Expected '{username}' to be invalid"


class TestExceptions:
    """Tests for custom exceptions."""

    def test_hydra_error_basic(self):
        """Test basic HydraError."""
        error = HydraError(code="HYDRA_ERROR", message="Test error")
        assert error.message == "Test error"
        assert error.code == "HYDRA_ERROR"
        assert error.status_code == 500

    def test_node_not_found_error(self):
        """Test NodeNotFoundError."""
        error = NodeNotFoundError("server-01")
        assert "server-01" in str(error.message)
        assert error.code == "NODE_NOT_FOUND"
        assert error.status_code == 404

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError(code="AUTH_ERROR", message="Auth failed")
        assert error.code == "AUTH_ERROR"
        assert error.status_code == 401

    def test_invalid_token_error(self):
        """Test InvalidTokenError."""
        error = InvalidTokenError("Token expired")
        assert error.code == "AUTH_INVALID_TOKEN"
        assert error.status_code == 401

    def test_authorization_error(self):
        """Test AuthorizationError."""
        error = AuthorizationError("nodes:write")
        assert error.code == "AUTH_INSUFFICIENT_PERMISSIONS"
        assert error.status_code == 403
        assert error.details.get("required_permission") == "nodes:write"

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Invalid node ID format")
        assert error.code == "VALIDATION_ERROR"
        assert error.status_code == 400

    def test_conflict_error(self):
        """Test ConflictError."""
        error = ConflictError("node", "server-01")
        assert error.code == "NODE_ALREADY_EXISTS"
        assert error.status_code == 409

    def test_node_already_registered_error(self):
        """Test NodeAlreadyRegisteredError."""
        error = NodeAlreadyRegisteredError("server-01")
        assert "server-01" in str(error.message)
        assert error.code == "NODE_ALREADY_REGISTERED"
        assert error.status_code == 409

    def test_service_unavailable_error(self):
        """Test ServiceUnavailableError."""
        error = ServiceUnavailableError("database", "Database connection failed")
        assert error.code == "DATABASE_UNAVAILABLE"
        assert error.status_code == 503

    def test_exception_has_details(self):
        """Test that exceptions properly store details."""
        error = NodeNotFoundError("server-01")
        assert "nodeId" in error.details
        assert error.details["nodeId"] == "server-01"


class TestConfig:
    """Tests for configuration."""

    def test_get_settings(self):
        """Test settings singleton."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_settings_defaults(self):
        """Test settings default values."""
        settings = get_settings()
        assert settings.env in ["development", "production", "test"]
        assert settings.jwt_expire_minutes > 0


class TestEmail:
    """Tests for email utilities."""

    @pytest.mark.asyncio
    async def test_email_service_initialization(self):
        """Test email service initialization."""
        from hydra.api.v1.core.email import EmailService
        from hydra.core.config import get_settings

        settings = get_settings()
        service = EmailService(settings)
        # Should not raise when SMTP is disabled
        assert service is not None
        assert service.settings is settings

    @pytest.mark.asyncio
    async def test_email_service_not_configured(self):
        """Test email service when SMTP is not configured."""
        from hydra.api.v1.core.email import EmailService
        from hydra.core.config import get_settings

        settings = get_settings()
        service = EmailService(settings)

        # When SMTP is not configured, send_email should return False
        if not service.is_configured:
            result = await service.send_email(
                to="test@example.com",
                subject="Test",
                body="Test body"
            )
            assert result is False
