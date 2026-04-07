"""Tests for document template endpoints (P2DOC-001)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_template():
    """Sample document template stored in MongoDB."""
    now = datetime.now(UTC)
    return {
        "templateId": "tmpl::runbook-overview",
        "name": "Runbook Overview",
        "description": "Overview section for node runbooks",
        "docType": "runbook",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "contentTemplate": "Node $node_id is a $node_class node.",
                "order": 1,
            },
            {
                "sectionId": "services",
                "title": "Services",
                "contentTemplate": "Running services: $services",
                "order": 2,
            },
        ],
        "variables": [
            {"name": "node_id", "source": "node.nodeId", "description": "Node identifier"},
            {"name": "node_class", "source": "node.class", "description": "Node class"},
            {"name": "services", "source": "services[].name", "description": "Service names"},
        ],
        "staleAfterHours": 24,
        "createdAt": now,
        "updatedAt": now,
    }


def _admin_setup(mock_mongodb, sample_user):
    """Configure mock_mongodb with an admin user."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    return admin_user


# ── Template CRUD Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_template(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test creating a new document template."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=None)  # No existing
    mock_templates.insert_one = AsyncMock()
    mock_mongodb.doc_templates = mock_templates

    response = await client.post(
        "/api/v1/docs/templates",
        json={
            "templateId": "tmpl::my-runbook",
            "name": "My Runbook Template",
            "docType": "runbook",
            "sections": [
                {
                    "sectionId": "overview",
                    "title": "Overview",
                    "contentTemplate": "This is node $node_id.",
                    "order": 1,
                },
            ],
            "variables": [
                {"name": "node_id", "source": "node.nodeId", "description": "The node ID"},
            ],
            "staleAfterHours": 48,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["templateId"] == "tmpl::my-runbook"
    assert data["name"] == "My Runbook Template"
    assert data["docType"] == "runbook"
    assert len(data["sections"]) == 1
    assert data["staleAfterHours"] == 48


@pytest.mark.asyncio
async def test_create_template_conflict(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """Test that creating a template with a duplicate ID returns 409."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    response = await client.post(
        "/api/v1/docs/templates",
        json={
            "templateId": sample_template["templateId"],
            "name": "Duplicate",
            "docType": "runbook",
            "sections": [
                {
                    "sectionId": "s1",
                    "title": "S1",
                    "contentTemplate": "Content",
                    "order": 1,
                },
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_templates(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """Test listing document templates with pagination."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.count_documents = AsyncMock(return_value=1)
    mock_templates.find.return_value = create_mock_cursor([sample_template])
    mock_mongodb.doc_templates = mock_templates

    response = await client.get(
        "/api/v1/docs/templates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] == 1
    assert len(data["data"]) == 1
    assert data["data"][0]["templateId"] == sample_template["templateId"]
    assert data["data"][0]["sectionCount"] == 2


@pytest.mark.asyncio
async def test_get_template(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """Test retrieving a single template by ID."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    response = await client.get(
        f"/api/v1/docs/templates/{sample_template['templateId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["templateId"] == sample_template["templateId"]
    assert data["docType"] == "runbook"
    assert len(data["sections"]) == 2
    assert len(data["variables"]) == 3


@pytest.mark.asyncio
async def test_get_template_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that fetching a non-existent template returns 404."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=None)
    mock_mongodb.doc_templates = mock_templates

    response = await client.get(
        "/api/v1/docs/templates/tmpl::nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_template(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """Test updating (PUT replacement) a document template."""
    _admin_setup(mock_mongodb, sample_user)

    updated = sample_template.copy()
    updated["name"] = "Updated Name"

    mock_templates = MagicMock()
    # First call: get_template in update_template, second: get_template for return
    mock_templates.find_one = AsyncMock(side_effect=[sample_template, updated])
    mock_templates.update_one = AsyncMock()
    mock_mongodb.doc_templates = mock_templates

    response = await client.put(
        f"/api/v1/docs/templates/{sample_template['templateId']}",
        json={
            "name": "Updated Name",
            "docType": "runbook",
            "sections": [
                {
                    "sectionId": "overview",
                    "title": "Overview",
                    "contentTemplate": "Updated: $node_id",
                    "order": 1,
                },
            ],
            "variables": [],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_template(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """Test deleting a document template."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_templates.delete_one = AsyncMock()
    mock_mongodb.doc_templates = mock_templates

    response = await client.delete(
        f"/api/v1/docs/templates/{sample_template['templateId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["templateId"] == sample_template["templateId"]
    assert data["deleted"] is True


# ── Template Rendering Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_render_template_creates_document(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """Test that rendering a template creates a new document with generated sections."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)  # No existing doc
    mock_docs.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.post(
        f"/api/v1/docs/templates/{sample_template['templateId']}/render",
        json={
            "docId": "doc::proxmox-01-runbook",
            "title": "Runbook: proxmox-01",
            "variables": {
                "node_id": "proxmox-01",
                "node_class": "compute",
                "services": "nginx, mongodb",
            },
            "category": "infrastructure",
            "tags": ["proxmox", "runbook"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["docId"] == "doc::proxmox-01-runbook"
    assert data["title"] == "Runbook: proxmox-01"
    assert data["version"] == 1

    # Verify the document was inserted with correct section content
    insert_call = mock_docs.insert_one.call_args[0][0]
    assert len(insert_call["sections"]) == 2
    assert insert_call["sections"][0]["content"] == "Node proxmox-01 is a compute node."
    assert insert_call["sections"][1]["content"] == "Running services: nginx, mongodb"
    assert insert_call["sections"][0]["source"] == "generated"
    assert insert_call["templateId"] == sample_template["templateId"]
    assert insert_call["lastGeneratedAt"] is not None
    assert insert_call["staleAfterHours"] == 24


@pytest.mark.asyncio
async def test_render_template_with_variables(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """Test that variable substitution works correctly, including missing variables."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)
    mock_docs.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    # Only provide node_id, leave node_class and services unresolved
    response = await client.post(
        f"/api/v1/docs/templates/{sample_template['templateId']}/render",
        json={
            "docId": "doc::partial-render",
            "title": "Partial Render",
            "variables": {
                "node_id": "test-node",
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201

    # safe_substitute leaves unresolved $variables as-is
    insert_call = mock_docs.insert_one.call_args[0][0]
    assert insert_call["sections"][0]["content"] == "Node test-node is a $node_class node."
    assert insert_call["sections"][1]["content"] == "Running services: $services"


@pytest.mark.asyncio
async def test_render_template_doc_conflict(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """Test that rendering into an existing doc_id returns 409."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    existing_doc = {"docId": "doc::already-exists"}
    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=existing_doc)
    mock_mongodb.docs = mock_docs

    response = await client.post(
        f"/api/v1/docs/templates/{sample_template['templateId']}/render",
        json={
            "docId": "doc::already-exists",
            "title": "Duplicate",
            "variables": {},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


# ── Staleness Detection Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_stale_documents(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that the stale endpoint returns documents past their staleness threshold."""
    _admin_setup(mock_mongodb, sample_user)

    now = datetime.now(UTC)
    stale_doc = {
        "docId": "doc::stale-runbook",
        "title": "Stale Runbook",
        "type": "runbook",
        "format": "markdown",
        "content": "# Stale",
        "linkedEntities": [],
        "version": 1,
        "status": "published",
        "lastGeneratedAt": now - timedelta(hours=48),  # 48 hours ago
        "staleAfterHours": 24,  # 24 hour threshold
        "createdAt": now - timedelta(hours=48),
        "updatedAt": now - timedelta(hours=48),
    }

    fresh_doc = {
        "docId": "doc::fresh-runbook",
        "title": "Fresh Runbook",
        "type": "runbook",
        "format": "markdown",
        "content": "# Fresh",
        "linkedEntities": [],
        "version": 1,
        "status": "published",
        "lastGeneratedAt": now - timedelta(hours=1),  # 1 hour ago
        "staleAfterHours": 24,  # 24 hour threshold
        "createdAt": now - timedelta(hours=1),
        "updatedAt": now - timedelta(hours=1),
    }

    mock_docs = MagicMock()
    mock_docs.find.return_value = create_mock_cursor([stale_doc, fresh_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs/stale",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] == 1
    assert len(data["data"]) == 1
    assert data["data"][0]["docId"] == "doc::stale-runbook"


@pytest.mark.asyncio
async def test_get_stale_documents_empty(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that stale endpoint returns empty list when no documents are stale."""
    _admin_setup(mock_mongodb, sample_user)

    mock_docs = MagicMock()
    mock_docs.find.return_value = create_mock_cursor([])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs/stale",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] == 0
    assert len(data["data"]) == 0


# ── Permission Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_template_requires_write_permission(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that creating a template requires docs:write permission (viewer is denied)."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/docs/templates",
        json={
            "templateId": "tmpl::forbidden",
            "name": "Forbidden Template",
            "docType": "guide",
            "sections": [
                {
                    "sectionId": "s1",
                    "title": "S1",
                    "contentTemplate": "Content",
                    "order": 1,
                },
            ],
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_render_template_requires_write_permission(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that rendering a template requires docs:write permission."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/docs/templates/tmpl::any/render",
        json={
            "docId": "doc::rendered",
            "title": "Rendered Doc",
            "variables": {},
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_stale_endpoint_requires_read_permission(
    client: AsyncClient,
    mock_mongodb,
):
    """Test that the stale endpoint requires authentication."""
    response = await client.get("/api/v1/docs/stale")
    assert response.status_code == 401


# ── DocResponse Section Serialization ───────────────────────────────────


@pytest.mark.asyncio
async def test_doc_response_includes_sections(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that the GET /docs/{doc_id} response includes sections when present."""
    _admin_setup(mock_mongodb, sample_user)

    now = datetime.now(UTC)
    doc_with_sections = {
        "docId": "doc::sectioned",
        "title": "Sectioned Doc",
        "description": "A document with sections",
        "type": "runbook",
        "format": "markdown",
        "content": "# Full content",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "## Overview\n\nThis is the overview.",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": "abc123",
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 1,
            },
            {
                "sectionId": "notes",
                "title": "Notes",
                "content": "## Notes\n\nManual notes here.",
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": "admin",
                "order": 2,
            },
        ],
        "linkedEntities": [],
        "tags": [],
        "version": 1,
        "author": "admin",
        "status": "published",
        "templateId": "tmpl::runbook-overview",
        "lastGeneratedAt": now,
        "staleAfterHours": 24,
        "createdAt": now,
        "updatedAt": now,
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc_with_sections)
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs/doc::sectioned",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["sections"]) == 2
    assert data["sections"][0]["sectionId"] == "overview"
    assert data["sections"][0]["source"] == "generated"
    assert data["sections"][1]["sectionId"] == "notes"
    assert data["sections"][1]["source"] == "manual"
    assert data["templateId"] == "tmpl::runbook-overview"
    assert data["lastGeneratedAt"] is not None
    assert data["staleAfterHours"] == 24


# ── Auto-Generation Pipeline Tests (P2DOC-002) ────────────────────────


@pytest.fixture
def sample_node_entity():
    """Sample node document for entity resolution."""
    return {
        "nodeId": "proxmox-01",
        "class": "compute",
        "type": "physical",
        "displayName": "Proxmox 01",
        "description": "Main hypervisor",
        "tags": ["production", "hypervisor"],
        "status": "active",
        "agentTier": "normal",
    }


@pytest.mark.asyncio
async def test_generate_document_from_entity(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
    sample_node_entity,
):
    """Generate a doc from template + node entity data."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)  # No existing doc
    mock_docs.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node_entity)

    response = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::runbook-overview",
            "entityType": "node",
            "entityId": "proxmox-01",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["docId"] == "doc::runbook-overview-proxmox-01"
    assert data["templateId"] == "tmpl::runbook-overview"
    assert len(data["linkedEntities"]) == 1
    assert data["linkedEntities"][0]["entityType"] == "node"
    assert data["linkedEntities"][0]["entityId"] == "proxmox-01"

    # Verify sections rendered with entity data
    insert_call = mock_docs.insert_one.call_args[0][0]
    assert "proxmox-01" in insert_call["sections"][0]["content"]
    assert "compute" in insert_call["sections"][0]["content"]
    assert insert_call["sections"][0]["source"] == "generated"


@pytest.mark.asyncio
async def test_generate_document_template_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """404 when template doesn't exist."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=None)
    mock_mongodb.doc_templates = mock_templates

    response = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::nonexistent",
            "entityType": "node",
            "entityId": "proxmox-01",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_document_entity_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
):
    """404 when entity doesn't exist."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)

    response = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::runbook-overview",
            "entityType": "node",
            "entityId": "nonexistent-node",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_document_with_variable_overrides(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
    sample_node_entity,
):
    """Variable overrides take precedence over entity data."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)
    mock_docs.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node_entity)

    response = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::runbook-overview",
            "entityType": "node",
            "entityId": "proxmox-01",
            "variables": {"services": "docker, redis, nginx"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    insert_call = mock_docs.insert_one.call_args[0][0]
    assert "docker, redis, nginx" in insert_call["sections"][1]["content"]


@pytest.mark.asyncio
async def test_regenerate_document(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
    sample_node_entity,
):
    """Regenerate updates generated sections, preserves manual."""
    _admin_setup(mock_mongodb, sample_user)

    now = datetime.now(UTC)
    generated_doc = {
        "docId": "doc::runbook-overview-proxmox-01",
        "title": "Runbook: proxmox-01",
        "type": "runbook",
        "format": "markdown",
        "content": "## Overview\n\nOld content\n\n## Notes\n\nManual notes",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "Old content",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": "old_fp",
                "lastGeneratedAt": now - timedelta(hours=48),
                "lastEditedAt": None,
                "editedBy": None,
                "order": 1,
            },
            {
                "sectionId": "services",
                "title": "Services",
                "content": "Old services",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": "old_fp",
                "lastGeneratedAt": now - timedelta(hours=48),
                "lastEditedAt": None,
                "editedBy": None,
                "order": 2,
            },
            {
                "sectionId": "notes",
                "title": "Notes",
                "content": "Manual notes here",
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": "admin",
                "order": 3,
            },
        ],
        "linkedEntities": [{"entityType": "node", "entityId": "proxmox-01"}],
        "version": 1,
        "status": "published",
        "templateId": "tmpl::runbook-overview",
        "lastGeneratedAt": now - timedelta(hours=48),
        "staleAfterHours": 24,
        "createdAt": now - timedelta(hours=48),
        "updatedAt": now - timedelta(hours=48),
        "versions": [],
    }

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=generated_doc)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node_entity)

    response = await client.post(
        "/api/v1/docs/doc::runbook-overview-proxmox-01/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["docId"] == "doc::runbook-overview-proxmox-01"
    assert data["version"] == 2
    assert data["sectionsUpdated"] == 2
    assert data["sectionsSkipped"] == 1
    assert "notes" in data["skippedSectionIds"]


@pytest.mark.asyncio
async def test_regenerate_manual_document_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Can't regenerate a doc without templateId."""
    _admin_setup(mock_mongodb, sample_user)

    now = datetime.now(UTC)
    manual_doc = {
        "docId": "doc::manual-doc",
        "title": "Manual Doc",
        "type": "guide",
        "format": "markdown",
        "content": "# Manual",
        "sections": [],
        "linkedEntities": [],
        "version": 1,
        "status": "published",
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=manual_doc)
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs/doc::manual-doc/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "template" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_regenerate_preserves_manual_sections(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_template,
    sample_node_entity,
):
    """Manual sections are not touched during regeneration."""
    _admin_setup(mock_mongodb, sample_user)

    now = datetime.now(UTC)
    doc_with_manual = {
        "docId": "doc::mixed-doc",
        "title": "Mixed Doc",
        "type": "runbook",
        "format": "markdown",
        "content": "## Overview\n\nOld\n\n## Manual\n\nDo not touch",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "Old",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": "old_fp",
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 1,
            },
            {
                "sectionId": "manual-section",
                "title": "Manual",
                "content": "Do not touch",
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": "admin",
                "order": 2,
            },
        ],
        "linkedEntities": [{"entityType": "node", "entityId": "proxmox-01"}],
        "version": 1,
        "status": "published",
        "templateId": "tmpl::runbook-overview",
        "lastGeneratedAt": now,
        "staleAfterHours": 24,
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=sample_template)
    mock_mongodb.doc_templates = mock_templates

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc_with_manual)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node_entity)

    response = await client.post(
        "/api/v1/docs/doc::mixed-doc/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    # Template has "overview" + "services"; doc had "overview" (generated) + "manual-section" (manual).
    # Merge engine renders both template sections (2 updated) and preserves the orphaned manual section (1 skipped).
    assert data["sectionsUpdated"] == 2
    assert data["sectionsSkipped"] == 1
    assert "manual-section" in data["skippedSectionIds"]

    # Verify the manual section content was preserved in the update call
    set_call = mock_docs.update_one.call_args_list[1]
    updated_sections = set_call[0][1]["$set"]["sections"]
    manual = [s for s in updated_sections if s["sectionId"] == "manual-section"][0]
    assert manual["content"] == "Do not touch"
    assert manual["source"] == "manual"


@pytest.mark.asyncio
async def test_check_staleness_detects_stale_sections(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Section with changed fingerprint reported as stale."""
    _admin_setup(mock_mongodb, sample_user)

    now = datetime.now(UTC)
    doc = {
        "docId": "doc::stale-check",
        "title": "Stale Check",
        "type": "runbook",
        "format": "markdown",
        "content": "## Overview\n\nOld data",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "Old data",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": "stale_fingerprint",
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 1,
            },
        ],
        "linkedEntities": [{"entityType": "node", "entityId": "proxmox-01"}],
        "version": 1,
        "status": "published",
        "templateId": "tmpl::runbook-overview",
        "lastGeneratedAt": now,
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_mongodb.docs = mock_docs

    # Node has changed data -> different fingerprint
    mock_mongodb.nodes.find_one = AsyncMock(return_value={
        "nodeId": "proxmox-01",
        "class": "compute",
        "type": "physical",
        "displayName": "Updated Proxmox",
        "description": "Changed description",
        "tags": ["updated"],
        "status": "active",
        "agentTier": "normal",
    })

    response = await client.get(
        "/api/v1/docs/doc::stale-check/staleness",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["isStale"] is True
    assert len(data["staleSections"]) == 1
    assert data["staleSections"][0]["sectionId"] == "overview"
    assert data["staleSections"][0]["storedFingerprint"] == "stale_fingerprint"


@pytest.mark.asyncio
async def test_check_staleness_all_fresh(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_node_entity,
):
    """No stale sections when fingerprints match."""
    _admin_setup(mock_mongodb, sample_user)

    # Compute the fingerprint that would result from sample_node_entity
    from hydra.api.v1.services.docs import _compute_fingerprint
    entity_vars = {
        "node_id": sample_node_entity["nodeId"],
        "node_class": sample_node_entity["class"],
        "node_type": sample_node_entity["type"],
        "display_name": sample_node_entity["displayName"],
        "hostname": sample_node_entity["displayName"],
        "description": sample_node_entity["description"],
        "tags": ", ".join(sample_node_entity["tags"]),
        "status": sample_node_entity["status"],
        "agent_tier": sample_node_entity["agentTier"],
    }
    current_fp = _compute_fingerprint(entity_vars)

    now = datetime.now(UTC)
    doc = {
        "docId": "doc::fresh-check",
        "title": "Fresh Check",
        "type": "runbook",
        "format": "markdown",
        "content": "## Overview\n\nCurrent data",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "Current data",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": current_fp,
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 1,
            },
        ],
        "linkedEntities": [{"entityType": "node", "entityId": "proxmox-01"}],
        "version": 1,
        "status": "published",
        "templateId": "tmpl::runbook-overview",
        "lastGeneratedAt": now,
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_mongodb.docs = mock_docs

    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node_entity)

    response = await client.get(
        "/api/v1/docs/doc::fresh-check/staleness",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["isStale"] is False
    assert len(data["staleSections"]) == 0


@pytest.mark.asyncio
async def test_flag_docs_stale_for_entity(
    mock_mongodb,
    sample_user,
):
    """Flag docs linked to an entity as stale."""
    from hydra.api.v1.services.docs import DocsService

    mock_result = MagicMock()
    mock_result.modified_count = 2
    mock_mongodb.docs.update_many = AsyncMock(return_value=mock_result)

    service = DocsService(mock_mongodb)
    count = await service.flag_docs_stale_for_entity("node", "proxmox-01")

    assert count == 2
    mock_mongodb.docs.update_many.assert_awaited_once()
    call_args = mock_mongodb.docs.update_many.call_args
    epoch = datetime(2000, 1, 1, tzinfo=UTC)
    assert call_args[0][1] == {"$set": {"lastGeneratedAt": epoch}}


@pytest.mark.asyncio
async def test_flagged_stale_docs_appear_in_get_stale_docs(
    mock_mongodb,
):
    """After flag_docs_stale_for_entity, documents appear in get_stale_docs."""
    from hydra.api.v1.services.docs import DocsService

    # A document that was flagged stale (lastGeneratedAt set to epoch)
    epoch = datetime(2000, 1, 1, tzinfo=UTC)
    flagged_doc = {
        "docId": "doc::flagged",
        "lastGeneratedAt": epoch,
        "staleAfterHours": 24,
        "status": "published",
    }

    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=[flagged_doc])
    mock_mongodb.docs.find = MagicMock(return_value=mock_cursor)

    service = DocsService(mock_mongodb)
    stale_docs, total = await service.get_stale_docs()

    assert total == 1
    assert stale_docs[0]["docId"] == "doc::flagged"


@pytest.mark.asyncio
async def test_generate_document_requires_permission(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """403 without docs:write permission."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::runbook-overview",
            "entityType": "node",
            "entityId": "proxmox-01",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_regenerate_requires_permission(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """403 without docs:write permission on regenerate."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/docs/doc::any-doc/regenerate",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_staleness_requires_permission(
    client: AsyncClient,
    mock_mongodb,
):
    """401 without auth on staleness check."""
    response = await client.get("/api/v1/docs/doc::any-doc/staleness")
    assert response.status_code == 401
