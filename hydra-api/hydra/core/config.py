"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, MongoDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    jwt_secret: str = Field(default="change-this-secret")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 7

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Singleton Settings instance loaded from environment.
    """
    return Settings()
