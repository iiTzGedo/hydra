"""Tests for workflow definition and execution endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.models.commands import CommandSource, CommandStatus
from hydra.api.v1.models.commands.workflows import WorkflowExecutionStatus
from hydra.api.v1.services.commands.workflows import WorkflowService
from tests.utils import create_mock_cursor


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_workflow():
    """Sample workflow document."""
    now = datetime.now(timezone.utc)
    return {
        "chainId": "chain_abc123",
        "name": "Restart Web Stack",
        "description": "Restart nginx then the app service",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::service::restart",
                "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
                "parameters": None,
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
            },
            {
                "stepId": "step-2",
                "registryId": "reg::service::restart",
                "target": {"nodeId": "server-01", "serviceId": "svc-app-c3d4"},
                "parameters": None,
                "dependsOn": ["step-1"],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
            },
        ],
        "inputs": None,
        "createdBy": "user_admin123",
        "createdAt": now,
        "updatedAt": None,
    }


@pytest.fixture
def sample_execution(sample_workflow):
    """Sample workflow execution document."""
    now = datetime.now(timezone.utc)
    return {
        "executionId": "exec_xyz789",
        "chainId": sample_workflow["chainId"],
        "name": sample_workflow["name"],
        "status": "running",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::service::restart",
                "commandId": None,
                "status": "pending",
                "retryCount": 0,
                "startedAt": None,
                "completedAt": None,
                "result": None,
                "error": None,
            },
            {
                "stepId": "step-2",
                "registryId": "reg::service::restart",
                "commandId": None,
                "status": "pending",
                "retryCount": 0,
                "startedAt": None,
                "completedAt": None,
                "result": None,
                "error": None,
            },
        ],
        "inputs": None,
        "startedBy": "user_admin123",
        "startedAt": now,
        "completedAt": None,
    }


def _setup_workflow_mocks(mock_mongodb, sample_user):
    """Common mock setup for workflow tests."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.workflows.insert_one = AsyncMock()
    mock_mongodb.workflows.update_one = AsyncMock()
    mock_mongodb.workflows.delete_one = AsyncMock()
    mock_mongodb.workflow_executions.insert_one = AsyncMock()
    mock_mongodb.workflow_executions.update_one = AsyncMock()


def trusted_write_headers(
    *,
    user_id: str = "user_admin123",
    role: str = "admin",
    client_id: str = "hydra-web",
) -> dict[str, str]:
    """Build trusted internal-request headers for workflow write tests."""
    return {
        "X-Hydra-Internal-Request": "true",
        "X-Hydra-Internal-Secret": "internal-secret-for-tests-0123456789",
        "X-Hydra-User-Id": user_id,
        "X-Hydra-Role": role,
        "X-Hydra-Client-Id": client_id,
    }


# ── Workflow CRUD ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_workflow_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test creating a new workflow."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    # Registry validation: all registryIds exist
    mock_mongodb.command_definitions.find_one = AsyncMock(
        return_value={"registryId": "reg::service::restart", "category": "service"}
    )

    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Restart Web Stack",
            "description": "Restart nginx then app",
            "steps": [
                {
                    "stepId": "step-1",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
                    "dependsOn": [],
                    "onFailure": "abort",
                },
                {
                    "stepId": "step-2",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01", "serviceId": "svc-app-c3d4"},
                    "dependsOn": ["step-1"],
                    "onFailure": "abort",
                },
            ],
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["name"] == "Restart Web Stack"
    assert data["data"]["chainId"].startswith("chain_")
    assert len(data["data"]["steps"]) == 2
    mock_mongodb.workflows.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_workflow_detects_cycle(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that cyclic step dependencies are rejected."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.command_definitions.find_one = AsyncMock(
        return_value={"registryId": "reg::service::restart"}
    )

    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Cyclic Workflow",
            "steps": [
                {
                    "stepId": "a",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01"},
                    "dependsOn": ["b"],
                },
                {
                    "stepId": "b",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01"},
                    "dependsOn": ["a"],
                },
            ],
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 422
    data = response.json()
    assert "cycle" in data["error"]["message"].lower() or "CYCLE" in data["error"]["code"]


