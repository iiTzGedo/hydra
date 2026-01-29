"""Tests for chat endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_chat_session():
    """Sample chat session document."""
    now = datetime.now(timezone.utc)
    return {
        "sessionId": "sess-abc123",
        "projectId": None,
        "title": "Infrastructure Query",
        "status": "active",
        "messageCount": 2,
        "llmProviderId": None,
        "mcpServerIds": [],
        "ownerId": "user_admin123",
        "createdAt": now,
        "updatedAt": now,
        "lastMessageAt": now,
    }


@pytest.fixture
def sample_chat_message():
    """Sample chat message document."""
    now = datetime.now(timezone.utc)
    return {
        "messageId": "msg-abc123",
        "sessionId": "sess-abc123",
        "role": "user",
        "content": "List all active servers",
        "toolCalls": [],
        "order": 1,
        "createdAt": now,
    }


@pytest.mark.asyncio
async def test_list_chat_sessions(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_chat_session,
):
    """Test listing chat sessions."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_chat = MagicMock()
    mock_chat.count_documents = AsyncMock(return_value=1)
    mock_chat.find_one = AsyncMock(return_value=sample_chat_session)
    mock_chat.find.return_value = create_mock_cursor([sample_chat_session])
    mock_mongodb.chat_sessions = mock_chat

    response = await client.get(
        "/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_create_chat_session(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_chat_session,
):
    """Test creating a chat session."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_chat = MagicMock()
    mock_chat.insert_one = AsyncMock()
    mock_chat.find_one = AsyncMock(return_value=sample_chat_session)
    mock_mongodb.chat_sessions = mock_chat

    response = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "New Session"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Session"


@pytest.mark.asyncio
async def test_get_chat_session(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_chat_session,
):
    """Test getting a chat session."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_chat = MagicMock()
    mock_chat.find_one = AsyncMock(return_value=sample_chat_session)
    mock_chat.find.return_value = create_mock_cursor([sample_chat_session])
    mock_chat.count_documents = AsyncMock(return_value=1)
    mock_mongodb.chat_sessions = mock_chat

    response = await client.get(
        f"/api/v1/chat/sessions/{sample_chat_session['sessionId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sessionId"] == sample_chat_session["sessionId"]


@pytest.mark.asyncio
async def test_delete_chat_session(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_chat_session,
):
    """Test deleting a chat session."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_chat = MagicMock()
    mock_chat.find_one = AsyncMock(return_value=sample_chat_session)
    mock_chat.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    mock_mongodb.chat_sessions = mock_chat

    mock_messages = MagicMock()
    mock_messages.delete_many = AsyncMock()
    mock_mongodb.chat_messages = mock_messages

    response = await client.delete(
        f"/api/v1/chat/sessions/{sample_chat_session['sessionId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_chat_messages(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_chat_session,
    sample_chat_message,
):
    """Test getting chat messages."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_sessions = MagicMock()
    mock_sessions.find_one = AsyncMock(return_value=sample_chat_session)
    mock_mongodb.chat_sessions = mock_sessions

    mock_messages = MagicMock()
    mock_messages.count_documents = AsyncMock(return_value=1)
    mock_messages.find_one = AsyncMock(return_value=sample_chat_message)
    mock_messages.find.return_value = create_mock_cursor([sample_chat_message])
    mock_mongodb.chat_messages = mock_messages

    response = await client.get(
        f"/api/v1/chat/sessions/{sample_chat_session['sessionId']}/messages",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_send_chat_message(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_chat_session,
):
    """Test sending a chat message."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_sessions = MagicMock()
    mock_sessions.find_one = AsyncMock(return_value=sample_chat_session)
    mock_sessions.update_one = AsyncMock()
    # Mock find_one_and_update for atomic message counter increment
    mock_sessions.find_one_and_update = AsyncMock(return_value={
        **sample_chat_session,
        "sessionContext": {"messageCount": 2, "thread": []},
    })
    mock_mongodb.chat_sessions = mock_sessions

    mock_messages = MagicMock()
    mock_messages.find_one = AsyncMock(return_value=None)
    mock_messages.insert_one = AsyncMock()
    mock_mongodb.chat_messages = mock_messages

    response = await client.post(
        f"/api/v1/chat/sessions/{sample_chat_session['sessionId']}/messages",
        json={"role": "user", "content": "List all active servers"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "List all active servers"


@pytest.mark.asyncio
async def test_chat_forbidden_for_agent(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agents cannot access chat."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        "/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_chat_session_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test accessing non-existent chat session."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_chat = MagicMock()
    mock_chat.find_one = AsyncMock(return_value=None)
    mock_mongodb.chat_sessions = mock_chat

    response = await client.get(
        "/api/v1/chat/sessions/sess-nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_chat_session,
):
    """Test chat sessions pagination."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_chat = MagicMock()
    mock_chat.count_documents = AsyncMock(return_value=50)
    mock_chat.find_one = AsyncMock(return_value=sample_chat_session)
    mock_chat.find.return_value = create_mock_cursor([sample_chat_session])
    mock_mongodb.chat_sessions = mock_chat

    response = await client.get(
        "/api/v1/chat/sessions?limit=10&offset=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
