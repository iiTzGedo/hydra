"""Tests for agent installation endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.core.deps import get_storage_service
from hydra.api.v1.main import app as v1_app
from hydra.api.v1.services.storage import StorageSource
from tests.utils import AsyncIterator


class DummyBackend:
    async def get_latest_version(self, _target: str | None = None) -> str:
        return "1.0.0"

    async def list_versions(self, _target: str | None = None) -> list[dict]:
        return [{"version": "1.0.0"}]

    def get_bundle_key(self, version: str) -> str:
        return f"bundles/{version}/hydra-agent-{version}.zip"

    async def get_object_metadata(self, _key: str) -> dict:
        return {"size": 3, "sha256": "deadbeef"}

    def get_object_stream(self, _key: str):
        return AsyncIterator([b"zip"])


class DummyStorage:
    def __init__(self) -> None:
        self.backend = DummyBackend()

    def is_source_available(self, _source: StorageSource) -> bool:
        return True

    def get_available_sources(self) -> list[StorageSource]:
        return [StorageSource.BINARY, StorageSource.OBS, StorageSource.LOCAL]

    def get_backend(self, _source: StorageSource) -> DummyBackend:
        return self.backend


@pytest.fixture
def dummy_storage():
    return DummyStorage()


@pytest.mark.asyncio
async def test_get_install_script(client: AsyncClient):
    """Test getting the installation script."""
    # Agent install endpoint is at /api/v1/agent/install
    response = await client.get("/api/v1/agent/install?source=local&os=linux")

    assert response.status_code == 200
    assert response.headers["X-Script-Type"] == "bash"


@pytest.mark.asyncio
async def test_get_install_script_with_params(client: AsyncClient):
    """Test getting the installation script with parameters."""
    response = await client.get(
        "/api/v1/agent/install?os=windows"
    )

    assert response.status_code == 200
    assert response.headers["X-Script-Type"] == "powershell"


@pytest.mark.asyncio
async def test_unix_default_install_is_prebuilt_binary(client: AsyncClient):
    """Default Unix install (source=binary) returns a prebuilt-binary script, not a 400."""
    response = await client.get("/api/v1/agent/install?os=linux")

    assert response.status_code == 200
    assert response.headers["X-Script-Type"] == "bash"
    assert response.headers["X-Install-Kind"] == "binary"
    body = response.text
    # Downloads a prebuilt binary (no cargo build) and bootstraps with a token.
    assert "source=binary" in body
    assert "bootstrap --token" in body
    assert "cargo build" not in body
    # Verifies the checksum returned by /agent/download.
    assert "x-checksum-sha256" in body.lower()


@pytest.mark.asyncio
async def test_unix_source_bundle_install_compiles(client: AsyncClient):
    """Explicit source=local/obs returns the source-bundle (compile) installer."""
    response = await client.get("/api/v1/agent/install?os=linux&source=local")

    assert response.status_code == 200
    assert response.headers["X-Script-Type"] == "bash"
    assert response.headers["X-Install-Kind"] == "bundle"
    assert "source=$SOURCE" in response.text or "source=local" in response.text


@pytest.mark.asyncio
async def test_windows_install_verifies_checksum_and_bootstraps(client: AsyncClient):
    """Windows PowerShell installer verifies the checksum and runs the headless bootstrap."""
    response = await client.get("/api/v1/agent/install?os=windows")

    assert response.status_code == 200
    body = response.text
    assert "Get-FileHash" in body
    assert "X-Checksum-SHA256" in body
    assert "bootstrap --token" in body


@pytest.mark.asyncio
async def test_get_agent_versions(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    dummy_storage,
):
    """Test getting available agent versions."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    v1_app.dependency_overrides[get_storage_service] = lambda: dummy_storage

    response = await client.get(
        "/api/v1/agent/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == StorageSource.BINARY.value


@pytest.mark.asyncio
async def test_download_agent_binary(client: AsyncClient, dummy_storage):
    """Test downloading agent binary."""
    v1_app.dependency_overrides[get_storage_service] = lambda: dummy_storage
    response = await client.get("/api/v1/agent/download?target=linux-amd64")

    assert response.status_code == 200
    assert response.headers["X-Hydra-Version"] == "1.0.0"


@pytest.mark.asyncio
async def test_download_agent_binary_with_version(client: AsyncClient, dummy_storage):
    """Test downloading agent binary with specific version."""
    v1_app.dependency_overrides[get_storage_service] = lambda: dummy_storage
    response = await client.get("/api/v1/agent/download?target=linux-amd64&version=1.0.0")

    assert response.status_code == 200
    assert response.headers["X-Hydra-Version"] == "1.0.0"
