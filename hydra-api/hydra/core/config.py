"""Application configuration using pydantic-settings."""

import warnings
from contextlib import contextmanager
from typing import Literal

from pydantic import Field, MongoDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_KNOWN_INSECURE_SECRETS = frozenset({"change-this-secret", "a1b2c3d4", "secret", "test"})


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be configured via environment variables with the HYDRA_ prefix.
    For example, HYDRA_API_PORT=8080 sets the api_port field.
    """

    model_config = SettingsConfigDict(
        env_prefix="HYDRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    env: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_workers: int = 4

    mongodb_uri: MongoDsn = Field(default="mongodb://mongo-dev.db.nimi.labs:27017")
    mongodb_database: str = "hydra_dev"
    mongodb_min_pool_size: int = 5
    mongodb_max_pool_size: int = 50

    redis_url: RedisDsn = Field(default="redis://redis-dev.db.nimi.labs:6379/0")
    redis_max_connections: int = 20

    jwt_secret: str = Field(description="JWT signing secret (HYDRA_JWT_SECRET)")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 7

    encryption_key: str | None = Field(
        default=None,
        description="Fernet encryption key (HYDRA_ENCRYPTION_KEY). If unset, derived from jwt_secret.",
    )

    agent_tls_verify: bool = Field(
        default=True,
        description="Verify TLS certificates when dispatching commands to agents",
    )

    registration_token_expire_days: int = 7
    registration_token_max_uses: int = 10

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    object_storage_enabled: bool = False
    object_storage_endpoint: str | None = Field(default=None)
    object_storage_bucket: str = "hydra-bucket"
    object_storage_access_key: str | None = Field(default=None)
    object_storage_secret_key: str | None = Field(default=None)
    object_storage_region: str = "garage"

    local_storage_enabled: bool = False
    local_storage_path: str = Field(
        default="/var/lib/hydra/bundles",
        description="Local filesystem path for agent bundles",
    )

    smtp_enabled: bool = False
    smtp_host: str | None = Field(default=None)
    smtp_port: int = 587
    smtp_username: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    smtp_from_address: str | None = Field(default=None)
    smtp_from_name: str = "Hydra"
    smtp_use_tls: bool = True
    smtp_starttls: bool = True
    smtp_timeout: int = 30

    password_reset_token_expire_hours: int = 24
    password_reset_base_url: str | None = Field(
        default=None,
        description="Base URL for password reset links (e.g., https://hydra.local)",
    )

    mcp_server_url: str = Field(
        default="http://hydra-mcp:8081",
        description="URL for the built-in Hydra MCP server (HTTP transport)",
    )
    mcp_internal_secret: str | None = Field(
        default=None,
        description="Shared secret for internal MCP requests (HYDRA_MCP_INTERNAL_SECRET)",
    )

    # Centralized defaults
    pagination_default_limit: int = 50
    pagination_max_limit: int = 200
    health_cutoff_hours: int = 24
    profile_section_weights: dict[str, float] = Field(
        default={
            "hardware": 0.30,
            "configs": 0.25,
            "software": 0.20,
            "storage": 0.15,
            "network": 0.10,
        },
        description="Section weights for profile diff scoring",
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.env == "production"

    @property
    def has_object_storage(self) -> bool:
        """Check if object storage (S3) is configured."""
        return (
            self.object_storage_enabled
            and self.object_storage_endpoint is not None
            and self.object_storage_access_key is not None
            and self.object_storage_secret_key is not None
        )

    @property
    def has_local_storage(self) -> bool:
        """Check if local storage is configured for agent bundles."""
        return self.local_storage_enabled and self.local_storage_path is not None

    @property
    def has_smtp(self) -> bool:
        """Check if SMTP is configured for sending emails."""
        return (
            self.smtp_enabled
            and self.smtp_host is not None
            and self.smtp_from_address is not None
        )

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        """Reject known-insecure JWT secrets in non-development environments."""
        if self.env != "development":
            if len(self.jwt_secret) < 32:
                raise ValueError(
                    "HYDRA_JWT_SECRET must be at least 32 characters "
                    "in non-development environments"
                )
            if self.jwt_secret in _KNOWN_INSECURE_SECRETS:
                raise ValueError(
                    "HYDRA_JWT_SECRET contains a known insecure value"
                )
        else:
            if self.jwt_secret in _KNOWN_INSECURE_SECRETS:
                warnings.warn(
                    "HYDRA_JWT_SECRET uses a known insecure value; "
                    "rotate before deploying to staging/production",
                    UserWarning,
                    stacklevel=2,
                )
        return self


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Singleton Settings instance loaded from environment.
    """
    global _settings_instance  # noqa: PLW0603
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def clear_settings_cache() -> None:
    """Clear the cached settings instance.

    Call this to force settings to be reloaded from environment on next access.
    Useful in tests to ensure clean state between test cases.
    """
    global _settings_instance  # noqa: PLW0603
    _settings_instance = None


@contextmanager
def override_settings(settings: Settings):
    """Temporarily override the global settings instance.

    Use in tests to inject custom settings without touching the environment.

    Args:
        settings: The Settings instance to use as the override.

    Yields:
        The overridden Settings instance.
    """
    global _settings_instance  # noqa: PLW0603
    previous = _settings_instance
    _settings_instance = settings
    try:
        yield settings
    finally:
        _settings_instance = previous
