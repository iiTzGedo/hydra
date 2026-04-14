"""Dashboard management service.

Phase 2 Wave 1 responsibilities:
- Spec-aligned board model (BoardType user/template/shared/kiosk, structured
  visibility, ownerType) with persistence in the ``dashboards`` collection.
- Dynamic widget registry access via ``widget_registry`` singleton with
  role-filtered responses.
- PATCH operations (update-settings, update-layout, update-widget,
  add-widget, remove-widget, reorder-widgets).
- Set-home endpoint that enforces single-home-per-user.
- Board limits (max 25 boards per user, max 10 shared boards per user).
- YAML export via ``export_board`` with ``format`` switch.
- Enhanced import validation with warnings for unknown widget types.
"""

from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import structlog
import yaml  # type: ignore[import-untyped]
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.dashboards import (
    AddWidgetRequest,
    BoardType,
    CreateBoardRequest,
    DashboardListParams,
    PatchAddWidget,
    PatchBoardOperation,
    PatchRemoveWidget,
    PatchReorderWidgets,
    PatchUpdateLayout,
    PatchUpdateSettings,
    PatchUpdateWidget,
    SaveAsTemplateRequest,
    ShareBoardRequest,
    UpdateBoardRequest,
    UpdateWidgetRequest,
    VisibilityScope,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.dashboards.templates import BUILTIN_TEMPLATES
from hydra.api.v1.services.dashboards.widget_registry import widget_registry
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


# ── Limits (Dashboard Technical Specification §19.C) ────────────────

MAX_BOARDS_PER_USER = 25
MAX_SHARED_BOARDS_PER_USER = 10
MAX_WIDGETS_PER_BOARD = 50


# ── Default visibility / layout / settings helpers ──────────────────


def _default_visibility() -> dict[str, Any]:
    return {"scope": "private", "sharedWith": {"roles": [], "users": []}}


def _default_settings() -> dict[str, Any]:
    return {
        "theme": "inherit",
        "autoRefresh": True,
        "refreshInterval": 30,
        "showHeader": True,
        "kioskMode": False,
        "kioskAutoScroll": False,
        "kioskScrollSpeed": 30,
        "backgroundImage": None,
        "customCss": None,
    }


def _default_grid_layout() -> dict[str, Any]:
    return {
        "mode": "grid",
        "grid": {
            "columns": 12,
            "rowHeight": 80,
            "breakpoints": {
                "xl": {"columns": 12, "width": 1536},
                "lg": {"columns": 12, "width": 1200},
                "md": {"columns": 8, "width": 996},
                "sm": {"columns": 4, "width": 480},
                "xs": {"columns": 2, "width": 0},
            },
            "compaction": "vertical",
            "margin": [16, 16],
            "padding": [0, 0],
        },
    }


def _serialize_visibility(visibility: Any) -> dict[str, Any]:
    """Coerce a visibility input into the structured shape stored in Mongo."""
    if visibility is None:
        return _default_visibility()
    if hasattr(visibility, "model_dump"):
        return cast(dict[str, Any], visibility.model_dump(by_alias=True))
    if isinstance(visibility, dict):
        scope = visibility.get("scope", "private")
        raw_shared = visibility.get("sharedWith") or visibility.get("shared_with") or {}
        roles = list(raw_shared.get("roles", []))
        users = list(raw_shared.get("users", []))
        return {"scope": scope, "sharedWith": {"roles": roles, "users": users}}
    return _default_visibility()


# ── Errors ──────────────────────────────────────────────────────────


class DashboardNotFoundError(NotFoundError):
    """Dashboard not found."""

    def __init__(self, board_id: str) -> None:
        super().__init__("dashboard", board_id)


class WidgetNotFoundError(NotFoundError):
    """Widget instance not found on dashboard."""

    def __init__(self, widget_id: str) -> None:
        super().__init__("widget", widget_id)


# ── Template variable substitution ───────────────────────────────

_VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _substitute_variables(obj: Any, variables: dict[str, Any]) -> Any:
    """Recursively walk *obj* and replace ``{{varName}}`` placeholders.

    - In strings: ``{{varName}}`` is replaced with the stringified variable value.
      If the entire string is a single placeholder (``"{{x}}"``), the raw typed
      value is substituted so numbers and booleans survive.
    - In dicts/lists: recurse into children.
    - Other types pass through unchanged.
    """
    if isinstance(obj, str):
        # Fast path: entire string is a single variable reference → return raw value
        single = _VAR_PATTERN.fullmatch(obj)
        if single:
            key = single.group(1)
            return variables.get(key, obj)
        # Partial replacement: may contain multiple interpolations
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return str(variables.get(key, match.group(0)))
        return _VAR_PATTERN.sub(_replace, obj)
    if isinstance(obj, dict):
        return {k: _substitute_variables(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_variables(item, variables) for item in obj]
    return obj


def _validate_template_variables(
    template_vars: dict[str, Any] | None,
    provided: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate provided variables against the template's variable schema.

    Returns the merged variables dict (defaults filled in for missing optional vars).
    Raises ``ValidationError`` if required variables are missing.
    """
    if not template_vars:
        return provided or {}

    schema = template_vars  # {name: {type, label, default, required, ...}}
    result: dict[str, Any] = {}
    missing: list[str] = []

    for var_name, var_def in schema.items():
        if provided and var_name in provided:
            result[var_name] = provided[var_name]
        elif isinstance(var_def, dict) and var_def.get("default") is not None:
            result[var_name] = var_def["default"]
        elif isinstance(var_def, dict) and var_def.get("required"):
            missing.append(var_name)
        # else: optional with no default — omit

    if missing:
        raise ValidationError(
            f"Missing required template variables: {', '.join(missing)}",
            {"missing": missing},
        )

    # Pass through any extra variables the user sent (forward-compat)
    if provided:
        for k, v in provided.items():
            if k not in result:
                result[k] = v

    return result


class DashboardService:
    """Service for dashboard board management operations."""

    def __init__(self, mongodb: MongoDB) -> None:
        self.db = mongodb
        self.collection = mongodb.db["dashboards"]

    # ── Widget validation ───────────────────────────────────────────

    def _validate_widget_types(
        self,
        widget_types: list[str],
        *,
        existing_widget_types: list[str] | None = None,
    ) -> None:
        """Validate widget types against the widget registry.

        Existing widget types are grandfathered during updates — the registry
        may drop a type but the board will still render it until the owner
        edits the board.
        """
        unknown, repeatable_violations = widget_registry.validate_widget_types(
            widget_types,
            existing_widget_types=existing_widget_types,
        )
        if unknown:
            raise ValidationError(
                f"Widget type(s) not in registry: {', '.join(sorted(set(unknown)))}",
                {"widgetTypes": sorted(set(unknown))},
            )
        if repeatable_violations:
            raise ValidationError(
                f"Widget type(s) cannot appear more than once: {', '.join(sorted(set(repeatable_violations)))}",
                {"widgetTypes": sorted(set(repeatable_violations)), "repeatable": False},
            )

    # ── Limits ─────────────────────────────────────────────────────

    async def _enforce_create_limit(self, owner_id: str) -> None:
        count = await self.collection.count_documents(
            {"ownerId": owner_id, "archivedAt": None},
        )
        if count >= MAX_BOARDS_PER_USER:
            raise ValidationError(
                f"Maximum board count reached ({MAX_BOARDS_PER_USER} per user)",
                {"limit": MAX_BOARDS_PER_USER, "current": count},
            )

    async def _enforce_share_limit(self, owner_id: str, board_id: str) -> None:
        count = await self.collection.count_documents(
            {
                "ownerId": owner_id,
                "archivedAt": None,
                "visibility.scope": {"$in": ["shared", "public"]},
                "boardId": {"$ne": board_id},
            }
        )
        if count >= MAX_SHARED_BOARDS_PER_USER:
            raise ValidationError(
                f"Maximum shared board count reached ({MAX_SHARED_BOARDS_PER_USER} per user)",
                {"limit": MAX_SHARED_BOARDS_PER_USER, "current": count},
            )

    # ── CRUD: boards ───────────────────────────────────────────────

    async def create_board(
        self,
        request: CreateBoardRequest,
        owner_id: str,
    ) -> dict[str, Any]:
        """Create a new dashboard board."""
        await self._enforce_create_limit(owner_id)

        now = datetime.now(UTC)
        board_id = f"board_{uuid4().hex[:12]}"

        self._validate_widget_types([widget.widget_type for widget in request.widgets])

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

        if len(widgets) > MAX_WIDGETS_PER_BOARD:
            raise ValidationError(
                f"Boards cannot have more than {MAX_WIDGETS_PER_BOARD} widgets",
                {"widgetCount": len(widgets), "limit": MAX_WIDGETS_PER_BOARD},
            )

        visibility = _serialize_visibility(request.visibility)

        # If the board is marked home on creation, clear any existing home for this user.
        if request.is_home:
            await self.collection.update_many(
                {"ownerId": owner_id, "isHome": True},
                {"$set": {"isHome": False, "updatedAt": now}},
            )

        doc: dict[str, Any] = {
            "boardId": board_id,
            "name": request.name,
            "description": request.description,
            "icon": request.icon,
            "ownerId": owner_id,
            "ownerType": "user",
            "boardType": request.board_type.value,
            "visibility": visibility,
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
        """Retrieve a board by identifier (no visibility check)."""
        doc = await self.collection.find_one({"boardId": board_id, "archivedAt": None})
        if not doc:
            raise DashboardNotFoundError(board_id)
        return self._format_board(doc)

    async def get_board_for_user(
        self,
        board_id: str,
        user_id: str,
        user_role: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a board visible to the requesting user."""
        doc = await self._get_visible_board(board_id, user_id, user_role)
        return self._format_board(doc)

    async def list_boards(
        self,
        params: DashboardListParams,
        user_id: str,
        user_role: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List boards with filtering, sorting, and pagination."""
        base_visibility_filter: dict[str, Any] = {
            "archivedAt": None,
            "$or": [
                {"ownerId": user_id},
                {"visibility.scope": "public"},
                {
                    "visibility.scope": "shared",
                    "$or": [
                        {"visibility.sharedWith.users": user_id},
                        *(
                            [{"visibility.sharedWith.roles": user_role}]
                            if user_role
                            else []
                        ),
                    ],
                },
            ],
        }

        filter_query: dict[str, Any] = dict(base_visibility_filter)

        if params.board_type:
            filter_query["boardType"] = params.board_type.value
        if params.visibility:
            filter_query["visibility.scope"] = params.visibility.value
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.owner_id:
            filter_query["ownerId"] = params.owner_id

        if params.search:
            escaped = re.escape(params.search)
            search_filter = {
                "$or": [
                    {"name": {"$regex": escaped, "$options": "i"}},
                    {"description": {"$regex": escaped, "$options": "i"}},
                ]
            }
            visibility_filter = filter_query.pop("$or", None)
            combined_and: list[dict[str, Any]] = []
            if visibility_filter:
                combined_and.append({"$or": visibility_filter})
            combined_and.append(search_filter)
            filter_query["$and"] = combined_and

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
        """Full replacement update (PUT semantics)."""
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
            update_fields["visibility"] = _serialize_visibility(request.visibility)
            if update_fields["visibility"]["scope"] in ("shared", "public"):
                await self._enforce_share_limit(user_id, board_id)
        if request.layout is not None:
            update_fields["layout"] = request.layout.model_dump(by_alias=True, exclude_none=True)
        if request.widgets is not None:
            if len(request.widgets) > MAX_WIDGETS_PER_BOARD:
                raise ValidationError(
                    f"Boards cannot have more than {MAX_WIDGETS_PER_BOARD} widgets",
                    {"widgetCount": len(request.widgets), "limit": MAX_WIDGETS_PER_BOARD},
                )
            self._validate_widget_types(
                [widget.widget_type for widget in request.widgets],
                existing_widget_types=[
                    cast(str, widget.get("widgetType"))
                    for widget in existing.get("widgets", [])
                    if widget.get("widgetType") is not None
                ],
            )
            update_fields["widgets"] = [
                w.model_dump(by_alias=True, exclude_none=True) for w in request.widgets
            ]
        if request.settings is not None:
            update_fields["settings"] = request.settings.model_dump(by_alias=True)
        if request.tags is not None:
            update_fields["tags"] = request.tags
        if request.is_home is not None:
            update_fields["isHome"] = request.is_home
            if request.is_home:
                await self.collection.update_many(
                    {
                        "ownerId": user_id,
                        "isHome": True,
                        "boardId": {"$ne": board_id},
                    },
                    {"$set": {"isHome": False, "updatedAt": update_fields["updatedAt"]}},
                )

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

        # Save version snapshot from the in-memory merge
        snapshot_doc = {**existing, **update_fields}
        await self._save_version_snapshot(snapshot_doc, user_id, "Board updated")

        return await self.get_board_for_user(board_id, user_id)

    async def patch_board(
        self,
        board_id: str,
        operations: list[PatchBoardOperation],
        user_id: str,
    ) -> dict[str, Any]:
        """Apply a sequence of PATCH operations to a board atomically in-memory.

        Every operation is applied to an in-memory snapshot so ordering is
        deterministic, then the resulting widgets/layout/settings are written
        with a single ``$set`` call so the version increments once.
        """
        existing = await self._get_owned_board(board_id, user_id, "update")

        widgets: list[dict[str, Any]] = list(existing.get("widgets", []))
        layout: dict[str, Any] = copy.deepcopy(existing.get("layout", _default_grid_layout()))
        settings: dict[str, Any] = copy.deepcopy(existing.get("settings", _default_settings()))
        applied_ops: list[str] = []

        for op in operations:
            if isinstance(op, PatchUpdateSettings):
                settings = op.settings.model_dump(by_alias=True)
                applied_ops.append("update-settings")
            elif isinstance(op, PatchUpdateLayout):
                layout = op.layout.model_dump(by_alias=True, exclude_none=True)
                applied_ops.append("update-layout")
            elif isinstance(op, PatchAddWidget):
                instance_id = f"wi_{uuid4().hex[:8]}"
                widget_doc: dict[str, Any] = {
                    "instanceId": instance_id,
                    **op.widget.model_dump(by_alias=True, exclude_none=True),
                }
                widget_doc.setdefault("dataBinding", None)
                widgets.append(widget_doc)
                applied_ops.append("add-widget")
            elif isinstance(op, PatchRemoveWidget):
                before = len(widgets)
                widgets = [w for w in widgets if w.get("instanceId") != op.instance_id]
                if len(widgets) == before:
                    raise WidgetNotFoundError(op.instance_id)
                applied_ops.append("remove-widget")
            elif isinstance(op, PatchUpdateWidget):
                idx: int | None = None
                for i, widget in enumerate(widgets):
                    if widget.get("instanceId") == op.instance_id:
                        idx = i
                        break
                if idx is None:
                    raise WidgetNotFoundError(op.instance_id)
                updates = op.changes.model_dump(by_alias=True, exclude_none=True)
                updated_widget: dict[str, Any] = dict(widgets[idx])
                for key, value in updates.items():
                    updated_widget[key] = value
                widgets[idx] = updated_widget
                applied_ops.append("update-widget")
            elif isinstance(op, PatchReorderWidgets):
                index_by_id = {w.get("instanceId"): w for w in widgets}
                missing = [iid for iid in op.order if iid not in index_by_id]
                if missing:
                    raise ValidationError(
                        f"Unknown widget instance IDs in reorder: {missing}",
                        {"missing": missing},
                    )
                ordered: list[dict[str, Any]] = [index_by_id[iid] for iid in op.order]
                remaining = [w for w in widgets if w.get("instanceId") not in set(op.order)]
                for position, widget in enumerate(ordered):
                    new_widget = dict(widget)
                    if new_widget.get("column") is not None:
                        new_widget["order"] = position
                    ordered[position] = new_widget
                widgets = ordered + remaining
                applied_ops.append("reorder-widgets")

        if len(widgets) > MAX_WIDGETS_PER_BOARD:
            raise ValidationError(
                f"Boards cannot have more than {MAX_WIDGETS_PER_BOARD} widgets",
                {"widgetCount": len(widgets), "limit": MAX_WIDGETS_PER_BOARD},
            )

        # Revalidate widget types (e.g. add-widget) against existing types.
        self._validate_widget_types(
            [str(w.get("widgetType", "")) for w in widgets],
            existing_widget_types=[
                str(w.get("widgetType", "")) for w in existing.get("widgets", [])
            ],
        )

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"boardId": board_id},
            {
                "$set": {
                    "widgets": widgets,
                    "layout": layout,
                    "settings": settings,
                    "updatedAt": now,
                    "version": existing.get("version", 1) + 1,
                }
            },
        )

        logger.info(
            "dashboard_patched",
            board_id=board_id,
            ops=applied_ops,
        )

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"patch_ops": applied_ops},
        )

        # Save version snapshot from in-memory state
        snapshot_doc = {
            **existing,
            "widgets": widgets,
            "layout": layout,
            "settings": settings,
            "updatedAt": now,
            "version": existing.get("version", 1) + 1,
        }
        await self._save_version_snapshot(
            snapshot_doc, user_id, f"Patch: {', '.join(applied_ops)}"
        )

        return await self.get_board_for_user(board_id, user_id)

    async def set_home_board(self, board_id: str, user_id: str) -> dict[str, Any]:
        """Mark a board as the user's home board, clearing the previous one."""
        # Board must be visible to the user (owned, shared, or public) —
        # users can set any visible board as their home, but cannot mark
        # other users' boards as home without affecting the owner's docs.
        board = await self._get_visible_board(board_id, user_id)
        now = datetime.now(UTC)

        # Clear previous home flag for this user's owned boards.
        await self.collection.update_many(
            {
                "ownerId": user_id,
                "isHome": True,
                "boardId": {"$ne": board_id},
            },
            {"$set": {"isHome": False, "updatedAt": now}},
        )

        # Flip the new board's isHome flag. For boards owned by the user this
        # flips the shared document; for non-owned boards we record the intent
        # as a side-effect on the board itself only if owned (per spec §3.4).
        if board.get("ownerId") == user_id:
            await self.collection.update_one(
                {"boardId": board_id},
                {
                    "$set": {
                        "isHome": True,
                        "updatedAt": now,
                        "version": board.get("version", 1) + 1,
                    }
                },
            )

        logger.info("dashboard_set_home", board_id=board_id, user_id=user_id)

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "set_home"},
        )

        return await self.get_board_for_user(board_id, user_id)

    async def delete_board(
        self,
        board_id: str,
        user_id: str,
        user_role: str | None = None,
    ) -> dict[str, Any]:
        """Soft delete a dashboard board. Admins can delete any board."""
        if user_role == "admin":
            doc = await self.collection.find_one({"boardId": board_id, "archivedAt": None})
            if not doc:
                raise DashboardNotFoundError(board_id)
            existing = cast(dict[str, Any], doc)
        else:
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

        existing["archivedAt"] = now
        existing["updatedAt"] = now
        return self._format_board(existing)

    async def clone_board(
        self,
        board_id: str,
        user_id: str,
        name: str | None = None,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Clone an existing board with optional variable substitution."""
        source = await self._get_visible_board(board_id, user_id)
        await self._enforce_create_limit(user_id)

        now = datetime.now(UTC)
        new_board_id = f"board_{uuid4().hex[:12]}"

        cloned = copy.deepcopy(source)
        cloned.pop("_id", None)
        cloned["boardId"] = new_board_id
        cloned["ownerId"] = user_id
        cloned["ownerType"] = "user"
        cloned["name"] = name or f"{source['name']} (Copy)"
        cloned["visibility"] = _default_visibility()
        cloned["isHome"] = False
        cloned["version"] = 1
        cloned["clonedFrom"] = board_id
        cloned["boardType"] = "user"
        cloned["createdAt"] = now
        cloned["updatedAt"] = now
        cloned["archivedAt"] = None

        for widget in cloned.get("widgets", []):
            widget["instanceId"] = f"wi_{uuid4().hex[:8]}"
            if variables:
                widget["config"] = _substitute_variables(widget.get("config", {}), variables)
                if widget.get("dataBinding"):
                    widget["dataBinding"] = _substitute_variables(widget["dataBinding"], variables)

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

    # ── CRUD: widgets (legacy single-widget endpoints) ──────────────

    async def add_widget(
        self,
        board_id: str,
        request: AddWidgetRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Add a widget to a board via the dedicated endpoint."""
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

        if len(existing.get("widgets", [])) + 1 > MAX_WIDGETS_PER_BOARD:
            raise ValidationError(
                f"Boards cannot have more than {MAX_WIDGETS_PER_BOARD} widgets",
                {"limit": MAX_WIDGETS_PER_BOARD},
            )

        instance_id = f"wi_{uuid4().hex[:8]}"
        widget_doc: dict[str, Any] = {
            "instanceId": instance_id,
            **request.model_dump(by_alias=True, exclude_none=True),
        }
        widget_doc.setdefault("dataBinding", None)

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
        """Update a widget on a board."""
        existing = await self._get_owned_board(board_id, user_id, "modify")

        widget_index: int | None = None
        for i, w in enumerate(existing.get("widgets", [])):
            if w.get("instanceId") == widget_id:
                widget_index = i
                break

        if widget_index is None:
            raise WidgetNotFoundError(widget_id)

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
        """Remove a widget from a board."""
        existing = await self._get_owned_board(board_id, user_id, "modify")

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

    # ── Visibility helpers ─────────────────────────────────────────

    async def _get_visible_board(
        self,
        board_id: str,
        user_id: str,
        user_role: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a board visible to the requesting user."""
        shared_conditions: list[dict[str, Any]] = [
            {"visibility.sharedWith.users": user_id},
        ]
        if user_role:
            shared_conditions.append({"visibility.sharedWith.roles": user_role})

        doc = await self.collection.find_one(
            {
                "boardId": board_id,
                "archivedAt": None,
                "$or": [
                    {"ownerId": user_id},
                    {"visibility.scope": "public"},
                    {
                        "visibility.scope": "shared",
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

    # ── Widget registry access ─────────────────────────────────────

    def get_widget_registry(
        self,
        category: str | None = None,
        user_role: str | None = None,
    ) -> dict[str, Any]:
        """Return role-filtered widget registry for the picker.

        Args:
            category: Optional spec category filter.
            user_role: Optional role for permission-based filtering.
        """
        widgets = widget_registry.list_for_role(user_role)
        if category:
            widgets = [w for w in widgets if w.get("category") == category]

        categories = widget_registry.categories_for_role(user_role)

        return {
            "widgets": widgets,
            "categories": categories,
            "total": len(widgets),
        }

    # ── Formatters ─────────────────────────────────────────────────

    def _format_board(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a board document for API response."""
        return {
            "boardId": doc["boardId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "icon": doc.get("icon"),
            "ownerId": doc["ownerId"],
            "ownerType": doc.get("ownerType", "user"),
            "boardType": doc["boardType"],
            "visibility": doc.get("visibility") or _default_visibility(),
            "layout": doc.get("layout", _default_grid_layout()),
            "widgets": doc.get("widgets", []),
            "settings": {**_default_settings(), **(doc.get("settings") or {})},
            "tags": doc.get("tags", []),
            "isHome": doc.get("isHome", False),
            "version": doc.get("version", 1),
            "clonedFrom": doc.get("clonedFrom"),
            "createdAt": doc["createdAt"],
            "updatedAt": doc["updatedAt"],
            "archivedAt": doc.get("archivedAt"),
        }

    def _format_board_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a board document for list response."""
        return {
            "boardId": doc["boardId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "icon": doc.get("icon"),
            "ownerId": doc["ownerId"],
            "ownerType": doc.get("ownerType", "user"),
            "boardType": doc["boardType"],
            "visibility": doc.get("visibility") or _default_visibility(),
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
        """Save a board as a reusable template."""
        source = await self._get_visible_board(board_id, user_id)

        now = datetime.now(UTC)
        template_id = f"tmpl_{uuid4().hex[:12]}"

        sanitized_widgets = []
        for widget in copy.deepcopy(source.get("widgets", [])):
            widget.pop("instanceId", None)
            sanitized_widgets.append(widget)

        variables_dict: dict[str, Any] | None = None
        if request.variables:
            variables_dict = {
                key: var.model_dump(by_alias=True)
                for key, var in request.variables.items()
            }

        doc: dict[str, Any] = {
            "templateId": template_id,
            "name": request.name,
            "description": request.description,
            "category": request.category.value,
            "targetRoles": request.target_roles,
            "requiredPlugins": request.required_plugins,
            "optionalPlugins": request.optional_plugins,
            "variables": variables_dict,
            "source": "user",
            "boardType": "user",
            "layout": source.get("layout", _default_grid_layout()),
            "widgets": sanitized_widgets,
            "settings": source.get("settings", _default_settings()),
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
        category: str | None = None,
        source: str | None = None,
        user_role: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List dashboard templates, filtered by category, source, and user role."""
        templates_col = self.db.db["dashboard_templates"]
        filter_query: dict[str, Any] = {}

        if category:
            filter_query["category"] = category
        if source:
            filter_query["source"] = source
        if tags:
            filter_query["tags"] = {"$all": tags}
        if user_role:
            # Only return templates whose targetRoles include the user's role,
            # or templates that have no targetRoles set (legacy/unrestricted).
            filter_query["$or"] = [
                {"targetRoles": user_role},
                {"targetRoles": {"$exists": False}},
                {"targetRoles": {"$size": 0}},
            ]
        if search:
            escaped = re.escape(search)
            search_conditions = [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"description": {"$regex": escaped, "$options": "i"}},
            ]
            if "$or" in filter_query:
                # Combine role filter with search using $and
                role_or = filter_query.pop("$or")
                filter_query["$and"] = [
                    {"$or": role_or},
                    {"$or": search_conditions},
                ]
            else:
                filter_query["$or"] = search_conditions

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
        """Retrieve a single template."""
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
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new board from a template with optional variable substitution."""
        templates_col = self.db.db["dashboard_templates"]
        template = await templates_col.find_one({"templateId": template_id})
        if not template:
            raise NotFoundError("dashboard_template", template_id)

        await self._enforce_create_limit(user_id)

        # Validate and merge provided variables with defaults from the schema
        resolved_vars = _validate_template_variables(
            template.get("variables"),
            variables,
        )

        now = datetime.now(UTC)
        board_id = f"board_{uuid4().hex[:12]}"

        widgets: list[dict[str, Any]] = []
        for widget in copy.deepcopy(template.get("widgets", [])):
            widget["instanceId"] = f"wi_{uuid4().hex[:8]}"
            # Apply variable substitution to widget config and data bindings
            if resolved_vars:
                widget["config"] = _substitute_variables(widget.get("config", {}), resolved_vars)
                if widget.get("dataBinding"):
                    widget["dataBinding"] = _substitute_variables(widget["dataBinding"], resolved_vars)
            widgets.append(widget)

        doc: dict[str, Any] = {
            "boardId": board_id,
            "name": name or template["name"],
            "description": template.get("description"),
            "icon": None,
            "ownerId": user_id,
            "ownerType": "user",
            "boardType": "user",
            "visibility": _default_visibility(),
            "layout": template.get("layout", _default_grid_layout()),
            "widgets": widgets,
            "settings": {**_default_settings(), **(template.get("settings") or {})},
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
        """Delete a dashboard template (creator only)."""
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

    # ── Version History ────────────────────────────────────────────

    async def _save_version_snapshot(
        self,
        board: dict[str, Any],
        user_id: str,
        change_description: str | None = None,
    ) -> None:
        """Persist a snapshot of the board's current state into ``dashboard_versions``."""
        versions_col = self.db.db["dashboard_versions"]
        snapshot = {
            k: v for k, v in board.items()
            if k not in ("_id",)
        }
        await versions_col.insert_one({
            "boardId": board["boardId"],
            "version": board.get("version", 1),
            "snapshot": snapshot,
            "savedBy": user_id,
            "savedAt": datetime.now(UTC),
            "changeDescription": change_description,
            "widgetCount": len(board.get("widgets", [])),
        })

    async def list_versions(
        self,
        board_id: str,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List version history for a board (newest first)."""
        await self._get_visible_board(board_id, user_id)

        versions_col = self.db.db["dashboard_versions"]
        filter_query = {"boardId": board_id}
        total = await versions_col.count_documents(filter_query)

        cursor = (
            versions_col.find(filter_query, {"snapshot": 0})
            .sort("version", DESCENDING)
            .skip(offset)
            .limit(limit)
        )

        results: list[dict[str, Any]] = []
        async for doc in cursor:
            results.append({
                "boardId": doc["boardId"],
                "version": doc["version"],
                "savedBy": doc["savedBy"],
                "savedAt": doc["savedAt"],
                "changeDescription": doc.get("changeDescription"),
                "widgetCount": doc.get("widgetCount", 0),
            })

        return results, total

    async def get_version(
        self,
        board_id: str,
        version: int,
        user_id: str,
    ) -> dict[str, Any]:
        """Retrieve a specific version snapshot."""
        await self._get_visible_board(board_id, user_id)

        versions_col = self.db.db["dashboard_versions"]
        doc = await versions_col.find_one({"boardId": board_id, "version": version})
        if not doc:
            raise NotFoundError("dashboard_version", f"{board_id}@v{version}")

        return {
            "boardId": doc["boardId"],
            "version": doc["version"],
            "snapshot": doc["snapshot"],
            "savedBy": doc["savedBy"],
            "savedAt": doc["savedAt"],
            "changeDescription": doc.get("changeDescription"),
        }

    async def restore_version(
        self,
        board_id: str,
        version: int,
        user_id: str,
    ) -> dict[str, Any]:
        """Restore a board to a previous version.

        Creates a new version (current + 1) with the snapshot content.
        """
        existing = await self._get_owned_board(board_id, user_id, "restore")

        versions_col = self.db.db["dashboard_versions"]
        version_doc = await versions_col.find_one({"boardId": board_id, "version": version})
        if not version_doc:
            raise NotFoundError("dashboard_version", f"{board_id}@v{version}")

        snapshot = version_doc["snapshot"]
        new_version = existing.get("version", 1) + 1
        now = datetime.now(UTC)

        # Snapshot current state before overwriting
        await self._save_version_snapshot(
            existing, user_id, f"Pre-restore snapshot (before restoring to v{version})"
        )

        # Restore layout, widgets, settings from the snapshot
        await self.collection.update_one(
            {"boardId": board_id},
            {
                "$set": {
                    "layout": snapshot.get("layout", _default_grid_layout()),
                    "widgets": snapshot.get("widgets", []),
                    "settings": snapshot.get("settings", _default_settings()),
                    "version": new_version,
                    "updatedAt": now,
                }
            },
        )

        logger.info(
            "dashboard_version_restored",
            board_id=board_id,
            restored_version=version,
            new_version=new_version,
        )

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "restore", "restoredVersion": version, "newVersion": new_version},
        )

        restored = await self.get_board_for_user(board_id, user_id)

        # Snapshot restored state
        restored_doc = await self.collection.find_one({"boardId": board_id, "archivedAt": None})
        if restored_doc:
            await self._save_version_snapshot(
                cast(dict[str, Any], restored_doc),
                user_id,
                f"Restored from v{version}",
            )

        return restored

    # ── Sharing ─────────────────────────────────────────────────────

    async def share_board(
        self,
        board_id: str,
        request: ShareBoardRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Update sharing settings for a board."""
        await self._get_owned_board(board_id, user_id, "share")

        if request.scope in (VisibilityScope.SHARED, VisibilityScope.PUBLIC):
            await self._enforce_share_limit(user_id, board_id)

        now = datetime.now(UTC)
        if request.scope == VisibilityScope.PRIVATE:
            visibility: dict[str, Any] = {"scope": "private", "sharedWith": {"roles": [], "users": []}}
        else:
            visibility = {
                "scope": request.scope.value,
                "sharedWith": request.shared_with.model_dump(by_alias=True),
            }

        await self.collection.update_one(
            {"boardId": board_id},
            {"$set": {"visibility": visibility, "updatedAt": now}},
        )

        logger.info(
            "dashboard_sharing_updated",
            board_id=board_id,
            scope=request.scope.value,
            roles=visibility["sharedWith"]["roles"],
            users=visibility["sharedWith"]["users"],
        )

        await log_audit(
            AuditAction.UPDATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "share", "scope": request.scope.value},
        )

        return {
            "boardId": board_id,
            "scope": request.scope.value,
            "sharedWith": visibility["sharedWith"],
        }

    async def get_shares(
        self,
        board_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Get sharing information for a board."""
        board = await self._get_owned_board(board_id, user_id, "view shares of")
        visibility = board.get("visibility") or _default_visibility()
        shared_with = visibility.get("sharedWith") or {"roles": [], "users": []}
        return {
            "roles": list(shared_with.get("roles", [])),
            "users": list(shared_with.get("users", [])),
        }

    async def revoke_shares(
        self,
        board_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Revoke all shares on a board."""
        await self._get_owned_board(board_id, user_id, "revoke shares on")

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"boardId": board_id},
            {
                "$set": {
                    "visibility": _default_visibility(),
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

    # ── Built-in template seeding ──────────────────────────────────

    async def seed_builtin_templates(self) -> int:
        """Upsert built-in templates into the ``dashboard_templates`` collection."""
        templates_col = self.db.db["dashboard_templates"]
        now = datetime.now(UTC)

        count = 0
        for template in BUILTIN_TEMPLATES:
            doc = copy.deepcopy(template)
            doc["widgetCount"] = len(doc.get("widgets", []))
            doc["createdBy"] = "system"
            doc.setdefault("source", "system")
            doc.setdefault("category", "general")
            doc.setdefault("targetRoles", ["admin", "operator", "viewer", "family"])
            doc.setdefault("requiredPlugins", [])
            doc.setdefault("optionalPlugins", [])
            doc["createdAt"] = now
            doc["updatedAt"] = now

            await templates_col.update_one(
                {"templateId": doc["templateId"]},
                {"$set": doc},
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
        export_format: str = "json",
    ) -> dict[str, Any]:
        """Export a board as a portable definition.

        Args:
            board_id: Board identifier.
            user_id: Requesting user (visibility check).
            export_format: ``json`` (default) or ``yaml``.

        Returns:
            A dict with key ``data`` containing either the JSON-friendly dict
            or a YAML-serialized string, plus ``format`` and ``contentType``.
        """
        if export_format not in ("json", "yaml"):
            raise ValidationError(
                f"Unsupported export format '{export_format}'",
                {"format": export_format, "allowed": ["json", "yaml"]},
            )

        board = await self._get_visible_board(board_id, user_id)

        exported_widgets = []
        for widget in copy.deepcopy(board.get("widgets", [])):
            widget.pop("instanceId", None)
            exported_widgets.append(widget)

        export_payload: dict[str, Any] = {
            "exportVersion": 1,
            "name": board["name"],
            "description": board.get("description"),
            "icon": board.get("icon"),
            "boardType": board.get("boardType", "user"),
            "layout": board.get("layout", _default_grid_layout()),
            "widgets": exported_widgets,
            "settings": {**_default_settings(), **(board.get("settings") or {})},
            "tags": board.get("tags", []),
        }

        if export_format == "yaml":
            yaml_text = yaml.safe_dump(
                export_payload,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
            )
            return {"format": "yaml", "contentType": "application/yaml", "data": yaml_text}

        return {"format": "json", "contentType": "application/json", "data": export_payload}

    def validate_import(
        self,
        export_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return a list of validation warnings/errors for an import payload.

        - ``unknown_widget_type``: warning when a widget_type is not in the registry.
        - ``invalid_data_binding``: warning when a dataBinding is missing
          required ``source``.
        """
        warnings: list[dict[str, Any]] = []
        widgets = export_data.get("widgets") or []
        for index, widget in enumerate(widgets):
            widget_type = str(widget.get("widgetType", ""))
            if widget_type and not widget_registry.has(widget_type):
                warnings.append(
                    {
                        "level": "warning",
                        "code": "unknown_widget_type",
                        "message": f"Widget type '{widget_type}' is not in the registry; it will render as a placeholder.",
                        "widgetIndex": index,
                    }
                )

            binding = widget.get("dataBinding")
            if binding is not None and not isinstance(binding, dict):
                warnings.append(
                    {
                        "level": "warning",
                        "code": "invalid_data_binding",
                        "message": "dataBinding must be an object or null",
                        "widgetIndex": index,
                    }
                )
            elif isinstance(binding, dict) and not binding.get("source"):
                warnings.append(
                    {
                        "level": "warning",
                        "code": "invalid_data_binding",
                        "message": "dataBinding.source is required",
                        "widgetIndex": index,
                    }
                )
        return warnings

    async def import_board(
        self,
        export_data: dict[str, Any],
        user_id: str,
        name: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Import a board from an exported definition.

        Returns ``(board, warnings)`` so the caller can surface validation
        issues to the user.
        """
        await self._enforce_create_limit(user_id)

        warnings = self.validate_import(export_data)

        now = datetime.now(UTC)
        board_id = f"board_{uuid4().hex[:12]}"

        widgets: list[dict[str, Any]] = []
        for widget in copy.deepcopy(export_data.get("widgets", [])):
            widget["instanceId"] = f"wi_{uuid4().hex[:8]}"
            widgets.append(widget)

        if len(widgets) > MAX_WIDGETS_PER_BOARD:
            raise ValidationError(
                f"Boards cannot have more than {MAX_WIDGETS_PER_BOARD} widgets",
                {"widgetCount": len(widgets), "limit": MAX_WIDGETS_PER_BOARD},
            )

        doc: dict[str, Any] = {
            "boardId": board_id,
            "name": name or export_data.get("name", "Imported Board"),
            "description": export_data.get("description"),
            "icon": export_data.get("icon"),
            "ownerId": user_id,
            "ownerType": "user",
            "boardType": export_data.get("boardType", BoardType.USER.value),
            "visibility": _default_visibility(),
            "layout": export_data.get("layout", _default_grid_layout()),
            "widgets": widgets,
            "settings": {**_default_settings(), **(export_data.get("settings") or {})},
            "tags": export_data.get("tags", []),
            "isHome": False,
            "version": 1,
            "clonedFrom": None,
            "createdAt": now,
            "updatedAt": now,
            "archivedAt": None,
        }

        await self.collection.insert_one(doc)

        logger.info(
            "dashboard_imported",
            board_id=board_id,
            user_id=user_id,
            warning_count=len(warnings),
        )

        await log_audit(
            AuditAction.CREATE,
            "dashboard",
            board_id,
            "user",
            user_id,
            True,
            details={"action": "import", "warnings": len(warnings)},
        )

        return self._format_board(doc), warnings

    # ── Template Formatters ─────────────────────────────────────────

    def _format_template(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a template document for API response."""
        return {
            "templateId": doc["templateId"],
            "name": doc["name"],
            "description": doc.get("description"),
            "category": doc.get("category", "general"),
            "targetRoles": doc.get("targetRoles", ["admin", "operator", "viewer", "family"]),
            "requiredPlugins": doc.get("requiredPlugins", []),
            "optionalPlugins": doc.get("optionalPlugins", []),
            "preview": doc.get("preview"),
            "variables": doc.get("variables"),
            "source": doc.get("source", "user"),
            "boardType": doc.get("boardType", "user"),
            "layout": doc.get("layout", _default_grid_layout()),
            "widgets": doc.get("widgets", []),
            "settings": {**_default_settings(), **(doc.get("settings") or {})},
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
            "category": doc.get("category", "general"),
            "targetRoles": doc.get("targetRoles", ["admin", "operator", "viewer", "family"]),
            "requiredPlugins": doc.get("requiredPlugins", []),
            "optionalPlugins": doc.get("optionalPlugins", []),
            "preview": doc.get("preview"),
            "source": doc.get("source", "user"),
            "boardType": doc.get("boardType", "user"),
            "tags": doc.get("tags", []),
            "widgetCount": doc.get("widgetCount", len(doc.get("widgets", []))),
            "createdBy": doc["createdBy"],
            "createdAt": doc["createdAt"],
        }


__all__ = [
    "DashboardNotFoundError",
    "DashboardService",
    "MAX_BOARDS_PER_USER",
    "MAX_SHARED_BOARDS_PER_USER",
    "MAX_WIDGETS_PER_BOARD",
    "WidgetNotFoundError",
]
