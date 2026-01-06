"""Configuration settings for Hydra MCP service."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP Service settings."""

    model_config = SettingsConfigDict(
        env_prefix="HYDRA_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API connection
    api_url: str = Field(
        default="http://localhost:8080/api/v1",
        description="Hydra API base URL",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for authentication (optional, can use JWT instead)",
    )
    api_timeout: int = Field(
        default=30,
        description="API request timeout in seconds",
    )

    # Server settings
    server_name: str = Field(
        default="hydra-mcp",
        description="MCP server name",
    )
    server_version: str = Field(
        default="0.1.0",
        description="MCP server version",
    )

    # TOON formatting (see https://github.com/toon-format/toon-python)
    toon_indent: int = Field(
        default=2,
        description="Indentation spaces for TOON output",
    )
    toon_delimiter: str = Field(
        default=",",
        description="Field delimiter for TOON arrays (',' | '\\t' | '|')",
    )
    toon_length_marker: str = Field(
        default="",
        description="Array length marker prefix ('' or '#')",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
