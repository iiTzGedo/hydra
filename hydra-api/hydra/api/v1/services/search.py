"""Global search service."""

import structlog
from pymongo.errors import OperationFailure

from hydra.api.v1.models.search import SearchEntityType
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class SearchService:
    """Global search service across infrastructure entities."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def search(
        self,
        query: str,
        types: list[SearchEntityType] | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> dict:
        """Search across nodes, services, groups, and networks.

        Args:
            query: Search query string.
            types: Entity types to search (all if not specified).
            tags: Filter by tags (AND logic).
            limit: Max results per entity type.

        Returns:
            Grouped search results with query, results, and total.
        """
        search_types = types or list(SearchEntityType)

        results = []
        total = 0

        for entity_type in search_types:
            if entity_type == SearchEntityType.NODES:
                group_result = await self._search_nodes(query, tags, limit)
            elif entity_type == SearchEntityType.SERVICES:
                group_result = await self._search_services(query, tags, limit)
            elif entity_type == SearchEntityType.GROUPS:
                group_result = await self._search_groups(query, tags, limit)
            elif entity_type == SearchEntityType.NETWORKS:
                group_result = await self._search_networks(query, tags, limit)
            else:
                continue

            if group_result["items"]:
                results.append(group_result)
                total += group_result["total"]

        logger.info(
            "search_completed",
            query=query,
            types=[t.value for t in search_types],
            total_results=total,
        )

        return {
            "query": query,
            "results": results,
            "total": total,
        }

    async def _search_nodes(
        self,
        query: str,
        tags: list[str] | None,
        limit: int,
    ) -> dict:
        """Search nodes using text index."""
        search_query: dict = {}

        if query:
            search_query["$text"] = {"$search": query}

        if tags:
            search_query["tags"] = {"$all": tags}

        search_query["status"] = {"$ne": "archived"}

        items = []
        projection = {
            "nodeId": 1,
            "displayName": 1,
            "description": 1,
            "tags": 1,
            "score": {"$meta": "textScore"} if query else 1,
        }

        try:
            if query:
                cursor = (
                    self.db.nodes.find(search_query, projection)
                    .sort([("score", {"$meta": "textScore"})])
                    .limit(limit)
                )
            else:
                cursor = self.db.nodes.find(search_query, projection).limit(limit)

            async for doc in cursor:
                items.append({
                    "entity_type": SearchEntityType.NODES,
                    "id": doc["nodeId"],
                    "name": doc.get("displayName", doc["nodeId"]),
                    "description": doc.get("description"),
                    "tags": doc.get("tags", []),
                    "score": doc.get("score"),
                })
        except OperationFailure as e:
            logger.warning("text_search_failed", collection="nodes", error=str(e), error_type="operation_failure")
            items = await self._regex_search_nodes(query, tags, limit)
        except Exception as e:
            logger.error("text_search_unexpected_error", collection="nodes", error=str(e), error_type=type(e).__name__)
            items = await self._regex_search_nodes(query, tags, limit)

        total = await self.db.nodes.count_documents(search_query) if search_query else len(items)

        return {
            "entity_type": SearchEntityType.NODES,
            "items": items,
            "total": min(total, limit),
        }

    async def _regex_search_nodes(
        self,
        query: str,
        tags: list[str] | None,
        limit: int,
    ) -> list[dict]:
        """Fallback regex search for nodes."""
        search_query: dict = {"status": {"$ne": "archived"}}

        if query:
            regex = {"$regex": query, "$options": "i"}
            search_query["$or"] = [
                {"nodeId": regex},
                {"displayName": regex},
                {"description": regex},
            ]

        if tags:
            search_query["tags"] = {"$all": tags}

        items = []
        cursor = self.db.nodes.find(search_query).limit(limit)

        async for doc in cursor:
            items.append({
                "entity_type": SearchEntityType.NODES,
                "id": doc["nodeId"],
                "name": doc.get("displayName", doc["nodeId"]),
                "description": doc.get("description"),
                "tags": doc.get("tags", []),
                "score": None,
            })

        return items

    async def _search_services(
        self,
        query: str,
        tags: list[str] | None,
        limit: int,
    ) -> dict:
        """Search services using text index."""
        search_query: dict = {}

        if query:
            search_query["$text"] = {"$search": query}

        if tags:
            search_query["tags"] = {"$all": tags}

        items = []
        projection = {
            "serviceId": 1,
            "name": 1,
            "displayName": 1,
            "description": 1,
            "tags": 1,
            "score": {"$meta": "textScore"} if query else 1,
        }

        try:
            if query:
                cursor = (
                    self.db.services.find(search_query, projection)
                    .sort([("score", {"$meta": "textScore"})])
                    .limit(limit)
                )
            else:
                cursor = self.db.services.find(search_query, projection).limit(limit)

            async for doc in cursor:
                items.append({
                    "entity_type": SearchEntityType.SERVICES,
                    "id": doc["serviceId"],
                    "name": doc.get("displayName", doc.get("name", doc["serviceId"])),
                    "description": doc.get("description"),
                    "tags": doc.get("tags", []),
                    "score": doc.get("score"),
                })
        except OperationFailure as e:
            logger.warning("text_search_failed", collection="services", error=str(e), error_type="operation_failure")
            items = await self._regex_search_services(query, tags, limit)
        except Exception as e:
            logger.error("text_search_unexpected_error", collection="services", error=str(e), error_type=type(e).__name__)
            items = await self._regex_search_services(query, tags, limit)

        total = await self.db.services.count_documents(search_query) if search_query else len(items)

        return {
            "entity_type": SearchEntityType.SERVICES,
            "items": items,
            "total": min(total, limit),
        }

    async def _regex_search_services(
        self,
        query: str,
        tags: list[str] | None,
        limit: int,
    ) -> list[dict]:
        """Fallback regex search for services."""
        search_query: dict = {}

        if query:
            regex = {"$regex": query, "$options": "i"}
            search_query["$or"] = [
                {"serviceId": regex},
                {"name": regex},
                {"displayName": regex},
                {"description": regex},
            ]

        if tags:
            search_query["tags"] = {"$all": tags}

        items = []
        cursor = self.db.services.find(search_query).limit(limit)

        async for doc in cursor:
            items.append({
                "entity_type": SearchEntityType.SERVICES,
                "id": doc["serviceId"],
                "name": doc.get("displayName", doc.get("name", doc["serviceId"])),
                "description": doc.get("description"),
                "tags": doc.get("tags", []),
                "score": None,
            })

        return items

    async def _search_groups(
        self,
        query: str,
        tags: list[str] | None,
        limit: int,
    ) -> dict:
        """Search groups."""
        search_query: dict = {}

        if query:
            regex = {"$regex": query, "$options": "i"}
            search_query["$or"] = [
                {"groupId": regex},
                {"name": regex},
                {"description": regex},
            ]

        if tags:
            search_query["tags"] = {"$all": tags}

        items = []
        cursor = self.db.groups.find(search_query).limit(limit)

        async for doc in cursor:
            items.append({
                "entity_type": SearchEntityType.GROUPS,
                "id": doc["groupId"],
                "name": doc.get("name", doc["groupId"]),
                "description": doc.get("description"),
                "tags": doc.get("tags", []),
                "score": None,
            })

        total = await self.db.groups.count_documents(search_query)

        return {
            "entity_type": SearchEntityType.GROUPS,
            "items": items,
            "total": min(total, limit),
        }

    async def _search_networks(
        self,
        query: str,
        tags: list[str] | None,
        limit: int,
    ) -> dict:
        """Search networks."""
        search_query: dict = {}

        if query:
            regex = {"$regex": query, "$options": "i"}
            search_query["$or"] = [
                {"networkId": regex},
                {"name": regex},
                {"cidr": regex},
                {"description": regex},
            ]

        if tags:
            search_query["tags"] = {"$all": tags}

        items = []
        cursor = self.db.networks.find(search_query).limit(limit)

        async for doc in cursor:
            items.append({
                "entity_type": SearchEntityType.NETWORKS,
                "id": doc["networkId"],
                "name": doc.get("name", doc["networkId"]),
                "description": doc.get("description"),
                "tags": doc.get("tags", []),
                "score": None,
            })

        total = await self.db.networks.count_documents(search_query)

        return {
            "entity_type": SearchEntityType.NETWORKS,
            "items": items,
            "total": min(total, limit),
        }
