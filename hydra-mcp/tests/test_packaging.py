"""Tests for packaging and container build assumptions."""

from pathlib import Path


def test_dockerfile_uses_uv_sync_and_correct_package_path():
    dockerfile = Path("Dockerfile").read_text()

    assert "COPY uv.lock ." in dockerfile
    assert "COPY hydra_mcp/ ./hydra_mcp/" in dockerfile
    assert "uv sync --frozen --no-dev" in dockerfile
    assert 'CMD ["uv", "run", "--no-sync", "hydra-mcp"]' in dockerfile
