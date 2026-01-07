FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (git required for toon-format from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY hydra/ ./hydra/

# Install dependencies (includes toon-format from git, uvicorn for HTTP)
RUN uv pip install --system -e . uvicorn[standard] fastapi

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
CMD ["hydra-mcp"]
