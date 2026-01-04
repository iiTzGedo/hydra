FROM python:3.11-slim

WORKDIR /app

# Install uv for faster package management
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY src/ ./src/

# Install dependencies
RUN uv pip install --system -e .

# Expose port
EXPOSE 8081

# Run the application
CMD ["python", "-m", "hydra_mcp.main"]
