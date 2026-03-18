"""Command execution endpoints."""

from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, require_permission
from hydra.api.v1.models.commands import (
    CommandCancelledResponse,
    CommandExecutionMethod,
    CommandListParams,
    CommandPollResponse,
    CommandQueuedResponse,
    CommandResponse,
    CommandResult,
    CommandResultSubmittedResponse,
    CommandSource,
    CommandStatus,
    CommandSummary,
    CommandType,
    CreateCommandRequest,
    SubmitCommandResultRequest,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.services.commands import CommandsService

router = APIRouter(prefix="/commands", tags=["Commands"])
logger = structlog.get_logger(__name__)


def get_commands_service(mongodb: MongoDBDep) -> CommandsService:
    """Get commands service dependency."""
    return CommandsService(mongodb)


CommandsServiceDep = Annotated[CommandsService, Depends(get_commands_service)]


@router.post(
    "",
    response_model=SuccessResponse[CommandQueuedResponse],
    response_model_by_alias=True,
    summary="Execute Command",
    description="""Submit a command for execution on a target node.

Dispatch is tier-aware:
- **Lite tier**: Rejected (400) — does not support command execution.
- **Normal tier**: Queued for poll-based execution (202 Accepted).
- **Max tier**: Attempted via direct HTTP call; falls back to queue on failure.

Returns 200 for synchronous direct execution, 202 for queued execution.
""",
    dependencies=[Depends(require_permission("commands:execute"))],
)
async def create_command(
    request: CreateCommandRequest,
    commands_service: CommandsServiceDep,
    current_user: CurrentUser,
) -> JSONResponse:
    """Submit a command for tier-aware execution on an agent.

    Args:
        request: Command specification including type, target, and parameters.
        commands_service: Commands service instance.
        current_user: User initiating the command.

    Returns:
        200 with result for direct execution, or 202 for queued execution.

    Raises:
        HTTPException 400: Invalid command or lite-tier agent.
        HTTPException 403: Insufficient permissions.
        HTTPException 404: Target node not found.
    """
    source = CommandSource.API
    if hasattr(current_user, "source"):
        source = current_user.source

    user_id = current_user.get("userId") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)

    command = await commands_service.create_command(
        request,
        user_id=user_id,
        source=source,
    )

    execution_method = command.get("executionMethod", "poll")
    result_data = command.get("result")

    response_data = CommandQueuedResponse(
        command_id=command["commandId"],
        type=CommandType(command["type"]),
        target=command["target"],
        action=command["action"],
        status=CommandStatus(command["status"]),
        execution_method=CommandExecutionMethod(execution_method),
        result=CommandResult(**result_data) if result_data else None,
        queued_at=command.get("queuedAt"),
        completed_at=command.get("completedAt"),
    )

    wrapped = SuccessResponse(data=response_data)
    status_code = 200 if execution_method == "direct" else 202

    return JSONResponse(
        content=wrapped.model_dump(by_alias=True, mode="json"),
        status_code=status_code,
    )


