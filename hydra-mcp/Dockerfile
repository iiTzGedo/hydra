FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (git required for toon-format from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ ./src/

# Install dependencies (includes toon-format from git)
RUN uv pip install --system -e .

# Run the MCP server (stdio-based, no port needed)
CMD ["hydra-mcp"]
