"""Service management service."""

from datetime import datetime, timezone
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra_api.core.exceptions import NodeNotFoundError, ServiceNotFoundError, ValidationError
from hydra_api.db.mongodb import MongoDB
from hydra_api.models.services import ServiceListParams, ServiceStatus, UpdateServiceRequest

logger = structlog.get_logger(__name__)


class ServicesService:
    """Service for managing discovered services."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_service(self, service_id: str) -> dict:
        """Get a single service by ID."""
        service = await self.db.services.find_one({"serviceId": service_id})
        if not service:
            raise ServiceNotFoundError(service_id)
        return self._format_service(service)

    async def list_services(self, params: ServiceListParams) -> tuple[list[dict], int]:
        """
        List services with filters and pagination.

        Returns:
            Tuple of (services list, total count)
        """
        # Build filter
        filter_query: dict[str, Any] = {}

        if params.node_id:
            filter_query["nodeId"] = params.node_id
        if params.runtime:
            filter_query["runtime"] = params.runtime.value
        if params.status:
            filter_query["status"] = params.status.value
        if params.name:
            # Partial match on name
            filter_query["name"] = {"$regex": params.name, "$options": "i"}
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.port:
            filter_query["exposure.ports.port"] = params.port
        if params.search:
            filter_query["$or"] = [
                {"name": {"$regex": params.search, "$options": "i"}},
                {"displayName": {"$regex": params.search, "$options": "i"}},
                {"serviceId": {"$regex": params.search, "$options": "i"}},
            ]

        # Sort
        sort_field_map = {
            "serviceId": "serviceId",
            "name": "name",
            "lastSeen": "lastSeen",
            "status": "status",
            "runtime": "runtime",
        }
        sort_field = sort_field_map.get(params.sort_by, "lastSeen")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        # Execute queries
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

    async def update_service(self, service_id: str, request: UpdateServiceRequest) -> dict:
        """Update service metadata."""
        # Check service exists
        existing = await self.db.services.find_one({"serviceId": service_id})
        if not existing:
            raise ServiceNotFoundError(service_id)

        # Build update
        update_fields: dict[str, Any] = {"lastUpdated": datetime.now(timezone.utc)}

        if request.display_name is not None:
            update_fields["displayName"] = request.display_name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.tags is not None:
            update_fields["tags"] = request.tags

        # Execute update
        result = await self.db.services.update_one(
            {"serviceId": service_id},
            {"$set": update_fields},
        )

        if result.modified_count == 0:
            logger.warning("service_update_no_changes", service_id=service_id)

        logger.info("service_updated", service_id=service_id, fields=list(update_fields.keys()))

        # Return updated service
        return await self.get_service(service_id)

    async def archive_service(self, service_id: str) -> dict:
        """Archive a service (soft delete)."""
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
                    "lastUpdated": datetime.now(timezone.utc),
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
    ) -> tuple[list[dict], int]:
        """Get services for a specific node."""
        # Verify node exists
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        # Build filter
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

    def _format_service(self, doc: dict) -> dict:
        """Format a service document for API response."""
        exposure = doc.get("exposure", {})

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
        }

    def _format_service_summary(self, doc: dict) -> dict:
        """Format a service document for list response."""
        return {
            "serviceId": doc["serviceId"],
            "name": doc["name"],
            "displayName": doc.get("displayName", doc["name"]),
            "runtime": doc["runtime"],
            "status": doc["status"],
            "version": doc.get("version"),
            "nodeId": doc["nodeId"],
            "lastSeen": doc.get("lastSeen"),
        }
