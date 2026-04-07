"""Tests for workflow definition and execution endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.core.exceptions import ValidationError
from hydra.api.v1.models.commands import CommandSource, CommandStatus
from hydra.api.v1.models.commands.workflows import WorkflowExecutionStatus
from hydra.api.v1.services.commands.workflows import WorkflowService, evaluate_condition
from tests.utils import create_mock_cursor

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_workflow():
    """Sample workflow document."""
    now = datetime.now(UTC)
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
    now = datetime.now(UTC)
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
async def test_create_workflow_accepts_valid_condition(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test workflow steps accept valid condition expressions."""
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
                },
                {
                    "stepId": "step-2",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
                    "dependsOn": ["step-1"],
                    "condition": "steps.step1.status == 'completed'",
                },
            ],
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["steps"][1]["condition"] == "steps.step1.status == 'completed'"


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

    # The new orchestration logic reads execution state multiple times:
    # once at batch start, once after step execution (for result context),
    # and once at the end for final status check.
    service.workflow_executions.find_one = AsyncMock(
        side_effect=[
            # Batch loop start check
            {"executionId": "exec_xyz789", "status": WorkflowExecutionStatus.RUNNING.value,
             "steps": [{"stepId": "step-1", "status": "completed", "result": None}]},
            # After step execution: fetch step results for condition context
            {"executionId": "exec_xyz789", "status": WorkflowExecutionStatus.RUNNING.value,
             "steps": [{"stepId": "step-1", "status": "completed", "result": None}]},
            # Final status check – execution was cancelled in the meantime
            {"executionId": "exec_xyz789", "status": WorkflowExecutionStatus.CANCELLED.value,
             "steps": [{"stepId": "step-1", "status": "completed", "result": None}]},
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
                "condition": None,
                "parallelGroup": None,
                "compensation": None,
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


# ── Condition Evaluator Tests ───────────────────────────────────────────


class TestConditionEvaluator:
    """Tests for the safe condition evaluator."""

    def test_workflow_condition_true_executes_step(self):
        """Test that a true condition evaluates correctly."""
        context = {
            "step-1": {"status": "completed", "output": {"code": 0}},
        }
        assert evaluate_condition("steps.step-1.status == 'completed'", context) is True

    def test_workflow_condition_false_skips_step(self):
        """Test that a false condition evaluates correctly."""
        context = {
            "step-1": {"status": "failed", "output": None},
        }
        assert evaluate_condition("steps.step-1.status == 'completed'", context) is False

    def test_workflow_condition_invalid_expression_rejected(self):
        """Test that function calls and unsafe expressions are rejected."""
        context = {"step-1": {"status": "completed", "output": None}}

        # Function call should be rejected
        with pytest.raises(ValidationError, match="Unsafe expression node type"):
            evaluate_condition("__import__('os').system('rm -rf /')", context)

        # Built-in function calls should be rejected
        with pytest.raises(ValidationError, match="Unsafe expression node type"):
            evaluate_condition("len('hello')", context)

        # Lambda should be rejected
        with pytest.raises(ValidationError, match="Unsafe expression node type"):
            evaluate_condition("(lambda: True)()", context)

    def test_condition_boolean_operators(self):
        """Test and/or/not operators in conditions."""
        context = {
            "step-1": {"status": "completed", "output": None},
            "step-2": {"status": "failed", "output": None},
        }
        assert evaluate_condition(
            "steps.step-1.status == 'completed' and steps.step-2.status == 'failed'",
            context,
        ) is True
        assert evaluate_condition(
            "steps.step-1.status == 'completed' or steps.step-2.status == 'completed'",
            context,
        ) is True
        assert evaluate_condition(
            "not steps.step-1.status == 'failed'",
            context,
        ) is True

    def test_condition_output_field_access(self):
        """Test accessing step output fields in conditions."""
        context = {
            "step-1": {"status": "completed", "output": {"exitCode": 0, "message": "ok"}},
        }
        assert evaluate_condition("steps.step-1.output.exitCode == 0", context) is True
        assert evaluate_condition("steps.step-1.output.message == 'ok'", context) is True
        assert evaluate_condition("steps.step-1.output.exitCode > 1", context) is False

    def test_condition_numeric_comparison(self):
        """Test numeric comparison operators."""
        context = {
            "step-1": {"status": "completed", "output": {"count": 5}},
        }
        assert evaluate_condition("steps.step-1.output.count >= 5", context) is True
        assert evaluate_condition("steps.step-1.output.count < 10", context) is True
        assert evaluate_condition("steps.step-1.output.count != 0", context) is True
        assert evaluate_condition("steps.step-1.output.count <= 4", context) is False

    def test_condition_missing_numeric_value_fails_closed(self):
        """Missing ordered-comparison values should evaluate false, not raise."""
        context = {
            "step-1": {"status": "completed", "output": {}},
        }
        assert evaluate_condition("steps.step-1.output.count > 5", context) is False

    def test_condition_mixed_type_numeric_value_fails_closed(self):
        """Type-incompatible ordered comparisons should evaluate false."""
        context = {
            "step-1": {"status": "completed", "output": {"count": "five"}},
        }
        assert evaluate_condition("steps.step-1.output.count > 5", context) is False

    def test_condition_syntax_error(self):
        """Test that syntax errors are caught."""
        with pytest.raises(ValidationError, match="Invalid condition syntax"):
            evaluate_condition("steps.step-1.status ==", {})

    def test_condition_unresolved_step_returns_none(self):
        """Test that referencing an unexecuted step returns None (falsy)."""
        context: dict = {}  # type: ignore[type-arg]
        # steps.nonexistent.status is None, so == 'completed' is False
        assert evaluate_condition("steps.nonexistent.status == 'completed'", context) is False


# ── Parallel Execution Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workflow_parallel_group_executes_concurrently():
    """Test that steps in the same parallelGroup execute via asyncio.gather."""
    import asyncio

    mongodb = MagicMock()
    service = WorkflowService(mongodb)

    execution_order: list[str] = []

    async def mock_execute_step(
        execution_id, chain_id, step, step_index,
        user_id, user_role, user_permissions, source, client_id,
    ):
        step_id = step["stepId"]
        execution_order.append(f"start:{step_id}")
        # Simulate a brief async delay to allow concurrency
        await asyncio.sleep(0)
        execution_order.append(f"end:{step_id}")
        return "completed"

    service._execute_step = mock_execute_step
    service._update_step_status = AsyncMock()
    service._update_step_command_id = AsyncMock()
    service._update_step_retry = AsyncMock()
    service._finish_execution = AsyncMock()
    service.workflow_executions.find_one = AsyncMock(
        return_value={"executionId": "exec_1", "status": "running", "steps": [
            {"stepId": "p1", "status": "completed", "result": None},
            {"stepId": "p2", "status": "completed", "result": None},
            {"stepId": "s3", "status": "completed", "result": None},
        ]}
    )

    workflow = {
        "chainId": "chain_parallel",
        "steps": [
            {
                "stepId": "p1",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": "group-a",
            },
            {
                "stepId": "p2",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": "group-a",
            },
            {
                "stepId": "s3",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
            },
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_1",
        workflow=workflow,
        user_id="user1",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.API,
        client_id=None,
        request=None,
    )

    # p1 and p2 should both start before either finishes (concurrency)
    # s3 should execute after the parallel group
    assert "start:p1" in execution_order
    assert "start:p2" in execution_order
    assert "start:s3" in execution_order
    # s3 should start after both p1 and p2 are done
    s3_start_idx = execution_order.index("start:s3")
    p1_end_idx = execution_order.index("end:p1")
    p2_end_idx = execution_order.index("end:p2")
    assert s3_start_idx > p1_end_idx
    assert s3_start_idx > p2_end_idx
    service._finish_execution.assert_awaited_once_with(
        "exec_1", WorkflowExecutionStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_workflow_condition_runtime_error_skips_step(monkeypatch):
    """Unexpected condition-evaluation errors should fail closed and skip the step."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)
    service._update_step_status = AsyncMock()
    service._execute_step = AsyncMock()

    def _raise_runtime_error(_expression, _context):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "hydra.api.v1.services.commands.workflows.evaluate_condition",
        _raise_runtime_error,
    )

    completed_steps: dict[str, bool] = {}
    result = await service._execute_single_step(
        execution_id="exec_xyz789",
        chain_id="chain_abc123",
        step_id="step-1",
        step_map={
            "step-1": {
                "stepId": "step-1",
                "dependsOn": [],
                "onFailure": "abort",
                "condition": "steps.step-0.output.count > 5",
            }
        },
        step_index_map={"step-1": 0},
        completed_steps=completed_steps,
        successful_step_ids=[],
        step_results={},
        has_failure_ref=[False],
        user_id="user_admin123",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.WEB,
        client_id="hydra-web",
        steps=[
            {
                "stepId": "step-1",
                "dependsOn": [],
                "onFailure": "abort",
                "condition": "steps.step-0.output.count > 5",
            }
        ],
    )

    assert result == {"cancelled": False, "abort": False, "has_failure": False}
    assert completed_steps["step-1"] is True
    service._update_step_status.assert_awaited_with(
        "exec_xyz789",
        "step-1",
        "skipped",
        error="Condition not met",
    )
    service._execute_step.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_parallel_group_failure_propagates():
    """Test that a failure in a parallel group step propagates correctly."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)

    async def mock_execute_step(
        execution_id, chain_id, step, step_index,
        user_id, user_role, user_permissions, source, client_id,
    ):
        if step["stepId"] == "p2":
            return "failed"
        return "completed"

    service._execute_step = mock_execute_step
    service._update_step_status = AsyncMock()
    service._update_step_command_id = AsyncMock()
    service._finish_execution = AsyncMock()
    service._run_compensation = AsyncMock()
    service.workflow_executions.find_one = AsyncMock(
        return_value={"executionId": "exec_2", "status": "running", "steps": [
            {"stepId": "p1", "status": "completed", "result": None},
            {"stepId": "p2", "status": "failed", "result": None},
        ]}
    )

    workflow = {
        "chainId": "chain_par_fail",
        "steps": [
            {
                "stepId": "p1",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": "group-a",
            },
            {
                "stepId": "p2",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": "group-a",
            },
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_2",
        workflow=workflow,
        user_id="user1",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.API,
        client_id=None,
        request=None,
    )

    # Should have aborted (p2 failed with abort policy)
    service._finish_execution.assert_awaited_once_with(
        "exec_2", WorkflowExecutionStatus.FAILED,
    )


# ── Compensation Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workflow_compensation_on_abort():
    """Test that compensation handlers run when a workflow aborts."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)

    compensation_calls: list[str] = []

    async def mock_execute_step(
        execution_id, chain_id, step, step_index,
        user_id, user_role, user_permissions, source, client_id,
    ):
        step_id = step["stepId"]

        # Compensation steps
        if step_id.startswith("comp_"):
            compensation_calls.append(step_id)
            return "completed"

        if step_id == "step-2":
            return "failed"
        return "completed"

    service._execute_step = mock_execute_step
    service._update_step_status = AsyncMock()
    service._update_step_command_id = AsyncMock()
    service._finish_execution = AsyncMock()
    service.workflow_executions.find_one = AsyncMock(
        return_value={"executionId": "exec_comp", "status": "running", "steps": [
            {"stepId": "step-1", "status": "completed", "result": None},
            {"stepId": "step-2", "status": "failed", "result": None},
        ]}
    )

    workflow = {
        "chainId": "chain_comp",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::service::start",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": {
                    "registryId": "reg::service::stop",
                    "parameters": {"force": True},
                },
            },
            {
                "stepId": "step-2",
                "registryId": "reg::deploy",
                "target": {"nodeId": "server-01"},
                "dependsOn": ["step-1"],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": None,
            },
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_comp",
        workflow=workflow,
        user_id="user1",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.API,
        client_id=None,
        request=None,
    )

    # step-1 succeeded, step-2 failed with abort -> compensation for step-1
    assert "comp_step-1" in compensation_calls
    service._finish_execution.assert_awaited_once_with(
        "exec_comp", WorkflowExecutionStatus.FAILED,
    )


@pytest.mark.asyncio
async def test_workflow_compensation_reverse_order():
    """Test that compensation runs in reverse completion order."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)

    compensation_order: list[str] = []

    async def mock_execute_step(
        execution_id, chain_id, step, step_index,
        user_id, user_role, user_permissions, source, client_id,
    ):
        step_id = step["stepId"]
        if step_id.startswith("comp_"):
            compensation_order.append(step_id)
            return "completed"
        if step_id == "step-3":
            return "failed"
        return "completed"

    service._execute_step = mock_execute_step
    service._update_step_status = AsyncMock()
    service._update_step_command_id = AsyncMock()
    service._finish_execution = AsyncMock()
    service.workflow_executions.find_one = AsyncMock(
        return_value={"executionId": "exec_rev", "status": "running", "steps": [
            {"stepId": "step-1", "status": "completed", "result": None},
            {"stepId": "step-2", "status": "completed", "result": None},
            {"stepId": "step-3", "status": "failed", "result": None},
        ]}
    )

    workflow = {
        "chainId": "chain_rev",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::service::start",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": {
                    "registryId": "reg::service::stop",
                    "parameters": None,
                },
            },
            {
                "stepId": "step-2",
                "registryId": "reg::service::start",
                "target": {"nodeId": "server-02"},
                "dependsOn": ["step-1"],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": {
                    "registryId": "reg::service::stop",
                    "parameters": None,
                },
            },
            {
                "stepId": "step-3",
                "registryId": "reg::deploy",
                "target": {"nodeId": "server-01"},
                "dependsOn": ["step-2"],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": None,
            },
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_rev",
        workflow=workflow,
        user_id="user1",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.API,
        client_id=None,
        request=None,
    )

    # step-1 and step-2 succeeded (in that order), step-3 failed
    # Compensation should run step-2 first, then step-1 (reverse)
    assert compensation_order == ["comp_step-2", "comp_step-1"]


# ── Condition + Execution Integration Tests ─────────────────────────────


@pytest.mark.asyncio
async def test_workflow_condition_true_step_executes():
    """Test that a step with a true condition is executed during workflow run."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)
    executed_steps: list[str] = []

    async def mock_execute_step(
        execution_id, chain_id, step, step_index,
        user_id, user_role, user_permissions, source, client_id,
    ):
        executed_steps.append(step["stepId"])
        return "completed"

    service._execute_step = mock_execute_step
    service._update_step_status = AsyncMock()
    service._finish_execution = AsyncMock()
    service.workflow_executions.find_one = AsyncMock(
        return_value={"executionId": "exec_cond", "status": "running", "steps": [
            {"stepId": "step-1", "status": "completed", "result": {"success": True}},
            {"stepId": "step-2", "status": "completed", "result": None},
        ]}
    )

    workflow = {
        "chainId": "chain_cond",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": None,
            },
            {
                "stepId": "step-2",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": ["step-1"],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": "steps.step-1.status == 'completed'",
                "parallelGroup": None,
                "compensation": None,
            },
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_cond",
        workflow=workflow,
        user_id="user1",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.API,
        client_id=None,
        request=None,
    )

    assert "step-1" in executed_steps
    assert "step-2" in executed_steps
    service._finish_execution.assert_awaited_once_with(
        "exec_cond", WorkflowExecutionStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_workflow_condition_false_step_skipped():
    """Test that a step with a false condition is skipped during workflow run."""
    mongodb = MagicMock()
    service = WorkflowService(mongodb)
    executed_steps: list[str] = []

    async def mock_execute_step(
        execution_id, chain_id, step, step_index,
        user_id, user_role, user_permissions, source, client_id,
    ):
        executed_steps.append(step["stepId"])
        return "completed"

    service._execute_step = mock_execute_step
    service._update_step_status = AsyncMock()
    service._finish_execution = AsyncMock()
    service.workflow_executions.find_one = AsyncMock(
        return_value={"executionId": "exec_skip", "status": "running", "steps": [
            {"stepId": "step-1", "status": "completed", "result": None},
            {"stepId": "step-2", "status": "skipped", "result": None},
        ]}
    )

    workflow = {
        "chainId": "chain_skip",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": None,
            },
            {
                "stepId": "step-2",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": ["step-1"],
                "onFailure": "abort",
                "maxRetries": 0,
                # This condition will be False because step-1 status is "completed" not "failed"
                "condition": "steps.step-1.status == 'failed'",
                "parallelGroup": None,
                "compensation": None,
            },
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_skip",
        workflow=workflow,
        user_id="user1",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.API,
        client_id=None,
        request=None,
    )

    # step-1 executed but step-2 should NOT have been executed (skipped)
    assert "step-1" in executed_steps
    assert "step-2" not in executed_steps
    # step-2 should have been marked as skipped
    service._update_step_status.assert_any_await(
        "exec_skip", "step-2", "skipped", error="Condition not met",
    )


# ── Bug-fix Verification Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_condition_sees_previous_step_output():
    """Prove step_results is populated so conditions can reference prior step output.

    Bug 1 verification: step_results must contain status and output from
    previously completed steps so that condition expressions like
    ``steps.step-1.output.exitCode == 0`` evaluate correctly.
    """
    mongodb = MagicMock()
    service = WorkflowService(mongodb)
    executed_steps: list[str] = []

    async def mock_execute_step(
        execution_id, chain_id, step, step_index,
        user_id, user_role, user_permissions, source, client_id,
    ):
        executed_steps.append(step["stepId"])
        return "completed"

    service._execute_step = mock_execute_step
    service._update_step_status = AsyncMock()
    service._finish_execution = AsyncMock()
    # The find_one mock returns step-1 with result containing exitCode=0
    service.workflow_executions.find_one = AsyncMock(
        return_value={
            "executionId": "exec_output",
            "status": "running",
            "steps": [
                {"stepId": "step-1", "status": "completed", "result": {"exitCode": 0}},
                {"stepId": "step-2", "status": "completed", "result": None},
            ],
        }
    )

    workflow = {
        "chainId": "chain_output_cond",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": None,
            },
            {
                "stepId": "step-2",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": ["step-1"],
                "onFailure": "abort",
                "maxRetries": 0,
                # This condition references step-1's OUTPUT, not just status
                "condition": "steps.step-1.output.exitCode == 0",
                "parallelGroup": None,
                "compensation": None,
            },
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_output",
        workflow=workflow,
        user_id="user1",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.API,
        client_id=None,
        request=None,
    )

    # Both steps must have executed: step-2's condition checked step-1's
    # output.exitCode == 0 which should be True from the populated step_results
    assert "step-1" in executed_steps
    assert "step-2" in executed_steps
    service._finish_execution.assert_awaited_once_with(
        "exec_output", WorkflowExecutionStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_compensation_runs_for_successful_steps():
    """Prove successful_step_ids is populated so compensation actually runs.

    Bug 2 verification: after a step completes successfully, its ID must be
    added to successful_step_ids so that ``_run_compensation`` iterates over
    real step IDs instead of an empty list.
    """
    mongodb = MagicMock()
    service = WorkflowService(mongodb)
    compensation_calls: list[str] = []

    async def mock_execute_step(
        execution_id, chain_id, step, step_index,
        user_id, user_role, user_permissions, source, client_id,
    ):
        step_id = step["stepId"]
        if step_id.startswith("comp_"):
            compensation_calls.append(step_id)
            return "completed"
        if step_id == "step-3":
            return "failed"
        return "completed"

    service._execute_step = mock_execute_step
    service._update_step_status = AsyncMock()
    service._update_step_command_id = AsyncMock()
    service._finish_execution = AsyncMock()
    service.workflow_executions.find_one = AsyncMock(
        return_value={
            "executionId": "exec_comp2",
            "status": "running",
            "steps": [
                {"stepId": "step-1", "status": "completed", "result": None},
                {"stepId": "step-2", "status": "completed", "result": None},
                {"stepId": "step-3", "status": "failed", "result": None},
            ],
        }
    )

    workflow = {
        "chainId": "chain_comp2",
        "steps": [
            {
                "stepId": "step-1",
                "registryId": "reg::service::start",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": {
                    "registryId": "reg::service::stop",
                    "parameters": None,
                },
            },
            {
                "stepId": "step-2",
                "registryId": "reg::service::start",
                "target": {"nodeId": "server-02"},
                "dependsOn": ["step-1"],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": {
                    "registryId": "reg::service::stop",
                    "parameters": None,
                },
            },
            {
                "stepId": "step-3",
                "registryId": "reg::deploy",
                "target": {"nodeId": "server-01"},
                "dependsOn": ["step-2"],
                "onFailure": "abort",
                "maxRetries": 0,
                "condition": None,
                "parallelGroup": None,
                "compensation": None,
            },
        ],
    }

    await service._run_workflow_execution(
        execution_id="exec_comp2",
        workflow=workflow,
        user_id="user1",
        user_role="admin",
        user_permissions=["*:*"],
        source=CommandSource.API,
        client_id=None,
        request=None,
    )

    # step-1 and step-2 succeeded, step-3 failed with abort policy
    # Compensation MUST run for step-2 then step-1 (reverse order)
    # If successful_step_ids were never populated, this list would be empty
    assert len(compensation_calls) == 2, (
        f"Expected 2 compensation calls but got {len(compensation_calls)}: "
        f"{compensation_calls}. This means successful_step_ids was not populated."
    )
    assert compensation_calls == ["comp_step-2", "comp_step-1"]


@pytest.mark.asyncio
async def test_parallel_group_with_internal_dependency_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Prove that steps in the same parallelGroup cannot depend on each other.

    Bug 3 verification: if step B depends on step A, and both are in
    parallelGroup 'g1', validation must reject the workflow because
    asyncio.gather would run them concurrently, violating the dependency.
    """
    _setup_workflow_mocks(mock_mongodb, sample_user)
    mock_mongodb.command_definitions.find_one = AsyncMock(
        return_value={"registryId": "reg::service::restart", "category": "service"}
    )

    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Bad Parallel Deps",
            "steps": [
                {
                    "stepId": "a",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01"},
                    "dependsOn": [],
                    "parallelGroup": "g1",
                },
                {
                    "stepId": "b",
                    "registryId": "reg::service::restart",
                    "target": {"nodeId": "server-01"},
                    "dependsOn": ["a"],
                    "parallelGroup": "g1",
                },
            ],
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 400
    data = response.json()
    assert "parallel" in data["error"]["message"].lower()


def test_parallel_group_with_internal_dependency_rejected_unit():
    """Unit test for parallel group + dependency conflict validation."""
    from hydra.api.v1.models.commands.workflows import CreateWorkflowRequest

    mongodb = MagicMock()
    service = WorkflowService(mongodb)

    # Build step models using Pydantic
    request = CreateWorkflowRequest(
        name="Bad Parallel",
        steps=[
            {
                "stepId": "a",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": [],
                "parallelGroup": "g1",
            },
            {
                "stepId": "b",
                "registryId": "reg::test",
                "target": {"nodeId": "server-01"},
                "dependsOn": ["a"],
                "parallelGroup": "g1",
            },
        ],
    )

    with pytest.raises((ValidationError, Exception), match="(?i)parallel"):
        service._validate_step_graph(request.steps)
