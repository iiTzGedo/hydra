"""Commands service for command queue management and execution tracking."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import structlog
from pymongo import ReturnDocument

from hydra.api.v1.core.exceptions import (
    CommandAlreadyExecutingError,
    CommandConfirmationExpiredError,
    CommandConfirmationInvalidError,
    CommandCooldownError,
    CommandMaxRetriesError,
    CommandNodeMismatchError,
    CommandNotCancellableError,
    CommandNotFoundError,
    CommandNotRetriableError,
    CommandNotSupportedError,
    CommandRateLimitError,
    CommandRegistryNotFoundError,
    CommandRejectedError,
    NodeNotFoundError,
    ValidationError,
)
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.auth import get_role_level
from hydra.api.v1.models.commands import (
    CommandDeliveryMode,
    CommandListParams,
    CommandSource,
    CommandStatus,
    CreateCommandRequest,
    SubmitCommandResultRequest,
)
from hydra.api.v1.models.notifications import NotificationSource, NotificationType
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

# Maximum consecutive direct-call failures before marking agent unreachable
MAX_DIRECT_FAILURES = 3

logger = structlog.get_logger(__name__)


class CommandsService:
    """Service for managing command execution queue."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb
        self.commands = mongodb.commands
        self.nodes = mongodb.nodes
        self.services = mongodb.services
        self.command_definitions = mongodb.command_definitions

    async def _emit_command_event(
        self, command: dict[str, Any], event_type: str
    ) -> None:
        """Publish a command lifecycle event for real-time subscribers.

        Best-effort: failures (e.g. Redis unavailable) are swallowed so command
        execution is never blocked by the events transport.
        """
        try:
            from hydra.api.v1.services.events import publish_command_event
            from hydra.db.redis import get_redis

            target = command.get("target") or {}
            await publish_command_event(
                get_redis(),
                command.get("commandId", ""),
                event_type,
                {
                    "commandId": command.get("commandId"),
                    "status": command.get("status"),
                    "nodeId": target.get("nodeId"),
                    "serviceId": target.get("serviceId"),
                    "registryId": command.get("registryId"),
                },
            )
        except Exception:  # pragma: no cover - transport failures are non-fatal
            logger.debug("command_event_emit_failed", exc_info=True)

    @staticmethod
    def _has_permission(user_permissions: list[str], required: str) -> bool:
        """Check if user permissions satisfy the required permission.

        Replicates the wildcard logic from deps.require_permission.
        """
        if "*:*" in user_permissions:
            return True
        if required in user_permissions:
            return True
        resource, action = required.split(":", 1) if ":" in required else (required, "*")
        return f"{resource}:*" in user_permissions

    @staticmethod
    def _write_origin_allowed(source: CommandSource, client_id: str | None) -> bool:
        """Allow command writes only from trusted Hydra web origins."""
        if source == CommandSource.WEB:
            return True
        return source == CommandSource.API and client_id == "hydra-api"

    async def _enforce_submission_policy(
        self,
        *,
        request: CreateCommandRequest | None,
        definition: dict[str, Any],
        user_id: str | None,
        user_role: str | None,
        user_permissions: list[str] | None,
        source: CommandSource,
        client_id: str | None,
        persist_rejection: bool,
    ) -> None:
        """Apply source restriction and RBAC checks for command submission."""
        if not self._write_origin_allowed(source, client_id):
            error_message = (
                "Command execution is only available from the Hydra web interface"
            )
            if persist_rejection and request is not None:
                await self._create_rejected_command(
                    request,
                    user_id,
                    source,
                    client_id,
                    error_code="CLIENT_NOT_AUTHORIZED",
                    error_message=error_message,
                )
            raise CommandRejectedError(error_message)

        minimum_role = definition.get("rbac", {}).get("minimumRole", "operator")
        if get_role_level(user_role or "") < get_role_level(minimum_role):
            error_message = (
                f"Role '{user_role or 'unknown'}' insufficient for "
                f"'{definition.get('registryId')}' (requires '{minimum_role}')"
            )
            if persist_rejection and request is not None:
                await self._create_rejected_command(
                    request,
                    user_id,
                    source,
                    client_id,
                    error_code="INSUFFICIENT_ROLE",
                    error_message=error_message,
                )
            raise CommandRejectedError(error_message)

        control_permission = definition.get("rbac", {}).get("controlPermission")
        if control_permission and (
            not user_permissions or not self._has_permission(
                user_permissions,
                control_permission,
            )
        ):
            error_message = (
                f"Missing permission '{control_permission}' for "
                f"'{definition.get('registryId')}'"
            )
            if persist_rejection and request is not None:
                await self._create_rejected_command(
                    request,
                    user_id,
                    source,
                    client_id,
                    error_code="MISSING_CONTROL_PERMISSION",
                    error_message=error_message,
                )
            raise CommandRejectedError(error_message)

    @staticmethod
    def _estimate_delivery_mode(tier: str, delivery_mode: str) -> str:
        """Estimate the effective execution mode for dry-run previews."""
        if tier == "lite":
            return "rejected"
        if tier == "max" and delivery_mode == CommandDeliveryMode.DIRECT_OR_POLL.value:
            return "direct"
        return "poll"

    async def _prepare_command_submission(
        self,
        request: CreateCommandRequest,
        *,
        user_id: str | None,
        user_role: str | None,
        user_permissions: list[str] | None,
        source: CommandSource,
        client_id: str | None,
        persist_rejection: bool,
        allow_policy_failure: bool = False,
    ) -> dict[str, Any]:
        """Build the shared, non-mutating execution context for a command."""
        definition = await self.command_definitions.find_one(
            {"registryId": request.registry_id}
        )
        if not definition:
            if persist_rejection:
                await self._create_rejected_command(
                    request,
                    user_id,
                    source,
                    client_id,
                    error_code="REGISTRY_NOT_FOUND",
                    error_message=(
                        f"Command '{request.registry_id}' is not registered in the catalog"
                    ),
                )
            raise CommandRegistryNotFoundError(request.registry_id)

        permission_check_passed = True
        try:
            await self._enforce_submission_policy(
                request=request,
                definition=definition,
                user_id=user_id,
                user_role=user_role,
                user_permissions=user_permissions,
                source=source,
                client_id=client_id,
                persist_rejection=persist_rejection,
            )
        except CommandRejectedError:
            if not allow_policy_failure:
                raise
            permission_check_passed = False

        node = await self.nodes.find_one(
            {"nodeId": request.target.node_id, "status": "active"}
        )
        if not node:
            raise NodeNotFoundError(request.target.node_id)

        tier = node.get("agentTier", "normal")
        category = definition.get("category", "custom")
        action = definition.get("action", request.registry_id.split("::")[-1])
        dispatch_parameters = dict(request.parameters or {})

        if category == "service":
            dispatch_parameters = await self._normalize_service_parameters(
                request, action, dispatch_parameters
            )

        timeout = request.timeout_seconds or definition.get("execution", {}).get("timeout", 60)
        delivery_mode = definition.get("execution", {}).get(
            "deliveryMode",
            CommandDeliveryMode.POLL_ONLY.value,
        )
        requires_confirmation = definition.get("rbac", {}).get(
            "requiresConfirmation", False
        )
        danger_level = definition.get("rbac", {}).get("dangerLevel", "medium")

        return {
            "definition": definition,
            "node": node,
            "tier": tier,
            "category": category,
            "action": action,
            "dispatch_parameters": dispatch_parameters,
            "timeout": timeout,
            "delivery_mode": delivery_mode,
            "requires_confirmation": requires_confirmation,
            "danger_level": danger_level,
            "permission_check_passed": permission_check_passed,
        }

    async def create_command(
        self,
        request: CreateCommandRequest,
        user_id: str | None = None,
        user_role: str | None = None,
        user_permissions: list[str] | None = None,
        source: CommandSource = CommandSource.API,
        client_id: str | None = None,
        chain: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a command with registry validation and tier-aware dispatch.

        1. Validate registryId against the command catalog
        2. Check RBAC minimumRole and controlPermission against user role/permissions
        3. Tier-aware dispatch: lite rejects, normal queues, max tries direct

        Args:
            request: Command creation payload with registryId, target, and parameters.
            user_id: The requesting user's identifier (None for system commands).
            user_role: The requesting user's role (for RBAC validation).
            user_permissions: The requesting user's permission list.
            source: The command source (API, MCP, etc.).
            client_id: The originating client identifier (e.g., 'hydra-web', 'claude-desktop').

        Returns:
            The created command document.

        Raises:
            CommandRegistryNotFoundError: If the registryId is not in the catalog.
            CommandRejectedError: If the user lacks the required role or permission.
            NodeNotFoundError: If the target node does not exist or is not active.
            CommandNotSupportedError: If the agent tier does not support commands.
        """
        prepared = await self._prepare_command_submission(
            request,
            user_id=user_id,
            user_role=user_role,
            user_permissions=user_permissions,
            source=source,
            client_id=client_id,
            persist_rejection=True,
        )
        definition = prepared["definition"]
        node = prepared["node"]
        tier = prepared["tier"]
        category = prepared["category"]
        action = prepared["action"]
        dispatch_parameters = prepared["dispatch_parameters"]
        timeout = prepared["timeout"]
        delivery_mode = prepared["delivery_mode"]
        requires_confirmation = prepared["requires_confirmation"]
        danger_level = prepared["danger_level"]

        # Lite tier: reject
        if tier == "lite":
            raise CommandNotSupportedError(
                f"Agent tier 'lite' on node '{request.target.node_id}' does not support "
                f"command execution. Upgrade to 'normal' or 'max' tier."
            )

        # Step 3: Rate limiting
        await self._check_rate_limits(user_id, request.target.node_id, definition)

        # Step 3b: Plugin execution resolution
        from hydra.api.v1.services.plugins.resolver import PluginResolver

        plugin_resolver = PluginResolver(self.mongodb)
        plugin_path = await plugin_resolver.resolve_execution_path(
            request.registry_id, request.target.node_id
        )
        if plugin_path is not None:
            logger.info(
                "plugin_execution_path_resolved",
                registry_id=request.registry_id,
                node_id=request.target.node_id,
                plugin_path=plugin_path.value,
            )

        # Step 4: Two-phase confirmation for dangerous commands
        if requires_confirmation:
            return await self._create_pending_confirmation(
                request, definition, category, action, timeout,
                dispatch_parameters, user_id, source, client_id, chain,
                danger_level,
            )

        # Max tier: only direct-execute duplicate-safe commands
        if tier == "max" and delivery_mode == CommandDeliveryMode.DIRECT_OR_POLL.value:
            direct_result = await self._try_direct_execution(
                node,
                request,
                definition,
                category,
                action,
                timeout,
                dispatch_parameters,
                user_id,
                source,
                client_id,
                chain,
            )
            if direct_result is not None:
                if plugin_path is not None:
                    await self._store_plugin_context(direct_result, plugin_path)
                return direct_result

        # Normal tier or max-tier fallback: queue for poll-based execution
        result = await self._queue_command(
            request,
            definition,
            category,
            action,
            timeout,
            dispatch_parameters,
            user_id,
            source,
            client_id,
            chain,
        )
        if plugin_path is not None:
            await self._store_plugin_context(result, plugin_path)
        return result

    async def dry_run_command(
        self,
        request: CreateCommandRequest,
        user_id: str | None = None,
        user_role: str | None = None,
        user_permissions: list[str] | None = None,
        source: CommandSource = CommandSource.API,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        """Preview a command without executing it.

        Validates the full pipeline (registry, RBAC, node, rate limits, cooldown)
        but does NOT persist a command record, dispatch to agents, increment
        rate-limit counters, set cooldowns, or emit audit logs.

        Returns a dict matching DryRunResponse fields.
        """
        from hydra.api.v1.models.commands.responses import DryRunResponse

        prepared = await self._prepare_command_submission(
            request,
            user_id=user_id,
            user_role=user_role,
            user_permissions=user_permissions,
            source=source,
            client_id=client_id,
            persist_rejection=False,
            allow_policy_failure=True,
        )
        definition = prepared["definition"]
        tier = prepared["tier"]

        # Step 1: Check rate limits (peek, do NOT increment)
        rate_limit_ok = await self._peek_rate_limits(
            user_id, request.target.node_id, definition
        )

        # Step 2: Check cooldown (peek, do NOT set)
        cooldown_ok = await self._peek_cooldown(
            request.target.node_id, definition
        )

        estimated_delivery = self._estimate_delivery_mode(
            tier, prepared["delivery_mode"]
        )

        return DryRunResponse(
            would_require_confirmation=prepared["requires_confirmation"],
            estimated_delivery_mode=estimated_delivery,
            target_node_tier=tier,
            permission_check_passed=prepared["permission_check_passed"],
            rate_limit_ok=rate_limit_ok,
            cooldown_ok=cooldown_ok,
            danger_level=prepared["danger_level"],
            registry_id=request.registry_id,
            target_node_id=request.target.node_id,
        ).model_dump(by_alias=True)

    async def _peek_rate_limits(
        self, user_id: str | None, node_id: str, definition: dict[str, Any]
    ) -> bool:
        """Check rate-limit counters without incrementing them.

        Returns True if all limits would allow the request, False otherwise.
        """
        try:
            from hydra.core.config import get_settings
            from hydra.db.redis import get_redis

            redis = get_redis()
            settings = get_settings()
            danger_level = definition.get("rbac", {}).get("dangerLevel", "medium")

            # Per-user rate limit peek
            if user_id:
                full_key = f"{redis.RATE_LIMIT_PREFIX}cmd:user:{user_id}"
                current = await redis.client.get(full_key)
                if current is not None and int(current) >= settings.command_rate_limit_per_user:
                    return False

            # Per-node rate limit peek
            full_key = f"{redis.RATE_LIMIT_PREFIX}cmd:node:{node_id}"
            current = await redis.client.get(full_key)
            if current is not None and int(current) >= settings.command_rate_limit_per_node:
                return False

            # Destructive command rate limit peek
            if danger_level in ("high", "critical") and user_id:
                full_key = f"{redis.RATE_LIMIT_PREFIX}cmd:destructive:user:{user_id}"
                current = await redis.client.get(full_key)
                if current is not None and int(current) >= settings.command_rate_limit_destructive_per_user:
                    return False

            return True
        except Exception:
            logger.warning("dry_run_rate_limit_peek_failed", reason="redis unavailable")
            return False

    async def _peek_cooldown(
        self, node_id: str, definition: dict[str, Any]
    ) -> bool:
        """Check cooldown status without setting a new cooldown.

        Returns True if no active cooldown, False otherwise.
        """
        danger_level = definition.get("rbac", {}).get("dangerLevel", "medium")
        if danger_level not in ("high", "critical"):
            return True

        try:
            from hydra.db.redis import get_redis

            redis = get_redis()
            cooldown_key = f"cmd:cooldown:{node_id}"
            ttl = int(await redis.client.ttl(cooldown_key))
            return ttl <= 0
        except Exception:
            logger.warning("dry_run_cooldown_peek_failed", reason="redis unavailable")
            return False

    async def _create_rejected_command(
        self,
        request: CreateCommandRequest,
        user_id: str | None,
        source: CommandSource,
        client_id: str | None = None,
        *,
        error_code: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Persist a rejected command for audit trail."""
        command_id = f"cmd-{uuid4().hex[:12]}"
        now = datetime.now(UTC)

        command_doc = {
            "commandId": command_id,
            "registryId": request.registry_id,
            "type": "unknown",
            "target": {
                "nodeId": request.target.node_id,
                "serviceId": request.target.service_id,
            },
            "action": request.registry_id.split("::")[-1] if "::" in request.registry_id else request.registry_id,
            "parameters": request.parameters or {},
            "status": CommandStatus.REJECTED.value,
            "executionMethod": None,
            "result": None,
            "error": {
                "code": error_code,
                "message": error_message,
            },
            "requestedBy": {
                "userId": user_id,
                "source": source.value,
                "clientId": client_id,
            },
            "timeoutSeconds": request.timeout_seconds or 60,
            "retryCount": 0,
            "maxRetries": 0,
            "retriedFrom": None,
            "chain": None,
            "createdAt": now,
            "queuedAt": None,
            "startedAt": None,
            "completedAt": now,
            "cancelledAt": None,
            "cancelledBy": None,
        }

        await self.commands.insert_one(command_doc)

        logger.info(
            "command_rejected",
            command_id=command_id,
            registry_id=request.registry_id,
            error_code=error_code,
        )

        # Audit log the rejection (security-relevant event)
        safe_create_task(
            log_audit(
                action=AuditAction.EXECUTE,
                resource_type="command",
                resource_id=command_id,
                actor_type="user",
                actor_id=user_id or "unknown",
                success=False,
                details={"registryId": request.registry_id, "errorCode": error_code},
                error=error_message,
            )
        )

        return command_doc

    async def _store_plugin_context(
        self,
        command_doc: dict[str, Any],
        plugin_path: Any,
    ) -> None:
        """Store plugin execution context on an existing command document.

        Args:
            command_doc: The command document to annotate (mutated in place).
            plugin_path: An ExecutionPathType enum value from the plugin resolver.
        """
        command_id = command_doc.get("commandId")
        if command_id:
            await self.commands.update_one(
                {"commandId": command_id},
                {"$set": {"executionContext.pluginPath": plugin_path.value}},
            )
            command_doc.setdefault("executionContext", {})["pluginPath"] = plugin_path.value

    async def _queue_command(
        self,
        request: CreateCommandRequest,
        _definition: dict[str, Any],
        category: str,
        action: str,
        timeout: int,
        dispatch_parameters: dict[str, Any],
        user_id: str | None,
        source: CommandSource,
        client_id: str | None = None,
        chain: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Queue a command for poll-based execution by the agent."""
        command_id = f"cmd-{uuid4().hex[:12]}"
        now = datetime.now(UTC)

        # Compute queue position
        queue_count = await self.commands.count_documents({
            "target.nodeId": request.target.node_id,
            "status": CommandStatus.QUEUED.value,
        })

        command_doc = {
            "commandId": command_id,
            "registryId": request.registry_id,
            "type": category,
            "target": {
                "nodeId": request.target.node_id,
                "serviceId": request.target.service_id,
            },
            "action": action,
            "parameters": dispatch_parameters,
            "status": CommandStatus.QUEUED.value,
            "executionMethod": "agent-poll",
            "result": None,
            "error": None,
            "requestedBy": {
                "userId": user_id,
                "source": source.value,
                "clientId": client_id,
            },
            "timeoutSeconds": timeout,
            "retryCount": 0,
            "maxRetries": _definition.get("execution", {}).get("maxRetries", 0),
            "retriedFrom": None,
            "queuePosition": queue_count + 1,
            "chain": chain,
            "createdAt": now,
            "queuedAt": now,
            "startedAt": None,
            "completedAt": None,
            "cancelledAt": None,
            "cancelledBy": None,
        }

        await self.commands.insert_one(command_doc)

        logger.info(
            "command_queued",
            command_id=command_id,
            registry_id=request.registry_id,
            type=category,
            target_node=request.target.node_id,
            action=action,
            execution_method="agent-poll",
        )

        await self._emit_command_event(command_doc, "command.created")

        return command_doc

    async def _try_direct_execution(
        self,
        node: dict[str, Any],
        request: CreateCommandRequest,
        _definition: dict[str, Any],
        category: str,
        action: str,
        timeout: int,
        dispatch_parameters: dict[str, Any],
        user_id: str | None,
        source: CommandSource,
        client_id: str | None = None,
        chain: dict[str, Any] | None = None,
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
            "registryId": request.registry_id,
            "target": {
                "nodeId": request.target.node_id,
                "serviceId": request.target.service_id,
            },
            "parameters": dispatch_parameters,
            "timeoutSeconds": timeout,
        }

        scheme = "https" if server_tls_enabled else "http"
        base_url = f"{scheme}://{server_address}:{server_port}"

        try:
            from hydra.core.config import get_settings

            settings = get_settings()
            async with httpx.AsyncClient(
                timeout=min(timeout, 30),
                verify=settings.agent_tls_verify,
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
                    "data": agent_result.get("result", {}).get("data")
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
                    "registryId": request.registry_id,
                    "type": category,
                    "target": {
                        "nodeId": request.target.node_id,
                        "serviceId": request.target.service_id,
                    },
                    "action": action,
                    "parameters": dispatch_parameters,
                    "status": final_status,
                    "executionMethod": "agent-direct",
                    "result": result_doc,
                    "error": None,
                    "requestedBy": {
                        "userId": user_id,
                        "source": source.value,
                        "clientId": client_id,
                    },
                    "timeoutSeconds": timeout,
                    "retryCount": 0,
                    "maxRetries": _definition.get("execution", {}).get("maxRetries", 0),
                    "retriedFrom": None,
                    "queuePosition": None,
                    "chain": chain,
                    "createdAt": now,
                    "queuedAt": None,
                    "startedAt": now,
                    "completedAt": datetime.now(UTC),
                    "cancelledAt": None,
                    "cancelledBy": None,
                }

                await self.commands.insert_one(command_doc)

                logger.info(
                    "command_executed_direct",
                    command_id=command_id,
                    node_id=node_id,
                    success=result_doc["success"],
                )

                await self._emit_command_event(command_doc, "command.completed")

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

    async def _normalize_service_parameters(
        self,
        request: CreateCommandRequest,
        action: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve a serviceId into the canonical execution parameters."""
        service_id = request.target.service_id
        if not service_id:
            raise ValidationError("Service commands require target.serviceId")

        service = await self.services.find_one({"serviceId": service_id})
        if not service:
            raise ValidationError(
                f"Service '{service_id}' was not found for command execution",
                details={"serviceId": service_id},
            )

        actual_node_id = service.get("nodeId")
        if actual_node_id != request.target.node_id:
            raise ValidationError(
                (
                    f"Service '{service_id}' belongs to node '{actual_node_id}', "
                    f"not '{request.target.node_id}'"
                ),
                details={
                    "serviceId": service_id,
                    "expectedNodeId": actual_node_id,
                    "targetNodeId": request.target.node_id,
                },
            )

        normalized = dict(parameters)
        normalized["serviceId"] = service_id
        normalized["name"] = service["name"]
        normalized["runtime"] = service.get("runtime", "systemd")

        image = service.get("image")
        if image:
            normalized["image"] = image

        if action == "update":
            runtime = normalized["runtime"]
            if runtime not in {"docker", "podman"}:
                raise ValidationError(
                    f"Service updates are only supported for docker or podman runtimes, not '{runtime}'",
                    details={"runtime": runtime, "serviceId": service_id},
                )
            if not image:
                raise ValidationError(
                    "Service update requires image metadata on the target service",
                    details={"serviceId": service_id},
                )

            version = normalized.get("version")
            if version:
                normalized["image"] = self._build_versioned_image(image, str(version))

        return normalized

    def _build_versioned_image(self, image: str, version: str) -> str:
        """Replace the tag on a container image while preserving registry paths."""
        if "@" in image:
            raise ValidationError(
                "Cannot override version for digest-pinned images",
                details={"image": image},
            )

        last_slash = image.rfind("/")
        last_colon = image.rfind(":")
        if last_colon <= last_slash:
            raise ValidationError(
                "Cannot override version for tagless images",
                details={"image": image},
            )

        return f"{image[:last_colon]}:{version}"

    async def get_command(self, command_id: str) -> dict[str, Any]:
        """Get a command by its identifier."""
        command = await self.commands.find_one({"commandId": command_id})
        if not command:
            raise CommandNotFoundError(command_id)
        return command  # type: ignore[no-any-return]

    async def list_commands(self, params: CommandListParams) -> tuple[list[dict[str, Any]], int]:
        """List commands with optional filtering and pagination."""
        query: dict[str, Any] = {}

        if params.node_id:
            query["target.nodeId"] = params.node_id
        if params.service_id:
            query["target.serviceId"] = params.service_id
        if params.registry_id:
            query["registryId"] = params.registry_id
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

    async def cancel_command(
        self,
        command_id: str,
        cancelled_by: str | None = None,
        confirm_cascade: bool = False,
    ) -> dict[str, Any]:
        """Cancel a pending or queued command.

        Args:
            command_id: The command identifier.
            cancelled_by: User ID of who cancelled the command.
            confirm_cascade: If True, also cancel sibling commands in the same chain.

        Returns:
            Dict with command_id, status, cancelled_at, cancelled_by,
            and cascade_cancelled_ids (when cascade was applied).

        Raises:
            CommandNotFoundError: If the command does not exist.
            CommandNotCancellableError: If the command is already executing or completed.
        """
        command = await self.get_command(command_id)

        cancellable_statuses = [
            CommandStatus.PENDING.value,
            CommandStatus.PENDING_CONFIRMATION.value,
            CommandStatus.QUEUED.value,
        ]
        if command["status"] not in cancellable_statuses:
            raise CommandNotCancellableError(command_id, command["status"])

        now = datetime.now(UTC)

        await self.commands.update_one(
            {"commandId": command_id},
            {
                "$set": {
                    "status": CommandStatus.CANCELLED.value,
                    "completedAt": now,
                    "cancelledAt": now,
                    "cancelledBy": cancelled_by,
                }
            },
        )

        logger.info("command_cancelled", command_id=command_id, cancelled_by=cancelled_by)

        command["status"] = CommandStatus.CANCELLED.value
        await self._emit_command_event(command, "command.status_changed")

        # Cascade cancel sibling commands in the same chain.
        cascade_cancelled_ids: list[str] | None = None
        chain = command.get("chain")
        if confirm_cascade and chain and chain.get("chainId"):
            chain_id = chain["chainId"]
            siblings = self.commands.find(
                {
                    "chain.chainId": chain_id,
                    "commandId": {"$ne": command_id},
                    "status": {"$in": cancellable_statuses},
                },
                projection={"commandId": 1},
            )
            cascade_cancelled_ids = []
            async for sibling in siblings:
                sibling_id = sibling["commandId"]
                await self.commands.update_one(
                    {"commandId": sibling_id},
                    {
                        "$set": {
                            "status": CommandStatus.CANCELLED.value,
                            "completedAt": now,
                            "cancelledAt": now,
                            "cancelledBy": cancelled_by,
                        }
                    },
                )
                cascade_cancelled_ids.append(sibling_id)
                await self._emit_command_event(
                    {
                        "commandId": sibling_id,
                        "status": CommandStatus.CANCELLED.value,
                        "target": sibling.get("target", {}),
                        "registryId": sibling.get("registryId"),
                    },
                    "command.status_changed",
                )

            if cascade_cancelled_ids:
                logger.info(
                    "cascade_cancelled",
                    chain_id=chain_id,
                    cancelled_count=len(cascade_cancelled_ids),
                    cancelled_ids=cascade_cancelled_ids,
                )

        return {
            "commandId": command_id,
            "status": CommandStatus.CANCELLED.value,
            "cancelledAt": now,
            "cancelledBy": cancelled_by,
            "cascadeCancelledIds": cascade_cancelled_ids,
        }

    async def poll_commands(self, node_id: str) -> list[dict[str, Any]]:
        """Poll for pending commands for a specific node.

        Atomically claims queued commands to prevent duplicate execution by
        concurrent pollers. Used by agents to fetch work.
        """
        node = await self.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        # Update lastSeenAt and lastPollContact on every agent poll.
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
            if command.get("registryId") == "reg::agent::network-scan":
                from hydra.api.v1.services.discovery import DiscoveryService

                scan_id = command.get("parameters", {}).get("scanId")
                if isinstance(scan_id, str) and scan_id:
                    await DiscoveryService(self.mongodb).mark_delegated_scan_running(
                        scan_id
                    )
            commands.append(command)

        result = []
        for cmd in commands:
            result.append(
                {
                    "commandId": cmd["commandId"],
                    "registryId": cmd.get("registryId"),
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
        """Mark a command as executing."""
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
        await self._emit_command_event(command, "command.status_changed")
        return command

    async def submit_result(
        self,
        node_id: str,
        command_id: str,
        result: SubmitCommandResultRequest,
    ) -> dict[str, Any]:
        """Submit command execution result from an agent."""
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
            "data": result.data,
        }

        update_set: dict[str, Any] = {
            "status": final_status.value,
            "result": result_doc,
            "completedAt": now,
        }

        # If failed, also set structured error
        if not result.success:
            update_set["error"] = {
                "code": "EXECUTION_FAILED",
                "message": result.error or "Command execution failed",
                "details": {"exitCode": result.exit_code},
            }

        await self.commands.update_one(
            {"commandId": command_id},
            {"$set": update_set},
        )

        logger.info(
            "command_result_submitted",
            command_id=command_id,
            success=result.success,
            status=final_status.value,
        )

        command["status"] = final_status.value
        command["result"] = result_doc
        command["completedAt"] = now
        await self._emit_command_event(command, "command.completed")

        if command.get("registryId") == "reg::agent::network-scan":
            from hydra.api.v1.services.discovery import DiscoveryService

            await DiscoveryService(self.mongodb).handle_scan_command_result(
                command,
                result.success,
                result.data,
                result.error,
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
                        component="hydra-api", service="commands", node_id=node_id  # type: ignore[arg-type]
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
                        component="hydra-api", service="commands", node_id=node_id  # type: ignore[arg-type]
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

        # Schedule auto-retry if the command failed and is retryable
        if not result.success:
            safe_create_task(self._maybe_auto_retry(command))

        return {
            "commandId": command_id,
            "status": final_status.value,
            "completedAt": now,
        }

    async def get_queue_view(
        self, node_id: str | None = None
    ) -> dict[str, Any]:
        """Get current queue state with statistics.

        Args:
            node_id: Optional filter by target node.

        Returns:
            Dict with queue items and stats.
        """
        base_query: dict[str, Any] = {}
        if node_id:
            base_query["target.nodeId"] = node_id

        queued_query = {**base_query, "status": CommandStatus.QUEUED.value}
        executing_query = {**base_query, "status": CommandStatus.EXECUTING.value}

        total_queued = await self.commands.count_documents(queued_query)
        total_executing = await self.commands.count_documents(executing_query)

        # Get oldest queued command
        oldest = await self.commands.find_one(
            queued_query,
            sort=[("queuedAt", 1)],
        )
        oldest_queued_at = oldest["queuedAt"] if oldest else None

        # Get queue items (queued + executing)
        active_query = {
            **base_query,
            "status": {"$in": [CommandStatus.QUEUED.value, CommandStatus.EXECUTING.value]},
        }
        cursor = self.commands.find(active_query).sort("queuedAt", 1).limit(200)
        queue_items = await cursor.to_list(length=200)

        return {
            "queue": queue_items,
            "stats": {
                "totalQueued": total_queued,
                "totalExecuting": total_executing,
                "oldestQueuedAt": oldest_queued_at,
            },
        }

    async def flush_queue(
        self,
        scope: str,
        user_id: str | None = None,
    ) -> int:
        """Flush (cancel) queued commands.

        Args:
            scope: 'all', 'node:<nodeId>', or 'user:<userId>'.
            user_id: The user performing the flush.

        Returns:
            Number of commands flushed.
        """
        query: dict[str, Any] = {"status": CommandStatus.QUEUED.value}

        if scope.startswith("node:"):
            query["target.nodeId"] = scope[5:]
        elif scope.startswith("user:"):
            query["requestedBy.userId"] = scope[5:]

        now = datetime.now(UTC)

        result = await self.commands.update_many(
            query,
            {
                "$set": {
                    "status": CommandStatus.CANCELLED.value,
                    "completedAt": now,
                    "cancelledAt": now,
                    "cancelledBy": user_id,
                }
            },
        )

        if result.modified_count > 0:
            logger.info(
                "queue_flushed",
                scope=scope,
                flushed_count=result.modified_count,
                flushed_by=user_id,
            )
            await log_audit(
                action=AuditAction.DELETE,
                resource_type="command_queue",
                resource_id=scope,
                actor_type="user",
                actor_id=user_id or "unknown",
                success=True,
                details={"scope": scope, "flushedCount": result.modified_count},
            )

        return result.modified_count

    async def timeout_stale_commands(self, timeout_minutes: int = 10) -> int:
        """Mark stale executing commands as timed out and expire pending confirmations."""
        # Expire unconfirmed commands
        now = datetime.now(UTC)
        expired = await self.commands.update_many(
            {
                "status": CommandStatus.PENDING_CONFIRMATION.value,
                "confirmationExpiresAt": {"$lt": now},
            },
            {
                "$set": {
                    "status": CommandStatus.CANCELLED.value,
                    "completedAt": now,
                    "cancelledAt": now,
                    "cancelledBy": "system:confirmation_expired",
                }
            },
        )
        if expired.modified_count > 0:
            logger.info("confirmations_expired", count=expired.modified_count)

        cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)

        # Capture timed-out commands before marking them, so we can send cancel
        # signals to nodes that support direct execution.
        stale_query = {
            "status": CommandStatus.EXECUTING.value,
            "startedAt": {"$lt": cutoff},
        }
        stale_commands: list[dict[str, Any]] = await self.commands.find(
            stale_query,
            projection={"commandId": 1, "target.nodeId": 1},
        ).to_list(length=500)

        result = await self.commands.update_many(
            stale_query,
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
                    "error": {
                        "code": "EXECUTION_TIMEOUT",
                        "message": "Command execution timed out",
                        "details": {"timeoutMinutes": timeout_minutes},
                    },
                }
            },
        )

        if result.modified_count > 0:
            logger.info("commands_timed_out", count=result.modified_count)

            # Fire cancel signals to max-tier nodes (best-effort, async).
            for cmd in stale_commands:
                node_id = cmd.get("target", {}).get("nodeId")
                command_id = cmd.get("commandId")
                if node_id and command_id:
                    safe_create_task(
                        self._send_timeout_cancel_signal(node_id, command_id)
                    )
                    safe_create_task(
                        self._emit_command_event(
                            {
                                "commandId": command_id,
                                "status": CommandStatus.TIMEOUT.value,
                                "target": cmd.get("target", {}),
                            },
                            "command.completed",
                        )
                    )

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
                    source=NotificationSource(component="hydra-api", service="commands"),  # type: ignore[arg-type]
                    title="Commands timed out",
                    message=f"{result.modified_count} command(s) timed out after {timeout_minutes} minutes",
                    details={"count": result.modified_count, "timeoutMinutes": timeout_minutes},
                    audit_entry_id=audit_id,
                )
            )

        return result.modified_count

    async def _send_timeout_cancel_signal(
        self, node_id: str, command_id: str
    ) -> None:
        """Send a cancel signal to a max-tier node's agent server (best-effort).

        For poll-only nodes, the agent will see the TIMEOUT status on next poll.
        For direct-execution nodes, we attempt an HTTP POST to abort immediately.
        """
        try:
            node = await self.nodes.find_one({"nodeId": node_id})
            if not node:
                return

            server_address = node.get("serverAddress")
            server_port = node.get("serverPort", 9100)
            server_secret = node.get("agentServerSecret")

            if not server_address or not server_secret:
                return  # Poll-only node; agent picks up TIMEOUT on next poll.

            import httpx

            scheme = "https" if node.get("serverTlsEnabled") else "http"
            url = f"{scheme}://{server_address}:{server_port}/cancel"

            async with httpx.AsyncClient(timeout=5.0, verify=False) as http:  # noqa: S501
                await http.post(
                    url,
                    json={"commandId": command_id, "reason": "timeout"},
                    headers={"Authorization": f"Bearer {server_secret}"},
                )

            logger.info(
                "timeout_cancel_signal_sent",
                node_id=node_id,
                command_id=command_id,
            )
        except Exception as exc:
            logger.debug(
                "timeout_cancel_signal_failed",
                node_id=node_id,
                command_id=command_id,
                error=str(exc),
            )

    # ── Safety controls (P2C-002) ───────────────────────────────────────

    async def _check_rate_limits(
        self, user_id: str | None, node_id: str, definition: dict[str, Any]
    ) -> None:
        """Check command rate limits using Redis counters.

        Raises CommandRateLimitError if any limit is exceeded.
        Silently skips if Redis is unavailable (fail-open for availability).
        """
        try:
            from hydra.core.config import get_settings
            from hydra.db.redis import get_redis

            redis = get_redis()
            settings = get_settings()
            danger_level = definition.get("rbac", {}).get("dangerLevel", "medium")

            # Per-user rate limit
            if user_id:
                allowed = await redis.rate_limit_check(
                    f"cmd:user:{user_id}",
                    settings.command_rate_limit_per_user,
                    settings.command_rate_limit_per_user_window,
                )
                if not allowed:
                    raise CommandRateLimitError(
                        "per_user", settings.command_rate_limit_per_user_window
                    )

            # Per-node rate limit
            allowed = await redis.rate_limit_check(
                f"cmd:node:{node_id}",
                settings.command_rate_limit_per_node,
                settings.command_rate_limit_per_node_window,
            )
            if not allowed:
                raise CommandRateLimitError(
                    "per_node", settings.command_rate_limit_per_node_window
                )

            # Destructive command rate limit (high/critical danger)
            if danger_level in ("high", "critical") and user_id:
                allowed = await redis.rate_limit_check(
                    f"cmd:destructive:user:{user_id}",
                    settings.command_rate_limit_destructive_per_user,
                    settings.command_rate_limit_destructive_window,
                )
                if not allowed:
                    raise CommandRateLimitError(
                        "destructive_per_user",
                        settings.command_rate_limit_destructive_window,
                    )
        except CommandRateLimitError:
            raise
        except Exception:
            logger.warning("rate_limit_check_skipped", reason="redis unavailable")

    async def _check_cooldown(self, node_id: str, danger_level: str) -> None:
        """Check if node is in cooldown from a previous destructive command."""
        if danger_level not in ("high", "critical"):
            return

        try:
            from hydra.db.redis import get_redis
            redis = get_redis()
            cooldown_key = f"cmd:cooldown:{node_id}"
            ttl = await redis.client.ttl(cooldown_key)
            if ttl > 0:
                raise CommandCooldownError(node_id, ttl)
        except CommandCooldownError:
            raise
        except Exception:
            logger.warning("cooldown_check_skipped", reason="redis unavailable")

    async def _set_cooldown(self, node_id: str, danger_level: str) -> None:
        """Set cooldown after a destructive command is dispatched."""
        if danger_level not in ("high", "critical"):
            return

        try:
            from hydra.core.config import get_settings
            from hydra.db.redis import get_redis
            redis = get_redis()
            settings = get_settings()
            cooldown_key = f"cmd:cooldown:{node_id}"
            await redis.client.setex(
                cooldown_key,
                settings.command_cooldown_destructive_seconds,
                "1",
            )
        except Exception:
            logger.warning("cooldown_set_failed", node_id=node_id)

    async def _create_pending_confirmation(
        self,
        request: CreateCommandRequest,
        definition: dict[str, Any],
        category: str,
        action: str,
        timeout: int,
        dispatch_parameters: dict[str, Any],
        user_id: str | None,
        source: CommandSource,
        client_id: str | None,
        chain: dict[str, Any] | None,
        danger_level: str,
    ) -> dict[str, Any]:
        """Create a command in pending_confirmation state for two-phase execution."""
        from hydra.core.config import get_settings
        settings = get_settings()

        command_id = f"cmd-{uuid4().hex[:12]}"
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=settings.command_confirmation_window_seconds)
        confirmation_message = definition.get("rbac", {}).get(
            "confirmationMessage",
            f"Please confirm execution of '{action}' on '{request.target.node_id}'.",
        )

        command_doc = {
            "commandId": command_id,
            "registryId": request.registry_id,
            "type": category,
            "target": {
                "nodeId": request.target.node_id,
                "serviceId": request.target.service_id,
            },
            "action": action,
            "parameters": dispatch_parameters,
            "status": CommandStatus.PENDING_CONFIRMATION.value,
            "executionMethod": None,
            "result": None,
            "error": None,
            "requestedBy": {
                "userId": user_id,
                "source": source.value,
                "clientId": client_id,
            },
            "timeoutSeconds": timeout,
            "retryCount": 0,
            "maxRetries": definition.get("execution", {}).get("maxRetries", 0),
            "retriedFrom": None,
            "chain": chain,
            "dangerLevel": danger_level,
            "confirmationExpiresAt": expires_at,
            "confirmationMessage": confirmation_message,
            "affectedNodes": [request.target.node_id],
            "createdAt": now,
            "queuedAt": None,
            "startedAt": None,
            "completedAt": None,
            "cancelledAt": None,
            "cancelledBy": None,
        }

        await self.commands.insert_one(command_doc)

        logger.info(
            "command_pending_confirmation",
            command_id=command_id,
            registry_id=request.registry_id,
            danger_level=danger_level,
            expires_at=expires_at.isoformat(),
        )

        return command_doc

    async def confirm_command(
        self,
        command_id: str,
        user_id: str | None = None,
        user_role: str | None = None,
        user_permissions: list[str] | None = None,
        source: CommandSource = CommandSource.API,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        """Confirm a pending command and dispatch it for execution.

        Validates the command is in pending_confirmation state, checks expiration
        and cooldown, then transitions to queued.
        """
        command = await self.get_command(command_id)

        if command["status"] != CommandStatus.PENDING_CONFIRMATION.value:
            raise CommandConfirmationInvalidError(command_id, command["status"])

        if command.get("requestedBy", {}).get("userId") != user_id:
            raise CommandRejectedError(
                "Only the user who requested this command may confirm it"
            )

        definition = await self.command_definitions.find_one(
            {"registryId": command.get("registryId")}
        )
        if not definition:
            raise CommandRegistryNotFoundError(command.get("registryId", "unknown"))

        confirmation_request = CreateCommandRequest(
            registry_id=command["registryId"],
            target={  # type: ignore[arg-type]
                "nodeId": command["target"]["nodeId"],
                "serviceId": command["target"].get("serviceId"),
            },
            parameters=command.get("parameters"),
            timeout_seconds=command.get("timeoutSeconds"),
        )

        await self._enforce_submission_policy(
            request=confirmation_request,
            definition=definition,
            user_id=user_id,
            user_role=user_role,
            user_permissions=user_permissions,
            source=source,
            client_id=client_id,
            persist_rejection=False,
        )

        # Check expiration
        expires_at = command.get("confirmationExpiresAt")
        if expires_at and datetime.now(UTC) > expires_at:
            now = datetime.now(UTC)
            await self.commands.update_one(
                {"commandId": command_id},
                {
                    "$set": {
                        "status": CommandStatus.CANCELLED.value,
                        "completedAt": now,
                        "cancelledAt": now,
                        "cancelledBy": "system:confirmation_expired",
                    }
                },
            )
            raise CommandConfirmationExpiredError(command_id)

        # Check cooldown at confirmation time
        danger_level = command.get("dangerLevel", "medium")
        node_id = command["target"]["nodeId"]
        await self._check_cooldown(node_id, danger_level)

        # Validate target node is still active
        node = await self.nodes.find_one({"nodeId": node_id, "status": "active"})
        if not node:
            raise NodeNotFoundError(node_id)

        tier = node.get("agentTier", "normal")
        if tier == "lite":
            raise CommandNotSupportedError(
                f"Agent tier 'lite' on node '{node_id}' does not support "
                f"command execution."
            )

        # Set cooldown for destructive commands
        await self._set_cooldown(node_id, danger_level)

        # Transition to queued
        now = datetime.now(UTC)
        queue_count = await self.commands.count_documents({
            "target.nodeId": node_id,
            "status": CommandStatus.QUEUED.value,
        })

        await self.commands.update_one(
            {"commandId": command_id},
            {
                "$set": {
                    "status": CommandStatus.QUEUED.value,
                    "queuedAt": now,
                    "executionMethod": "agent-poll",
                    "queuePosition": queue_count + 1,
                }
            },
        )

        logger.info(
            "command_confirmed",
            command_id=command_id,
            confirmed_by=user_id,
            danger_level=danger_level,
        )

        # Audit the confirmation
        safe_create_task(
            log_audit(
                action=AuditAction.EXECUTE,
                resource_type="command",
                resource_id=command_id,
                actor_type="user",
                actor_id=user_id or "unknown",
                success=True,
                details={
                    "registryId": command.get("registryId"),
                    "action": "confirm",
                    "dangerLevel": danger_level,
                },
            )
        )

        return await self.get_command(command_id)

    # ── Command Retries (P2B-002) ──────────────────────────────────────────

    # Retriable terminal statuses
    RETRIABLE_STATUSES = frozenset({CommandStatus.FAILED.value, CommandStatus.TIMEOUT.value})

    async def _maybe_auto_retry(self, command: dict[str, Any]) -> None:
        """Check if a failed command should be auto-retried with backoff.

        Called as a fire-and-forget background task after a command fails.
        Applies exponential backoff based on the current retry count before
        dispatching the retry.
        """
        import asyncio as _asyncio

        registry_id = command.get("registryId")
        if not registry_id:
            return

        definition = await self.command_definitions.find_one(
            {"registryId": registry_id}
        )
        if not definition:
            return

        execution_config = definition.get("execution", {})
        if not execution_config.get("retryable", False):
            return

        max_retries = execution_config.get("maxRetries", 0)
        # Resolve the original command to check retry count
        original_id = command.get("retriedFrom") or command["commandId"]
        original = (
            command
            if original_id == command["commandId"]
            else await self.get_command(original_id)
        )
        current_retry_count = original.get("retryCount", 0)
        if current_retry_count >= max_retries:
            return

        # Exponential backoff: 2^retry_count * 5 seconds (5s, 10s, 20s, ...)
        backoff_seconds = (2 ** current_retry_count) * 5
        logger.info(
            "auto_retry_scheduled",
            command_id=command["commandId"],
            original_command_id=original_id,
            backoff_seconds=backoff_seconds,
            retry_count=current_retry_count + 1,
        )

        await _asyncio.sleep(backoff_seconds)

        try:
            await self.retry_command(
                command["commandId"],
                is_auto_retry=True,
            )
        except Exception:
            logger.warning(
                "auto_retry_failed",
                command_id=command["commandId"],
                exc_info=True,
            )

    async def retry_command(
        self,
        command_id: str,
        *,
        user_id: str | None = None,
        user_role: str | None = None,
        user_permissions: list[str] | None = None,
        source: CommandSource = CommandSource.API,
        client_id: str | None = None,
        is_auto_retry: bool = False,
    ) -> dict[str, Any]:
        """Retry a failed or timed-out command.

        Creates a new command record linked to the original via ``retriedFrom``,
        increments ``retryCount`` on the original, and dispatches the new command
        through the normal tier-aware routing path.

        Args:
            command_id: The command to retry.
            user_id: The requesting user (None for auto-retry).
            user_role: The user's role.
            user_permissions: The user's permission list.
            source: The command source.
            client_id: The originating client identifier.
            is_auto_retry: True when invoked by the background auto-retry logic.

        Returns:
            The newly created retry command document.

        Raises:
            CommandNotFoundError: If the command does not exist.
            CommandNotRetriableError: If the command is not in a retriable state.
            CommandMaxRetriesError: If max retries have been reached.
            CommandRegistryNotFoundError: If the command's definition is missing.
        """
        command = await self.get_command(command_id)

        # Validate retriable state
        if command["status"] not in self.RETRIABLE_STATUSES:
            raise CommandNotRetriableError(command_id, command["status"])

        # Resolve the original command for retry chains (follow retriedFrom links)
        original_command_id = command.get("retriedFrom") or command_id
        original_command = (
            command
            if original_command_id == command_id
            else await self.get_command(original_command_id)
        )

        # Look up the command definition for retry policy
        registry_id = command.get("registryId")
        definition = await self.command_definitions.find_one(
            {"registryId": registry_id}
        ) if registry_id else None

        if not definition:
            raise CommandRegistryNotFoundError(registry_id or "unknown")

        execution_config = definition.get("execution", {})
        retryable = execution_config.get("retryable", False)
        max_retries = execution_config.get("maxRetries", 0)

        if not retryable or max_retries <= 0:
            raise CommandNotRetriableError(
                command_id,
                f"{command['status']} (definition not retryable)",
            )

        # Check retry count on the original command
        current_retry_count = original_command.get("retryCount", 0)
        if current_retry_count >= max_retries:
            raise CommandMaxRetriesError(command_id, max_retries, current_retry_count)

        # Re-check RBAC for manual retries (auto-retries use system authority)
        if not is_auto_retry:
            await self._enforce_submission_policy(
                request=None,
                definition=definition,
                user_id=user_id,
                user_role=user_role,
                user_permissions=user_permissions,
                source=source,
                client_id=client_id,
                persist_rejection=False,
            )

        # Increment retryCount on the original command
        new_retry_count = current_retry_count + 1
        await self.commands.update_one(
            {"commandId": original_command_id},
            {"$set": {"retryCount": new_retry_count}},
        )

        # Build and dispatch the retry command through the normal creation path
        retry_request = CreateCommandRequest(
            registry_id=command["registryId"],
            target={  # type: ignore[arg-type]
                "nodeId": command["target"]["nodeId"],
                "serviceId": command["target"].get("serviceId"),
            },
            parameters=command.get("parameters"),
            timeout_seconds=command.get("timeoutSeconds"),
        )

        retry_cmd = await self.create_command(
            retry_request,
            user_id=user_id if not is_auto_retry else "system:auto-retry",
            user_role=user_role if not is_auto_retry else "admin",
            user_permissions=user_permissions if not is_auto_retry else ["*:*"],
            source=source if not is_auto_retry else CommandSource.AUTOMATION,
            client_id=client_id if not is_auto_retry else "hydra-api",
            chain=command.get("chain"),
        )

        # Patch the retry command with linkage to the original
        await self.commands.update_one(
            {"commandId": retry_cmd["commandId"]},
            {
                "$set": {
                    "retriedFrom": original_command_id,
                    "retryCount": new_retry_count,
                    "maxRetries": max_retries,
                }
            },
        )
        retry_cmd["retriedFrom"] = original_command_id
        retry_cmd["retryCount"] = new_retry_count
        retry_cmd["maxRetries"] = max_retries

        logger.info(
            "command_retried",
            command_id=retry_cmd["commandId"],
            original_command_id=original_command_id,
            retry_count=new_retry_count,
            max_retries=max_retries,
            auto_retry=is_auto_retry,
        )

        # Audit the retry
        safe_create_task(
            log_audit(
                action=AuditAction.EXECUTE,
                resource_type="command",
                resource_id=retry_cmd["commandId"],
                actor_type="system" if is_auto_retry else "user",
                actor_id="hydra-api" if is_auto_retry else (user_id or "unknown"),
                success=True,
                details={
                    "registryId": registry_id,
                    "action": "retry",
                    "originalCommandId": original_command_id,
                    "retryCount": new_retry_count,
                    "autoRetry": is_auto_retry,
                },
            )
        )

        return retry_cmd

    async def schedule_auto_retries(self) -> int:
        """Check for recently failed/timed-out commands that are auto-retryable.

        Called periodically by the background task scheduler. For each eligible
        command, schedules a retry with exponential backoff by checking elapsed
        time since failure against the expected backoff delay.

        Returns:
            Number of auto-retries scheduled.
        """
        now = datetime.now(UTC)
        retried = 0

        # Find commands that failed or timed out recently and may be retryable
        cursor = self.commands.find({
            "status": {"$in": [CommandStatus.FAILED.value, CommandStatus.TIMEOUT.value]},
            "retriedFrom": None,  # Only originals, not retry attempts themselves
            "completedAt": {"$gte": now - timedelta(hours=1)},  # Within last hour
        }).sort("completedAt", -1).limit(50)

        commands = await cursor.to_list(length=50)

        for cmd in commands:
            registry_id = cmd.get("registryId")
            if not registry_id:
                continue

            definition = await self.command_definitions.find_one(
                {"registryId": registry_id}
            )
            if not definition:
                continue

            execution_config = definition.get("execution", {})
            if not execution_config.get("retryable", False):
                continue

            max_retries = execution_config.get("maxRetries", 0)
            current_retry_count = cmd.get("retryCount", 0)
            if current_retry_count >= max_retries:
                continue

            # Exponential backoff: 2^retry_count * 5 seconds (5s, 10s, 20s, ...)
            backoff_seconds = (2 ** current_retry_count) * 5
            completed_at = cmd.get("completedAt")
            if not completed_at:
                continue

            elapsed = (now - completed_at).total_seconds()
            if elapsed < backoff_seconds:
                continue  # Not yet time for this retry

            try:
                await self.retry_command(
                    cmd["commandId"],
                    is_auto_retry=True,
                )
                retried += 1
            except Exception:
                logger.warning(
                    "auto_retry_failed",
                    command_id=cmd["commandId"],
                    registry_id=registry_id,
                    exc_info=True,
                )

        if retried > 0:
            logger.info("auto_retries_scheduled", count=retried)

        return retried
