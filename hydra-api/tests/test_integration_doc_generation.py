"""Integration tests for the documentation generation lifecycle (W5-IT4).

Covers: template creation, document generation from templates, hybrid editing
(manual sections preserved on regeneration), staleness detection, and
cross-entity updates.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor

# ── Helpers ────────────────────────────────────────────────────────────


def _admin_setup(mock_mongodb: Any, sample_user: dict[str, Any]) -> dict[str, Any]:
    """Configure mock_mongodb with an admin user."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    return admin_user


def _make_template(
    template_id: str = "tmpl::node-runbook",
    *,
    stale_after_hours: int = 24,
) -> dict[str, Any]:
    """Build a sample template document for tests."""
    now = datetime.now(UTC)
    return {
        "templateId": template_id,
        "name": "Node Runbook",
        "description": "Auto-generated runbook for a node",
        "docType": "runbook",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "contentTemplate": "Hostname: $hostname, IP: $ip_address",
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
            {"name": "hostname", "source": "node.displayName", "description": "Node hostname"},
            {"name": "ip_address", "source": "node.network.ipv4", "description": "Node IP"},
            {"name": "services", "source": "services[].name", "description": "Service names"},
        ],
        "staleAfterHours": stale_after_hours,
        "createdAt": now,
        "updatedAt": now,
    }


