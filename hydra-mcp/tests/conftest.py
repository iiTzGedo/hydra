"""Shared pytest configuration for hydra-mcp tests."""

import os

os.environ.setdefault("HYDRA_MCP_INTERNAL_SECRET", "internal-secret-for-tests-0123456789")
