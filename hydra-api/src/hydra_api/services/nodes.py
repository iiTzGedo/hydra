"""Node management service."""

from datetime import datetime, timezone
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra_api.core.exceptions import NodeNotFoundError, ValidationError
from hydra_api.db.mongodb import MongoDB
from hydra_api.models.nodes import NodeListParams, NodeStatus, UpdateNodeRequest

logger = structlog.get_logger(__name__)


class NodeService:
    """Service for node management operations."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_node(self, node_id: str) -> dict:
        """Get a single node by ID."""
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)
        return self._format_node(node)

    async def list_nodes(self, params: NodeListParams) -> tuple[list[dict], int]:
        """
        List nodes with filters and pagination.

        Returns:
            Tuple of (nodes list, total count)
        """
        # Build filter
        filter_query: dict[str, Any] = {}

        if params.node_class:
            filter_query["class"] = params.node_class.value
        if params.node_type:
            filter_query["type"] = params.node_type.value
        if params.kind:
            filter_query["kind"] = params.kind.value
        if params.status:
            filter_query["status"] = params.status.value
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.parent_node_id:
            filter_query["parentNodeId"] = params.parent_node_id
        if params.network_id:
            filter_query["networkIds"] = params.network_id
        if params.search:
            filter_query["$text"] = {"$search": params.search}

        # Sort
        sort_field_map = {
            "nodeId": "nodeId",
            "displayName": "displayName",
            "registeredAt": "registeredAt",
            "lastProfileAt": "lastProfileAt",
            "lastUpdated": "lastUpdated",
        }
        sort_field = sort_field_map.get(params.sort_by, "lastUpdated")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        # Execute queries
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

    async def update_node(self, node_id: str, request: UpdateNodeRequest) -> dict:
        """Update node metadata."""
        # Check node exists
        existing = await self.db.nodes.find_one({"nodeId": node_id})
        if not existing:
            raise NodeNotFoundError(node_id)

        # Build update
        update_fields: dict[str, Any] = {"lastUpdated": datetime.now(timezone.utc)}

        if request.display_name is not None:
            update_fields["displayName"] = request.display_name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.kind is not None:
            update_fields["kind"] = request.kind.value
        if request.tags is not None:
            update_fields["tags"] = request.tags
        if request.parent_node_id is not None:
            # Validate parent exists if not null
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

        # Execute update
        result = await self.db.nodes.update_one(
            {"nodeId": node_id},
            {"$set": update_fields},
        )

        if result.modified_count == 0:
            logger.warning("node_update_no_changes", node_id=node_id)

        logger.info("node_updated", node_id=node_id, fields=list(update_fields.keys()))

        # Return updated node
        return await self.get_node(node_id)

    async def archive_node(self, node_id: str) -> dict:
        """Archive a node (soft delete)."""
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
                    "lastUpdated": datetime.now(timezone.utc),
                }
            },
        )

        logger.info("node_archived", node_id=node_id)
        return await self.get_node(node_id)

    async def get_node_children(self, node_id: str) -> list[dict]:
        """Get child nodes of a parent node."""
        # Verify parent exists
        parent = await self.db.nodes.find_one({"nodeId": node_id})
        if not parent:
            raise NodeNotFoundError(node_id)

        children = []
        cursor = self.db.nodes.find({"parentNodeId": node_id})
        async for child in cursor:
            children.append(self._format_node_summary(child))

        return children

    async def update_node_networks(self, node_id: str, network_ids: list[str]) -> None:
        """Update the network associations for a node."""
        result = await self.db.nodes.update_one(
            {"nodeId": node_id},
            {
                "$set": {
                    "networkIds": network_ids,
                    "lastUpdated": datetime.now(timezone.utc),
                }
            },
        )
        if result.matched_count == 0:
            raise NodeNotFoundError(node_id)

    async def update_last_profile(self, node_id: str, profile_time: datetime) -> None:
        """Update the last profile timestamp for a node."""
        result = await self.db.nodes.update_one(
            {"nodeId": node_id},
            {
                "$set": {
                    "lastProfileAt": profile_time,
                    "lastUpdated": datetime.now(timezone.utc),
                }
            },
        )
        if result.matched_count == 0:
            raise NodeNotFoundError(node_id)

    def _format_node(self, doc: dict) -> dict:
        """Format a node document for API response."""
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
            "registeredAt": doc["registeredAt"],
            "lastUpdated": doc["lastUpdated"],
            "lastProfileAt": doc.get("lastProfileAt"),
            "status": doc["status"],
        }

    def _format_node_summary(self, doc: dict) -> dict:
        """Format a node document for list response."""
        return {
            "nodeId": doc["nodeId"],
            "class": doc["class"],
            "type": doc["type"],
            "kind": doc.get("kind"),
            "displayName": doc["displayName"],
            "tags": doc.get("tags", []),
            "status": doc["status"],
            "lastProfileAt": doc.get("lastProfileAt"),
        }
