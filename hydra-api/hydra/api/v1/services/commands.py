"""Commands service for command queue management and execution tracking."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
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
    CommandNotSupportedError,
    NodeNotFoundError,
)
from hydra.api.v1.models.commands import (
    CommandListParams,
    CommandSource,
    CommandStatus,
    CreateCommandRequest,
    SubmitCommandResultRequest,
)

# Maximum consecutive direct-call failures before marking agent unreachable
MAX_DIRECT_FAILURES = 3

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
        """Create a command with tier-aware dispatch.

        - Lite tier: rejected (does not support command execution)
        - Normal tier: queued for poll-based execution
        - Max tier: try direct HTTP call to agent, fallback to queue on failure

        Args:
            request: Command creation payload with type, target, action, and parameters.
            user_id: The requesting user's identifier (None for system commands).
            source: The command source (API, MCP, etc.).

        Returns:
            The created command document. Contains 'executionMethod' field
            indicating how the command was dispatched ('direct' or 'poll').

        Raises:
            NodeNotFoundError: If the target node does not exist or is not active.
            CommandNotSupportedError: If the agent tier does not support commands.
        """
        node = await self.nodes.find_one({"nodeId": request.target.node_id, "status": "active"})
        if not node:
            raise NodeNotFoundError(request.target.node_id)

        tier = node.get("agentTier", "normal")

        # Lite tier: reject
        if tier == "lite":
            raise CommandNotSupportedError(
                f"Agent tier 'lite' on node '{request.target.node_id}' does not support "
                f"command execution. Upgrade to 'normal' or 'max' tier."
            )

        # Max tier: try direct execution first
        if tier == "max":
            direct_result = await self._try_direct_execution(node, request, user_id, source)
            if direct_result is not None:
                return direct_result

        # Normal tier or max-tier fallback: queue for poll-based execution
        return await self._queue_command(request, user_id, source)

    async def _queue_command(
        self,
        request: CreateCommandRequest,
        user_id: str | None,
        source: CommandSource,
    ) -> dict[str, Any]:
        """Queue a command for poll-based execution by the agent."""
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
            "executionMethod": "poll",
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
            "command_queued",
            command_id=command_id,
            type=request.type.value,
            target_node=request.target.node_id,
            action=request.action,
            execution_method="poll",
        )

        return command_doc

    async def _try_direct_execution(
        self,
        node: dict,
        request: CreateCommandRequest,
        user_id: str | None,
        source: CommandSource,
    ) -> dict[str, Any] | None:
        """Attempt direct command execution on a max-tier agent's HTTP server.

        Returns the completed command document on success, or None to fall back
        to poll-based execution.
        """
        server_address = node.get("serverAddress")
        server_port = node.get("serverPort", 9100)
        server_tls_enabled = bool(node.get("serverTlsEnabled"))
        server_secret = node.get("agentServerSecret")

        if not server_address or not server_secret:
            logger.debug(
                "direct_execution_skipped",
                node_id=node["nodeId"],
                reason="missing serverAddress or agentServerSecret",
            )
            return None

        # Check reachability — skip direct if known unreachable
        if not node.get("serverReachable", True):
            failed = node.get("failedDirectAttempts", 0)
            if failed >= MAX_DIRECT_FAILURES:
                logger.debug(
                    "direct_execution_skipped",
                    node_id=node["nodeId"],
                    reason=f"unreachable after {failed} failures",
                )
                return None

        command_id = f"cmd-{uuid4().hex[:12]}"
        now = datetime.now(UTC)
        node_id = node["nodeId"]

        # Build the execute payload for the agent's POST /execute endpoint
        execute_payload = {
            "commandId": command_id,
            "registryId": request.action,
            "target": {
                "nodeId": request.target.node_id,
                "serviceId": request.target.service_id,
            },
            "parameters": request.parameters,
            "timeoutSeconds": request.timeout_seconds,
        }

        scheme = "https" if server_tls_enabled else "http"
        base_url = f"{scheme}://{server_address}:{server_port}"

        try:
            async with httpx.AsyncClient(
                timeout=min(request.timeout_seconds, 30),
                verify=False,
            ) as client:
                response = await client.post(
                    f"{base_url}/execute",
                    headers={"Authorization": f"Bearer {server_secret}"},
                    json=execute_payload,
                )

            if response.status_code == 200:
                agent_result = response.json()
                await self._update_reachability(node_id, success=True)

                # Build completed command document
                result_doc = {
                    "success": agent_result.get("status") == "completed",
                    "output": agent_result.get("result", {}).get("output")
                    if isinstance(agent_result.get("result"), dict)
                    else None,
                    "exitCode": agent_result.get("result", {}).get("exitCode")
                    if isinstance(agent_result.get("result"), dict)
                    else None,
                    "error": agent_result.get("result", {}).get("error")
                    if isinstance(agent_result.get("result"), dict)
                    else None,
                }

                final_status = (
                    CommandStatus.COMPLETED.value
                    if result_doc["success"]
                    else CommandStatus.FAILED.value
                )

                command_doc = {
                    "commandId": command_id,
                    "type": request.type.value,
                    "target": {
                        "nodeId": request.target.node_id,
                        "serviceId": request.target.service_id,
                    },
                    "action": request.action,
                    "parameters": request.parameters or {},
                    "status": final_status,
                    "executionMethod": "direct",
                    "result": result_doc,
                    "requestedBy": {
                        "userId": user_id,
                        "source": source.value,
                    },
                    "timeoutSeconds": request.timeout_seconds,
                    "createdAt": now,
                    "queuedAt": None,
                    "startedAt": now,
                    "completedAt": datetime.now(UTC),
                }

                await self.commands.insert_one(command_doc)

                logger.info(
                    "command_executed_direct",
                    command_id=command_id,
                    node_id=node_id,
                    success=result_doc["success"],
                )

                return command_doc

            logger.warning(
                "direct_execution_failed",
                node_id=node_id,
                status_code=response.status_code,
            )
            return None

        except httpx.RequestError as e:
            logger.warning(
                "direct_execution_failed",
                node_id=node_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            await self._update_reachability(node_id, success=False, error=str(e))
            return None
        except Exception as e:
            logger.error(
                "direct_execution_unexpected_error",
                node_id=node_id,
                error=str(e),
            )
            return None

    async def _update_reachability(
        self, node_id: str, *, success: bool, error: str | None = None
    ) -> None:
        """Update max-tier agent reachability tracking in the node document."""
        now = datetime.now(UTC)

        if success:
            await self.nodes.update_one(
                {"nodeId": node_id},
                {
                    "$set": {
                        "serverReachable": True,
                        "failedDirectAttempts": 0,
                        "lastDirectContact": now,
                        "lastUpdated": now,
                    }
                },
            )
        else:
            result = await self.nodes.find_one_and_update(
                {"nodeId": node_id},
                {
                    "$inc": {"failedDirectAttempts": 1},
                    "$set": {
                        "lastError": error,
                        "lastUpdated": now,
                    },
                },
                return_document=ReturnDocument.AFTER,
            )
            if result and result.get("failedDirectAttempts", 0) >= MAX_DIRECT_FAILURES:
                await self.nodes.update_one(
                    {"nodeId": node_id},
                    {"$set": {"serverReachable": False}},
                )

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

    async def list_commands(self, params: CommandListParams) -> tuple[list[dict[str, Any]], int]:
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

        # Update lastSeenAt and lastPollContact on every agent poll.
        # If the agent was previously marked unreachable, reset reachability
        # since it's clearly online (it just polled us).
        now = datetime.now(UTC)
        poll_update: dict[str, Any] = {
            "lastSeenAt": now,
            "lastPollContact": now,
            "serverReachable": True,
            "failedDirectAttempts": 0,
        }
        if node.get("serverReachable") is False or node.get("failedDirectAttempts", 0) > 0:
            logger.info(
                "agent_reachability_restored",
                node_id=node_id,
                reason="poll contact received",
            )
        await self.nodes.update_one(
            {"nodeId": node_id},
            {"$set": poll_update},
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
            result.append(
                {
                    "commandId": cmd["commandId"],
                    "type": cmd["type"],
                    "action": cmd["action"],
                    "target": {
                        "nodeId": cmd["target"]["nodeId"],
                        "serviceId": cmd["target"].get("serviceId"),
                    },
                    "parameters": cmd.get("parameters") or None,
                    "timeoutSeconds": cmd["timeoutSeconds"],
                }
            )

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
            raise CommandNodeMismatchError(command_id, command["target"]["nodeId"], node_id)

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
            safe_create_task(
                emit_notification(
                    notification_type=NotificationType.COMMAND_EXECUTION_SUCCEEDED,
                    source=NotificationSource(
                        component="hydra-api", service="commands", node_id=node_id
                    ),
                    title="Command completed",
                    message=f"Command {command_id} completed successfully on {node_id}",
                    details={
                        "commandId": command_id,
                        "nodeId": node_id,
                        "exitCode": result.exit_code,
                    },
                    audit_entry_id=audit_id,
                )
            )
        else:
            audit_id = await log_audit(
                action=AuditAction.EXECUTE,
                resource_type="command",
                resource_id=command_id,
                actor_type="node",
                actor_id=node_id,
                success=False,
                details={
                    "commandId": command_id,
                    "nodeId": node_id,
                    "exitCode": result.exit_code,
                    "error": result.error,
                },
                error=result.error,
            )
            safe_create_task(
                emit_notification(
                    notification_type=NotificationType.COMMAND_EXECUTION_FAILED,
                    source=NotificationSource(
                        component="hydra-api", service="commands", node_id=node_id
                    ),
                    title="Command failed",
                    message=f"Command {command_id} failed on {node_id}: {result.error or 'unknown error'}",
                    details={
                        "commandId": command_id,
                        "nodeId": node_id,
                        "exitCode": result.exit_code,
                        "error": result.error,
                    },
                    audit_entry_id=audit_id,
                )
            )

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
            safe_create_task(
                emit_notification(
                    notification_type=NotificationType.COMMAND_EXECUTION_TIMEOUT,
                    source=NotificationSource(component="hydra-api", service="commands"),
                    title="Commands timed out",
                    message=f"{result.modified_count} command(s) timed out after {timeout_minutes} minutes",
                    details={"count": result.modified_count, "timeoutMinutes": timeout_minutes},
                    audit_entry_id=audit_id,
                )
            )

        return result.modified_count
