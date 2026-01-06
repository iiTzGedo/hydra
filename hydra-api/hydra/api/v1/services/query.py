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
        """Execute a structured query."""
        collection = self._get_collection(request.collection)

        # Build query
        query = request.filter or {}

        # Get total count
        total = await collection.count_documents(query)

        # Build cursor
        cursor = collection.find(query, projection=request.projection)

        if request.sort:
            sort_list = [(k, v) for k, v in request.sort.items()]
            cursor = cursor.sort(sort_list)

        cursor = cursor.skip(request.skip).limit(request.limit)

        results = await cursor.to_list(length=request.limit)

        # Remove internal MongoDB _id field
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
        """Get infrastructure capacity summary."""
        # Base query for physical nodes
        query: dict[str, Any] = {"status": "active"}

        if not include_logical:
            query["type"] = "physical"

        if network_id:
            query["networkIds"] = network_id

        # If group_id, we need to resolve group members first
        if group_id:
            group = await self.mongodb.groups.find_one({"groupId": group_id})
            if group:
                # Get node IDs from group members
                members = group.get("members", {})
                node_ids = [m.get("nodeId") for m in members.get("nodes", []) if m.get("nodeId")]
                if node_ids:
                    query["nodeId"] = {"$in": node_ids}

        # Aggregate capacity from latest profiles
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
                        "$sum": {"$ifNull": ["$latestProfile.storage.totalBytes", 0]}
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

        # Group by class
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
                            "$sum": {"$ifNull": ["$latestProfile.storage.totalBytes", 0]}
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

        # Group by location
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
        """Log an audited action."""
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

    async def list_entries(
        self, params: AuditListParams
    ) -> tuple[list[dict[str, Any]], int]:
        """List audit log entries with filters."""
        query: dict[str, Any] = {}

        if params.action:
            query["action"] = params.action.value
        if params.resource_type:
            query["resource.type"] = params.resource_type
        if params.resource_id:
            query["resource.id"] = params.resource_id
        if params.actor_id:
            query["actor.id"] = params.actor_id

        # Date range
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
