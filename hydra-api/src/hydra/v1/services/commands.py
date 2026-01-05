"""Commands service for command queue management and execution tracking."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from hydra.db.mongodb import MongoDBManager
from hydra.v1.core.exceptions import (
    CommandNotCancellableError,
    CommandNotFoundError,
    HydraError,
    NodeNotFoundError,
)
from hydra.v1.models.commands import (
    CommandListParams,
    CommandSource,
    CommandStatus,
    CreateCommandRequest,
    SubmitCommandResultRequest,
)

logger = structlog.get_logger(__name__)


class CommandsService:
    """Service for managing command execution queue."""

    def __init__(self, mongodb: MongoDBManager):
        self.mongodb = mongodb
        self.commands = mongodb.commands
        self.nodes = mongodb.nodes

    async def create_command(
        self,
        request: CreateCommandRequest,
        user_id: str | None = None,
        source: CommandSource = CommandSource.API,
    ) -> dict[str, Any]:
        """Create and queue a new command."""
        # Verify target node exists
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
        """Get a command by ID."""
        command = await self.commands.find_one({"commandId": command_id})
        if not command:
            raise CommandNotFoundError(command_id)
        return command

    async def list_commands(
        self, params: CommandListParams
    ) -> tuple[list[dict[str, Any]], int]:
        """List commands with filters."""
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
        """Cancel a pending or queued command."""
        command = await self.get_command(command_id)

        # Only pending or queued commands can be cancelled
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
        """Poll for pending commands for a specific node (agent endpoint)."""
        # Verify node exists
        node = await self.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        # Find queued commands for this node
        cursor = self.commands.find({
            "target.nodeId": node_id,
            "status": CommandStatus.QUEUED.value,
        })
        cursor = cursor.sort("queuedAt", 1)  # FIFO order

        commands = await cursor.to_list(length=10)  # Max 10 at a time

        # Format for agent consumption
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
        """Mark a command as executing (called by agent when it picks up the command)."""
        command = await self.get_command(command_id)

        if command["status"] != CommandStatus.QUEUED.value:
            raise HydraError(
                "COMMAND_ALREADY_EXECUTING",
                f"Command '{command_id}' is not in queued state",
                status_code=422,
            )

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
        """Submit command execution result (agent endpoint)."""
        command = await self.get_command(command_id)

        # Verify the command is for this node
        if command["target"]["nodeId"] != node_id:
            raise HydraError(
                "COMMAND_NODE_MISMATCH",
                f"Command '{command_id}' is not for node '{node_id}'",
                status_code=403,
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

        return {
            "commandId": command_id,
            "status": final_status.value,
            "completedAt": now,
        }

    async def timeout_stale_commands(self, timeout_minutes: int = 10) -> int:
        """Mark stale executing commands as timed out.

        This would typically be called by a background task.
        """
        cutoff = datetime.now(UTC)
        # Use timedelta to calculate the cutoff time
        from datetime import timedelta
        cutoff = cutoff - timedelta(minutes=timeout_minutes)

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

        return result.modified_count
