"""Node management service."""

from datetime import UTC, datetime
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import NodeNotFoundError, ValidationError
from hydra.api.v1.models.nodes import NodeListParams, NodeStatus, UpdateNodeRequest
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.icons import resolve_icon_descriptor
from hydra.api.v1.services.query import log_audit
from hydra.core.config import get_settings
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


def build_node_agent_info(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Build the nested ``agent`` object from a flat node document.

    The node document persists agent metadata as flat fields (``agentTier``,
    ``serverAddress``, ``serverReachable``, …) for query simplicity. The API
    contract exposes them nested under ``agent.serverConfig`` / ``agent.serverStatus``
    (spec §3.4). This translates the storage shape into the response shape.

    Returns None only when a node has no agent metadata at all (legacy/edge);
    every registered node has at least a tier.
    """
    tier = doc.get("agentTier")
    server_config: dict[str, Any] | None = None
    server_status: dict[str, Any] | None = None

    # serverConfig/serverStatus only exist for max-tier agents exposing a server.
    if doc.get("serverAddress") is not None:
        server_config = {
            "enabled": True,
            "bindAddress": doc.get("serverBindAddress"),
            "advertiseAddress": doc.get("serverAddress"),
            "port": doc.get("serverPort"),
            "tlsEnabled": doc.get("serverTlsEnabled"),
        }
        server_status = {
            "isReachable": doc.get("serverReachable"),
            "lastDirectContact": doc.get("lastDirectContact"),
            "failedDirectAttempts": doc.get("failedDirectAttempts"),
            "lastPollContact": doc.get("lastPollContact"),
        }

    credential_rotated_at = doc.get("credentialRotatedAt")
    if tier is None and server_config is None and credential_rotated_at is None:
        return None

    return {
        "tier": tier,
        "serverConfig": server_config,
        "serverStatus": server_status,
        "credentialRotatedAt": credential_rotated_at,
    }


class NodeService:
    """Service for node management operations."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_node(self, node_id: str) -> dict[str, Any]:
        """Retrieve a single node by its identifier.

        Args:
            node_id: The unique node identifier.

        Returns:
            The formatted node document.

        Raises:
            NodeNotFoundError: If no node exists with the given ID.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)
        return self._format_node(node)

    async def list_nodes(self, params: NodeListParams) -> tuple[list[dict[str, Any]], int]:
        """List nodes with filtering, sorting, and pagination.

        Args:
            params: Filter and pagination parameters including class, type,
                kind, status, tags, and search query.

        Returns:
            A tuple of (list of node summaries, total count).
        """
        filter_query: dict[str, Any] = {}

        if params.node_class:
            filter_query["class"] = params.node_class.value
        if params.node_type:
            filter_query["type"] = params.node_type.value
        if params.kind:
            filter_query["kind"] = params.kind.value
        if params.status:
            filter_query["status"] = params.status.value
        if params.agent_tier:
            filter_query["agentTier"] = params.agent_tier.value
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.parent_node_id:
            filter_query["parentNodeId"] = params.parent_node_id
        if params.network_id:
            filter_query["networkIds"] = params.network_id
        if params.search:
            filter_query["$text"] = {"$search": params.search}

        sort_field_map = {
            "nodeId": "nodeId",
            "displayName": "displayName",
            "registeredAt": "registeredAt",
            "lastProfileAt": "lastProfileAt",
            "lastUpdated": "lastUpdated",
        }
        sort_field = sort_field_map.get(params.sort_by, "lastUpdated")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        total = await self.db.nodes.count_documents(filter_query)

        cursor = (
            self.db.nodes.find(filter_query)
            .sort(sort_field, sort_direction)
            .skip(params.offset)
            .limit(params.limit)
        )

        nodes = []
        async for node in cursor:
            nodes.append(self._format_node_summary(node))

        logger.info(
            "nodes_listed",
            total=total,
            returned=len(nodes),
            filters=filter_query,
        )

        return nodes, total

    async def update_node(self, node_id: str, request: UpdateNodeRequest, user_id: str | None = None) -> dict[str, Any]:
        """Update node metadata.

        Args:
            node_id: The node identifier to update.
            request: Fields to update including display name, description,
                kind, tags, parent node, and status.
            user_id: Optional user ID of the actor performing the update.

        Returns:
            The updated node document.

        Raises:
            NodeNotFoundError: If no node exists with the given ID.
            ValidationError: If parent node reference is invalid.
        """
        existing = await self.db.nodes.find_one({"nodeId": node_id})
        if not existing:
            raise NodeNotFoundError(node_id)

        update_fields: dict[str, Any] = {"lastUpdated": datetime.now(UTC)}

        if request.display_name is not None:
            update_fields["displayName"] = request.display_name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.kind is not None:
            update_fields["kind"] = request.kind.value
        if request.tags is not None:
            update_fields["tags"] = request.tags
        if request.parent_node_id is not None:
            if request.parent_node_id:
                parent = await self.db.nodes.find_one({"nodeId": request.parent_node_id})
                if not parent:
                    raise ValidationError(
                        f"Parent node '{request.parent_node_id}' not found",
                        {"parentNodeId": request.parent_node_id},
                    )
            update_fields["parentNodeId"] = request.parent_node_id or None
        if request.status is not None:
            update_fields["status"] = request.status.value

        result = await self.db.nodes.update_one(
            {"nodeId": node_id},
            {"$set": update_fields},
        )

        if result.modified_count == 0:
            logger.warning("node_update_no_changes", node_id=node_id)

        logger.info("node_updated", node_id=node_id, fields=list(update_fields.keys()))

        await log_audit(
            AuditAction.UPDATE,
            "node",
            node_id,
            "user",
            user_id or "unknown",
            True,
            details={"fields": list(update_fields.keys())},
        )

        return await self.get_node(node_id)

    async def archive_node(self, node_id: str, user_id: str | None = None) -> dict[str, Any]:
        """Archive a node (soft delete).

        Args:
            node_id: The node identifier to archive.
            user_id: Optional user ID of the actor performing the archive.

        Returns:
            The archived node document.

        Raises:
            NodeNotFoundError: If no node exists with the given ID.
            ValidationError: If the node is already archived.
        """
        existing = await self.db.nodes.find_one({"nodeId": node_id})
        if not existing:
            raise NodeNotFoundError(node_id)

        if existing["status"] == NodeStatus.ARCHIVED.value:
            raise ValidationError(f"Node '{node_id}' is already archived")

        await self.db.nodes.update_one(
            {"nodeId": node_id},
            {
                "$set": {
                    "status": NodeStatus.ARCHIVED.value,
                    "lastUpdated": datetime.now(UTC),
                }
            },
        )

        logger.info("node_archived", node_id=node_id)

        await log_audit(
            AuditAction.ARCHIVE,
            "node",
            node_id,
            "user",
            user_id or "unknown",
            True,
        )

        return await self.get_node(node_id)

    async def get_node_children(self, node_id: str) -> list[dict[str, Any]]:
        """Get child nodes of a parent node.

        Args:
            node_id: The parent node identifier.

        Returns:
            List of child node summaries.

        Raises:
            NodeNotFoundError: If the parent node does not exist.
        """
        parent = await self.db.nodes.find_one({"nodeId": node_id})
        if not parent:
            raise NodeNotFoundError(node_id)

        children = []
        cursor = self.db.nodes.find({"parentNodeId": node_id})
        async for child in cursor:
            children.append(self._format_node_summary(child))

        return children

    async def update_node_networks(self, node_id: str, network_ids: list[str]) -> None:
        """Update network associations for a node.

        Args:
            node_id: The node identifier.
            network_ids: List of network IDs to associate.

        Raises:
            NodeNotFoundError: If no node exists with the given ID.
        """
        result = await self.db.nodes.update_one(
            {"nodeId": node_id},
            {
                "$set": {
                    "networkIds": network_ids,
                    "lastUpdated": datetime.now(UTC),
                }
            },
        )
        if result.matched_count == 0:
            raise NodeNotFoundError(node_id)

    async def update_last_profile(self, node_id: str, profile_time: datetime) -> None:
        """Update the last profile timestamp for a node.

        Args:
            node_id: The node identifier.
            profile_time: The timestamp of the profile submission.

        Raises:
            NodeNotFoundError: If no node exists with the given ID.
        """
        result = await self.db.nodes.update_one(
            {"nodeId": node_id},
            {
                "$set": {
                    "lastProfileAt": profile_time,
                    "lastUpdated": datetime.now(UTC),
                }
            },
        )
        if result.matched_count == 0:
            raise NodeNotFoundError(node_id)

    async def list_agents(
        self,
        status: str | None = None,
        healthy_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List all registered agents (nodes with submitted profiles).

        An agent is considered healthy if it has submitted a profile within
        the last 24 hours.

        Args:
            status: Optional status filter.
            healthy_only: Only return healthy agents.
            limit: Maximum results to return.
            offset: Pagination offset.

        Returns:
            Dict containing agents list, total count, active count, and pagination info.
        """
        from datetime import timedelta

        now = datetime.now(UTC)
        settings = get_settings()
        health_threshold = now - timedelta(hours=settings.health_cutoff_hours)

        query: dict[str, Any] = {"lastProfileAt": {"$ne": None}}

        if status:
            query["status"] = status

        total = await self.db.nodes.count_documents(query)

        # Use aggregation pipeline to avoid N+1 queries for profile stats
        pipeline = [
            {"$match": query},
            {"$sort": {"lastProfileAt": DESCENDING}},
            {"$skip": offset},
            {"$limit": limit},
            # Join with profiles to get count and latest version in one query
            {
                "$lookup": {
                    "from": "profiles",
                    "let": {"nodeId": "$nodeId"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$nodeId", "$$nodeId"]}}},
                        {
                            "$facet": {
                                "count": [{"$count": "total"}],
                                "latest": [
                                    {"$sort": {"submittedAt": DESCENDING}},
                                    {"$limit": 1},
                                    {"$project": {"version": 1}},
                                ],
                            }
                        },
                    ],
                    "as": "profileStats",
                }
            },
            {"$unwind": {"path": "$profileStats", "preserveNullAndEmptyArrays": True}},
        ]

        agents = []
        active_count = 0

        async for node in self.db.nodes.aggregate(pipeline):  # type: ignore[arg-type]
            last_profile_at = node.get("lastProfileAt")
            last_seen_at = node.get("lastSeenAt")
            # Use lastSeenAt if available (includes profile + command poll), fall back to lastProfileAt
            effective_seen = last_seen_at or last_profile_at
            is_healthy = effective_seen is not None and effective_seen >= health_threshold

            if healthy_only and not is_healthy:
                continue

            if is_healthy:
                active_count += 1

            # Extract profile stats from aggregation result
            profile_stats = node.get("profileStats", {})
            count_result = profile_stats.get("count", [])
            latest_result = profile_stats.get("latest", [])

            profile_count = count_result[0]["total"] if count_result else 0
            last_profile_version = latest_result[0].get("version") if latest_result else None

            agents.append({
                "nodeId": node["nodeId"],
                "class": node["class"],
                "type": node["type"],
                "kind": node.get("kind"),
                "displayName": node["displayName"],
                "tags": node.get("tags", []),
                "registeredBy": node.get("registeredBy"),
                "registeredAt": node["registeredAt"],
                "status": node["status"],
                "lastProfileAt": last_profile_at,
                "profileCount": profile_count,
                "lastProfileVersion": last_profile_version,
                "isHealthy": is_healthy,
                "agentTier": node.get("agentTier"),
            })

        if healthy_only:
            active_count = len(agents)
        else:
            active_query = {**query, "lastProfileAt": {"$gte": health_threshold}}
            active_count = await self.db.nodes.count_documents(active_query)

        logger.info(
            "agents_listed",
            total=total,
            active=active_count,
            returned=len(agents),
        )

        return {
            "agents": agents,
            "total": total,
            "active": active_count,
            "limit": limit,
            "offset": offset,
        }

    def _format_node(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a node document for API response."""
        icon = resolve_icon_descriptor(
            name=doc.get("kind") or doc.get("class"),
            provider=doc.get("platform") or doc.get("os"),
            fallback=doc.get("class", "server"),
        )
        return {
            "nodeId": doc["nodeId"],
            "class": doc["class"],
            "type": doc["type"],
            "kind": doc.get("kind"),
            "displayName": doc["displayName"],
            "description": doc.get("description"),
            "tags": doc.get("tags", []),
            "parentNodeId": doc.get("parentNodeId"),
            "networkIds": doc.get("networkIds", []),
            "registeredBy": doc.get("registeredBy"),
            "registeredAt": doc["registeredAt"],
            "lastUpdated": doc["lastUpdated"],
            "lastProfileAt": doc.get("lastProfileAt"),
            "lastSeenAt": doc.get("lastSeenAt"),
            "status": doc["status"],
            "agent": build_node_agent_info(doc),
            "icon": icon,
        }

    def _format_node_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a node document for list response."""
        icon = resolve_icon_descriptor(
            name=doc.get("kind") or doc.get("class"),
            provider=doc.get("platform") or doc.get("os"),
            fallback=doc.get("class", "server"),
        )
        return {
            "nodeId": doc["nodeId"],
            "class": doc["class"],
            "type": doc["type"],
            "kind": doc.get("kind"),
            "displayName": doc["displayName"],
            "tags": doc.get("tags", []),
            "registeredBy": doc.get("registeredBy"),
            "status": doc["status"],
            "lastProfileAt": doc.get("lastProfileAt"),
            "lastSeenAt": doc.get("lastSeenAt"),
            "agent": build_node_agent_info(doc),
            "icon": icon,
        }
