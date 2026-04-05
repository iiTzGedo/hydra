"""Group management service with selector resolution."""

import re
from datetime import UTC, datetime
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import ConflictError, GroupNotFoundError, ValidationError
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.groups import (
    CreateGroupRequest,
    GroupEntityType,
    GroupListParams,
    GroupSelectors,
    UpdateGroupRequest,
)
from hydra.api.v1.models.notifications import NotificationSource, NotificationType, SourceComponent
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

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
    ) -> dict[str, Any]:
        """Retrieve a group by its identifier.

        Args:
            group_id: The unique group identifier.
            resolve_members: Whether to resolve and include group members.
            member_limit: Maximum number of members to return if resolving.

        Returns:
            The formatted group document, optionally with resolved members.

        Raises:
            GroupNotFoundError: If no group exists with the given ID.
        """
        group = await self.db.groups.find_one({"groupId": group_id})
        if not group:
            raise GroupNotFoundError(group_id)

        result = self._format_group(group)

        if resolve_members:
            members = await self._resolve_members(group, limit=member_limit)
            result["members"] = members

        return result

    async def list_groups(self, params: GroupListParams) -> tuple[list[dict[str, Any]], int]:
        """List groups with filtering and pagination.

        Args:
            params: Filter, sort, and pagination parameters.

        Returns:
            Tuple of (groups list, total count).
        """
        filter_query: dict[str, Any] = {}

        if params.types:
            filter_query["types"] = {"$in": [t.value for t in params.types]}
        if params.parent_group_id:
            filter_query["parentGroupIds"] = params.parent_group_id
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.search:
            escaped = re.escape(params.search)
            filter_query["$or"] = [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"groupId": {"$regex": escaped, "$options": "i"}},
                {"description": {"$regex": escaped, "$options": "i"}},
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

    async def create_group(self, request: CreateGroupRequest) -> dict[str, Any]:
        """Create a new group with selectors.

        Args:
            request: Group creation request with selectors.

        Returns:
            The created group document.

        Raises:
            GroupAlreadyExistsError: If a group with the same ID exists.
            ValidationError: If a parent group does not exist.
        """
        existing = await self.db.groups.find_one({"groupId": request.group_id})
        if existing:
            raise GroupAlreadyExistsError(request.group_id)

        if request.parent_group_ids:
            parent_ids = list(set(request.parent_group_ids))
            found_parents = await self.db.groups.find(
                {"groupId": {"$in": parent_ids}}
            ).to_list(length=len(parent_ids))
            found_ids = {p["groupId"] for p in found_parents}
            for parent_id in parent_ids:
                if parent_id not in found_ids:
                    raise GroupNotFoundError(parent_id)

        now = datetime.now(UTC)

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
        await self._update_member_count(request.group_id)

        logger.info("group_created", group_id=request.group_id)

        return await self.get_group(request.group_id)

    async def update_group(self, group_id: str, request: UpdateGroupRequest) -> dict[str, Any]:
        """Update group metadata and selectors.

        Args:
            group_id: The group identifier to update.
            request: Fields to update.

        Returns:
            The updated group document.

        Raises:
            GroupNotFoundError: If the group does not exist.
            ValidationError: If validation fails for parent groups.
        """
        existing = await self.db.groups.find_one({"groupId": group_id})
        if not existing:
            raise GroupNotFoundError(group_id)

        update_fields: dict[str, Any] = {"updatedAt": datetime.now(UTC)}

        if request.name is not None:
            update_fields["name"] = request.name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.selectors is not None:
            update_fields["selectors"] = request.selectors.model_dump(by_alias=True, exclude_none=True)
        if request.parent_group_ids is not None:
            if group_id in request.parent_group_ids:
                raise ValidationError("Group cannot be its own parent")
            parent_ids = list(set(request.parent_group_ids))
            if parent_ids:
                found_parents = await self.db.groups.find(
                    {"groupId": {"$in": parent_ids}}
                ).to_list(length=len(parent_ids))
                found_ids = {p["groupId"] for p in found_parents}
                for parent_id in parent_ids:
                    if parent_id not in found_ids:
                        raise GroupNotFoundError(parent_id)
            update_fields["parentGroupIds"] = request.parent_group_ids
        if request.tags is not None:
            update_fields["tags"] = request.tags

        await self.db.groups.update_one(
            {"groupId": group_id},
            {"$set": update_fields},
        )

        if request.selectors is not None:
            await self._update_member_count(group_id)

        logger.info("group_updated", group_id=group_id, fields=list(update_fields.keys()))

        return await self.get_group(group_id)

    async def delete_group(self, group_id: str) -> dict[str, Any]:
        """Delete a group and remove it from parent references.

        Args:
            group_id: The group identifier to delete.

        Returns:
            The deleted group document.

        Raises:
            GroupNotFoundError: If the group does not exist.
        """
        existing = await self.db.groups.find_one({"groupId": group_id})
        if not existing:
            raise GroupNotFoundError(group_id)

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
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Get resolved members for a group with pagination.

        Args:
            group_id: The group identifier.
            entity_type: Optional filter for entity type (node or service).
            limit: Maximum number of members per type.
            offset: Pagination offset.

        Returns:
            Tuple of (members dict by type, totals dict).

        Raises:
            GroupNotFoundError: If the group does not exist.
        """
        group = await self.db.groups.find_one({"groupId": group_id})
        if not group:
            raise GroupNotFoundError(group_id)

        selectors = GroupSelectors(**group.get("selectors", {}))

        members = {"nodes": [], "services": []}  # type: ignore[var-annotated]
        totals = {"nodes": 0, "services": 0}

        if (entity_type is None or entity_type == GroupEntityType.NODE) and GroupEntityType.NODE.value in group.get("types", []):
            nodes, node_total = await self._resolve_nodes(selectors, limit, offset)
            members["nodes"] = nodes
            totals["nodes"] = node_total

        if (entity_type is None or entity_type == GroupEntityType.SERVICE) and GroupEntityType.SERVICE.value in group.get("types", []):
            services, service_total = await self._resolve_services(selectors, limit, offset)
            members["services"] = services
            totals["services"] = service_total

        return members, totals

    async def resolve_group(self, group_id: str) -> dict[str, Any]:
        """Force re-resolution of group membership counts.

        Args:
            group_id: The group identifier to resolve.

        Returns:
            Resolution result with old and new counts and changes.

        Raises:
            GroupNotFoundError: If the group does not exist.
        """
        group = await self.db.groups.find_one({"groupId": group_id})
        if not group:
            raise GroupNotFoundError(group_id)

        old_count = group.get("memberCount", {})
        await self._update_member_count(group_id)

        updated_group = await self.db.groups.find_one({"groupId": group_id})
        new_count = updated_group.get("memberCount", {})  # type: ignore[union-attr]

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

        total_members = new_count.get("nodes", 0) + new_count.get("services", 0)
        group_name = updated_group.get("name", group_id)  # type: ignore[union-attr]
        audit_id = await log_audit(
            action=AuditAction.UPDATE,
            resource_type="group",
            resource_id=group_id,
            actor_type="system",
            actor_id="group_resolver",
            details={
                "groupName": group_name,
                "memberCount": {
                    "nodes": new_count.get("nodes", 0),
                    "services": new_count.get("services", 0),
                    "total": total_members,
                },
                "changes": changes,
            },
        )
        safe_create_task(emit_notification(
            notification_type=NotificationType.GROUP_MEMBERSHIP_CHANGED,
            source=NotificationSource(
                component=SourceComponent.HYDRA_API,
                service="groups",
            ),
            title="Group membership changed",
            message=f"Group {group_name} membership updated ({total_members} members)",
            details={
                "groupId": group_id,
                "memberCount": {
                    "nodes": new_count.get("nodes", 0),
                    "services": new_count.get("services", 0),
                    "total": total_members,
                },
                "changes": changes,
            },
            audit_entry_id=audit_id,
        ))

        return {
            "groupId": group_id,
            "memberCount": new_count,
            "changes": changes,
        }

    async def _resolve_members(self, group: dict[str, Any], limit: int = 20) -> dict[str, Any]:
        """Resolve group members based on selectors."""
        selectors = GroupSelectors(**group.get("selectors", {}))
        types = group.get("types", [])

        members = {"nodes": [], "services": []}  # type: ignore[var-annotated]

        if "node" in types:
            nodes, _ = await self._resolve_nodes(selectors, limit=limit, offset=0)
            members["nodes"] = nodes

        if "service" in types:
            services, _ = await self._resolve_services(selectors, limit=limit, offset=0)
            members["services"] = services

        return members

    async def get_member_node_ids(self, group_id: str) -> list[str]:
        """Get node IDs belonging to a group via selector resolution.

        Lightweight method that returns only node IDs without full member details.

        Args:
            group_id: The group identifier.

        Returns:
            List of node IDs matching the group's selectors.

        Raises:
            GroupNotFoundError: If the group does not exist.
        """
        group = await self.db.groups.find_one({"groupId": group_id})
        if not group:
            raise GroupNotFoundError(group_id)

        if "node" not in group.get("types", []):
            return []

        selectors = GroupSelectors(**group.get("selectors", {}))
        filter_query = self._build_node_filter(selectors)
        if not filter_query:
            return []

        cursor = self.db.nodes.find(filter_query, {"nodeId": 1, "_id": 0})
        return [doc["nodeId"] async for doc in cursor]

    async def _resolve_nodes(
        self,
        selectors: GroupSelectors,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
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
    ) -> tuple[list[dict[str, Any]], int]:
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

        if selectors.id and selectors.id.is_all:
            conditions.append({"nodeId": {"$in": selectors.id.is_all}})

        if selectors.network and selectors.network.is_any:
            conditions.append({"networkIds": {"$in": selectors.network.is_any}})

        if selectors.status and selectors.status.is_any:
            conditions.append({"status": {"$in": selectors.status.is_any}})

        if selectors.kind and selectors.kind.is_any:
            conditions.append({"kind": {"$in": selectors.kind.is_any}})

        if selectors.tags and selectors.tags.is_any:
            conditions.append({"tags": {"$in": selectors.tags.is_any}})

        if selectors.tags and selectors.tags.is_all:
            conditions.append({"tags": {"$all": selectors.tags.is_all}})

        if not conditions:
            return {}

        return {"$or": conditions} if len(conditions) > 1 else conditions[0]

    def _build_service_filter(self, selectors: GroupSelectors) -> dict[str, Any]:
        """Build MongoDB filter for service selection."""
        conditions = []

        if selectors.id and selectors.id.is_all:
            conditions.append({"serviceId": {"$in": selectors.id.is_all}})

        if selectors.runtime and selectors.runtime.is_any:
            conditions.append({"runtime": {"$in": selectors.runtime.is_any}})

        if selectors.status and selectors.status.is_any:
            conditions.append({"status": {"$in": selectors.status.is_any}})

        if selectors.tags and selectors.tags.is_any:
            conditions.append({"tags": {"$in": selectors.tags.is_any}})

        if selectors.tags and selectors.tags.is_all:
            conditions.append({"tags": {"$all": selectors.tags.is_all}})

        if not conditions:
            return {}

        return {"$or": conditions} if len(conditions) > 1 else conditions[0]

    def _get_matched_selectors(
        self,
        entity: dict[str, Any],
        selectors: GroupSelectors,
        entity_type: str,
    ) -> list[str]:
        """Get list of selector names that matched this entity."""
        matched = []

        if selectors.id and selectors.id.is_all:
            id_field = "nodeId" if entity_type == "node" else "serviceId"
            if entity.get(id_field) in selectors.id.is_all:
                matched.append("id.isAll")

        if entity_type == "node" and selectors.network and selectors.network.is_any:
            entity_networks = set(entity.get("networkIds", []))
            if entity_networks & set(selectors.network.is_any):
                matched.append("network.isAny")

        if selectors.status and selectors.status.is_any and entity.get("status") in selectors.status.is_any:
            matched.append("status.isAny")

        if entity_type == "node" and selectors.kind and selectors.kind.is_any and entity.get("kind") in selectors.kind.is_any:
            matched.append("kind.isAny")

        if entity_type == "service" and selectors.runtime and selectors.runtime.is_any and entity.get("runtime") in selectors.runtime.is_any:
            matched.append("runtime.isAny")

        if selectors.tags and selectors.tags.is_any:
            entity_tags = set(entity.get("tags", []))
            if entity_tags & set(selectors.tags.is_any):
                matched.append("tags.isAny")

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
                        "lastComputed": datetime.now(UTC),
                    }
                }
            },
        )

    async def get_node_groups(self, node_id: str) -> list[dict[str, Any]]:
        """Get all groups that a specific node belongs to.

        Fetches the node once and checks all group selectors in-memory,
        avoiding N+1 queries.

        Args:
            node_id: The node ID to check membership for.

        Returns:
            List of group summaries the node belongs to.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            return []

        # Fetch all groups that include node type
        cursor = self.db.groups.find({
            "$or": [
                {"types": "node"},
                {"types": {"$size": 0}},
                {"types": {"$exists": False}},
            ]
        })

        matching_groups = []
        async for group in cursor:
            selectors = GroupSelectors(**group.get("selectors", {}))
            matched = self._get_matched_selectors(node, selectors, "node")
            if matched:
                summary = self._format_group_summary(group)
                summary["matchedSelectors"] = matched
                matching_groups.append(summary)

        return matching_groups

    def _format_group(self, doc: dict[str, Any]) -> dict[str, Any]:
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

    def _format_group_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a group document for list response."""
        return {
            "groupId": doc["groupId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "types": doc.get("types", []),
            "memberCount": doc.get("memberCount", {"nodes": 0, "services": 0}),
            "tags": doc.get("tags", []),
        }
