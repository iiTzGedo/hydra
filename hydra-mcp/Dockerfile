FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (git required for toon-format from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY hydra_mcp/ ./hydra_mcp/

# Install dependencies
RUN uv sync --frozen --no-dev

# Default environment variables
ENV HYDRA_MCP_TRANSPORT=http
ENV HYDRA_MCP_HTTP_HOST=0.0.0.0
ENV HYDRA_MCP_HTTP_PORT=8081

# Expose HTTP port
EXPOSE 8081

# Health check for HTTP transport
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Run the MCP server (defaults to HTTP transport via env)
CMD ["uv", "run", "--no-sync", "hydra-mcp"]
