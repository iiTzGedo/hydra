"""Tests for hydra-mcp configuration validation."""

import pytest

from hydra_mcp.config import Settings


class TestSettingsValidation:
    """Tests for pydantic settings validation rules."""

    def test_network_transports_do_not_require_internal_secret(self):
        settings = Settings(transport="streamable-http", internal_secret=None)

        assert settings.transport == "streamable-http"
        assert settings.internal_secret is None

    def test_short_internal_secret_is_rejected(self):
        with pytest.raises(ValueError, match="at least 32 characters"):
            Settings(internal_secret="too-short")