@pytest.mark.asyncio
async def test_create_workflow_invalid_dependency_ref(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that referencing unknown step IDs is rejected."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.command_definitions.find_one = AsyncMock(
        return_value={"registryId": "reg::service::restart"}
    )

    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Bad Deps",
            "steps": [
                {
                    "stepId": "a",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01"},
                    "dependsOn": ["nonexistent"],
                },
            ],
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_workflow_unknown_registry_id(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that unknown registryIds in steps are rejected."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=None)

    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Bad Registry",
            "steps": [
                {
                    "stepId": "step-1",
                    "registryId": "reg::service::nonexistent",
                    "target": {"nodeId": "server-01"},
                },
            ],
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_workflow_rejects_bearer_write_origin(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test bearer-authenticated workflow writes are rejected."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Restart Web Stack",
            "steps": [
                {
                    "stepId": "step-1",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
                },
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "CLIENT_NOT_AUTHORIZED"


@pytest.mark.asyncio
async def test_create_workflow_rejects_unsupported_condition(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test workflow steps reject unsupported conditional execution."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.command_definitions.find_one = AsyncMock(
        return_value={"registryId": "reg::service::restart", "category": "service"}
    )

    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Conditional Workflow",
            "steps": [
                {
                    "stepId": "step-1",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
                    "condition": "status == 'healthy'",
                },
            ],
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "condition" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_list_workflows(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_workflow,
):
    """Test listing workflows."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflows.count_documents = AsyncMock(return_value=1)
    mock_mongodb.workflows.find.return_value = create_mock_cursor([sample_workflow])

    response = await client.get(
        "/api/v1/workflows",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["chainId"] == "chain_abc123"
    assert data["data"][0]["stepCount"] == 2
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_get_workflow(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_workflow,
):
    """Test getting a specific workflow."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflows.find_one = AsyncMock(return_value=sample_workflow)

    response = await client.get(
        "/api/v1/workflows/chain_abc123",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["chainId"] == "chain_abc123"
    assert data["data"]["name"] == "Restart Web Stack"
    assert len(data["data"]["steps"]) == 2
    assert data["data"]["steps"][0]["stepId"] == "step-1"
    assert data["data"]["steps"][1]["dependsOn"] == ["step-1"]


@pytest.mark.asyncio
async def test_get_workflow_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent workflow."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflows.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/workflows/chain_nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_workflow(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_workflow,
):
    """Test updating a workflow."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflows.find_one = AsyncMock(return_value=sample_workflow)

    updated_workflow = sample_workflow.copy()
    updated_workflow["name"] = "Updated Web Stack"
    mock_mongodb.workflows.find_one = AsyncMock(
        side_effect=[sample_workflow, updated_workflow]
    )

    response = await client.patch(
        "/api/v1/workflows/chain_abc123",
        json={"name": "Updated Web Stack"},
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    mock_mongodb.workflows.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_workflow(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_workflow,
):
    """Test deleting a workflow."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflows.find_one = AsyncMock(return_value=sample_workflow)
    mock_mongodb.workflow_executions.count_documents = AsyncMock(return_value=0)

    response = await client.delete(
        "/api/v1/workflows/chain_abc123",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["deleted"] is True
    mock_mongodb.workflows.delete_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_workflow_with_active_executions(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_workflow,
):
    """Test that workflows with active executions cannot be deleted."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflows.find_one = AsyncMock(return_value=sample_workflow)
    mock_mongodb.workflow_executions.count_documents = AsyncMock(return_value=1)

    response = await client.delete(
        "/api/v1/workflows/chain_abc123",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 422


# ── Workflow Execution ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_workflow(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_workflow,
):
    """Test executing a workflow returns 202."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflows.find_one = AsyncMock(return_value=sample_workflow)
    # Mock the command creation that happens in background
    mock_mongodb.command_definitions.find_one = AsyncMock(
        return_value={"registryId": "reg::service::restart", "category": "service", "rbac": {"minimumRole": "operator"}, "execution": {"timeout": 60}}
    )
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )
    mock_mongodb.commands.insert_one = AsyncMock()
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)

    response = await client.post(
        "/api/v1/workflows/chain_abc123/execute",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["executionId"].startswith("exec_")
    assert data["data"]["chainId"] == "chain_abc123"
    assert data["data"]["status"] == "running"
    assert len(data["data"]["steps"]) == 2
    mock_mongodb.workflow_executions.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_execution(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_execution,
):
    """Test getting a workflow execution."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflow_executions.find_one = AsyncMock(return_value=sample_execution)

    response = await client.get(
        "/api/v1/workflows/executions/exec_xyz789",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["executionId"] == "exec_xyz789"
    assert data["data"]["status"] == "running"
    assert len(data["data"]["steps"]) == 2


@pytest.mark.asyncio
async def test_list_executions(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_execution,
):
    """Test listing workflow executions."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflow_executions.count_documents = AsyncMock(return_value=1)
    mock_mongodb.workflow_executions.find.return_value = create_mock_cursor([sample_execution])

    response = await client.get(
        "/api/v1/workflows/chain_abc123/executions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["executionId"] == "exec_xyz789"
    assert data["data"][0]["stepCount"] == 2


@pytest.mark.asyncio
async def test_cancel_execution(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_execution,
):
    """Test cancelling a workflow execution."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.workflow_executions.find_one = AsyncMock(return_value=sample_execution)

    # After cancel, return updated execution
    cancelled_execution = sample_execution.copy()
    cancelled_execution["status"] = "cancelled"
    mock_mongodb.workflow_executions.find_one = AsyncMock(
        side_effect=[sample_execution, cancelled_execution]
    )

    response = await client.post(
        "/api/v1/workflows/executions/exec_xyz789/cancel",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    mock_mongodb.workflow_executions.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_cancel_completed_execution_fails(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_execution,
):
    """Test that completed executions cannot be cancelled."""
    _setup_workflow_mocks(mock_mongodb, sample_user)
    completed_execution = sample_execution.copy()
    completed_execution["status"] = "completed"
    mock_mongodb.workflow_executions.find_one = AsyncMock(return_value=completed_execution)

    response = await client.post(
        "/api/v1/workflows/executions/exec_xyz789/cancel",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_execute_step_preserves_cancelled_status(monkeypatch):
    """Test cancelled commands keep the workflow step and execution cancelled."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)

    service.commands_service = MagicMock()
    service.commands_service.create_command = AsyncMock(
        return_value={"commandId": "cmd-step-1"}
    )
    service.commands_service.get_command = AsyncMock(
        return_value={
            "status": CommandStatus.CANCELLED.value,
            "result": None,
            "error": {"message": "cancelled by user"},
        }
    )
    service.workflow_executions.find_one = AsyncMock(
        side_effect=[
            {"executionId": "exec_xyz789", "status": WorkflowExecutionStatus.RUNNING.value},
            {"executionId": "exec_xyz789", "status": WorkflowExecutionStatus.RUNNING.value},
        ]
    )
    service._update_step_status = AsyncMock()
    service._update_step_command_id = AsyncMock()
    service._finish_execution = AsyncMock()

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(
        "hydra.api.v1.services.commands.workflows.asyncio.sleep",
        _no_sleep,
    )

    outcome = await service._execute_step(
        execution_id="exec_xyz789",
        chain_id="chain_abc123",
        step={
            "stepId": "step-1",
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        step_index=0,
        user_id="user_admin123",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.WEB,
        client_id="hydra-web",
    )

    assert outcome == "cancelled"
    service._update_step_status.assert_any_await(
        "exec_xyz789",
        "step-1",
        "cancelled",
        result=None,
        error="cancelled by user",
    )
    service._finish_execution.assert_awaited_once_with(
        "exec_xyz789",
        WorkflowExecutionStatus.CANCELLED,
    )


@pytest.mark.asyncio
async def test_run_workflow_execution_does_not_overwrite_cancelled_status():
    """Test a cancelled workflow is not finalized to another terminal state."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)
    service._topological_sort = MagicMock(return_value=["step-1"])
    service._execute_step = AsyncMock(return_value="completed")
    service._finish_execution = AsyncMock()
    service.workflow_executions.find_one = AsyncMock(
        side_effect=[
            {"executionId": "exec_xyz789", "status": WorkflowExecutionStatus.RUNNING.value},
            {"executionId": "exec_xyz789", "status": WorkflowExecutionStatus.CANCELLED.value},
        ]
    )

    workflow = {
        "chainId": "chain_abc123",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::service::restart",
                "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
            }
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_xyz789",
        workflow=workflow,
        user_id="user_admin123",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.WEB,
        client_id="hydra-web",
        request=None,
    )

    service._finish_execution.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_step_forwards_permissions_and_origin(monkeypatch):
    """Test workflow step execution uses the direct command RBAC/source context."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)

    service.commands_service = MagicMock()
    service.commands_service.create_command = AsyncMock(
        return_value={"commandId": "cmd-step-1"}
    )
    service.commands_service.get_command = AsyncMock(
        return_value={
            "status": CommandStatus.COMPLETED.value,
            "result": {"success": True},
            "error": None,
        }
    )
    service.workflow_executions.find_one = AsyncMock(
        return_value={"executionId": "exec_xyz789", "status": WorkflowExecutionStatus.RUNNING.value}
    )
    service._update_step_status = AsyncMock()
    service._update_step_command_id = AsyncMock()
    service._finish_execution = AsyncMock()

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(
        "hydra.api.v1.services.commands.workflows.asyncio.sleep",
        _no_sleep,
    )

    outcome = await service._execute_step(
        execution_id="exec_xyz789",
        chain_id="chain_abc123",
        step={
            "stepId": "step-1",
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
            "dependsOn": [],
        },
        step_index=0,
        user_id="user_operator123",
        user_role="operator",
        user_permissions=["commands:execute", "services:*"],
        source=CommandSource.WEB,
        client_id="hydra-web",
    )

    assert outcome == "completed"
    create_kwargs = service.commands_service.create_command.await_args.kwargs
    assert create_kwargs["user_permissions"] == ["commands:execute", "services:*"]
    assert create_kwargs["source"] == CommandSource.WEB
    assert create_kwargs["client_id"] == "hydra-web"


# ── Permission Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workflow_forbidden_for_viewer(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot create workflows."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Test",
            "steps": [
                {
                    "stepId": "s1",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01"},
                },
            ],
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403
