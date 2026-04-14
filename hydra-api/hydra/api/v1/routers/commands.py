"""Command execution endpoints."""

from datetime import UTC, datetime
from typing import Annotated

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
from hydra.api.v1.core.exceptions import AdminOnlyError
from hydra.api.v1.models.commands import (
    CommandCancelledResponse,
    CommandCategory,
    CommandDefinitionResponse,
    CommandDefinitionSummary,
    CommandExecutionMethod,
    CommandListParams,
    CommandPollResponse,
    CommandQueuedResponse,
    CommandResponse,
    CommandResult,
    CommandResultSubmittedResponse,
    CommandRetriedResponse,
    CommandSource,
    CommandStatus,
    CommandSummary,
    CommandType,
    CreateCommandRequest,
    DryRunResponse,
    QueueFlushRequest,
    QueueFlushResponse,
    QueueStats,
    QueueViewResponse,
    SubmitCommandResultRequest,
)
from hydra.api.v1.models.commands.registry import (
    AuditConfig,
    CommandDeliveryMode,
    ExecutionConfig,
    RbacConfig,
    RegistryMetadata,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.services.commands import CommandsService
from hydra.api.v1.services.commands.registry import CommandRegistryService

router = APIRouter(prefix="/commands", tags=["Commands"])
logger = structlog.get_logger(__name__)


def get_commands_service(mongodb: MongoDBDep) -> CommandsService:
    """Get commands service dependency."""
    return CommandsService(mongodb)


def get_registry_service(mongodb: MongoDBDep) -> CommandRegistryService:
    """Get command registry service dependency."""
    return CommandRegistryService(mongodb)


CommandsServiceDep = Annotated[CommandsService, Depends(get_commands_service)]
RegistryServiceDep = Annotated[CommandRegistryService, Depends(get_registry_service)]


# ── Command Catalog ──────────────────────────────────────────────────────


catalog_router = APIRouter(prefix="/command-catalog", tags=["Command Catalog"])


@catalog_router.get(
    "",
    response_model=SuccessResponse[list[CommandDefinitionSummary]],
    response_model_by_alias=True,
    summary="List Command Catalog",
    description="List all registered command definitions.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def list_command_catalog(
    registry_service: RegistryServiceDep,
    category: CommandCategory | None = None,
    include_deprecated: bool = Query(default=False, alias="includeDeprecated"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[CommandDefinitionSummary]]:
    """List command definitions from the catalog."""
    definitions, total = await registry_service.list_definitions(
        category=category.value if category else None,
        include_deprecated=include_deprecated,
        limit=limit,
        offset=offset,
    )

    return SuccessResponse(
        data=[
            CommandDefinitionSummary(
                registry_id=d["registryId"],
                category=CommandCategory(d["category"]),
                action=d["action"],
                display_name=d["displayName"],
                description=d.get("description"),
                minimum_role=d.get("rbac", {}).get("minimumRole", "operator"),
                requires_confirmation=d.get("rbac", {}).get("requiresConfirmation", False),
                danger_level=d.get("rbac", {}).get("dangerLevel", "medium"),
                control_permission=d.get("rbac", {}).get("controlPermission"),
                timeout=d.get("execution", {}).get("timeout", 60),
                delivery_mode=d.get("execution", {}).get("deliveryMode", CommandDeliveryMode.POLL_ONLY.value),
                built_in=d.get("metadata", {}).get("builtIn", False),
                deprecated=d.get("metadata", {}).get("deprecated", False),
            )
            for d in definitions
        ],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@catalog_router.get(
    "/{registry_id:path}",
    response_model=SuccessResponse[CommandDefinitionResponse],
    response_model_by_alias=True,
    summary="Get Command Definition",
    description="Get a single command definition by registry ID.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def get_command_definition(
    registry_id: str,
    registry_service: RegistryServiceDep,
) -> SuccessResponse[CommandDefinitionResponse]:
    """Get a command definition from the catalog."""
    d = await registry_service.get_definition(registry_id)

    return SuccessResponse(
        data=CommandDefinitionResponse(
            registry_id=d["registryId"],
            category=CommandCategory(d["category"]),
            action=d["action"],
            display_name=d["displayName"],
            description=d.get("description"),
            target_schema=d.get("targetSchema"),
            parameters_schema=d.get("parametersSchema"),
            execution=ExecutionConfig(**d.get("execution", {})),
            rbac=RbacConfig(**d.get("rbac", {"minimumRole": "operator"})),
            audit=AuditConfig(**d.get("audit", {})),
            metadata=RegistryMetadata(**d.get("metadata", {"addedAt": d.get("createdAt", datetime.now(UTC))})),
        )
    )


# ── Commands ─────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=SuccessResponse[CommandQueuedResponse | DryRunResponse],
    response_model_by_alias=True,
    summary="Execute Command",
    description="""Submit a command for execution on a target node.

Dispatch is tier-aware:
- **Lite tier**: Rejected (400) — does not support command execution.
- **Normal tier**: Queued for poll-based execution (202 Accepted).
- **Max tier**: Attempted via direct HTTP call; falls back to queue on failure.

Set `dryRun=true` to validate the full execution path and receive a non-persisting preview.
Returns 200 for dry-run previews or synchronous direct execution, 202 for queued execution.
""",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def create_command(
    request: CreateCommandRequest,
    commands_service: CommandsServiceDep,
    current_user: CurrentUser,
) -> JSONResponse:
    """Submit a command for tier-aware execution on an agent."""
    source = CommandSource(get_command_request_source(current_user))
    user_id = get_authenticated_user_id(current_user)
    user_role = get_authenticated_role(current_user)
    user_permissions = get_authenticated_permissions(current_user)
    client_id = get_authenticated_client_id(current_user)

    # Dry-run: validate and preview without executing
    if request.dry_run:
        preview = await commands_service.dry_run_command(
            request,
            user_id=user_id,
            user_role=user_role,
            user_permissions=user_permissions,
            source=source,
            client_id=client_id,
        )
        dry_run_wrapped = SuccessResponse(data=preview)
        return JSONResponse(
            content=dry_run_wrapped.model_dump(by_alias=True, mode="json"),
            status_code=200,
        )

    command = await commands_service.create_command(
        request,
        user_id=user_id,
        user_role=user_role,
        user_permissions=user_permissions,
        source=source,
        client_id=client_id,
    )

    execution_method = command.get("executionMethod")
    result_data = command.get("result")
    is_pending_confirmation = command["status"] == CommandStatus.PENDING_CONFIRMATION.value

    response_data = CommandQueuedResponse(
        command_id=command["commandId"],
        registry_id=command.get("registryId"),
        type=CommandType(command["type"]),
        target=command["target"],
        action=command["action"],
        status=CommandStatus(command["status"]),
        execution_method=CommandExecutionMethod(execution_method) if execution_method else (None if is_pending_confirmation else CommandExecutionMethod.AGENT_POLL),
        result=CommandResult(**result_data) if result_data else None,
        queue_position=command.get("queuePosition"),
        queued_at=command.get("queuedAt"),
        completed_at=command.get("completedAt"),
        requires_confirmation=is_pending_confirmation,
        confirmation_message=command.get("confirmationMessage"),
        danger_level=command.get("dangerLevel"),
        affected_nodes=command.get("affectedNodes", []),
        confirmation_expires_at=command.get("confirmationExpiresAt"),
    )

    wrapped = SuccessResponse(data=response_data)
    status_code = 200 if execution_method == "agent-direct" else 202

    return JSONResponse(
        content=wrapped.model_dump(by_alias=True, mode="json"),
        status_code=status_code,
    )


@router.get(
    "/queue",
    response_model=SuccessResponse[QueueViewResponse],
    response_model_by_alias=True,
    summary="View Command Queue",
    description="View the current command queue with statistics.",
    dependencies=[Depends(require_permission("commands:read"))],
)
async def view_queue(
    commands_service: CommandsServiceDep,
    node_id: str | None = Query(default=None, alias="nodeId"),
) -> SuccessResponse[QueueViewResponse]:
    """View the current command queue."""
    result = await commands_service.get_queue_view(node_id=node_id)

    queue_items = [
        CommandSummary(
            command_id=cmd["commandId"],
            registry_id=cmd.get("registryId"),
            type=CommandType(cmd["type"]),
            target=cmd["target"],
            action=cmd["action"],
            status=CommandStatus(cmd["status"]),
            created_at=cmd["createdAt"],
        )
        for cmd in result["queue"]
    ]

    stats = QueueStats(
        total_queued=result["stats"]["totalQueued"],
        total_executing=result["stats"]["totalExecuting"],
        oldest_queued_at=result["stats"]["oldestQueuedAt"],
    )

    return SuccessResponse(
        data=QueueViewResponse(queue=queue_items, stats=stats)
    )


@router.post(
    "/queue/flush",
    response_model=SuccessResponse[QueueFlushResponse],
    response_model_by_alias=True,
    summary="Flush Command Queue",
    description="Flush (cancel) all queued commands. Admin only.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def flush_queue(
    request: QueueFlushRequest,
    commands_service: CommandsServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[QueueFlushResponse]:
    """Flush queued commands."""
    user_role = get_authenticated_role(current_user)
    if user_role != "admin":
        raise AdminOnlyError("flush_queue")

    if not request.confirm:
        from hydra.api.v1.core.exceptions import ValidationError
        raise ValidationError("Set confirm=true to flush the queue")

    user_id = get_authenticated_user_id(current_user)

    flushed = await commands_service.flush_queue(
        scope=request.scope,
        user_id=user_id,
    )

    return SuccessResponse(
        data=QueueFlushResponse(flushed_count=flushed)
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
    service_id: str | None = Query(default=None, alias="serviceId"),
    registry_id: str | None = Query(default=None, alias="registryId"),
    type: CommandType | None = None,
    status: CommandStatus | None = None,
    since: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[CommandSummary]]:
    """Retrieve command execution history."""
    params = CommandListParams(
        node_id=node_id,
        service_id=service_id,
        registry_id=registry_id,
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
                registry_id=cmd.get("registryId"),
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
    """Retrieve detailed information about a specific command."""
    command = await commands_service.get_command(command_id)

    execution_method = command.get("executionMethod")

    return SuccessResponse(
        data=CommandResponse(
            command_id=command["commandId"],
            registry_id=command.get("registryId"),
            type=CommandType(command["type"]),
            target=command["target"],
            action=command["action"],
            parameters=command.get("parameters"),
            status=CommandStatus(command["status"]),
            execution_method=CommandExecutionMethod(execution_method) if execution_method else None,
            result=command.get("result"),
            error=command.get("error"),
            requested_by=command.get("requestedBy"),
            timeout_seconds=command["timeoutSeconds"],
            retry_count=command.get("retryCount", 0),
            max_retries=command.get("maxRetries", 0),
            retried_from=command.get("retriedFrom"),
            queue_position=command.get("queuePosition"),
            chain=command.get("chain"),
            created_at=command["createdAt"],
            queued_at=command.get("queuedAt"),
            started_at=command.get("startedAt"),
            completed_at=command.get("completedAt"),
            cancelled_at=command.get("cancelledAt"),
            cancelled_by=command.get("cancelledBy"),
            danger_level=command.get("dangerLevel"),
            confirmation_message=command.get("confirmationMessage"),
            confirmation_expires_at=command.get("confirmationExpiresAt"),
        )
    )


@router.post(
    "/{command_id}/confirm",
    response_model=SuccessResponse[CommandQueuedResponse],
    response_model_by_alias=True,
    summary="Confirm Command",
    description="Confirm a pending command for execution. Required for destructive operations.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def confirm_command(
    command_id: str,
    commands_service: CommandsServiceDep,
    current_user: CurrentUser,
) -> JSONResponse:
    """Confirm a command that is pending confirmation."""
    user_id = get_authenticated_user_id(current_user)
    user_role = get_authenticated_role(current_user)
    user_permissions = get_authenticated_permissions(current_user)
    source = CommandSource(get_command_request_source(current_user))
    client_id = get_authenticated_client_id(current_user)

    command = await commands_service.confirm_command(
        command_id,
        user_id=user_id,
        user_role=user_role,
        user_permissions=user_permissions,
        source=source,
        client_id=client_id,
    )

    execution_method = command.get("executionMethod")

    response_data = CommandQueuedResponse(  # type: ignore[call-arg]
        command_id=command["commandId"],
        registry_id=command.get("registryId"),
        type=CommandType(command["type"]),
        target=command["target"],
        action=command["action"],
        status=CommandStatus(command["status"]),
        execution_method=CommandExecutionMethod(execution_method) if execution_method else CommandExecutionMethod.AGENT_POLL,
        queue_position=command.get("queuePosition"),
        queued_at=command.get("queuedAt"),
    )

    wrapped = SuccessResponse(data=response_data)
    return JSONResponse(
        content=wrapped.model_dump(by_alias=True, mode="json"),
        status_code=202,
    )


@router.post(
    "/{command_id}/cancel",
    response_model=SuccessResponse[CommandCancelledResponse],
    response_model_by_alias=True,
    summary="Cancel Command",
    description="Cancel a pending or queued command.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def cancel_command(
    command_id: str,
    commands_service: CommandsServiceDep,
    current_user: CurrentUser,
    confirm_cascade: bool = Query(
        default=False,
        alias="confirmCascade",
        description="Also cancel sibling commands in the same chain.",
    ),
) -> SuccessResponse[CommandCancelledResponse]:
    """Cancel a command that has not yet completed."""
    user_id = get_authenticated_user_id(current_user)

    result = await commands_service.cancel_command(
        command_id, cancelled_by=user_id, confirm_cascade=confirm_cascade
    )

    return SuccessResponse(
        data=CommandCancelledResponse(
            command_id=result["commandId"],
            status=CommandStatus(result["status"]),
            cancelled_at=result["cancelledAt"],
            cancelled_by=result.get("cancelledBy"),
            cascade_cancelled_ids=result.get("cascadeCancelledIds"),
        )
    )


@router.post(
    "/{command_id}/retry",
    response_model=SuccessResponse[CommandRetriedResponse],
    response_model_by_alias=True,
    status_code=202,
    summary="Retry Command",
    description="Retry a failed or timed-out command. Creates a new command linked to the original.",
    dependencies=[
        Depends(require_permission("commands:execute")),
        Depends(require_trusted_write_origin()),
    ],
)
async def retry_command(
    command_id: str,
    commands_service: CommandsServiceDep,
    current_user: CurrentUser,
) -> JSONResponse:
    """Retry a failed or timed-out command."""
    user_id = get_authenticated_user_id(current_user)
    user_role = get_authenticated_role(current_user)
    user_permissions = get_authenticated_permissions(current_user)
    source = CommandSource(get_command_request_source(current_user))
    client_id = get_authenticated_client_id(current_user)

    result = await commands_service.retry_command(
        command_id,
        user_id=user_id,
        user_role=user_role,
        user_permissions=user_permissions,
        source=source,
        client_id=client_id,
    )

    response_data = CommandRetriedResponse(
        command_id=result["commandId"],
        original_command_id=result["retriedFrom"],
        retry_count=result["retryCount"],
        max_retries=result["maxRetries"],
        status=CommandStatus(result["status"]),
    )

    wrapped = SuccessResponse(data=response_data)
    return JSONResponse(
        content=wrapped.model_dump(by_alias=True, mode="json"),
        status_code=202,
    )


# ── Agent Endpoints (Node-scoped) ────────────────────────────────────────


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
    """Poll for commands pending execution on a specific node."""
    commands = await commands_service.poll_commands(node_id)

    return SuccessResponse(
        data=CommandPollResponse(commands=commands)  # type: ignore[arg-type]
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
    """Submit the result of command execution from an agent."""
    result = await commands_service.submit_result(node_id, command_id, request)

    return SuccessResponse(
        data=CommandResultSubmittedResponse(
            command_id=result["commandId"],
            status=CommandStatus(result["status"]),
            completed_at=result["completedAt"],
        )
    )
