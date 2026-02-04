"""Query and analytics service for infrastructure data."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from hydra.db.mongodb import MongoDB
from hydra.api.v1.models.query import (
    AuditAction,
    AuditListParams,
    CapacityGroupBy,
    QueryCollection,
    QueryRequest,
)

logger = structlog.get_logger(__name__)


class QueryService:
    """Service for advanced queries and analytics."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb

    def _get_collection(self, name: QueryCollection):
        """Get collection by name."""
        mapping = {
            QueryCollection.NODES: self.mongodb.nodes,
            QueryCollection.PROFILES: self.mongodb.profiles,
            QueryCollection.SERVICES: self.mongodb.services,
            QueryCollection.GROUPS: self.mongodb.groups,
            QueryCollection.NETWORKS: self.mongodb.networks,
        }
        return mapping[name]

    async def execute_query(self, request: QueryRequest) -> tuple[list[dict], int]:
        """Execute a structured query against a specified collection.

        Args:
            request: Query parameters including collection, filter, projection,
                sort, skip, and limit.

        Returns:
            Tuple of (query results, total count).
        """
        collection = self._get_collection(request.collection)
        query = request.filter or {}
        total = await collection.count_documents(query)
        cursor = collection.find(query, projection=request.projection)

        if request.sort:
            sort_list = [(k, v) for k, v in request.sort.items()]
            cursor = cursor.sort(sort_list)

        cursor = cursor.skip(request.skip).limit(request.limit)

        results = await cursor.to_list(length=request.limit)

        for r in results:
            r.pop("_id", None)

        return results, total

    async def get_capacity(
        self,
        group_by: CapacityGroupBy | None = None,
        include_logical: bool = False,
        group_id: str | None = None,
        network_id: str | None = None,
    ) -> dict[str, Any]:
        """Get infrastructure capacity summary.

        Aggregates hardware resources from latest profiles across nodes,
        optionally grouped by class or location.

        Args:
            group_by: Optional grouping dimension (class, location).
            include_logical: Include logical nodes in calculations.
            group_id: Limit to nodes in a specific group.
            network_id: Limit to nodes in a specific network.

        Returns:
            Capacity summary with totals and optional breakdowns by class/location.
        """
        query: dict[str, Any] = {"status": "active"}

        if not include_logical:
            query["type"] = "physical"

        if network_id:
            query["networkIds"] = network_id

        if group_id:
            group = await self.mongodb.groups.find_one({"groupId": group_id})
            if group:
                members = group.get("members", {})
                node_ids = [m.get("nodeId") for m in members.get("nodes", []) if m.get("nodeId")]
                if node_ids:
                    query["nodeId"] = {"$in": node_ids}
        pipeline = [
            {"$match": {"status": "active"}},
            {
                "$lookup": {
                    "from": "profiles",
                    "let": {"nodeId": "$nodeId"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$nodeId", "$$nodeId"]}}},
                        {"$sort": {"submittedAt": -1}},
                        {"$limit": 1},
                    ],
                    "as": "latestProfile",
                }
            },
            {"$unwind": {"path": "$latestProfile", "preserveNullAndEmptyArrays": True}},
            {
                "$group": {
                    "_id": None,
                    "totalNodes": {"$sum": 1},
                    "physicalNodes": {
                        "$sum": {"$cond": [{"$eq": ["$type", "physical"]}, 1, 0]}
                    },
                    "logicalNodes": {
                        "$sum": {"$cond": [{"$eq": ["$type", "logical"]}, 1, 0]}
                    },
                    "totalCores": {
                        "$sum": {"$ifNull": ["$latestProfile.hardware.cpu.cores", 0]}
                    },
                    "totalMemoryBytes": {
                        "$sum": {"$ifNull": ["$latestProfile.hardware.memory.totalBytes", 0]}
                    },
                    "totalStorageBytes": {
                        "$sum": {"$ifNull": ["$latestProfile.storage.totalCapacityBytes", 0]}
                    },
                }
            },
        ]

        results = await self.mongodb.nodes.aggregate(pipeline).to_list(length=1)

        if results:
            r = results[0]
            summary = {
                "totalNodes": r.get("totalNodes", 0),
                "physicalNodes": r.get("physicalNodes", 0),
                "logicalNodes": r.get("logicalNodes", 0),
                "totalCores": r.get("totalCores", 0),
                "totalMemoryGB": round(r.get("totalMemoryBytes", 0) / (1024**3), 2),
                "totalStorageTB": round(r.get("totalStorageBytes", 0) / (1024**4), 2),
            }
        else:
            summary = {
                "totalNodes": 0,
                "physicalNodes": 0,
                "logicalNodes": 0,
                "totalCores": 0,
                "totalMemoryGB": 0,
                "totalStorageTB": 0,
            }

        response = {"summary": summary}

        if group_by == CapacityGroupBy.CLASS or group_by is None:
            class_pipeline = [
                {"$match": {"status": "active"}},
                {
                    "$lookup": {
                        "from": "profiles",
                        "let": {"nodeId": "$nodeId"},
                        "pipeline": [
                            {"$match": {"$expr": {"$eq": ["$nodeId", "$$nodeId"]}}},
                            {"$sort": {"submittedAt": -1}},
                            {"$limit": 1},
                        ],
                        "as": "latestProfile",
                    }
                },
                {"$unwind": {"path": "$latestProfile", "preserveNullAndEmptyArrays": True}},
                {
                    "$group": {
                        "_id": "$class",
                        "nodes": {"$sum": 1},
                        "cores": {
                            "$sum": {"$ifNull": ["$latestProfile.hardware.cpu.cores", 0]}
                        },
                        "memoryBytes": {
                            "$sum": {"$ifNull": ["$latestProfile.hardware.memory.totalBytes", 0]}
                        },
                        "storageBytes": {
                            "$sum": {"$ifNull": ["$latestProfile.storage.totalCapacityBytes", 0]}
                        },
                    }
                },
            ]

            class_results = await self.mongodb.nodes.aggregate(class_pipeline).to_list(length=10)
            by_class = {}
            for r in class_results:
                if r["_id"]:
                    by_class[r["_id"]] = {
                        "nodes": r["nodes"],
                        "cores": r.get("cores", 0),
                        "memoryGB": round(r.get("memoryBytes", 0) / (1024**3), 2),
                        "storageTB": round(r.get("storageBytes", 0) / (1024**4), 2),
                    }
            response["byClass"] = by_class

        if group_by == CapacityGroupBy.LOCATION or group_by is None:
            location_pipeline = [
                {"$match": {"status": "active", "location.site": {"$exists": True}}},
                {
                    "$lookup": {
                        "from": "profiles",
                        "let": {"nodeId": "$nodeId"},
                        "pipeline": [
                            {"$match": {"$expr": {"$eq": ["$nodeId", "$$nodeId"]}}},
                            {"$sort": {"submittedAt": -1}},
                            {"$limit": 1},
                        ],
                        "as": "latestProfile",
                    }
                },
                {"$unwind": {"path": "$latestProfile", "preserveNullAndEmptyArrays": True}},
                {
                    "$group": {
                        "_id": {
                            "$concat": [
                                {"$ifNull": ["$location.site", "unknown"]},
                                "/",
                                {"$ifNull": ["$location.rack", "default"]},
                            ]
                        },
                        "nodes": {"$sum": 1},
                        "cores": {
                            "$sum": {"$ifNull": ["$latestProfile.hardware.cpu.cores", 0]}
                        },
                        "memoryBytes": {
                            "$sum": {"$ifNull": ["$latestProfile.hardware.memory.totalBytes", 0]}
                        },
                    }
                },
            ]

            location_results = await self.mongodb.nodes.aggregate(location_pipeline).to_list(length=50)
            by_location = {}
            for r in location_results:
                if r["_id"]:
                    by_location[r["_id"]] = {
                        "nodes": r["nodes"],
                        "cores": r.get("cores", 0),
                        "memoryGB": round(r.get("memoryBytes", 0) / (1024**3), 2),
                    }
            response["byLocation"] = by_location

        return response


