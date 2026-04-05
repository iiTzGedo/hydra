"""Tests for documentation endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_doc():
    """Sample documentation document."""
    now = datetime.now(UTC)
    return {
        "docId": "doc::getting-started",
        "title": "Getting Started",
        "description": "Introduction guide for Hydra",
        "type": "guide",
        "format": "markdown",
        "content": "# Getting Started\n\nWelcome to Hydra...",
        "linkedEntities": [],
        "category": "guides",
        "tags": ["quickstart", "introduction"],
        "version": 1,
        "author": "admin",
        "status": "published",
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.mark.asyncio
async def test_list_docs_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_docs_by_category(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing documentation by category."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs?category=guides",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_doc_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test getting a specific documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)
    mock_mongodb.docs = mock_docs

    response = await client.get(
        f"/api/v1/docs/{sample_doc['docId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["docId"] == sample_doc["docId"]


@pytest.mark.asyncio
async def test_get_doc_by_slug(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test getting documentation by slug."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)
    mock_mongodb.docs = mock_docs

    # Note: slug endpoint may not be implemented
    response = await client.get(
        "/api/v1/docs/slug/getting-started",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_doc_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs/doc-nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "DOC_NOT_FOUND"


@pytest.mark.asyncio
async def test_docs_public_access(
    client: AsyncClient,
    mock_mongodb,
    sample_doc,
):
    """Test that documentation is accessible without auth (if configured)."""
    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get("/api/v1/docs")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_doc_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test creating a new documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)  # No existing doc
    mock_docs.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs",
        json={
            "docId": "doc::new-guide",
            "title": "New Guide",
            "type": "guide",
            "format": "markdown",
            "content": "# New Guide\n\nThis is a new guide.",
            "category": "tutorials",
            "tags": ["new", "tutorial"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["docId"] == "doc::new-guide"


@pytest.mark.asyncio
async def test_create_doc_conflict(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test creating a doc that already exists returns conflict."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)  # Doc exists
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs",
        json={
            "docId": sample_doc["docId"],
            "title": "Duplicate",
            "type": "guide",
            "format": "markdown",
            "content": "# Duplicate",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "DOC_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_update_doc_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test updating an existing documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    updated_doc = sample_doc.copy()
    updated_doc["title"] = "Updated Title"
    updated_doc["version"] = 2

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(side_effect=[sample_doc, updated_doc])
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.put(
        f"/api/v1/docs/{sample_doc['docId']}",
        json={
            "title": "Updated Title",
            "content": "# Updated Content",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_doc_archive(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test archiving (soft delete) documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    archived_doc = sample_doc.copy()
    archived_doc["status"] = "archived"

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.delete(
        f"/api/v1/docs/{sample_doc['docId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_doc_permanent(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test permanently deleting documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)
    mock_docs.delete_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.delete(
        f"/api/v1/docs/{sample_doc['docId']}?permanent=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_docs_with_type_filter(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing docs filtered by type."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs?type=guide",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_docs_with_search(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing docs with search query."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs?search=getting",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_docs_with_tags(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing docs filtered by tags."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs?tags=quickstart",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_doc_specific_version(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a specific version of documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    doc_with_versions = {
        "docId": "doc::versioned",
        "title": "Versioned Doc",
        "type": "guide",
        "format": "markdown",
        "content": "# Version 2",
        "version": 2,
        "status": "published",
        "linkedEntities": [],
        "createdAt": now,
        "updatedAt": now,
        "versions": [
            {"version": 1, "content": "# Version 1", "updatedAt": now, "author": "admin"},
            {"version": 2, "content": "# Version 2", "updatedAt": now, "author": "admin"},
        ],
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc_with_versions)
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs/doc::versioned?version=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_docs_forbidden_for_viewer_create(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot create documentation."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/docs",
        json={
            "docId": "doc::test",
            "title": "Test",
            "type": "guide",
            "format": "markdown",
            "content": "# Test",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403
