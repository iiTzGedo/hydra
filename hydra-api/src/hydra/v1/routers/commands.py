"""Command execution endpoints."""

from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.v1.core.deps import CurrentUserDep, MongoDBDep, require_permission
from hydra.v1.models.commands import (
    CommandCancelledResponse,
    CommandListParams,
    CommandPollResponse,
    CommandQueuedResponse,
    CommandResponse,
    CommandResultSubmittedResponse,
    CommandSource,
    CommandStatus,
    CommandSummary,
    CommandType,
    CreateCommandRequest,
    SubmitCommandResultRequest,
)
from hydra.v1.models.common import PaginationMeta, SuccessResponse
from hydra.v1.services.commands import CommandsService

router = APIRouter(prefix="/commands", tags=["Commands"])
logger = structlog.get_logger(__name__)


def get_commands_service(mongodb: MongoDBDep) -> CommandsService:
    """Get commands service dependency."""
    return CommandsService(mongodb)


CommandsServiceDep = Annotated[CommandsService, Depends(get_commands_service)]


@router.post(
    "",
    response_model=SuccessResponse[CommandQueuedResponse],
    status_code=202,
    summary="Queue Command",
    description="Queue a command for execution on a target node.",
    dependencies=[Depends(require_permission("commands:execute"))],
)
async def create_command(
    request: CreateCommandRequest,
    commands_service: CommandsServiceDep,
    current_user: CurrentUserDep,
) -> SuccessResponse[CommandQueuedResponse]:
    """Queue a new command for execution."""
    # Determine source based on request context
    source = CommandSource.API
    if hasattr(current_user, "source"):
        source = current_user.source

    user_id = current_user.get("userId") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)

    command = await commands_service.create_command(
        request,
        user_id=user_id,
        source=source,
    )

    return SuccessResponse(
        data=CommandQueuedResponse(
            command_id=command["commandId"],
            type=CommandType(command["type"]),
            target=command["target"],
            action=command["action"],
            status=CommandStatus(command["status"]),
            queued_at=command["queuedAt"],
        )
    )


@router.get(
    "",
    response_model=SuccessResponse[list[CommandSummary]],
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
    """List commands with filters."""
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
    summary="Get Command",
    description="Get detailed information about a specific command.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def get_command(
    command_id: str,
    commands_service: CommandsServiceDep,
) -> SuccessResponse[CommandResponse]:
    """Get a single command by ID."""
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
    summary="Cancel Command",
    description="Cancel a pending or queued command.",
    dependencies=[Depends(require_permission("commands:execute"))],
)
async def cancel_command(
    command_id: str,
    commands_service: CommandsServiceDep,
) -> SuccessResponse[CommandCancelledResponse]:
    """Cancel a command."""
    result = await commands_service.cancel_command(command_id)

    return SuccessResponse(
        data=CommandCancelledResponse(
            command_id=result["commandId"],
            status=CommandStatus(result["status"]),
            cancelled_at=result["cancelledAt"],
        )
    )


# ==================== Node Commands Endpoints (for agents) ====================

nodes_commands_router = APIRouter(prefix="/nodes", tags=["Nodes"])


@nodes_commands_router.get(
    "/{node_id}/commands/poll",
    response_model=SuccessResponse[CommandPollResponse],
    summary="Poll Commands",
    description="Poll for pending commands (agent endpoint).",
    dependencies=[Depends(require_permission("commands:poll"))],
)
async def poll_commands(
    node_id: str,
    commands_service: CommandsServiceDep,
) -> SuccessResponse[CommandPollResponse]:
    """Poll for pending commands for a node."""
    commands = await commands_service.poll_commands(node_id)

    return SuccessResponse(
        data=CommandPollResponse(commands=commands)
    )


@nodes_commands_router.post(
    "/{node_id}/commands/{command_id}/result",
    response_model=SuccessResponse[CommandResultSubmittedResponse],
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
    """Submit command execution result."""
    result = await commands_service.submit_result(node_id, command_id, request)

    return SuccessResponse(
        data=CommandResultSubmittedResponse(
            command_id=result["commandId"],
            status=CommandStatus(result["status"]),
            completed_at=result["completedAt"],
        )
    )
