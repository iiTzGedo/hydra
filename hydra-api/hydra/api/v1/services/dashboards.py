"""Dashboard management service."""

import copy
import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.dashboards import (
    AddWidgetRequest,
    CreateBoardRequest,
    DashboardListParams,
    SaveAsTemplateRequest,
    ShareBoardRequest,
    UpdateBoardRequest,
    UpdateWidgetRequest,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)

# ── Widget Registry ─────────────────────────────────────────────────

COMMON_WIDGET_CONFIG_SCHEMA: list[dict[str, object]] = [
    {
        "key": "title",
        "label": "Title",
        "fieldType": "text",
        "description": "Optional display title override for the widget header.",
        "placeholder": "Leave blank to use the default title",
    },
    {
        "key": "subtitle",
        "label": "Subtitle",
        "fieldType": "text",
        "description": "Short supporting text shown under the title.",
        "placeholder": "Optional supporting context",
    },
    {
        "key": "collapsible",
        "label": "Collapsible",
        "fieldType": "boolean",
        "description": "Allow the widget body to be collapsed from the header.",
    },
    {
        "key": "defaultCollapsed",
        "label": "Start collapsed",
        "fieldType": "boolean",
        "description": "Collapse the widget body when the board first loads.",
    },
]


def _widget_definition(
    *,
    widget_type: str,
    display_name: str,
    description: str,
    category: str,
    icon: str,
    default_size: dict[str, int],
    min_size: dict[str, int],
    max_size: dict[str, int],
    source: str = "hydra",
    config_schema: list[dict[str, object]] | None = None,
    repeatable: bool = False,
) -> dict[str, object]:
    return {
        "widgetType": widget_type,
        "displayName": display_name,
        "description": description,
        "category": category,
        "icon": icon,
        "source": source,
        "defaultSize": default_size,
        "minSize": min_size,
        "maxSize": max_size,
        "configSchema": copy.deepcopy(config_schema or COMMON_WIDGET_CONFIG_SCHEMA),
        "capabilities": {
            "configurable": True,
            "supportsVisibilityToggle": True,
            "repeatable": repeatable,
        },
    }


WIDGET_REGISTRY: list[dict[str, object]] = [
    _widget_definition(
        widget_type="hydra::stats-cards",
        display_name="Stats Overview",
        description="Key infrastructure metrics at a glance.",
        category="data-display",
        icon="bar-chart-3",
        default_size={"w": 12, "h": 2},
        min_size={"w": 6, "h": 2},
        max_size={"w": 12, "h": 4},
    ),
    _widget_definition(
        widget_type="hydra::capacity-overview",
        display_name="Capacity Overview",
        description="Resource utilization and capacity planning for your fleet.",
        category="infrastructure",
        icon="hard-drive",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 6},
    ),
    _widget_definition(
        widget_type="hydra::service-summary",
        display_name="Service Summary",
        description="Overview of service health and operational status.",
        category="status",
        icon="activity",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 6},
    ),
    _widget_definition(
        widget_type="hydra::recent-activity",
        display_name="Recent Activity",
        description="Latest infrastructure events and state changes.",
        category="activity",
        icon="clock",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 6},
    ),
    _widget_definition(
        widget_type="hydra::mini-topology",
        display_name="Infrastructure Topology",
        description="Visual map of the current topology snapshot.",
        category="infrastructure",
        icon="network",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 8},
    ),
    _widget_definition(
        widget_type="hydra::node-status-grid",
        display_name="Node Status Grid",
        description="Grid view of node health, reachability, and role.",
        category="status",
        icon="server",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 6},
    ),
    _widget_definition(
        widget_type="hydra::clock",
        display_name="Clock",
        description="Minimal time and timezone display for glanceable boards.",
        category="utility",
        icon="clock-3",
        default_size={"w": 3, "h": 2},
        min_size={"w": 2, "h": 2},
        max_size={"w": 4, "h": 3},
        source="external",
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "timezone",
                "label": "Timezone",
                "fieldType": "text",
                "description": "IANA timezone identifier, for example Europe/London.",
                "placeholder": "Europe/London",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::rss-feed",
        display_name="RSS Feed",
        description="Render headlines from an RSS or Atom feed.",
        category="content",
        icon="rss",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        source="external",
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "feedUrl",
                "label": "Feed URL",
                "fieldType": "text",
                "description": "Public RSS or Atom feed URL.",
                "placeholder": "https://example.com/feed.xml",
            },
            {
                "key": "maxItems",
                "label": "Items",
                "fieldType": "number",
                "description": "Maximum number of entries to show.",
                "minValue": 1,
                "maxValue": 20,
            },
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::bookmark-grid",
        display_name="Bookmark Grid",
        description="Pinned links for internal tools and external dashboards.",
        category="content",
        icon="bookmark",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        source="external",
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "linksMarkdown",
                "label": "Links",
                "fieldType": "text",
                "description": "One link per line in Markdown format: [Label](https://example.com).",
                "placeholder": "[Glance](https://github.com/glanceapp/glance)",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::iframe",
        display_name="Embed / Iframe",
        description="Embed a trusted external dashboard or panel.",
        category="content",
        icon="app-window",
        default_size={"w": 12, "h": 6},
        min_size={"w": 6, "h": 4},
        max_size={"w": 12, "h": 12},
        source="external",
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "src",
                "label": "Source URL",
                "fieldType": "text",
                "description": "Trusted URL to render in an iframe.",
                "placeholder": "https://grafana.example.com/d/overview",
            },
            {
                "key": "allowFullscreen",
                "label": "Allow fullscreen",
                "fieldType": "boolean",
                "description": "Allow the embedded content to request fullscreen mode.",
            },
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::markdown",
        display_name="Markdown Block",
        description="Freeform manual notes, runbooks, or callouts rendered inline.",
        category="content",
        icon="square-pen",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 10},
        source="external",
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "markdown",
                "label": "Markdown",
                "fieldType": "text",
                "description": "Markdown content rendered inside the widget body.",
                "placeholder": "## Notes\\n\\nRemember to rotate backups on Friday.",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::weather",
        display_name="Weather",
        description="Provider-backed weather snapshot for a configured location.",
        category="utility",
        icon="cloud-sun",
        default_size={"w": 4, "h": 3},
        min_size={"w": 3, "h": 2},
        max_size={"w": 6, "h": 4},
        source="external",
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "location",
                "label": "Location",
                "fieldType": "text",
                "description": "City or provider-specific location query.",
                "placeholder": "London, UK",
            },
            {
                "key": "units",
                "label": "Units",
                "fieldType": "select",
                "description": "Preferred temperature units.",
                "options": [
                    {"label": "Metric", "value": "metric"},
                    {"label": "Imperial", "value": "imperial"},
                ],
            },
        ],
        repeatable=True,
    ),
]

