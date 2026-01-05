"""Group management service with selector resolution."""

from datetime import datetime, timezone
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.v1.core.exceptions import ConflictError, GroupNotFoundError, ValidationError
from hydra.db.mongodb import MongoDB
from hydra.v1.models.groups import (
    CreateGroupRequest,
    GroupEntityType,
    GroupListParams,
    GroupSelectors,
    UpdateGroupRequest,
)

logger = structlog.get_logger(__name__)


class GroupAlreadyExistsError(ConflictError):
    """Group already exists."""

    def __init__(self, group_id: str):
        super().__init__("group", group_id)


class GroupsService:
    """Service for group management with selector resolution."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_group(
        self,
        group_id: str,
        resolve_members: bool = False,
        member_limit: int = 20,
    ) -> dict:
        """Get a single group by ID."""
        group = await self.db.groups.find_one({"groupId": group_id})
        if not group:
            raise GroupNotFoundError(group_id)

        result = self._format_group(group)

        if resolve_members:
            members = await self._resolve_members(group, limit=member_limit)
            result["members"] = members

        return result

    async def list_groups(self, params: GroupListParams) -> tuple[list[dict], int]:
        """
        List groups with filters and pagination.

        Returns:
            Tuple of (groups list, total count)
        """
        filter_query: dict[str, Any] = {}

        if params.types:
            filter_query["types"] = {"$in": [t.value for t in params.types]}
        if params.parent_group_id:
            filter_query["parentGroupIds"] = params.parent_group_id
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.search:
            filter_query["$or"] = [
                {"name": {"$regex": params.search, "$options": "i"}},
                {"groupId": {"$regex": params.search, "$options": "i"}},
                {"description": {"$regex": params.search, "$options": "i"}},
            ]

        sort_field_map = {
            "groupId": "groupId",
            "name": "name",
            "createdAt": "createdAt",
            "updatedAt": "updatedAt",
        }
        sort_field = sort_field_map.get(params.sort_by, "updatedAt")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        total = await self.db.groups.count_documents(filter_query)

        cursor = (
            self.db.groups.find(filter_query)
            .sort(sort_field, sort_direction)
            .skip(params.offset)
            .limit(params.limit)
        )

        groups = []
        async for group in cursor:
            groups.append(self._format_group_summary(group))

        logger.info(
            "groups_listed",
            total=total,
            returned=len(groups),
        )

        return groups, total

    async def create_group(self, request: CreateGroupRequest) -> dict:
        """Create a new group."""
        existing = await self.db.groups.find_one({"groupId": request.group_id})
        if existing:
            raise GroupAlreadyExistsError(request.group_id)

        # Validate parent groups if specified
        for parent_id in request.parent_group_ids:
            parent = await self.db.groups.find_one({"groupId": parent_id})
            if not parent:
                raise ValidationError(
                    f"Parent group '{parent_id}' not found",
                    {"parentGroupId": parent_id},
                )

        now = datetime.now(timezone.utc)

        group_doc = {
            "groupId": request.group_id,
            "name": request.name,
            "description": request.description,
            "types": [t.value for t in request.types],
            "selectors": request.selectors.model_dump(by_alias=True, exclude_none=True),
            "parentGroupIds": request.parent_group_ids,
            "memberCount": {
                "nodes": 0,
                "services": 0,
                "lastComputed": None,
            },
            "tags": request.tags,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.groups.insert_one(group_doc)

        # Resolve members after creation
        await self._update_member_count(request.group_id)

        logger.info("group_created", group_id=request.group_id)

        return await self.get_group(request.group_id)

    async def update_group(self, group_id: str, request: UpdateGroupRequest) -> dict:
        """Update group metadata."""
        existing = await self.db.groups.find_one({"groupId": group_id})
        if not existing:
            raise GroupNotFoundError(group_id)

        update_fields: dict[str, Any] = {"updatedAt": datetime.now(timezone.utc)}

        if request.name is not None:
            update_fields["name"] = request.name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.selectors is not None:
            update_fields["selectors"] = request.selectors.model_dump(by_alias=True, exclude_none=True)
        if request.parent_group_ids is not None:
            # Validate parent groups
            for parent_id in request.parent_group_ids:
                if parent_id == group_id:
                    raise ValidationError("Group cannot be its own parent")
                parent = await self.db.groups.find_one({"groupId": parent_id})
                if not parent:
                    raise ValidationError(
                        f"Parent group '{parent_id}' not found",
                        {"parentGroupId": parent_id},
                    )
            update_fields["parentGroupIds"] = request.parent_group_ids
        if request.tags is not None:
            update_fields["tags"] = request.tags

        await self.db.groups.update_one(
            {"groupId": group_id},
            {"$set": update_fields},
        )

        # Re-resolve members if selectors changed
        if request.selectors is not None:
            await self._update_member_count(group_id)

        logger.info("group_updated", group_id=group_id, fields=list(update_fields.keys()))

        return await self.get_group(group_id)

    async def delete_group(self, group_id: str) -> dict:
        """Delete a group."""
        existing = await self.db.groups.find_one({"groupId": group_id})
        if not existing:
            raise GroupNotFoundError(group_id)

        # Remove from parent references in other groups
        await self.db.groups.update_many(
            {"parentGroupIds": group_id},
            {"$pull": {"parentGroupIds": group_id}},
        )

        await self.db.groups.delete_one({"groupId": group_id})

        logger.info("group_deleted", group_id=group_id)

        return self._format_group(existing)

    async def get_group_members(
        self,
        group_id: str,
        entity_type: GroupEntityType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[dict, dict]:
        """
        Get resolved members for a group with pagination.

        Returns:
            Tuple of (members dict, totals dict)
        """
        group = await self.db.groups.find_one({"groupId": group_id})
        if not group:
            raise GroupNotFoundError(group_id)

        selectors = GroupSelectors(**group.get("selectors", {}))
        types = [GroupEntityType(t) for t in group.get("types", [])]

        members = {"nodes": [], "services": []}
        totals = {"nodes": 0, "services": 0}

        # Resolve nodes if applicable
        if (entity_type is None or entity_type == GroupEntityType.NODE) and GroupEntityType.NODE.value in group.get("types", []):
            nodes, node_total = await self._resolve_nodes(selectors, limit, offset)
            members["nodes"] = nodes
            totals["nodes"] = node_total

        # Resolve services if applicable
        if (entity_type is None or entity_type == GroupEntityType.SERVICE) and GroupEntityType.SERVICE.value in group.get("types", []):
            services, service_total = await self._resolve_services(selectors, limit, offset)
            members["services"] = services
            totals["services"] = service_total

        return members, totals

    async def resolve_group(self, group_id: str) -> dict:
        """Force re-resolution of group membership."""
        group = await self.db.groups.find_one({"groupId": group_id})
        if not group:
            raise GroupNotFoundError(group_id)

        old_count = group.get("memberCount", {})
        await self._update_member_count(group_id)

        updated_group = await self.db.groups.find_one({"groupId": group_id})
        new_count = updated_group.get("memberCount", {})

        changes = {
            "nodesChanged": new_count.get("nodes", 0) - old_count.get("nodes", 0),
            "servicesChanged": new_count.get("services", 0) - old_count.get("services", 0),
        }

        logger.info(
            "group_resolved",
            group_id=group_id,
            old_nodes=old_count.get("nodes", 0),
            new_nodes=new_count.get("nodes", 0),
            old_services=old_count.get("services", 0),
            new_services=new_count.get("services", 0),
        )

        return {
            "groupId": group_id,
            "memberCount": new_count,
            "changes": changes,
        }

    async def _resolve_members(self, group: dict, limit: int = 20) -> dict:
        """Resolve group members based on selectors."""
        selectors = GroupSelectors(**group.get("selectors", {}))
        types = group.get("types", [])

        members = {"nodes": [], "services": []}

        if "node" in types:
            nodes, _ = await self._resolve_nodes(selectors, limit=limit, offset=0)
            members["nodes"] = nodes

        if "service" in types:
            services, _ = await self._resolve_services(selectors, limit=limit, offset=0)
            members["services"] = services

        return members

    async def _resolve_nodes(
        self,
        selectors: GroupSelectors,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        """Resolve nodes matching selectors."""
        filter_query = self._build_node_filter(selectors)

        if not filter_query:
            return [], 0

        total = await self.db.nodes.count_documents(filter_query)

        cursor = (
            self.db.nodes.find(filter_query)
            .skip(offset)
            .limit(limit)
        )

        nodes = []
        async for node in cursor:
            matched = self._get_matched_selectors(node, selectors, "node")
            nodes.append({
                "nodeId": node["nodeId"],
                "displayName": node["displayName"],
                "matchedSelectors": matched,
            })

        return nodes, total

    async def _resolve_services(
        self,
        selectors: GroupSelectors,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        """Resolve services matching selectors."""
        filter_query = self._build_service_filter(selectors)

        if not filter_query:
            return [], 0

        total = await self.db.services.count_documents(filter_query)

        cursor = (
            self.db.services.find(filter_query)
            .skip(offset)
            .limit(limit)
        )

        services = []
        async for svc in cursor:
            matched = self._get_matched_selectors(svc, selectors, "service")
            services.append({
                "serviceId": svc["serviceId"],
                "name": svc["name"],
                "nodeId": svc["nodeId"],
                "matchedSelectors": matched,
            })

        return services, total

    def _build_node_filter(self, selectors: GroupSelectors) -> dict[str, Any]:
        """Build MongoDB filter for node selection."""
        conditions = []

        # id.isAll - explicit node IDs
        if selectors.id and selectors.id.is_all:
            conditions.append({"nodeId": {"$in": selectors.id.is_all}})

        # network.isAny - nodes in any listed network
        if selectors.network and selectors.network.is_any:
            conditions.append({"networkIds": {"$in": selectors.network.is_any}})

        # status.isAny - nodes with any listed status
        if selectors.status and selectors.status.is_any:
            conditions.append({"status": {"$in": selectors.status.is_any}})

        # kind.isAny - nodes with any listed kind
        if selectors.kind and selectors.kind.is_any:
            conditions.append({"kind": {"$in": selectors.kind.is_any}})

        # tags.isAny - nodes with any listed tag
        if selectors.tags and selectors.tags.is_any:
            conditions.append({"tags": {"$in": selectors.tags.is_any}})

        # tags.isAll - nodes with all listed tags
        if selectors.tags and selectors.tags.is_all:
            conditions.append({"tags": {"$all": selectors.tags.is_all}})

        if not conditions:
            return {}

        # OR logic between different selector types
        return {"$or": conditions} if len(conditions) > 1 else conditions[0]

    def _build_service_filter(self, selectors: GroupSelectors) -> dict[str, Any]:
        """Build MongoDB filter for service selection."""
        conditions = []

        # id.isAll - explicit service IDs
        if selectors.id and selectors.id.is_all:
            conditions.append({"serviceId": {"$in": selectors.id.is_all}})

        # runtime.isAny - services with any listed runtime
        if selectors.runtime and selectors.runtime.is_any:
            conditions.append({"runtime": {"$in": selectors.runtime.is_any}})

        # status.isAny - services with any listed status
        if selectors.status and selectors.status.is_any:
            conditions.append({"status": {"$in": selectors.status.is_any}})

        # tags.isAny - services with any listed tag
        if selectors.tags and selectors.tags.is_any:
            conditions.append({"tags": {"$in": selectors.tags.is_any}})

        # tags.isAll - services with all listed tags
        if selectors.tags and selectors.tags.is_all:
            conditions.append({"tags": {"$all": selectors.tags.is_all}})

        if not conditions:
            return {}

        return {"$or": conditions} if len(conditions) > 1 else conditions[0]

    def _get_matched_selectors(
        self,
        entity: dict,
        selectors: GroupSelectors,
        entity_type: str,
    ) -> list[str]:
        """Get list of selector names that matched this entity."""
        matched = []

        # id.isAll
        if selectors.id and selectors.id.is_all:
            id_field = "nodeId" if entity_type == "node" else "serviceId"
            if entity.get(id_field) in selectors.id.is_all:
                matched.append("id.isAll")

        # network.isAny (nodes only)
        if entity_type == "node" and selectors.network and selectors.network.is_any:
            entity_networks = set(entity.get("networkIds", []))
            if entity_networks & set(selectors.network.is_any):
                matched.append("network.isAny")

        # status.isAny
        if selectors.status and selectors.status.is_any:
            if entity.get("status") in selectors.status.is_any:
                matched.append("status.isAny")

        # kind.isAny (nodes only)
        if entity_type == "node" and selectors.kind and selectors.kind.is_any:
            if entity.get("kind") in selectors.kind.is_any:
                matched.append("kind.isAny")

        # runtime.isAny (services only)
        if entity_type == "service" and selectors.runtime and selectors.runtime.is_any:
            if entity.get("runtime") in selectors.runtime.is_any:
                matched.append("runtime.isAny")

        # tags.isAny
        if selectors.tags and selectors.tags.is_any:
            entity_tags = set(entity.get("tags", []))
            if entity_tags & set(selectors.tags.is_any):
                matched.append("tags.isAny")

        # tags.isAll
        if selectors.tags and selectors.tags.is_all:
            entity_tags = set(entity.get("tags", []))
            if set(selectors.tags.is_all).issubset(entity_tags):
                matched.append("tags.isAll")

        return matched

    async def _update_member_count(self, group_id: str) -> None:
        """Update the cached member count for a group."""
        group = await self.db.groups.find_one({"groupId": group_id})
        if not group:
            return

        selectors = GroupSelectors(**group.get("selectors", {}))
        types = group.get("types", [])

        node_count = 0
        service_count = 0

        if "node" in types:
            filter_query = self._build_node_filter(selectors)
            if filter_query:
                node_count = await self.db.nodes.count_documents(filter_query)

        if "service" in types:
            filter_query = self._build_service_filter(selectors)
            if filter_query:
                service_count = await self.db.services.count_documents(filter_query)

        await self.db.groups.update_one(
            {"groupId": group_id},
            {
                "$set": {
                    "memberCount": {
                        "nodes": node_count,
                        "services": service_count,
                        "lastComputed": datetime.now(timezone.utc),
                    }
                }
            },
        )

    def _format_group(self, doc: dict) -> dict:
        """Format a group document for API response."""
        return {
            "groupId": doc["groupId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "types": doc.get("types", []),
            "selectors": doc.get("selectors", {}),
            "parentGroupIds": doc.get("parentGroupIds", []),
            "memberCount": doc.get("memberCount", {"nodes": 0, "services": 0}),
            "tags": doc.get("tags", []),
            "createdAt": doc.get("createdAt"),
            "updatedAt": doc.get("updatedAt"),
        }

    def _format_group_summary(self, doc: dict) -> dict:
        """Format a group document for list response."""
        return {
            "groupId": doc["groupId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "types": doc.get("types", []),
            "memberCount": doc.get("memberCount", {"nodes": 0, "services": 0}),
            "tags": doc.get("tags", []),
        }
