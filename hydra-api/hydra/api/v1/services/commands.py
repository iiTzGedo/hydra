"""Commands service for command queue management and execution tracking."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from pymongo import ReturnDocument

from hydra.api.v1.core.tasks import safe_create_task
from hydra.db.mongodb import MongoDB
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.models.notifications import NotificationType, NotificationSource
from hydra.api.v1.services.query import log_audit
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.core.exceptions import (
    CommandAlreadyExecutingError,
    CommandNotCancellableError,
    CommandNodeMismatchError,
    CommandNotFoundError,
    NodeNotFoundError,
)
from hydra.api.v1.models.commands import (
    CommandListParams,
    CommandSource,
    CommandStatus,
    CreateCommandRequest,
    SubmitCommandResultRequest,
)

logger = structlog.get_logger(__name__)


class CommandsService:
    """Service for managing command execution queue."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb
        self.commands = mongodb.commands
        self.nodes = mongodb.nodes

    async def create_command(
        self,
        request: CreateCommandRequest,
        user_id: str | None = None,
        source: CommandSource = CommandSource.API,
    ) -> dict[str, Any]:
        """Create and queue a new command for execution on a target node.

        Args:
            request: Command creation payload with type, target, action, and parameters.
            user_id: The requesting user's identifier (None for system commands).
            source: The command source (API, MCP, etc.).

        Returns:
            The created command document.

        Raises:
            NodeNotFoundError: If the target node does not exist or is not active.
        """
        node = await self.nodes.find_one({"nodeId": request.target.node_id, "status": "active"})
        if not node:
            raise NodeNotFoundError(request.target.node_id)

        command_id = f"cmd-{uuid4().hex[:12]}"
        now = datetime.now(UTC)

        command_doc = {
            "commandId": command_id,
            "type": request.type.value,
            "target": {
                "nodeId": request.target.node_id,
                "serviceId": request.target.service_id,
            },
            "action": request.action,
            "parameters": request.parameters or {},
            "status": CommandStatus.QUEUED.value,
            "result": None,
            "requestedBy": {
                "userId": user_id,
                "source": source.value,
            },
            "timeoutSeconds": request.timeout_seconds,
            "createdAt": now,
            "queuedAt": now,
            "startedAt": None,
            "completedAt": None,
        }

        await self.commands.insert_one(command_doc)

        logger.info(
            "command_created",
            command_id=command_id,
            type=request.type.value,
            target_node=request.target.node_id,
            action=request.action,
        )

        return command_doc

    async def get_command(self, command_id: str) -> dict[str, Any]:
        """Get a command by its identifier.

        Args:
            command_id: The command identifier.

        Returns:
            The command document.

        Raises:
            CommandNotFoundError: If the command does not exist.
        """
        command = await self.commands.find_one({"commandId": command_id})
        if not command:
            raise CommandNotFoundError(command_id)
        return command

    async def list_commands(
        self, params: CommandListParams
    ) -> tuple[list[dict[str, Any]], int]:
        """List commands with optional filtering and pagination.

        Args:
            params: Query parameters including node_id, type, status, since, offset, limit.

        Returns:
            Tuple of (list of command documents, total count).
        """
        query: dict[str, Any] = {}

        if params.node_id:
            query["target.nodeId"] = params.node_id
        if params.type:
            query["type"] = params.type.value
        if params.status:
            query["status"] = params.status.value
        if params.since:
            query["createdAt"] = {"$gte": params.since}

        total = await self.commands.count_documents(query)

        cursor = self.commands.find(query)
        cursor = cursor.sort("createdAt", -1)
        cursor = cursor.skip(params.offset).limit(params.limit)

        commands = await cursor.to_list(length=params.limit)

        return commands, total

    async def cancel_command(self, command_id: str) -> dict[str, Any]:
        """Cancel a pending or queued command.

        Args:
            command_id: The command identifier.

        Returns:
            Dict with command_id, status, and cancelled_at timestamp.

        Raises:
            CommandNotFoundError: If the command does not exist.
            CommandNotCancellableError: If the command is already executing or completed.
        """
        command = await self.get_command(command_id)

        if command["status"] not in [CommandStatus.PENDING.value, CommandStatus.QUEUED.value]:
            raise CommandNotCancellableError(command_id, command["status"])

        now = datetime.now(UTC)

        await self.commands.update_one(
            {"commandId": command_id},
            {
                "$set": {
                    "status": CommandStatus.CANCELLED.value,
                    "completedAt": now,
                }
            },
        )

        logger.info("command_cancelled", command_id=command_id)

        return {
            "commandId": command_id,
            "status": CommandStatus.CANCELLED.value,
            "cancelledAt": now,
        }

    async def poll_commands(self, node_id: str) -> list[dict[str, Any]]:
        """Poll for pending commands for a specific node.

        Atomically claims queued commands to prevent duplicate execution by
        concurrent pollers. Used by agents to fetch work.

        Args:
            node_id: The node identifier to poll commands for.

        Returns:
            List of command payloads formatted for agent consumption.

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        node = await self.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        # Update lastSeenAt on every agent poll
        await self.nodes.update_one(
            {"nodeId": node_id},
            {"$set": {"lastSeenAt": datetime.now(UTC)}},
        )

        commands: list[dict[str, Any]] = []
        for _ in range(10):
            command = await self.commands.find_one_and_update(
                {
                    "target.nodeId": node_id,
                    "status": CommandStatus.QUEUED.value,
                },
                {
                    "$set": {
                        "status": CommandStatus.EXECUTING.value,
                        "startedAt": datetime.now(UTC),
                    }
                },
                sort=[("queuedAt", 1)],
                return_document=ReturnDocument.AFTER,
            )
            if not command:
                break
            commands.append(command)

        result = []
        for cmd in commands:
            result.append({
                "commandId": cmd["commandId"],
                "type": cmd["type"],
                "action": cmd["action"],
                "parameters": {
                    **cmd.get("parameters", {}),
                    "serviceId": cmd["target"].get("serviceId"),
                },
                "timeoutSeconds": cmd["timeoutSeconds"],
            })

        return result

    async def mark_command_executing(self, command_id: str) -> dict[str, Any]:
        """Mark a command as executing.

        Called by the agent when it begins processing a command.

        Args:
            command_id: The command identifier.

        Returns:
            The updated command document.

        Raises:
            CommandNotFoundError: If the command does not exist.
            HydraError: If the command is not in queued state.
        """
        command = await self.get_command(command_id)

        if command["status"] == CommandStatus.EXECUTING.value:
            if not command.get("startedAt"):
                now = datetime.now(UTC)
                await self.commands.update_one(
                    {"commandId": command_id},
                    {"$set": {"startedAt": now}},
                )
                command["startedAt"] = now
            return command
        if command["status"] != CommandStatus.QUEUED.value:
            raise CommandAlreadyExecutingError(command_id, command["status"])

        now = datetime.now(UTC)

        await self.commands.update_one(
            {"commandId": command_id},
            {
                "$set": {
                    "status": CommandStatus.EXECUTING.value,
                    "startedAt": now,
                }
            },
        )

        logger.info("command_executing", command_id=command_id)

        command["status"] = CommandStatus.EXECUTING.value
        command["startedAt"] = now
        return command

    async def submit_result(
        self,
        node_id: str,
        command_id: str,
        result: SubmitCommandResultRequest,
    ) -> dict[str, Any]:
        """Submit command execution result from an agent.

        Args:
            node_id: The node identifier submitting the result.
            command_id: The command identifier.
            result: Execution result with success status, output, exit code, and error.

        Returns:
            Dict with command_id, final status, and completed_at timestamp.

        Raises:
            CommandNotFoundError: If the command does not exist.
            HydraError: If the command is not assigned to the submitting node.
        """
        command = await self.get_command(command_id)

        if command["target"]["nodeId"] != node_id:
            raise CommandNodeMismatchError(
                command_id, command["target"]["nodeId"], node_id
            )

        now = datetime.now(UTC)
        final_status = CommandStatus.COMPLETED if result.success else CommandStatus.FAILED

        result_doc = {
            "success": result.success,
            "output": result.output,
            "exitCode": result.exit_code,
            "error": result.error,
        }

        await self.commands.update_one(
            {"commandId": command_id},
            {
                "$set": {
                    "status": final_status.value,
                    "result": result_doc,
                    "completedAt": now,
                }
            },
        )

        logger.info(
            "command_result_submitted",
            command_id=command_id,
            success=result.success,
            status=final_status.value,
        )

        if result.success:
            audit_id = await log_audit(
                action=AuditAction.EXECUTE,
                resource_type="command",
                resource_id=command_id,
                actor_type="node",
                actor_id=node_id,
                success=True,
                details={"commandId": command_id, "nodeId": node_id, "exitCode": result.exit_code},
            )
            safe_create_task(emit_notification(
                notification_type=NotificationType.COMMAND_EXECUTION_SUCCEEDED,
                source=NotificationSource(component="hydra-api", service="commands", node_id=node_id),
                title="Command completed",
                message=f"Command {command_id} completed successfully on {node_id}",
                details={"commandId": command_id, "nodeId": node_id, "exitCode": result.exit_code},
                audit_entry_id=audit_id,
            ))
        else:
            audit_id = await log_audit(
                action=AuditAction.EXECUTE,
                resource_type="command",
                resource_id=command_id,
                actor_type="node",
                actor_id=node_id,
                success=False,
                details={"commandId": command_id, "nodeId": node_id, "exitCode": result.exit_code, "error": result.error},
                error=result.error,
            )
            safe_create_task(emit_notification(
                notification_type=NotificationType.COMMAND_EXECUTION_FAILED,
                source=NotificationSource(component="hydra-api", service="commands", node_id=node_id),
                title="Command failed",
                message=f"Command {command_id} failed on {node_id}: {result.error or 'unknown error'}",
                details={"commandId": command_id, "nodeId": node_id, "exitCode": result.exit_code, "error": result.error},
                audit_entry_id=audit_id,
            ))

        return {
            "commandId": command_id,
            "status": final_status.value,
            "completedAt": now,
        }

    async def timeout_stale_commands(self, timeout_minutes: int = 10) -> int:
        """Mark stale executing commands as timed out.

        Typically called by a background task to clean up commands that have
        been executing longer than the allowed timeout.

        Args:
            timeout_minutes: Number of minutes after which executing commands are timed out.

        Returns:
            The number of commands that were marked as timed out.
        """
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)

        result = await self.commands.update_many(
            {
                "status": CommandStatus.EXECUTING.value,
                "startedAt": {"$lt": cutoff},
            },
            {
                "$set": {
                    "status": CommandStatus.TIMEOUT.value,
                    "completedAt": datetime.now(UTC),
                    "result": {
                        "success": False,
                        "output": None,
                        "exitCode": None,
                        "error": "Command execution timed out",
                    },
                }
            },
        )

        if result.modified_count > 0:
            logger.info("commands_timed_out", count=result.modified_count)
            audit_id = await log_audit(
                action=AuditAction.EXECUTE,
                resource_type="command",
                resource_id="bulk-timeout",
                actor_type="system",
                actor_id="hydra-api",
                success=False,
                details={"count": result.modified_count, "timeoutMinutes": timeout_minutes},
                error="timeout",
            )
            safe_create_task(emit_notification(
                notification_type=NotificationType.COMMAND_EXECUTION_TIMEOUT,
                source=NotificationSource(component="hydra-api", service="commands"),
                title="Commands timed out",
                message=f"{result.modified_count} command(s) timed out after {timeout_minutes} minutes",
                details={"count": result.modified_count, "timeoutMinutes": timeout_minutes},
                audit_entry_id=audit_id,
            ))

        return result.modified_count