WIDGET_REGISTRY_BY_TYPE: dict[str, dict[str, object]] = {
    cast(str, widget["widgetType"]): widget for widget in WIDGET_REGISTRY
}


class DashboardNotFoundError(NotFoundError):
    """Dashboard not found."""

    def __init__(self, board_id: str) -> None:
        super().__init__("dashboard", board_id)


class WidgetNotFoundError(NotFoundError):
    """Widget instance not found on dashboard."""

    def __init__(self, widget_id: str) -> None:
        super().__init__("widget", widget_id)


class DashboardService:
    """Service for dashboard board management operations."""

    def __init__(self, mongodb: MongoDB) -> None:
        self.db = mongodb
        self.collection = mongodb.db["dashboards"]

    def _validate_widget_types(
        self,
        widget_types: list[str],
        *,
        existing_widget_types: list[str] | None = None,
    ) -> None:
        """Validate widget types against the live registry.

        Existing widget types are allowed to persist during board updates even
        if they are no longer advertised in the registry, but callers may not
        add new unsupported widget types or increase a non-repeatable widget's
        count beyond what already exists on the board.
        """
        existing_counts: dict[str, int] = {}
        for widget_type in existing_widget_types or []:
            existing_counts[widget_type] = existing_counts.get(widget_type, 0) + 1

        requested_counts: dict[str, int] = {}
        for widget_type in widget_types:
            requested_counts[widget_type] = requested_counts.get(widget_type, 0) + 1

        for widget_type, requested_count in requested_counts.items():
            definition = WIDGET_REGISTRY_BY_TYPE.get(widget_type)
            existing_count = existing_counts.get(widget_type, 0)

            if definition is None:
                if requested_count <= existing_count:
                    continue
                raise ValidationError(
                    f"Widget type '{widget_type}' is not available in the widget registry",
                    {"widgetType": widget_type},
                )

            capabilities = cast(
                dict[str, object],
                definition.get("capabilities", {}),
            )
            repeatable = bool(capabilities.get("repeatable", True))

            if not repeatable and requested_count > 1 and requested_count > existing_count:
                raise ValidationError(
                    f"Widget type '{widget_type}' can only be added once per dashboard",
                    {
                        "widgetType": widget_type,
                        "repeatable": False,
                        "requestedCount": requested_count,
                    },
                )

    async def create_board(
        self,
        request: CreateBoardRequest,
        owner_id: str,
    ) -> dict[str, Any]:
        """Create a new dashboard board.

        Args:
            request: Board creation details.
            owner_id: User ID of the board owner.

        Returns:
            The created board document.
        """
        now = datetime.now(UTC)
        board_id = f"board_{uuid4().hex[:12]}"

        self._validate_widget_types([widget.widget_type for widget in request.widgets])

        # Build widget instances from the request
        widgets: list[dict[str, Any]] = []
        for widget_req in request.widgets:
            instance_id = f"wi_{uuid4().hex[:8]}"
            widget_doc: dict[str, Any] = {
                "instanceId": instance_id,
                **widget_req.model_dump(by_alias=True, exclude_none=True),
            }
            if "dataBinding" not in widget_doc:
                widget_doc["dataBinding"] = None
            widgets.append(widget_doc)

        doc: dict[str, Any] = {
            "boardId": board_id,
            "name": request.name,
            "description": request.description,
            "icon": request.icon,
            "ownerId": owner_id,
            "boardType": request.board_type.value,
            "visibility": request.visibility.value,
            "layout": request.layout.model_dump(by_alias=True, exclude_none=True),
            "widgets": widgets,
            "settings": request.settings.model_dump(by_alias=True),
            "tags": request.tags,
            "isHome": request.is_home,
            "version": 1,
            "clonedFrom": None,
            "createdAt": now,
            "updatedAt": now,
            "archivedAt": None,
        }

        await self.collection.insert_one(doc)

        logger.info("dashboard_created", board_id=board_id, owner_id=owner_id)

        await log_audit(
            AuditAction.CREATE,
            "dashboard",
            board_id,
            "user",
            owner_id,
            True,
            details={"name": request.name, "boardType": request.board_type.value},
        )

        return self._format_board(doc)

    async def get_board(self, board_id: str) -> dict[str, Any]:
        """Retrieve a single board by its identifier.

        Args:
            board_id: The unique board identifier.

        Returns:
            The formatted board document.

        Raises:
            DashboardNotFoundError: If no board exists with the given ID.
        """
        doc = await self.collection.find_one({"boardId": board_id, "archivedAt": None})
        if not doc:
            raise DashboardNotFoundError(board_id)
        return self._format_board(doc)

    async def get_board_for_user(
        self,
        board_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Retrieve a single board visible to the requesting user."""
        doc = await self._get_visible_board(board_id, user_id)
        return self._format_board(doc)

    async def list_boards(
        self,
        params: DashboardListParams,
        user_id: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """List boards with filtering, sorting, and pagination.

        Owner filtering: users see their own boards plus shared and public boards.

        Args:
            params: Filter and pagination parameters.
            user_id: The requesting user's ID for ownership filtering.

        Returns:
            A tuple of (list of board summaries, total count).
        """
        # Base filter: not archived, and either owned by user or shared/public
        # For shared boards, also match if user is in allowedUsers (or no allowedUsers set)
        filter_query: dict[str, Any] = {
            "archivedAt": None,
            "$or": [
                {"ownerId": user_id},
                {"visibility": "public"},
                {
                    "visibility": "shared",
                    "$or": [
                        {"allowedUsers": {"$exists": False}},
                        {"allowedUsers": {"$size": 0}},
                        {"allowedUsers": user_id},
                    ],
                },
            ],
        }

        if params.board_type:
            filter_query["boardType"] = params.board_type.value
        if params.visibility:
            filter_query["visibility"] = params.visibility.value
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.search:
            escaped = re.escape(params.search)
            filter_query["$or"] = [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"description": {"$regex": escaped, "$options": "i"}},
            ]
            # When searching, we still need the ownership/visibility filter
            # Restructure as $and to combine both $or conditions
            ownership_filter = {
                "$or": [
                    {"ownerId": user_id},
                    {"visibility": {"$in": ["shared", "public"]}},
                ]
            }
            search_filter = {
                "$or": [
                    {"name": {"$regex": escaped, "$options": "i"}},
                    {"description": {"$regex": escaped, "$options": "i"}},
                ]
            }
            filter_query.pop("$or")
            filter_query["$and"] = [ownership_filter, search_filter]

        sort_field_map = {
            "name": "name",
            "createdAt": "createdAt",
            "updatedAt": "updatedAt",
        }
        sort_field = sort_field_map.get(params.sort_by, "updatedAt")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        total = await self.collection.count_documents(filter_query)

        cursor = (
            self.collection.find(filter_query)
            .sort(sort_field, sort_direction)
            .skip(params.offset)
            .limit(params.limit)
        )

        boards: list[dict[str, Any]] = []
        async for doc in cursor:
            boards.append(self._format_board_summary(doc))

        logger.info(
            "dashboards_listed",
            total=total,
            returned=len(boards),
            user_id=user_id,
        )

        return boards, total

    async def update_board(
        self,
        board_id: str,
        request: UpdateBoardRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Update a dashboard board.

        Args:
            board_id: The board identifier to update.
            request: Fields to update.
            user_id: The user ID performing the update.

        Returns:
            The updated board document.

        Raises:
            DashboardNotFoundError: If no board exists with the given ID.
            ValidationError: If the user is not the owner.
        """
        existing = await self._get_owned_board(board_id, user_id, "update")

        update_fields: dict[str, Any] = {
            "updatedAt": datetime.now(UTC),
            "version": existing.get("version", 1) + 1,
        }

        if request.name is not None:
            update_fields["name"] = request.name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.icon is not None:
            update_fields["icon"] = request.icon
        if request.board_type is not None:
            update_fields["boardType"] = request.board_type.value
        if request.visibility is not None:
            update_fields["visibility"] = request.visibility.value
        if request.layout is not None:
            update_fields["layout"] = request.layout.model_dump(by_alias=True, exclude_none=True)
        if request.widgets is not None:
            self._validate_widget_types(
                [widget.widget_type for widget in request.widgets],
                existing_widget_types=[
                    cast(str, widget.get("widgetType"))
                    for widget in existing.get("widgets", [])
                    if widget.get("widgetType") is not None
                ],
            )
            update_fields["widgets"] = [w.model_dump(by_alias=True, exclude_none=True) for w in request.widgets]
        if request.settings is not None:
            update_fields["settings"] = request.settings.model_dump(by_alias=True)
        if request.tags is not None:
            update_fields["tags"] = request.tags
        if request.is_home is not None:
            update_fields["isHome"] = request.is_home

        await self.collection.update_one(
            {"boardId": board_id},
            {"$set": update_fields},
        )

        logger.info("dashboard_updated", board_id=board_id, fields=list(update_fields.keys()))

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"fields": list(update_fields.keys())},
        )

        return await self.get_board_for_user(board_id, user_id)

    async def delete_board(
        self,
        board_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Soft delete a dashboard board.

        Args:
            board_id: The board identifier to delete.
            user_id: The user ID performing the delete.

        Returns:
            The archived board document.

        Raises:
            DashboardNotFoundError: If no board exists with the given ID.
            ValidationError: If the user is not the owner.
        """
        existing = await self._get_owned_board(board_id, user_id, "delete")

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"boardId": board_id},
            {"$set": {"archivedAt": now, "updatedAt": now}},
        )

        logger.info("dashboard_deleted", board_id=board_id, user_id=user_id)

        await log_audit(
            AuditAction.DELETE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
        )

        # Return the board as it was before archival
        existing["archivedAt"] = now
        existing["updatedAt"] = now
        return self._format_board(existing)

    async def clone_board(
        self,
        board_id: str,
        user_id: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Clone an existing board.

        Creates a deep copy of the board with a new boardId and ownerId.

        Args:
            board_id: The source board identifier.
            user_id: The user ID for the new board owner.
            name: Optional override name for the cloned board.

        Returns:
            The newly created cloned board document.

        Raises:
            DashboardNotFoundError: If the source board does not exist.
        """
        source = await self._get_visible_board(board_id, user_id)

        now = datetime.now(UTC)
        new_board_id = f"board_{uuid4().hex[:12]}"

        # Deep copy the source board
        cloned = copy.deepcopy(source)
        cloned.pop("_id", None)
        cloned["boardId"] = new_board_id
        cloned["ownerId"] = user_id
        cloned["name"] = name or f"{source['name']} (Copy)"
        cloned["visibility"] = "private"
        cloned["isHome"] = False
        cloned["version"] = 1
        cloned["clonedFrom"] = board_id
        cloned["createdAt"] = now
        cloned["updatedAt"] = now
        cloned["archivedAt"] = None

        # Regenerate instance IDs for all widgets
        for widget in cloned.get("widgets", []):
            widget["instanceId"] = f"wi_{uuid4().hex[:8]}"

        await self.collection.insert_one(cloned)

        logger.info(
            "dashboard_cloned",
            source_board_id=board_id,
            new_board_id=new_board_id,
            user_id=user_id,
        )

        await log_audit(
            AuditAction.CREATE,
            "dashboard",
            new_board_id,
            "user",
            user_id,
            True,
            details={"clonedFrom": board_id},
        )

        return self._format_board(cloned)

    async def add_widget(
        self,
        board_id: str,
        request: AddWidgetRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Add a widget to a board.

        Args:
            board_id: The board identifier.
            request: Widget details to add.
            user_id: The user ID performing the operation.

        Returns:
            The updated board document.

        Raises:
            DashboardNotFoundError: If the board does not exist.
            ValidationError: If the user is not the owner.
        """
        existing = await self._get_owned_board(board_id, user_id, "modify")
        existing_widget_types = [
            cast(str, widget.get("widgetType"))
            for widget in existing.get("widgets", [])
            if widget.get("widgetType") is not None
        ]
        self._validate_widget_types(
            [*existing_widget_types, request.widget_type],
            existing_widget_types=existing_widget_types,
        )

        instance_id = f"wi_{uuid4().hex[:8]}"
        widget_doc: dict[str, Any] = {
            "instanceId": instance_id,
            **request.model_dump(by_alias=True, exclude_none=True),
        }
        if "dataBinding" not in widget_doc:
            widget_doc["dataBinding"] = None

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"boardId": board_id},
            {
                "$push": {"widgets": widget_doc},
                "$set": {
                    "updatedAt": now,
                    "version": existing.get("version", 1) + 1,
                },
            },
        )

        logger.info("widget_added", board_id=board_id, instance_id=instance_id)

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "add_widget", "instanceId": instance_id, "widgetType": request.widget_type},
        )

        return await self.get_board_for_user(board_id, user_id)

    async def update_widget(
        self,
        board_id: str,
        widget_id: str,
        request: UpdateWidgetRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Update a widget on a board.

        Args:
            board_id: The board identifier.
            widget_id: The widget instance identifier.
            request: Widget update details.
            user_id: The user ID performing the operation.

        Returns:
            The updated board document.

        Raises:
            DashboardNotFoundError: If the board does not exist.
            WidgetNotFoundError: If the widget does not exist on the board.
            ValidationError: If the user is not the owner.
        """
        existing = await self._get_owned_board(board_id, user_id, "modify")

        # Find the widget in the widgets array
        widget_index: int | None = None
        for i, w in enumerate(existing.get("widgets", [])):
            if w.get("instanceId") == widget_id:
                widget_index = i
                break

        if widget_index is None:
            raise WidgetNotFoundError(widget_id)

        # Build update operations for the specific widget
        update_set: dict[str, Any] = {
            "updatedAt": datetime.now(UTC),
            "version": existing.get("version", 1) + 1,
        }

        if request.position is not None:
            update_set[f"widgets.{widget_index}.position"] = request.position.model_dump(by_alias=True)
        if request.placements is not None:
            update_set[f"widgets.{widget_index}.placements"] = {
                key: value.model_dump(by_alias=True)
                for key, value in request.placements.items()
            }
        if request.column is not None:
            update_set[f"widgets.{widget_index}.column"] = request.column
        if request.order is not None:
            update_set[f"widgets.{widget_index}.order"] = request.order
        if request.config is not None:
            update_set[f"widgets.{widget_index}.config"] = request.config
        if request.data_binding is not None:
            update_set[f"widgets.{widget_index}.dataBinding"] = request.data_binding.model_dump(by_alias=True)

        await self.collection.update_one(
            {"boardId": board_id},
            {"$set": update_set},
        )

        logger.info("widget_updated", board_id=board_id, widget_id=widget_id)

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "update_widget", "instanceId": widget_id},
        )

        return await self.get_board_for_user(board_id, user_id)

    async def delete_widget(
        self,
        board_id: str,
        widget_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Remove a widget from a board.

        Args:
            board_id: The board identifier.
            widget_id: The widget instance identifier to remove.
            user_id: The user ID performing the operation.

        Returns:
            The updated board document.

        Raises:
            DashboardNotFoundError: If the board does not exist.
            WidgetNotFoundError: If the widget does not exist on the board.
            ValidationError: If the user is not the owner.
        """
        existing = await self._get_owned_board(board_id, user_id, "modify")

        # Verify the widget exists
        widget_exists = any(
            w.get("instanceId") == widget_id for w in existing.get("widgets", [])
        )
        if not widget_exists:
            raise WidgetNotFoundError(widget_id)

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"boardId": board_id},
            {
                "$pull": {"widgets": {"instanceId": widget_id}},
                "$set": {
                    "updatedAt": now,
                    "version": existing.get("version", 1) + 1,
                },
            },
        )

        logger.info("widget_deleted", board_id=board_id, widget_id=widget_id)

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "delete_widget", "instanceId": widget_id},
        )

        return await self.get_board_for_user(board_id, user_id)

    async def _get_visible_board(
        self,
        board_id: str,
        user_id: str,
        user_role: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a board visible to the requesting user.

        Private boards remain owner-only. Non-owners may resolve only
        shared or public boards. Invisible boards deliberately return 404
        so callers cannot infer private board existence.

        Args:
            board_id: Board identifier.
            user_id: Requesting user's ID.
            user_role: Requesting user's role (used for role-based sharing).
        """
        shared_conditions: list[dict[str, Any]] = [
            {"allowedUsers": {"$exists": False}},
            {"allowedUsers": {"$size": 0}},
            {"allowedUsers": user_id},
            # Extended sharing: match by sharedWith.users
            {"sharedWith.users": user_id},
        ]
        if user_role:
            shared_conditions.append({"sharedWith.roles": user_role})

        doc = await self.collection.find_one(
            {
                "boardId": board_id,
                "archivedAt": None,
                "$or": [
                    {"ownerId": user_id},
                    {"visibility": "public"},
                    {
                        "visibility": "shared",
                        "$or": shared_conditions,
                    },
                ],
            }
        )
        if not doc:
            raise DashboardNotFoundError(board_id)
        return cast(dict[str, Any], doc)

    async def _get_owned_board(
        self,
        board_id: str,
        user_id: str,
        action: str,
    ) -> dict[str, Any]:
        """Resolve a board that must be owned by the requesting user."""
        doc = await self.collection.find_one({"boardId": board_id, "archivedAt": None})
        if not doc:
            raise DashboardNotFoundError(board_id)

        if doc["ownerId"] != user_id:
            raise ValidationError(
                f"Only the board owner can {action} dashboard '{board_id}'",
                {"boardId": board_id, "ownerId": doc["ownerId"]},
            )

        return cast(dict[str, Any], doc)

    def get_widget_registry(self, category: str | None = None) -> dict[str, Any]:
        """Return the widget registry, optionally filtered by category.

        Args:
            category: Optional category filter (e.g., "status", "activity").

        Returns:
            Dict with widgets list, category summaries, and total count.
        """
        widgets = list(WIDGET_REGISTRY)
        if category:
            widgets = [w for w in widgets if w["category"] == category]

        # Build category summary from the full registry (not filtered)
        cat_counts: dict[str, int] = {}
        for w in WIDGET_REGISTRY:
            cat = str(w["category"])
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        categories = [
            {"id": k, "name": k.replace("-", " ").title(), "count": v}
            for k, v in sorted(cat_counts.items())
        ]

        return {
            "widgets": widgets,
            "categories": categories,
            "total": len(widgets),
        }

    def _format_board(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a board document for API response."""
        return {
            "boardId": doc["boardId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "icon": doc.get("icon"),
            "ownerId": doc["ownerId"],
            "boardType": doc["boardType"],
            "visibility": doc.get("visibility", "private"),
            "layout": doc.get("layout", {"columns": 12, "rowHeight": 80, "breakpoints": {}}),
            "widgets": doc.get("widgets", []),
            "settings": doc.get("settings", {}),
            "tags": doc.get("tags", []),
            "isHome": doc.get("isHome", False),
            "version": doc.get("version", 1),
            "clonedFrom": doc.get("clonedFrom"),
            "createdAt": doc["createdAt"],
            "updatedAt": doc["updatedAt"],
            "archivedAt": doc.get("archivedAt"),
        }

    def _format_board_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a board document for list response (no widgets array)."""
        return {
            "boardId": doc["boardId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "icon": doc.get("icon"),
            "ownerId": doc["ownerId"],
            "boardType": doc["boardType"],
            "visibility": doc.get("visibility", "private"),
            "widgetCount": len(doc.get("widgets", [])),
            "tags": doc.get("tags", []),
            "isHome": doc.get("isHome", False),
            "version": doc.get("version", 1),
            "createdAt": doc["createdAt"],
            "updatedAt": doc["updatedAt"],
        }

    # ── Templates ───────────────────────────────────────────────────

    async def save_as_template(
        self,
        board_id: str,
        request: SaveAsTemplateRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Save a board as a reusable template.

        Strips user-specific data (ownerId, visibility, isHome) and preserves
        only the layout, widgets, and settings so any user can instantiate it.

        Args:
            board_id: Source board identifier.
            request: Template name, description, and tags.
            user_id: The user creating the template.

        Returns:
            The created template document.
        """
        source = await self._get_visible_board(board_id, user_id)

        now = datetime.now(UTC)
        template_id = f"tmpl_{uuid4().hex[:12]}"

        # Sanitize widgets: strip instance IDs (will be regenerated on instantiation)
        sanitized_widgets = []
        for widget in copy.deepcopy(source.get("widgets", [])):
            widget.pop("instanceId", None)
            sanitized_widgets.append(widget)

        doc: dict[str, Any] = {
            "templateId": template_id,
            "name": request.name,
            "description": request.description,
            "boardType": source.get("boardType", "custom"),
            "layout": source.get("layout", {"columns": 12, "rowHeight": 80, "breakpoints": {}}),
            "widgets": sanitized_widgets,
            "settings": source.get("settings", {}),
            "tags": request.tags,
            "widgetCount": len(sanitized_widgets),
            "createdBy": user_id,
            "sourceBoard": board_id,
            "createdAt": now,
            "updatedAt": now,
        }

        templates_col = self.db.db["dashboard_templates"]
        await templates_col.insert_one(doc)

        logger.info("dashboard_template_saved", template_id=template_id, source_board=board_id)

        await log_audit(
            AuditAction.CREATE,
            "dashboard_template",
            template_id,
            "user",
            user_id,
            True,
            details={"name": request.name, "sourceBoard": board_id},
        )

        return self._format_template(doc)

    async def list_templates(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List available dashboard templates with optional filtering.

        Args:
            limit: Max results.
            offset: Skip count.
            search: Search by name or description.
            tags: Filter by tags.

        Returns:
            A tuple of (list of template summaries, total count).
        """
        templates_col = self.db.db["dashboard_templates"]
        filter_query: dict[str, Any] = {}

        if tags:
            filter_query["tags"] = {"$all": tags}
        if search:
            escaped = re.escape(search)
            filter_query["$or"] = [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"description": {"$regex": escaped, "$options": "i"}},
            ]

        total = await templates_col.count_documents(filter_query)

        cursor = (
            templates_col.find(filter_query)
            .sort("createdAt", DESCENDING)
            .skip(offset)
            .limit(limit)
        )

        templates: list[dict[str, Any]] = []
        async for doc in cursor:
            templates.append(self._format_template_summary(doc))

        return templates, total

    async def get_template(self, template_id: str) -> dict[str, Any]:
        """Retrieve a single template by its identifier.

        Args:
            template_id: Template identifier.

        Returns:
            The formatted template document.

        Raises:
            NotFoundError: If no template exists with the given ID.
        """
        templates_col = self.db.db["dashboard_templates"]
        doc = await templates_col.find_one({"templateId": template_id})
        if not doc:
            raise NotFoundError("dashboard_template", template_id)
        return self._format_template(doc)

    async def instantiate_template(
        self,
        template_id: str,
        user_id: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new board from a template.

        Args:
            template_id: Source template identifier.
            user_id: Owner of the new board.
            name: Optional override name.

        Returns:
            The newly created board document.
        """
        templates_col = self.db.db["dashboard_templates"]
        template = await templates_col.find_one({"templateId": template_id})
        if not template:
            raise NotFoundError("dashboard_template", template_id)

        now = datetime.now(UTC)
        board_id = f"board_{uuid4().hex[:12]}"

        # Reconstitute widgets with fresh instance IDs
        widgets: list[dict[str, Any]] = []
        for widget in copy.deepcopy(template.get("widgets", [])):
            widget["instanceId"] = f"wi_{uuid4().hex[:8]}"
            widgets.append(widget)

        doc: dict[str, Any] = {
            "boardId": board_id,
            "name": name or template["name"],
            "description": template.get("description"),
            "icon": None,
            "ownerId": user_id,
            "boardType": template.get("boardType", "custom"),
            "visibility": "private",
            "layout": template.get("layout", {"columns": 12, "rowHeight": 80, "breakpoints": {}}),
            "widgets": widgets,
            "settings": template.get("settings", {}),
            "tags": [],
            "isHome": False,
            "version": 1,
            "clonedFrom": None,
            "templateId": template_id,
            "createdAt": now,
            "updatedAt": now,
            "archivedAt": None,
        }

        await self.collection.insert_one(doc)

        logger.info(
            "dashboard_instantiated_from_template",
            board_id=board_id,
            template_id=template_id,
            user_id=user_id,
        )

        await log_audit(
            AuditAction.CREATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"templateId": template_id},
        )

        return self._format_board(doc)

    async def delete_template(
        self,
        template_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Delete a dashboard template.

        Only the creator can delete a template.

        Args:
            template_id: Template identifier.
            user_id: The user requesting deletion.

        Returns:
            The deleted template document.

        Raises:
            NotFoundError: If the template does not exist.
            ValidationError: If the user is not the creator.
        """
        templates_col = self.db.db["dashboard_templates"]
        doc = await templates_col.find_one({"templateId": template_id})
        if not doc:
            raise NotFoundError("dashboard_template", template_id)
        if doc["createdBy"] != user_id:
            raise ValidationError(
                f"Only the template creator can delete template '{template_id}'",
                {"templateId": template_id, "createdBy": doc["createdBy"]},
            )

        await templates_col.delete_one({"templateId": template_id})

        logger.info("dashboard_template_deleted", template_id=template_id, user_id=user_id)

        await log_audit(
            AuditAction.DELETE,
            "dashboard_template",
            template_id,
            "user",
            user_id,
            True,
        )

        return self._format_template(doc)

    # ── Sharing ─────────────────────────────────────────────────────

    async def share_board(
        self,
        board_id: str,
        request: ShareBoardRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Update sharing settings for a board.

        Args:
            board_id: Board identifier.
            request: New visibility and allowed users.
            user_id: The user making the change (must be owner).

        Returns:
            Updated sharing settings.
        """
        await self._get_owned_board(board_id, user_id, "share")

        now = datetime.now(UTC)
        update_fields: dict[str, Any] = {
            "visibility": request.visibility.value,
            "updatedAt": now,
        }

        # allowedUsers only meaningful for shared visibility
        if request.visibility == "shared":
            update_fields["allowedUsers"] = request.allowed_users
        else:
            update_fields["allowedUsers"] = []

        await self.collection.update_one(
            {"boardId": board_id},
            {"$set": update_fields},
        )

        logger.info(
            "dashboard_sharing_updated",
            board_id=board_id,
            visibility=request.visibility.value,
            allowed_users_count=len(request.allowed_users),
        )

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "share", "visibility": request.visibility.value},
        )

        return {
            "boardId": board_id,
            "visibility": request.visibility.value,
            "allowedUsers": request.allowed_users if request.visibility == "shared" else [],
        }

    async def get_shares(
        self,
        board_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Get sharing information for a board.

        Args:
            board_id: Board identifier.
            user_id: The user requesting info (must be owner).

        Returns:
            Dict with sharedWith target (roles + users).
        """
        board = await self._get_owned_board(board_id, user_id, "view shares of")
        shared_with = board.get("sharedWith", {})
        return {
            "roles": shared_with.get("roles", []),
            "users": shared_with.get("users", []),
        }

    async def revoke_shares(
        self,
        board_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Revoke all shares on a board, resetting visibility to private.

        Args:
            board_id: Board identifier.
            user_id: The user revoking shares (must be owner).

        Returns:
            The updated board document.
        """
        await self._get_owned_board(board_id, user_id, "revoke shares on")

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"boardId": board_id},
            {
                "$set": {
                    "visibility": "private",
                    "sharedWith": {"roles": [], "users": []},
                    "allowedUsers": [],
                    "updatedAt": now,
                },
            },
        )

        logger.info("dashboard_shares_revoked", board_id=board_id, user_id=user_id)

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "revoke_shares"},
        )

        return await self.get_board_for_user(board_id, user_id)

    async def seed_builtin_templates(self) -> int:
        """Seed built-in dashboard templates.

        Upserts 9 built-in templates using existing widget types.
        Returns the number of templates upserted.
        """
        templates_col = self.db.db["dashboard_templates"]
        now = datetime.now(UTC)

        def _widget(widget_type: str, x: int, y: int, w: int, h: int) -> dict[str, Any]:
            return {
                "widgetType": widget_type,
                "position": {"x": x, "y": y, "w": w, "h": h},
                "config": {},
                "dataBinding": None,
            }

        builtin_templates: list[dict[str, Any]] = [
            {
                "templateId": "tmpl_infra_overview",
                "name": "Infrastructure Overview",
                "description": "A comprehensive view of your infrastructure with stats, node status, and capacity metrics.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::stats-cards", 0, 0, 12, 2),
                    _widget("hydra::node-status-grid", 0, 2, 12, 4),
                    _widget("hydra::capacity-overview", 0, 6, 12, 4),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["infrastructure", "overview", "builtin"],
            },
            {
                "templateId": "tmpl_service_health",
                "name": "Service Health",
                "description": "Monitor service health and key infrastructure metrics.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::service-summary", 0, 0, 6, 4),
                    _widget("hydra::stats-cards", 6, 0, 6, 2),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["services", "health", "builtin"],
            },
            {
                "templateId": "tmpl_network_ops",
                "name": "Network Operations",
                "description": "Network topology and infrastructure metrics at a glance.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::mini-topology", 0, 0, 12, 4),
                    _widget("hydra::stats-cards", 0, 4, 12, 2),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["network", "topology", "builtin"],
            },
            {
                "templateId": "tmpl_capacity",
                "name": "Capacity Planning",
                "description": "Resource utilization and capacity metrics for planning.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::capacity-overview", 0, 0, 12, 4),
                    _widget("hydra::stats-cards", 0, 4, 12, 2),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["capacity", "planning", "builtin"],
            },
            {
                "templateId": "tmpl_activity",
                "name": "Activity Monitor",
                "description": "Track recent infrastructure events and key metrics.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::recent-activity", 0, 0, 6, 4),
                    _widget("hydra::stats-cards", 6, 0, 6, 2),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["activity", "events", "builtin"],
            },
            {
                "templateId": "tmpl_minimal",
                "name": "Minimal Home",
                "description": "A clean, minimal dashboard with just the key stats.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::stats-cards", 0, 0, 12, 2),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["minimal", "home", "builtin"],
            },
            {
                "templateId": "tmpl_ops_center",
                "name": "Operations Center",
                "description": "Full operations view with all core widgets for comprehensive monitoring.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::stats-cards", 0, 0, 12, 2),
                    _widget("hydra::service-summary", 0, 2, 6, 4),
                    _widget("hydra::recent-activity", 6, 2, 6, 4),
                    _widget("hydra::capacity-overview", 0, 6, 12, 4),
                    _widget("hydra::mini-topology", 0, 10, 12, 4),
                    _widget("hydra::node-status-grid", 0, 14, 12, 4),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["operations", "full", "builtin"],
            },
            {
                "templateId": "tmpl_iot",
                "name": "IoT Dashboard",
                "description": "Monitor IoT nodes and device status across your infrastructure.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::stats-cards", 0, 0, 12, 2),
                    _widget("hydra::node-status-grid", 0, 2, 12, 4),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["iot", "devices", "builtin"],
            },
            {
                "templateId": "tmpl_security",
                "name": "Security Overview",
                "description": "Security-focused view with recent activity and key infrastructure metrics.",
                "boardType": "custom",
                "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {"lg": {"columns": 12, "width": 1200}, "md": {"columns": 8, "width": 996}, "sm": {"columns": 4, "width": 768}}},
                "widgets": [
                    _widget("hydra::stats-cards", 0, 0, 12, 2),
                    _widget("hydra::recent-activity", 0, 2, 12, 4),
                ],
                "settings": {"theme": "inherit", "autoRefresh": True, "refreshInterval": 30, "showHeader": True, "kioskMode": False},
                "tags": ["security", "audit", "builtin"],
            },
        ]

        count = 0
        for template in builtin_templates:
            template["widgetCount"] = len(template["widgets"])
            template["createdBy"] = "system"
            template["createdAt"] = now
            template["updatedAt"] = now

            await templates_col.update_one(
                {"templateId": template["templateId"]},
                {"$set": template},
                upsert=True,
            )
            count += 1

        logger.info("builtin_templates_seeded", count=count)
        return count

    # ── Export / Import ─────────────────────────────────────────────

    async def export_board(
        self,
        board_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Export a board as a portable JSON definition.

        Strips user-specific data (ownerId, boardId, timestamps, instance IDs)
        so the export can be imported by any user.

        Args:
            board_id: Board identifier.
            user_id: Requesting user (visibility check).

        Returns:
            Portable board export dictionary.
        """
        board = await self._get_visible_board(board_id, user_id)

        # Strip instance IDs from widgets (will be regenerated on import)
        exported_widgets = []
        for widget in copy.deepcopy(board.get("widgets", [])):
            widget.pop("instanceId", None)
            exported_widgets.append(widget)

        return {
            "exportVersion": 1,
            "name": board["name"],
            "description": board.get("description"),
            "icon": board.get("icon"),
            "boardType": board.get("boardType", "custom"),
            "layout": board.get("layout", {"columns": 12, "rowHeight": 80, "breakpoints": {}}),
            "widgets": exported_widgets,
            "settings": board.get("settings", {}),
            "tags": board.get("tags", []),
        }

    async def import_board(
        self,
        export_data: dict[str, Any],
        user_id: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Import a board from an exported definition.

        Args:
            export_data: The exported board definition.
            user_id: Owner for the new board.
            name: Optional override name.

        Returns:
            The newly created board document.
        """
        now = datetime.now(UTC)
        board_id = f"board_{uuid4().hex[:12]}"

        # Validate widget types exist in registry (allow existing for forward compat)
        widget_types = [w.get("widgetType", "") for w in export_data.get("widgets", [])]
        self._validate_widget_types(widget_types)

        # Reconstitute widgets with fresh instance IDs
        widgets: list[dict[str, Any]] = []
        for widget in copy.deepcopy(export_data.get("widgets", [])):
            widget["instanceId"] = f"wi_{uuid4().hex[:8]}"
            widgets.append(widget)

        doc: dict[str, Any] = {
            "boardId": board_id,
            "name": name or export_data.get("name", "Imported Board"),
            "description": export_data.get("description"),
            "icon": export_data.get("icon"),
            "ownerId": user_id,
            "boardType": export_data.get("boardType", "custom"),
            "visibility": "private",
            "layout": export_data.get("layout", {"columns": 12, "rowHeight": 80, "breakpoints": {}}),
            "widgets": widgets,
            "settings": export_data.get("settings", {}),
            "tags": export_data.get("tags", []),
            "isHome": False,
            "version": 1,
            "clonedFrom": None,
            "createdAt": now,
            "updatedAt": now,
            "archivedAt": None,
        }

        await self.collection.insert_one(doc)

        logger.info("dashboard_imported", board_id=board_id, user_id=user_id)

        await log_audit(
            AuditAction.CREATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "import"},
        )

        return self._format_board(doc)

    # ── Template Formatters ─────────────────────────────────────────

    def _format_template(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a template document for API response."""
        return {
            "templateId": doc["templateId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "boardType": doc.get("boardType", "custom"),
            "layout": doc.get("layout", {"columns": 12, "rowHeight": 80, "breakpoints": {}}),
            "widgets": doc.get("widgets", []),
            "settings": doc.get("settings", {}),
            "tags": doc.get("tags", []),
            "widgetCount": doc.get("widgetCount", len(doc.get("widgets", []))),
            "createdBy": doc["createdBy"],
            "createdAt": doc["createdAt"],
            "updatedAt": doc["updatedAt"],
        }

    def _format_template_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a template document for list response."""
        return {
            "templateId": doc["templateId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "boardType": doc.get("boardType", "custom"),
            "tags": doc.get("tags", []),
            "widgetCount": doc.get("widgetCount", len(doc.get("widgets", []))),
            "createdBy": doc["createdBy"],
            "createdAt": doc["createdAt"],
        }
