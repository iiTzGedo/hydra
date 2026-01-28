"""Tests for AI/LLM endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.core.crypto import encrypt_value
from hydra.api.v1.services.ai import AIService
from tests.utils import create_mock_cursor


@pytest.fixture
def sample_ai_provider():
    """Sample AI provider configuration (database document format)."""
    api_key = "sk-ant-test123"
    encrypted_key = encrypt_value(api_key)
    now = datetime.now(timezone.utc)
    return {
        "providerId": "llm_anthropic123",  # Database field name
        "name": "anthropic-claude",
        "type": "anthropic",
        "apiKeyEncrypted": encrypted_key,
        "apiKeyLast4": api_key[-4:],
        "apiKeySet": True,
        "baseUrl": None,
        "model": "claude-3-5-sonnet-20241022",
        "isDefault": True,
        "isValid": True,
        "lastValidatedAt": now,
        "createdBy": "user_admin123",
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.mark.asyncio
async def test_list_ai_providers(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_ai_provider,
):
    """Test listing AI providers."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.ai_models.find_one = AsyncMock(return_value=sample_ai_provider)
    mock_mongodb.ai_models.find.return_value = create_mock_cursor([sample_ai_provider])
    mock_mongodb.ai_models.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        "/api/v1/ai/configs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    # Response uses configId, fixture uses database field providerId
    assert data["configs"][0]["configId"] == sample_ai_provider["providerId"]


@pytest.mark.asyncio
async def test_get_ai_provider(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_ai_provider,
):
    """Test getting a specific AI provider."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.ai_models.find_one = AsyncMock(return_value=sample_ai_provider)
    mock_mongodb.ai_models.find.return_value = create_mock_cursor([sample_ai_provider])
    mock_mongodb.ai_models.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        "/api/v1/ai/configs/provider-test123",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    # Response uses configId, fixture uses database field providerId
    assert data["configId"] == sample_ai_provider["providerId"]


@pytest.mark.asyncio
async def test_create_ai_provider(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test creating an AI provider."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.post(
        "/api/v1/ai/configs",
        json={
            "type": "anthropic",
            "name": "anthropic-claude",
            "apiKey": "sk-ant-test123",
            "model": "claude-3-5-sonnet-20241022",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "anthropic-claude"
    assert data["type"] == "anthropic"
    assert data["apiKeyLast4"] == "t123"


@pytest.mark.asyncio
async def test_ai_forbidden_for_agent(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot access AI endpoints."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        "/api/v1/ai/configs",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    # Agent should get 403
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_ai_provider(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_ai_provider,
):
    """Test updating an AI provider."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    updated_provider = sample_ai_provider.copy()
    updated_provider["name"] = "updated-name"

    mock_mongodb.ai_models.find_one = AsyncMock(side_effect=[sample_ai_provider, updated_provider])
    mock_mongodb.ai_models.update_one = AsyncMock()

    response = await client.put(
        f"/api/v1/ai/configs/{sample_ai_provider['providerId']}",
        json={"name": "updated-name"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "updated-name"


@pytest.mark.asyncio
async def test_delete_ai_provider(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_ai_provider,
):
    """Test deleting an AI provider."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_mongodb.ai_models.find_one = AsyncMock(return_value=sample_ai_provider)
    mock_mongodb.ai_models.delete_one = AsyncMock()

    response = await client.delete(
        f"/api/v1/ai/configs/{sample_ai_provider['providerId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True


@pytest.mark.asyncio
async def test_validate_ai_provider(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_ai_provider,
    monkeypatch,
):
    """Test validating an AI provider."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_mongodb.ai_models.find_one = AsyncMock(return_value=sample_ai_provider)
    mock_mongodb.ai_models.update_one = AsyncMock()

    async def fake_validate(_self, _api_key):
        return True, "API key is valid", ["claude-3-5-sonnet-20241022"]

    monkeypatch.setattr(AIService, "_validate_anthropic", fake_validate)

    response = await client.post(
        f"/api/v1/ai/configs/{sample_ai_provider['providerId']}/validate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # Response uses configId, fixture uses database field providerId
    assert data["configId"] == sample_ai_provider["providerId"]
    assert data["isValid"] is True


@pytest.mark.asyncio
async def test_get_ai_provider_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent AI provider."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.ai_models.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/ai/configs/nonexistent-provider",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ai_forbidden_for_viewer(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer can read AI providers (no write)."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)
    mock_mongodb.ai_models.find.return_value = create_mock_cursor([])
    mock_mongodb.ai_models.count_documents = AsyncMock(return_value=0)

    # Viewer should be able to list (read)
    response = await client.get(
        "/api/v1/ai/configs",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ai_agent_cannot_create(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot create AI providers."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.post(
        "/api/v1/ai/configs",
        json={
            "type": "anthropic",
            "name": "Test",
            "apiKey": "test-key",
            "model": "claude-3-5-sonnet-20241022",
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_agent_cannot_update(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot update AI providers."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.put(
        "/api/v1/ai/configs/some-provider",
        json={"name": "Updated"},
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_agent_cannot_delete(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot delete AI providers."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.delete(
        "/api/v1/ai/configs/some-provider",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_agent_cannot_validate(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot validate AI providers."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.post(
        "/api/v1/ai/configs/some-provider/validate",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403