class AuditService:
    """Service for audit log management."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb
        self.audit_log = mongodb.audit_log

    async def log_action(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        actor_type: str,
        actor_id: str,
        success: bool,
        details: dict[str, Any] | None = None,
        error: str | None = None,
        ip: str | None = None,
    ) -> str:
        """Log an audited action.

        Args:
            action: The audit action type.
            resource_type: Type of resource being acted upon.
            resource_id: Identifier of the resource.
            actor_type: Type of actor (user, agent, system).
            actor_id: Identifier of the actor.
            success: Whether the action succeeded.
            details: Optional additional details.
            error: Optional error message if action failed.
            ip: Optional IP address of the actor.

        Returns:
            The generated audit entry ID.
        """
        entry_id = f"audit-{uuid4().hex[:12]}"
        now = datetime.now(UTC)

        entry = {
            "entryId": entry_id,
            "timestamp": now,
            "action": action.value,
            "resource": {
                "type": resource_type,
                "id": resource_id,
            },
            "actor": {
                "type": actor_type,
                "id": actor_id,
                "ip": ip,
            },
            "details": details,
            "result": {
                "success": success,
                "error": error,
            },
        }

        await self.audit_log.insert_one(entry)

        logger.info(
            "audit_logged",
            entry_id=entry_id,
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
        )

        return entry_id

    async def delete_entries_by_window(
        self,
        since: datetime,
        until: datetime,
    ) -> int:
        """Delete audit log entries within a time window.

        Args:
            since: Start of the time window (inclusive).
            until: End of the time window (inclusive).

        Returns:
            Number of entries deleted.
        """
        query = {
            "timestamp": {
                "$gte": since,
                "$lte": until,
            }
        }
        result = await self.audit_log.delete_many(query)
        deleted = result.deleted_count

        logger.info(
            "audit_entries_deleted",
            since=since.isoformat(),
            until=until.isoformat(),
            deleted_count=deleted,
        )

        return deleted

    async def list_entries(
        self, params: AuditListParams
    ) -> tuple[list[dict[str, Any]], int]:
        """List audit log entries with filters.

        Args:
            params: Query parameters including action, resource_type, resource_id,
                actor_id, since, until, offset, and limit.

        Returns:
            Tuple of (audit entries, total count).
        """
        query: dict[str, Any] = {}

        if params.action:
            query["action"] = params.action.value
        if params.resource_type:
            query["resource.type"] = params.resource_type
        if params.resource_id:
            query["resource.id"] = params.resource_id
        if params.actor_id:
            query["actor.id"] = params.actor_id

        date_query = {}
        if params.since:
            date_query["$gte"] = params.since
        if params.until:
            date_query["$lte"] = params.until
        if date_query:
            query["timestamp"] = date_query

        total = await self.audit_log.count_documents(query)

        cursor = self.audit_log.find(query)
        cursor = cursor.sort("timestamp", -1)
        cursor = cursor.skip(params.offset).limit(params.limit)

        entries = await cursor.to_list(length=params.limit)

        return entries, total


# ---------------------------------------------------------------------------
# Module-level helper for audit logging from services
# ---------------------------------------------------------------------------


async def log_audit(
    action: AuditAction,
    resource_type: str,
    resource_id: str,
    actor_type: str,
    actor_id: str,
    success: bool = True,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
    ip: str | None = None,
) -> str | None:
    """Convenience function to log an audit entry from any service.

    Obtains the MongoDB singleton, creates an AuditService,
    and calls log_action(). Returns the entry_id for linking to notifications.
    Unlike emit_notification, this is awaited inline (not fire-and-forget)
    so callers can pass the entry_id to emit_notification().

    Returns None on failure (never raises).
    """
    try:
        from hydra.db.mongodb import get_mongodb

        mongodb = get_mongodb()
        service = AuditService(mongodb)
        return await service.log_action(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_type=actor_type,
            actor_id=actor_id,
            success=success,
            details=details,
            error=error,
            ip=ip,
        )
    except Exception:
        logger.exception(
            "log_audit_helper_failed",
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        return None