@router.get(
    "",
    response_model=SuccessResponse[list[CommandSummary]],
    response_model_by_alias=True,
    summary="List Commands",
    description="List command history with optional filters.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def list_commands(
    commands_service: CommandsServiceDep,
    node_id: str | None = Query(default=None, alias="nodeId"),
    type: CommandType | None = None,
    status: CommandStatus | None = None,
    since: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[CommandSummary]]:
    """Retrieve command execution history.

    Args:
        commands_service: Commands service instance.
        node_id: Filter by target node ID.
        type: Filter by command type.
        status: Filter by execution status.
        since: Only include commands created after this timestamp.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of command summaries.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    params = CommandListParams(
        node_id=node_id,
        type=type,
        status=status,
        since=since,
        limit=limit,
        offset=offset,
    )

    commands, total = await commands_service.list_commands(params)

    return SuccessResponse(
        data=[
            CommandSummary(
                command_id=cmd["commandId"],
                type=CommandType(cmd["type"]),
                target=cmd["target"],
                action=cmd["action"],
                status=CommandStatus(cmd["status"]),
                created_at=cmd["createdAt"],
            )
            for cmd in commands
        ],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/{command_id}",
    response_model=SuccessResponse[CommandResponse],
    response_model_by_alias=True,
    summary="Get Command",
    description="Get detailed information about a specific command.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def get_command(
    command_id: str,
    commands_service: CommandsServiceDep,
) -> SuccessResponse[CommandResponse]:
    """Retrieve detailed information about a specific command.

    Args:
        command_id: Unique identifier of the command.
        commands_service: Commands service instance.

    Returns:
        Complete command details including result if available.

    Raises:
        HTTPException 404: Command not found.
        HTTPException 403: Insufficient permissions.
    """
    command = await commands_service.get_command(command_id)

    return SuccessResponse(
        data=CommandResponse(
            command_id=command["commandId"],
            type=CommandType(command["type"]),
            target=command["target"],
            action=command["action"],
            parameters=command.get("parameters"),
            status=CommandStatus(command["status"]),
            result=command.get("result"),
            requested_by=command.get("requestedBy"),
            timeout_seconds=command["timeoutSeconds"],
            created_at=command["createdAt"],
            queued_at=command.get("queuedAt"),
            started_at=command.get("startedAt"),
            completed_at=command.get("completedAt"),
        )
    )


@router.post(
    "/{command_id}/cancel",
    response_model=SuccessResponse[CommandCancelledResponse],
    response_model_by_alias=True,
    summary="Cancel Command",
    description="Cancel a pending or queued command.",
    dependencies=[Depends(require_permission("commands:execute"))],
)
async def cancel_command(
    command_id: str,
    commands_service: CommandsServiceDep,
) -> SuccessResponse[CommandCancelledResponse]:
    """Cancel a command that has not yet completed.

    Args:
        command_id: Unique identifier of the command to cancel.
        commands_service: Commands service instance.

    Returns:
        Cancellation confirmation.

    Raises:
        HTTPException 400: Command cannot be cancelled (already completed).
        HTTPException 404: Command not found.
        HTTPException 403: Insufficient permissions.
    """
    result = await commands_service.cancel_command(command_id)

    return SuccessResponse(
        data=CommandCancelledResponse(
            command_id=result["commandId"],
            status=CommandStatus(result["status"]),
            cancelled_at=result["cancelledAt"],
        )
    )


nodes_commands_router = APIRouter(prefix="/nodes", tags=["Nodes"])


@nodes_commands_router.get(
    "/{node_id}/commands/poll",
    response_model=SuccessResponse[CommandPollResponse],
    response_model_by_alias=True,
    summary="Poll Commands",
    description="Poll for pending commands (agent endpoint).",
    dependencies=[Depends(require_permission("commands:poll"))],
)
async def poll_commands(
    node_id: str,
    commands_service: CommandsServiceDep,
) -> SuccessResponse[CommandPollResponse]:
    """Poll for commands pending execution on a specific node.

    Args:
        node_id: Unique identifier of the polling node.
        commands_service: Commands service instance.

    Returns:
        List of commands awaiting execution.

    Raises:
        HTTPException 403: Insufficient permissions (agent-only endpoint).
    """
    commands = await commands_service.poll_commands(node_id)

    return SuccessResponse(
        data=CommandPollResponse(commands=commands)
    )


@nodes_commands_router.post(
    "/{node_id}/commands/{command_id}/result",
    response_model=SuccessResponse[CommandResultSubmittedResponse],
    response_model_by_alias=True,
    summary="Submit Command Result",
    description="Submit command execution result (agent endpoint).",
    dependencies=[Depends(require_permission("commands:poll"))],
)
async def submit_command_result(
    node_id: str,
    command_id: str,
    request: SubmitCommandResultRequest,
    commands_service: CommandsServiceDep,
) -> SuccessResponse[CommandResultSubmittedResponse]:
    """Submit the result of command execution from an agent.

    Args:
        node_id: Unique identifier of the executing node.
        command_id: Unique identifier of the command.
        request: Execution result including output and status.
        commands_service: Commands service instance.

    Returns:
        Confirmation of result submission.

    Raises:
        HTTPException 400: Invalid result or command not assigned to node.
        HTTPException 404: Command not found.
        HTTPException 403: Insufficient permissions (agent-only endpoint).
    """
    result = await commands_service.submit_result(node_id, command_id, request)

    return SuccessResponse(
        data=CommandResultSubmittedResponse(
            command_id=result["commandId"],
            status=CommandStatus(result["status"]),
            completed_at=result["completedAt"],
        )
    )