def _make_generated_doc(
    doc_id: str = "doc::node-runbook-test-server-01",
    template_id: str = "tmpl::node-runbook",
    *,
    sections: list[dict[str, Any]] | None = None,
    version: int = 1,
    hours_ago: int = 0,
    stale_after_hours: int = 24,
    linked_entities: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a generated document for tests."""
    now = datetime.now(UTC) - timedelta(hours=hours_ago)
    if sections is None:
        sections = [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "Hostname: test-server-01, IP: 192.168.1.100",
                "source": "generated",
                "templateRef": template_id,
                "dataFingerprint": "abc123",
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 1,
            },
            {
                "sectionId": "services",
                "title": "Services",
                "content": "Running services: nginx, mongodb",
                "source": "generated",
                "templateRef": template_id,
                "dataFingerprint": "abc123",
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 2,
            },
        ]
    if linked_entities is None:
        linked_entities = [{"entityType": "node", "entityId": "test-server-01"}]
    return {
        "docId": doc_id,
        "title": "Runbook: test-server-01",
        "description": "Auto-generated runbook for a node",
        "type": "runbook",
        "format": "markdown",
        "content": "## Overview\n\nHostname: test-server-01, IP: 192.168.1.100\n\n## Services\n\nRunning services: nginx, mongodb",
        "sections": sections,
        "linkedEntities": linked_entities,
        "category": None,
        "tags": [],
        "version": version,
        "author": "admin",
        "status": "published",
        "templateId": template_id,
        "lastGeneratedAt": now,
        "staleAfterHours": stale_after_hours,
        "createdAt": now,
        "updatedAt": now,
        "versions": [
            {
                "version": version,
                "content": "## Overview\n\nHostname: test-server-01, IP: 192.168.1.100\n\n## Services\n\nRunning services: nginx, mongodb",
                "sections": sections,
                "updatedAt": now,
                "author": "admin",
            },
        ],
    }


def _make_node(
    node_id: str = "test-server-01",
    *,
    display_name: str = "test-server-01",
    status: str = "active",
) -> dict[str, Any]:
    """Build a minimal node document."""
    now = datetime.now(UTC)
    return {
        "nodeId": node_id,
        "class": "compute",
        "type": "physical",
        "kind": "bare-metal",
        "displayName": display_name,
        "description": "A test server",
        "tags": ["test"],
        "parentNodeId": None,
        "agentTier": "normal",
        "networkIds": [],
        "registeredAt": now,
        "lastUpdated": now,
        "lastProfileAt": now,
        "status": status,
    }


# ── 1. Template-to-Doc Generation ─────────────────────────────────────


@pytest.mark.asyncio
async def test_template_to_doc_generation(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Create a template with variables, generate a doc via POST /docs/generate,
    and verify generated content is interpolated with actual node values."""
    _admin_setup(mock_mongodb, sample_user)

    template = _make_template()
    node = _make_node()

    # Template lookup
    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=template)
    mock_mongodb.doc_templates = mock_templates

    # Node lookup for entity data resolution
    mock_mongodb.nodes.find_one = AsyncMock(return_value=node)

    # Doc collection: no existing doc, then insert
    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)
    mock_docs.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::node-runbook",
            "entityType": "node",
            "entityId": "test-server-01",
            "variables": {
                "ip_address": "192.168.1.100",
                "services": "nginx, mongodb",
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["docId"] == "doc::node-runbook-test-server-01"
    assert data["type"] == "runbook"
    assert data["version"] == 1
    assert data["templateId"] == "tmpl::node-runbook"

    # Verify sections have interpolated content
    sections = data["sections"]
    assert len(sections) == 2
    overview = sections[0]
    assert overview["sectionId"] == "overview"
    assert overview["source"] == "generated"
    # hostname is resolved from node.displayName, ip_address from variable override
    assert "test-server-01" in overview["content"]
    assert "192.168.1.100" in overview["content"]

    services_section = sections[1]
    assert services_section["sectionId"] == "services"
    assert "nginx, mongodb" in services_section["content"]

    # Verify linkedEntities
    assert len(data["linkedEntities"]) == 1
    assert data["linkedEntities"][0]["entityType"] == "node"
    assert data["linkedEntities"][0]["entityId"] == "test-server-01"


# ── 2. Hybrid Edit Preservation ──────────────────────────────────────


@pytest.mark.asyncio
async def test_hybrid_edit_preservation(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Generate doc from template, manually edit one section (marking it
    manual-override), regenerate, and verify the manual section is preserved
    while template-driven sections are updated."""
    _admin_setup(mock_mongodb, sample_user)

    template = _make_template()
    node = _make_node()
    doc = _make_generated_doc()

    # --- Step 1: Edit the "overview" section via PATCH ---

    # After edit, section becomes manual-override
    edited_doc = _make_generated_doc(version=2)
    edited_doc["sections"][0]["source"] = "manual-override"
    edited_doc["sections"][0]["content"] = "Manually written overview"
    edited_doc["sections"][0]["lastEditedAt"] = datetime.now(UTC)
    edited_doc["sections"][0]["editedBy"] = "user_admin123"
    edited_doc["version"] = 2

    mock_docs = MagicMock()
    # edit_section calls get_doc (find_one) then get_doc again after update
    mock_docs.find_one = AsyncMock(side_effect=[doc, edited_doc])
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    edit_response = await client.patch(
        f"/api/v1/docs/{doc['docId']}/sections/overview",
        json={"content": "Manually written overview"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert edit_response.status_code == 200
    edit_data = edit_response.json()["data"]
    # Find the overview section in the response
    overview_section = next(s for s in edit_data["sections"] if s["sectionId"] == "overview")
    assert overview_section["source"] == "manual-override"
    assert overview_section["content"] == "Manually written overview"

    # --- Step 2: Regenerate the document ---

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=template)
    mock_mongodb.doc_templates = mock_templates

    mock_mongodb.nodes.find_one = AsyncMock(return_value=node)

    # regenerate calls get_doc first
    mock_docs2 = MagicMock()
    mock_docs2.find_one = AsyncMock(return_value=edited_doc)
    mock_docs2.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs2

    regen_response = await client.post(
        f"/api/v1/docs/{doc['docId']}/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert regen_response.status_code == 200
    regen_data = regen_response.json()["data"]
    assert regen_data["docId"] == doc["docId"]
    assert regen_data["sectionsSkipped"] == 1
    assert "overview" in regen_data["skippedSectionIds"]
    assert regen_data["sectionsUpdated"] == 1
    assert regen_data["warningCount"] >= 1

    # Verify warning about manual override preservation
    warnings = regen_data["warnings"]
    assert any(w["code"] == "MANUAL_OVERRIDE_PRESERVED" for w in warnings)


# ── 3. Variable Staleness Detection ──────────────────────────────────


@pytest.mark.asyncio
async def test_variable_staleness_detection(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Generate doc referencing node data, change the node's data, and verify
    per-section staleness is detected via GET /docs/{doc_id}/staleness."""
    _admin_setup(mock_mongodb, sample_user)

    doc = _make_generated_doc()

    # Node has changed (different displayName) since the doc was generated
    updated_node = _make_node(display_name="new-hostname")

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_mongodb.docs = mock_docs

    mock_mongodb.nodes.find_one = AsyncMock(return_value=updated_node)

    response = await client.get(
        f"/api/v1/docs/{doc['docId']}/staleness",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["docId"] == doc["docId"]
    assert data["isStale"] is True
    assert len(data["staleSections"]) >= 1

    # Both generated sections should be stale because the fingerprint changed
    stale_ids = [s["sectionId"] for s in data["staleSections"]]
    assert "overview" in stale_ids
    assert "services" in stale_ids

    # Verify fingerprints differ
    for section_info in data["staleSections"]:
        assert section_info["currentFingerprint"] != section_info["storedFingerprint"]


# ── 4. Cross-Entity Doc Update ───────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_entity_doc_update(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Generate doc linked to a node entity, change entity data (simulating
    adding a service), regenerate, and verify updated content."""
    _admin_setup(mock_mongodb, sample_user)

    template = _make_template()
    doc = _make_generated_doc()

    # The node data now includes updated info
    updated_node = _make_node(display_name="updated-server")

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=template)
    mock_mongodb.doc_templates = mock_templates

    mock_mongodb.nodes.find_one = AsyncMock(return_value=updated_node)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.post(
        f"/api/v1/docs/{doc['docId']}/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    regen_data = response.json()["data"]

    # Both sections were generated (no manual overrides), so both should update
    assert regen_data["sectionsUpdated"] == 2
    assert regen_data["sectionsSkipped"] == 0

    # Verify the update_one call used the new content
    update_calls = mock_docs.update_one.call_args_list
    # The second update_one call sets content/sections/version
    set_call = update_calls[1][0][1]["$set"]
    assert "updated-server" in set_call["content"]


# ── 5. Multi-Template Independence ───────────────────────────────────


@pytest.mark.asyncio
async def test_multi_template_independence(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Create two different templates, generate docs from each for the same entity,
    and verify both docs are independent with correctly templated content."""
    _admin_setup(mock_mongodb, sample_user)

    template_a = _make_template(template_id="tmpl::runbook-a")
    template_a["name"] = "Runbook A"
    template_a["sections"] = [
        {
            "sectionId": "intro",
            "title": "Introduction",
            "contentTemplate": "Intro for $hostname",
            "order": 1,
        },
    ]

    template_b = _make_template(template_id="tmpl::runbook-b")
    template_b["name"] = "Runbook B"
    template_b["sections"] = [
        {
            "sectionId": "summary",
            "title": "Summary",
            "contentTemplate": "Summary for $hostname at $ip_address",
            "order": 1,
        },
    ]

    node = _make_node()

    # --- Render template A ---
    mock_templates_a = MagicMock()
    mock_templates_a.find_one = AsyncMock(return_value=template_a)
    mock_mongodb.doc_templates = mock_templates_a
    mock_mongodb.nodes.find_one = AsyncMock(return_value=node)

    mock_docs_a = MagicMock()
    mock_docs_a.find_one = AsyncMock(return_value=None)
    mock_docs_a.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs_a

    response_a = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::runbook-a",
            "entityType": "node",
            "entityId": "test-server-01",
            "variables": {"ip_address": "10.0.0.1"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response_a.status_code == 201
    data_a = response_a.json()["data"]
    assert data_a["templateId"] == "tmpl::runbook-a"
    sections_a = data_a["sections"]
    assert len(sections_a) == 1
    assert sections_a[0]["sectionId"] == "intro"
    assert "test-server-01" in sections_a[0]["content"]

    # --- Render template B ---
    mock_templates_b = MagicMock()
    mock_templates_b.find_one = AsyncMock(return_value=template_b)
    mock_mongodb.doc_templates = mock_templates_b

    mock_docs_b = MagicMock()
    mock_docs_b.find_one = AsyncMock(return_value=None)
    mock_docs_b.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs_b

    response_b = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::runbook-b",
            "entityType": "node",
            "entityId": "test-server-01",
            "variables": {"ip_address": "10.0.0.1"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response_b.status_code == 201
    data_b = response_b.json()["data"]
    assert data_b["templateId"] == "tmpl::runbook-b"
    sections_b = data_b["sections"]
    assert len(sections_b) == 1
    assert sections_b[0]["sectionId"] == "summary"
    assert "10.0.0.1" in sections_b[0]["content"]

    # Verify independence: different doc IDs and different content
    assert data_a["docId"] != data_b["docId"]
    assert sections_a[0]["content"] != sections_b[0]["content"]


# ── 6. Doc CRUD Round Trip ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_doc_crud_round_trip(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Full lifecycle: create doc, read it, update (manual edit), read
    (verify edit persists), archive/delete."""
    _admin_setup(mock_mongodb, sample_user)

    now = datetime.now(UTC)

    # --- CREATE ---
    mock_docs_create = MagicMock()
    mock_docs_create.find_one = AsyncMock(return_value=None)
    mock_docs_create.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs_create

    create_response = await client.post(
        "/api/v1/docs",
        json={
            "docId": "doc::lifecycle-test",
            "title": "Lifecycle Test",
            "type": "guide",
            "format": "markdown",
            "content": "# Lifecycle\n\nOriginal content.",
            "category": "testing",
            "tags": ["lifecycle"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert create_response.status_code == 201
    create_data = create_response.json()["data"]
    assert create_data["docId"] == "doc::lifecycle-test"
    assert create_data["version"] == 1

    # --- READ ---
    created_doc = {
        "docId": "doc::lifecycle-test",
        "title": "Lifecycle Test",
        "description": None,
        "type": "guide",
        "format": "markdown",
        "content": "# Lifecycle\n\nOriginal content.",
        "sections": [
            {
                "sectionId": "content",
                "title": "Lifecycle Test",
                "content": "# Lifecycle\n\nOriginal content.",
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": "admin",
                "order": 0,
            },
        ],
        "linkedEntities": [],
        "category": "testing",
        "tags": ["lifecycle"],
        "version": 1,
        "author": "admin",
        "status": "published",
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }

    mock_docs_read = MagicMock()
    mock_docs_read.find_one = AsyncMock(return_value=created_doc)
    mock_mongodb.docs = mock_docs_read

    read_response = await client.get(
        "/api/v1/docs/doc::lifecycle-test",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert read_response.status_code == 200
    read_data = read_response.json()["data"]
    assert read_data["docId"] == "doc::lifecycle-test"
    assert read_data["title"] == "Lifecycle Test"
    assert read_data["version"] == 1
    assert read_data["status"] == "published"

    # --- UPDATE ---
    updated_doc = created_doc.copy()
    updated_doc["title"] = "Updated Lifecycle"
    updated_doc["version"] = 2
    updated_doc["updatedAt"] = now

    mock_docs_update = MagicMock()
    # update_doc calls get_doc (first find_one), then get_doc again after update
    mock_docs_update.find_one = AsyncMock(side_effect=[created_doc, updated_doc])
    mock_docs_update.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs_update

    update_response = await client.put(
        "/api/v1/docs/doc::lifecycle-test",
        json={"title": "Updated Lifecycle", "content": "# Updated\n\nUpdated content."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert update_response.status_code == 200
    update_data = update_response.json()["data"]
    assert update_data["docId"] == "doc::lifecycle-test"
    assert update_data["version"] == 2

    # --- READ AGAIN (verify edit) ---
    mock_docs_read2 = MagicMock()
    mock_docs_read2.find_one = AsyncMock(return_value=updated_doc)
    mock_mongodb.docs = mock_docs_read2

    read2_response = await client.get(
        "/api/v1/docs/doc::lifecycle-test",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert read2_response.status_code == 200
    assert read2_response.json()["data"]["title"] == "Updated Lifecycle"

    # --- DELETE (archive) ---
    mock_docs_del = MagicMock()
    mock_docs_del.find_one = AsyncMock(return_value=updated_doc)
    mock_docs_del.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs_del

    delete_response = await client.delete(
        "/api/v1/docs/doc::lifecycle-test",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert delete_response.status_code == 200
    delete_data = delete_response.json()["data"]
    assert delete_data["docId"] == "doc::lifecycle-test"
    assert delete_data["status"] == "archived"


# ── 7. Template Variable Listing ─────────────────────────────────────


@pytest.mark.asyncio
async def test_template_variable_listing(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Create a template with multiple variables and verify the template
    response includes the variable definitions/placeholders."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=None)  # No existing
    mock_templates.insert_one = AsyncMock()
    mock_mongodb.doc_templates = mock_templates

    response = await client.post(
        "/api/v1/docs/templates",
        json={
            "templateId": "tmpl::multi-var-test",
            "name": "Multi Variable Template",
            "docType": "reference",
            "sections": [
                {
                    "sectionId": "header",
                    "title": "Header",
                    "contentTemplate": "Host: $hostname, IP: $ip_address, OS: $os_name",
                    "order": 1,
                },
            ],
            "variables": [
                {"name": "hostname", "source": "node.displayName", "description": "Node hostname"},
                {"name": "ip_address", "source": "node.network.ipv4", "description": "Primary IP address"},
                {"name": "os_name", "source": "profile.software.os.name", "description": "Operating system"},
            ],
            "staleAfterHours": 12,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["templateId"] == "tmpl::multi-var-test"
    assert len(data["variables"]) == 3

    var_names = [v["name"] for v in data["variables"]]
    assert "hostname" in var_names
    assert "ip_address" in var_names
    assert "os_name" in var_names

    # Verify each variable has source and description
    for var in data["variables"]:
        assert "source" in var
        assert var["source"]  # non-empty
        assert "description" in var

    # Verify sections contain the template
    assert len(data["sections"]) == 1
    assert "$hostname" in data["sections"][0]["contentTemplate"]
    assert "$ip_address" in data["sections"][0]["contentTemplate"]
    assert "$os_name" in data["sections"][0]["contentTemplate"]


# ── 8. Invalid Template Reference ────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_template_reference(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Attempt to generate doc from a non-existent template ID and verify
    a 404 error response."""
    _admin_setup(mock_mongodb, sample_user)

    # Template not found
    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=None)
    mock_mongodb.doc_templates = mock_templates

    response = await client.post(
        "/api/v1/docs/generate",
        json={
            "templateId": "tmpl::nonexistent",
            "entityType": "node",
            "entityId": "test-server-01",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    error_data = response.json()
    assert "error" in error_data


@pytest.mark.asyncio
async def test_render_nonexistent_template_returns_404(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Attempt to render a non-existent template via the render endpoint
    and verify a 404 error response."""
    _admin_setup(mock_mongodb, sample_user)

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=None)
    mock_mongodb.doc_templates = mock_templates

    response = await client.post(
        "/api/v1/docs/templates/tmpl::nonexistent/render",
        json={
            "docId": "doc::rendered-from-nowhere",
            "title": "Ghost Doc",
            "variables": {},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


# ── 9. Staleness via GET /docs/stale ─────────────────────────────────


@pytest.mark.asyncio
async def test_stale_docs_time_based(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Generate a doc, simulate time passing beyond staleAfterHours, and
    verify it appears in GET /docs/stale."""
    _admin_setup(mock_mongodb, sample_user)

    stale_doc = _make_generated_doc(
        doc_id="doc::stale-test",
        hours_ago=48,
        stale_after_hours=24,
    )

    fresh_doc = _make_generated_doc(doc_id="doc::fresh-test", hours_ago=1, stale_after_hours=24)

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
    assert data["data"][0]["docId"] == "doc::stale-test"


# ── 10. Regeneration of Doc Without Manual Edits ─────────────────────


@pytest.mark.asyncio
async def test_regenerate_all_sections_updated(
    client: AsyncClient,
    mock_mongodb: Any,
    admin_token: str,
    sample_user: dict[str, Any],
):
    """Regenerate a doc where all sections are 'generated' (no manual edits)
    and verify all sections are updated with zero skips."""
    _admin_setup(mock_mongodb, sample_user)

    template = _make_template()
    node = _make_node()
    doc = _make_generated_doc()

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=template)
    mock_mongodb.doc_templates = mock_templates

    mock_mongodb.nodes.find_one = AsyncMock(return_value=node)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.post(
        f"/api/v1/docs/{doc['docId']}/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sectionsUpdated"] == 2
    assert data["sectionsSkipped"] == 0
    assert data["warningCount"] == 0
    assert data["warnings"] == []
    assert data["version"] == doc["version"] + 1
