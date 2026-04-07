"""Workflow definition and execution endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from hydra.api.v1.core.deps import (
    CurrentUser,
    MongoDBDep,
    get_authenticated_client_id,
    get_authenticated_permissions,
    get_authenticated_role,
    get_authenticated_user_id,
    get_command_request_source,
    require_permission,
    require_trusted_write_origin,
)
from hydra.api.v1.models.commands import CommandSource
from hydra.api.v1.models.commands.workflows import (
    CreateWorkflowRequest,
    ExecuteWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowExecutionResponse,
    WorkflowExecutionStatus,
    WorkflowExecutionSummary,
    WorkflowInput,
    WorkflowResponse,
    WorkflowStep,
    WorkflowStepExecution,
    WorkflowSummary,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.services.commands.workflows import WorkflowService

router = APIRouter(prefix="/workflows", tags=["Workflows"])
logger = structlog.get_logger(__name__)


def get_workflow_service(mongodb: MongoDBDep) -> WorkflowService:
    """Get workflow service dependency."""
    return WorkflowService(mongodb)


WorkflowServiceDep = Annotated[WorkflowService, Depends(get_workflow_service)]


# ── Workflow CRUD ────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[list[WorkflowSummary]],
    response_model_by_alias=True,
    summary="List Workflows",
    description="List workflow definitions with pagination.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def list_workflows(
    workflow_service: WorkflowServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[WorkflowSummary]]:
    """List workflow definitions."""
    workflows, total = await workflow_service.list_workflows(
        limit=limit, offset=offset
    )

    return SuccessResponse(
        data=[
            WorkflowSummary(
                chain_id=w["chainId"],
                name=w["name"],
                description=w.get("description"),
                step_count=len(w.get("steps", [])),
                created_by=w.get("createdBy"),
                created_at=w["createdAt"],
                updated_at=w.get("updatedAt"),
            )
            for w in workflows
        ],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=SuccessResponse[WorkflowResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Create Workflow",
    description="Create a new workflow definition.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def create_workflow(
    request: CreateWorkflowRequest,
    workflow_service: WorkflowServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[WorkflowResponse]:
    """Create a new workflow definition."""
    user_id = get_authenticated_user_id(current_user)

    workflow = await workflow_service.create_workflow(request, user_id=user_id)

    return SuccessResponse(data=_format_workflow_response(workflow))


@router.get(
    "/{chain_id}",
    response_model=SuccessResponse[WorkflowResponse],
    response_model_by_alias=True,
    summary="Get Workflow",
    description="Get a workflow definition by chain ID.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def get_workflow(
    chain_id: str,
    workflow_service: WorkflowServiceDep,
) -> SuccessResponse[WorkflowResponse]:
    """Get a workflow definition."""
    workflow = await workflow_service.get_workflow(chain_id)
    return SuccessResponse(data=_format_workflow_response(workflow))


@router.patch(
    "/{chain_id}",
    response_model=SuccessResponse[WorkflowResponse],
    response_model_by_alias=True,
    summary="Update Workflow",
    description="Update a workflow definition.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def update_workflow(
    chain_id: str,
    request: UpdateWorkflowRequest,
    workflow_service: WorkflowServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[WorkflowResponse]:
    """Update a workflow definition."""
    user_id = get_authenticated_user_id(current_user)

    workflow = await workflow_service.update_workflow(
        chain_id, request, user_id=user_id
    )
    return SuccessResponse(data=_format_workflow_response(workflow))


@router.delete(
    "/{chain_id}",
    response_model=SuccessResponse[dict[str, Any]],
    response_model_by_alias=True,
    summary="Delete Workflow",
    description="Delete a workflow definition.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def delete_workflow(
    chain_id: str,
    workflow_service: WorkflowServiceDep,
) -> SuccessResponse[dict[str, Any]]:
    """Delete a workflow definition."""
    await workflow_service.delete_workflow(chain_id)
    return SuccessResponse(data={"chainId": chain_id, "deleted": True})


# ── Workflow Execution ───────────────────────────────────────────────────


@router.post(
    "/{chain_id}/execute",
    response_model=SuccessResponse[WorkflowExecutionResponse],
    response_model_by_alias=True,
    summary="Execute Workflow",
    description="Execute a workflow, returning immediately with an execution ID.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def execute_workflow(
    chain_id: str,
    workflow_service: WorkflowServiceDep,
    current_user: CurrentUser,
    request: ExecuteWorkflowRequest | None = None,
) -> JSONResponse:
    """Execute a workflow."""
    user_id = get_authenticated_user_id(current_user)
    user_role = get_authenticated_role(current_user)
    user_permissions = get_authenticated_permissions(current_user)
    source = CommandSource(get_command_request_source(current_user))
    client_id = get_authenticated_client_id(current_user)

    execution = await workflow_service.execute_workflow(
        chain_id,
        request=request,
        user_id=user_id,
        user_role=user_role,
        user_permissions=user_permissions,
        source=source,
        client_id=client_id,
    )

    response_data = _format_execution_response(execution)
    wrapped = SuccessResponse(data=response_data)

    return JSONResponse(
        content=wrapped.model_dump(by_alias=True, mode="json"),
        status_code=202,
    )


@router.get(
    "/{chain_id}/executions",
    response_model=SuccessResponse[list[WorkflowExecutionSummary]],
    response_model_by_alias=True,
    summary="List Workflow Executions",
    description="List executions for a specific workflow.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def list_workflow_executions(
    chain_id: str,
    workflow_service: WorkflowServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[WorkflowExecutionSummary]]:
    """List executions for a workflow."""
    executions, total = await workflow_service.list_executions(
        chain_id=chain_id, limit=limit, offset=offset
    )

    return SuccessResponse(
        data=[_format_execution_summary(e) for e in executions],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/executions/{execution_id}",
    response_model=SuccessResponse[WorkflowExecutionResponse],
    response_model_by_alias=True,
    summary="Get Workflow Execution",
    description="Get details of a workflow execution.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def get_workflow_execution(
    execution_id: str,
    workflow_service: WorkflowServiceDep,
) -> SuccessResponse[WorkflowExecutionResponse]:
    """Get a workflow execution."""
    execution = await workflow_service.get_execution(execution_id)
    return SuccessResponse(data=_format_execution_response(execution))


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=SuccessResponse[WorkflowExecutionResponse],
    response_model_by_alias=True,
    summary="Cancel Workflow Execution",
    description="Cancel a running workflow execution.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def cancel_workflow_execution(
    execution_id: str,
    workflow_service: WorkflowServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[WorkflowExecutionResponse]:
    """Cancel a workflow execution."""
    user_id = get_authenticated_user_id(current_user)

    execution = await workflow_service.cancel_execution(
        execution_id, user_id=user_id
    )
    return SuccessResponse(data=_format_execution_response(execution))


# ── Format Helpers ───────────────────────────────────────────────────────


def _format_workflow_response(w: dict[str, Any]) -> WorkflowResponse:
    """Format a workflow document into a WorkflowResponse."""
    steps = []
    for s in w.get("steps", []):
        from hydra.api.v1.models.commands.schemas import CommandTarget
        from hydra.api.v1.models.commands.workflows import StepFailurePolicy

        steps.append(
            WorkflowStep(
                step_id=s["stepId"],
                registry_id=s["registryId"],
                target=CommandTarget(
                    node_id=s["target"]["nodeId"],
                    service_id=s["target"].get("serviceId"),
                ),
                parameters=s.get("parameters"),
                depends_on=s.get("dependsOn", []),
                on_failure=StepFailurePolicy(s.get("onFailure", "abort")),
                max_retries=s.get("maxRetries", 0),
                condition=s.get("condition"),
                parallel_group=s.get("parallelGroup"),
                compensation=s.get("compensation"),
            )
        )

    inputs = None
    if w.get("inputs"):
        inputs = {
            k: WorkflowInput(**v) for k, v in w["inputs"].items()
        }

    return WorkflowResponse(
        chain_id=w["chainId"],
        name=w["name"],
        description=w.get("description"),
        steps=steps,
        inputs=inputs,
        created_by=w.get("createdBy"),
        created_at=w["createdAt"],
        updated_at=w.get("updatedAt"),
    )


def _format_execution_response(e: dict[str, Any]) -> WorkflowExecutionResponse:
    """Format an execution document into a WorkflowExecutionResponse."""
    steps = [
        WorkflowStepExecution(
            step_id=s["stepId"],
            registry_id=s["registryId"],
            command_id=s.get("commandId"),
            status=s.get("status", "pending"),
            retry_count=s.get("retryCount", 0),
            started_at=s.get("startedAt"),
            completed_at=s.get("completedAt"),
            result=s.get("result"),
            error=s.get("error"),
        )
        for s in e.get("steps", [])
    ]

    return WorkflowExecutionResponse(
        execution_id=e["executionId"],
        chain_id=e["chainId"],
        name=e["name"],
        status=WorkflowExecutionStatus(e["status"]),
        steps=steps,
        inputs=e.get("inputs"),
        started_by=e.get("startedBy"),
        started_at=e["startedAt"],
        completed_at=e.get("completedAt"),
    )


def _format_execution_summary(e: dict[str, Any]) -> WorkflowExecutionSummary:
    """Format an execution document into a summary."""
    steps = e.get("steps", [])
    completed = sum(
        1 for s in steps if s.get("status") in ["completed", "failed", "cancelled", "skipped"]
    )

    return WorkflowExecutionSummary(
        execution_id=e["executionId"],
        chain_id=e["chainId"],
        name=e["name"],
        status=WorkflowExecutionStatus(e["status"]),
        step_count=len(steps),
        completed_steps=completed,
        started_by=e.get("startedBy"),
        started_at=e["startedAt"],
        completed_at=e.get("completedAt"),
    )
