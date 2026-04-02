"""Configuration settings for Hydra MCP service."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the Hydra MCP service.

    Settings are loaded from environment variables with the HYDRA_MCP_ prefix
    and can be overridden via a .env file.

    Attributes:
        api_url: Base URL for the Hydra API.
        api_key: Optional API key for authentication.
        api_timeout: Request timeout in seconds.
        server_name: Name of the MCP server.
        server_version: Version string for the MCP server.
        transport: Transport mode (stdio, http, sse, streamable-http).
        http_host: Host address for HTTP transport.
        http_port: Port number for HTTP transport.
        cors_origins: Allowed CORS origins for HTTP transport.
        toon_indent: Indentation spaces for TOON output.
        toon_delimiter: Field delimiter for TOON arrays.
        toon_length_marker: Array length marker prefix.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_format: Log format (json or text).

    Example:
        Configure via environment variables::

            export HYDRA_MCP_API_URL=http://localhost:8080/api/v1
            export HYDRA_MCP_TRANSPORT=http
            export HYDRA_MCP_HTTP_PORT=8081
    """

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
    allow_unauthenticated: bool = Field(
        default=False,
        description="Explicitly allow unauthenticated access on non-stdio transports for local development only",
    )
    internal_secret: str | None = Field(
        default=None,
        description="Shared secret for validating X-Hydra-Internal-Request headers (HYDRA_MCP_INTERNAL_SECRET)",
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

    # Transport settings
    transport: str = Field(
        default="stdio",
        description="Transport mode: 'stdio', 'http', 'sse', or 'streamable-http'",
    )
    http_host: str = Field(
        default="127.0.0.1",
        description="HTTP server host (only used when transport=http)",
    )
    http_port: int = Field(
        default=8081,
        description="HTTP server port (only used when transport=http)",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins for HTTP transport",
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
    """Get the cached settings instance.

    Uses LRU caching to ensure a single Settings instance is created and
    reused throughout the application lifecycle.

    Returns:
        The singleton Settings instance with configuration loaded from
        environment variables and .env file.
    """
    return Settings()
