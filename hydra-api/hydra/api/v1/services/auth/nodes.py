"""Node registration mixin: register nodes and refresh node API keys."""

import secrets
from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.core.exceptions import (
    NodeAlreadyRegisteredError,
    NodeNotFoundError,
)
from hydra.api.v1.core.security import hash_password
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.auth import NodeRegistrationRequest
from hydra.api.v1.models.notifications import (
    ActorType,
    NotificationActor,
    NotificationSource,
    NotificationType,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient

logger = structlog.get_logger(__name__)


class NodeRegistrationMixin:
    """Mixin providing node registration and API key refresh."""
    db: MongoDB
    redis: RedisClient | None


    async def register_node(
        self, request: NodeRegistrationRequest, registered_by: str
    ) -> dict[str, Any]:
        """Register a new node and return API key credentials.

        Args:
            request: Node registration payload with node_id, class, type, etc.
            registered_by: User ID of the registering user.

        Returns:
            Registration details including the API key (shown only once).

        Raises:
            NodeAlreadyRegisteredError: If a node with this ID already exists.
        """
        existing = await self.db.nodes.find_one({"nodeId": request.node_id})
        if existing:
            raise NodeAlreadyRegisteredError(request.node_id)

        now = datetime.now(UTC)

        node_doc = {
            "nodeId": request.node_id,
            "class": request.node_class,
            "type": request.node_type,
            "kind": request.kind,
            "displayName": request.display_name or request.node_id,
            "description": request.description,
            "tags": request.tags,
            "parentNodeId": request.parent_node_id,
            "networkIds": [],
            "location": request.location,
            "agentTier": request.agent_tier or "normal",
            "serverAddress": request.server_address,
            "serverPort": request.server_port,
            "serverTlsEnabled": request.server_tls_enabled,
            "registeredAt": now,
            "registeredBy": registered_by,
            "lastUpdated": now,
            "lastProfileAt": None,
            "status": "active",
        }

        # Generate server secret for max-tier agents
        agent_server_secret = None
        if request.agent_tier == "max" and request.server_address:
            agent_server_secret = f"hsk_api_{secrets.token_urlsafe(32)}"
            node_doc["agentServerSecret"] = agent_server_secret
            node_doc["serverReachable"] = True
            node_doc["failedDirectAttempts"] = 0
            node_doc["lastDirectContact"] = None
            node_doc["lastPollContact"] = None

        await self.db.nodes.insert_one(node_doc)

        key_id = f"key_node_{secrets.token_urlsafe(8)}"
        api_key = f"hyk_{key_id}.{secrets.token_urlsafe(32)}"

        key_doc = {
            "keyId": key_id,
            "keyHash": hash_password(api_key),
            "name": f"{request.node_id}-agent",
            "type": "node",
            "ownerId": registered_by,
            "ownerType": "user",
            "nodeId": request.node_id,
            "permissions": [
                f"profiles:write:{request.node_id}",
                f"commands:poll:{request.node_id}",
            ],
            "expiresAt": None,
            "lastUsedAt": None,
            "createdAt": now,
            "revokedAt": None,
        }

        await self.db.api_keys.insert_one(key_doc)

        await self.db.users.update_one(
            {"userId": registered_by},
            {"$addToSet": {"registeredNodes": request.node_id}},
        )

        logger.info(
            "node_registered",
            node_id=request.node_id,
            node_class=request.node_class,
            registered_by=registered_by,
        )

        audit_id = await log_audit(
            AuditAction.REGISTER, "node", request.node_id,
            "user", registered_by, True,
            details={
                "nodeId": request.node_id,
                "nodeClass": request.node_class,
                "nodeType": request.node_type,
                "apiKeyId": key_id,
            },
        )

        safe_create_task(emit_notification(
            notification_type=NotificationType.NODE_REGISTERED,
            source=NotificationSource(component="hydra-api", service="auth"),  # type: ignore[arg-type]
            title="Node registered",
            message=f"Node {request.node_id} registered successfully",
            details={"nodeId": request.node_id, "nodeClass": request.node_class},
            actor=NotificationActor(type=ActorType.USER, id=registered_by),
            audit_entry_id=audit_id,
            mongodb=self.db,
            redis=self.redis,
            resolve_dependencies=False,
        ))

        result = {
            "node_id": request.node_id,
            "api_key": api_key,
            "api_key_id": key_id,
            "registered_by": registered_by,
            "registered_at": now,
            "status": "active",
        }
        if agent_server_secret:
            result["agent_server_secret"] = agent_server_secret
        return result

    async def refresh_node_api_key(
        self, node_id: str, refreshed_by: str | None = None
    ) -> dict[str, Any]:
        """Refresh the API key for a node, revoking the previous key.

        Args:
            node_id: The node identifier.
            refreshed_by: User ID performing the refresh.

        Returns:
            New API key details (the key is shown only once).

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        now = datetime.now(UTC)

        await self.db.api_keys.update_many(
            {"nodeId": node_id, "revokedAt": None},
            {"$set": {"revokedAt": now}},
        )

        key_id = f"key_node_{secrets.token_urlsafe(8)}"
        api_key = f"hyk_{key_id}.{secrets.token_urlsafe(32)}"

        key_doc = {
            "keyId": key_id,
            "keyHash": hash_password(api_key),
            "name": f"{node_id}-agent",
            "type": "node",
            "ownerId": node.get("registeredBy", refreshed_by),
            "ownerType": "user",
            "nodeId": node_id,
            "permissions": [
                f"profiles:write:{node_id}",
                f"commands:poll:{node_id}",
            ],
            "expiresAt": None,
            "lastUsedAt": None,
            "createdAt": now,
            "revokedAt": None,
        }

        await self.db.api_keys.insert_one(key_doc)

        logger.info(
            "node_api_key_refreshed",
            node_id=node_id,
            key_id=key_id,
        )

        return {
            "node_id": node_id,
            "api_key_id": key_id,
            "api_key": api_key,
            "previous_key_revoked": True,
            "refreshed_at": now,
        }
