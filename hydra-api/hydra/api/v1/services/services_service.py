"""Service management service."""

import re
from datetime import UTC, datetime
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import NodeNotFoundError, ServiceNotFoundError, ValidationError
from hydra.api.v1.models.services import ServiceListParams, UpdateServiceRequest
from hydra.api.v1.services.icons import resolve_icon_descriptor
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class ServicesService:
    """Service for managing discovered services."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_service(self, service_id: str) -> dict[str, Any]:
        """Retrieve a single service by its identifier.

        Args:
            service_id: The unique service identifier.

        Returns:
            The formatted service document.

        Raises:
            ServiceNotFoundError: If no service exists with the given ID.
        """
        service = await self.db.services.find_one({"serviceId": service_id})
        if not service:
            raise ServiceNotFoundError(service_id)
        return self._format_service(service)

    async def list_services(self, params: ServiceListParams) -> tuple[list[dict[str, Any]], int]:
        """List services with optional filtering, sorting, and pagination.

        Args:
            params: Query parameters including filters (node_id, runtime, status,
                name, tags, port, search), sorting (sort_by, sort_order),
                and pagination (offset, limit).

        Returns:
            A tuple of (list of formatted service summaries, total count).
        """
        filter_query: dict[str, Any] = {}

        if params.node_id:
            filter_query["nodeId"] = params.node_id
        if params.runtime:
            filter_query["runtime"] = params.runtime.value
        if params.status:
            filter_query["status"] = params.status.value
        if params.name:
            filter_query["name"] = {"$regex": params.name, "$options": "i"}
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.port:
            filter_query["exposure.ports.port"] = params.port
        if params.search:
            escaped = re.escape(params.search)
            filter_query["$or"] = [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"displayName": {"$regex": escaped, "$options": "i"}},
                {"serviceId": {"$regex": escaped, "$options": "i"}},
            ]

        sort_field_map = {
            "serviceId": "serviceId",
            "name": "name",
            "lastSeen": "lastSeen",
            "status": "status",
            "runtime": "runtime",
        }
        sort_field = sort_field_map.get(params.sort_by, "lastSeen")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        total = await self.db.services.count_documents(filter_query)

        cursor = (
            self.db.services.find(filter_query)
            .sort(sort_field, sort_direction)
            .skip(params.offset)
            .limit(params.limit)
        )

        services = []
        async for service in cursor:
            services.append(self._format_service_summary(service))

        logger.info(
            "services_listed",
            total=total,
            returned=len(services),
            filters={k: v for k, v in filter_query.items() if k != "$or"},
        )

        return services, total

    async def update_service(self, service_id: str, request: UpdateServiceRequest) -> dict[str, Any]:
        """Update mutable service metadata.

        Args:
            service_id: The unique service identifier.
            request: Update payload with optional display_name, description, and tags.

        Returns:
            The updated service document.

        Raises:
            ServiceNotFoundError: If no service exists with the given ID.
        """
        existing = await self.db.services.find_one({"serviceId": service_id})
        if not existing:
            raise ServiceNotFoundError(service_id)

        update_fields: dict[str, Any] = {"lastUpdated": datetime.now(UTC)}

        if request.display_name is not None:
            update_fields["displayName"] = request.display_name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.tags is not None:
            update_fields["tags"] = request.tags

        result = await self.db.services.update_one(
            {"serviceId": service_id},
            {"$set": update_fields},
        )

        if result.modified_count == 0:
            logger.warning("service_update_no_changes", service_id=service_id)

        logger.info("service_updated", service_id=service_id, fields=list(update_fields.keys()))

        return await self.get_service(service_id)

    async def archive_service(self, service_id: str) -> dict[str, Any]:
        """Archive a service by setting its status to archived.

        Args:
            service_id: The unique service identifier.

        Returns:
            The archived service document.

        Raises:
            ServiceNotFoundError: If no service exists with the given ID.
            ValidationError: If the service is already archived.
        """
        existing = await self.db.services.find_one({"serviceId": service_id})
        if not existing:
            raise ServiceNotFoundError(service_id)

        if existing.get("status") == "archived":
            raise ValidationError(f"Service '{service_id}' is already archived")

        await self.db.services.update_one(
            {"serviceId": service_id},
            {
                "$set": {
                    "status": "archived",
                    "lastUpdated": datetime.now(UTC),
                }
            },
        )

        logger.info("service_archived", service_id=service_id)
        return await self.get_service(service_id)

    async def get_services_by_node(
        self,
        node_id: str,
        runtime: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List services running on a specific node.

        Args:
            node_id: The node identifier to filter by.
            runtime: Optional runtime filter (e.g., docker, systemd).
            status: Optional status filter (e.g., running, stopped).
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            A tuple of (list of service summaries, total count).

        Raises:
            NodeNotFoundError: If the specified node does not exist.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        filter_query: dict[str, Any] = {"nodeId": node_id}
        if runtime:
            filter_query["runtime"] = runtime
        if status:
            filter_query["status"] = status

        total = await self.db.services.count_documents(filter_query)

        cursor = (
            self.db.services.find(filter_query)
            .sort("lastSeen", DESCENDING)
            .skip(offset)
            .limit(limit)
        )

        services = []
        async for service in cursor:
            services.append(self._format_service_summary(service))

        return services, total

    def _format_service(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a service document for API response."""
        exposure = doc.get("exposure", {})
        icon = resolve_icon_descriptor(
            name=doc.get("name") or doc.get("image"),
            provider=doc.get("runtime"),
            fallback=doc.get("runtime", "boxes"),
        )

        return {
            "serviceId": doc["serviceId"],
            "runtime": doc["runtime"],
            "name": doc["name"],
            "displayName": doc.get("displayName", doc["name"]),
            "description": doc.get("description"),
            "status": doc["status"],
            "version": doc.get("version"),
            "image": doc.get("image"),
            "profileId": doc.get("profileId"),
            "nodeId": doc["nodeId"],
            "exposure": {
                "ports": exposure.get("ports", []),
                "endpoints": exposure.get("endpoints", []),
            } if exposure else None,
            "resources": doc.get("resources"),
            "attachments": doc.get("attachments"),
            "origin": doc.get("origin", {}),
            "health": doc.get("health"),
            "tags": doc.get("tags", []),
            "firstSeen": doc.get("firstSeen"),
            "lastSeen": doc.get("lastSeen"),
            "icon": icon,
        }

    def _format_service_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a service document for list response."""
        icon = resolve_icon_descriptor(
            name=doc.get("name") or doc.get("image"),
            provider=doc.get("runtime"),
            fallback=doc.get("runtime", "boxes"),
        )
        return {
            "serviceId": doc["serviceId"],
            "name": doc["name"],
            "displayName": doc.get("displayName", doc["name"]),
            "runtime": doc["runtime"],
            "status": doc["status"],
            "version": doc.get("version"),
            "nodeId": doc["nodeId"],
            "lastSeen": doc.get("lastSeen"),
            "icon": icon,
        }
