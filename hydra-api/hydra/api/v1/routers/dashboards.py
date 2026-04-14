"""Dashboard management endpoints."""

from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response

from hydra.api.v1.core.deps import (
    CurrentUser,
    MongoDBDep,
    require_permission,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.dashboards import (
    AddWidgetRequest,
    BoardExport,
    BoardResponse,
    BoardSummary,
    BoardType,
    CloneBoardRequest,
    CreateBoardRequest,
    DashboardListParams,
    ImportBoardRequest,
    ImportBoardResponse,
    ImportValidationIssue,
    InstantiateTemplateRequest,
    PatchBoardRequest,
    SaveAsTemplateRequest,
    ShareBoardRequest,
    ShareBoardResponse,
    ShareTarget,
    TemplateResponse,
    TemplateSummary,
    UpdateBoardRequest,
    UpdateWidgetRequest,
    VersionSnapshotResponse,
    VersionSummary,
    VisibilityScope,
    WidgetRegistryResponse,
)
from hydra.api.v1.services.dashboards import DashboardService

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])
logger = structlog.get_logger(__name__)


def get_dashboard_service(mongodb: MongoDBDep) -> DashboardService:
    """Get dashboard service dependency."""
    return DashboardService(mongodb)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


def _user_id(current_user: dict[str, Any]) -> str:
    return current_user.get("user_id") or current_user.get("userId") or current_user.get("sub") or ""


def _user_role(current_user: dict[str, Any]) -> str | None:
    role = current_user.get("role")
    return str(role) if role else None


@router.get(
    "",
    response_model=SuccessResponse[list[BoardSummary]],
    response_model_by_alias=True,
    summary="List Dashboards",
    description="List all dashboards visible to the current user with optional filters and pagination.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def list_dashboards(
    dashboard_service: DashboardServiceDep,
    current_user: CurrentUser,
    board_type: BoardType | None = Query(default=None, alias="boardType"),
    owner_id: str | None = Query(default=None, alias="ownerId"),
    visibility: VisibilityScope | None = Query(
        default=None,
        description="Filter by visibility scope (private, shared, public)",
    ),
    tags: list[str] | None = Query(default=None),
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["name", "createdAt", "updatedAt"] = Query(default="updatedAt", alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[BoardSummary]]:
    """Retrieve a paginated list of dashboards visible to the user."""
    user_id = _user_id(current_user)
    role = _user_role(current_user)

    params = DashboardListParams(
        board_type=board_type,
        owner_id=owner_id,
        visibility=visibility,
        tags=tags,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    boards, total = await dashboard_service.list_boards(params, user_id, role)

    return SuccessResponse(
        data=[BoardSummary(**board) for board in boards],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Create Dashboard",
    description="Create a new dashboard board.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def create_dashboard(
    request: CreateBoardRequest,
    dashboard_service: DashboardServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[BoardResponse]:
    """Create a new dashboard board owned by the current user."""
    user_id = _user_id(current_user)
    board = await dashboard_service.create_board(request, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.get(
    "/widgets/registry",
    response_model=SuccessResponse[WidgetRegistryResponse],
    response_model_by_alias=True,
    summary="Widget Registry",
    description="Get available widget types filtered by user role.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def get_widget_registry(
    dashboard_service: DashboardServiceDep,
    current_user: CurrentUser,
    category: str | None = Query(default=None, description="Filter by widget category"),
) -> SuccessResponse[WidgetRegistryResponse]:
    """Get widget types the current user's role may view."""
    registry = dashboard_service.get_widget_registry(
        category=category,
        user_role=_user_role(current_user),
    )
    return SuccessResponse(data=WidgetRegistryResponse(**registry))


# ── Template Endpoints ──────────────────────────────────────────────


@router.get(
    "/templates",
    response_model=SuccessResponse[list[TemplateSummary]],
    response_model_by_alias=True,
    summary="List Dashboard Templates",
    description="List available dashboard templates with optional filtering by category, source, tags, and user role.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def list_templates(
    dashboard_service: DashboardServiceDep,
    current_user: CurrentUser,
    category: str | None = Query(default=None, description="Filter by template category"),
    source: str | None = Query(default=None, description="Filter by template source (system, user)"),
    search: str | None = None,
    tags: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[TemplateSummary]]:
    """List available dashboard templates filtered by the user's role."""
    user_role = _user_role(current_user)
    templates, total = await dashboard_service.list_templates(
        limit=limit,
        offset=offset,
        search=search,
        tags=tags,
        category=category,
        source=source,
        user_role=user_role,
    )
    return SuccessResponse(
        data=[TemplateSummary(**t) for t in templates],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/templates/{template_id}",
    response_model=SuccessResponse[TemplateResponse],
    response_model_by_alias=True,
    summary="Get Dashboard Template",
    description="Get detailed information about a dashboard template.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def get_template(
    dashboard_service: DashboardServiceDep,
    template_id: str = Path(description="Dashboard template ID"),
) -> SuccessResponse[TemplateResponse]:
    """Retrieve a single dashboard template by its identifier."""
    template = await dashboard_service.get_template(template_id)
    return SuccessResponse(data=TemplateResponse(**template))


@router.post(
    "/templates/{template_id}/instantiate",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Instantiate Template",
    description="Create a new dashboard board from a template.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def instantiate_template(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    template_id: str = Path(description="Dashboard template ID"),
    request: InstantiateTemplateRequest | None = None,
) -> SuccessResponse[BoardResponse]:
    """Create a new board from a dashboard template with optional variable substitution."""
    user_id = _user_id(current_user)
    name = request.name if request else None
    variables = request.variables if request else None
    board = await dashboard_service.instantiate_template(template_id, user_id, name, variables)
    return SuccessResponse(data=BoardResponse(**board))


@router.delete(
    "/templates/{template_id}",
    response_model=SuccessResponse[TemplateResponse],
    response_model_by_alias=True,
    summary="Delete Dashboard Template",
    description="Delete a dashboard template. Only the creator can delete.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def delete_template(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    template_id: str = Path(description="Dashboard template ID"),
) -> SuccessResponse[TemplateResponse]:
    """Delete a dashboard template."""
    user_id = _user_id(current_user)
    template = await dashboard_service.delete_template(template_id, user_id)
    return SuccessResponse(data=TemplateResponse(**template))


# ── Import Endpoint ─────────────────────────────────────────────────


@router.post(
    "/import",
    response_model=SuccessResponse[ImportBoardResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Import Dashboard",
    description="Import a dashboard from an exported JSON definition, returning any validation warnings.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def import_dashboard(
    request: ImportBoardRequest,
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
) -> SuccessResponse[ImportBoardResponse]:
    """Import a board from an exported definition with validation warnings."""
    user_id = _user_id(current_user)
    export_data = request.board.model_dump(by_alias=True)
    board, warnings = await dashboard_service.import_board(export_data, user_id, request.name)
    return SuccessResponse(
        data=ImportBoardResponse(
            board=BoardResponse(**board),
            warnings=[ImportValidationIssue(**w) for w in warnings],
        )
    )


# ── Version History Endpoints ──────────────────────────────────────


@router.get(
    "/{dashboard_id}/versions",
    response_model=SuccessResponse[list[VersionSummary]],
    response_model_by_alias=True,
    summary="List Board Versions",
    description="List version history for a dashboard board.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def list_versions(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[VersionSummary]]:
    """List version history for a board (newest first)."""
    user_id = _user_id(current_user)
    versions, total = await dashboard_service.list_versions(
        dashboard_id, user_id, limit=limit, offset=offset,
    )
    return SuccessResponse(
        data=[VersionSummary(**v) for v in versions],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/{dashboard_id}/versions/{version}",
    response_model=SuccessResponse[VersionSnapshotResponse],
    response_model_by_alias=True,
    summary="Get Board Version",
    description="Get a specific version snapshot for a dashboard board.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def get_version(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
    version: int = Path(description="Version number to retrieve"),
) -> SuccessResponse[VersionSnapshotResponse]:
    """Retrieve a specific version snapshot."""
    user_id = _user_id(current_user)
    result = await dashboard_service.get_version(dashboard_id, version, user_id)
    return SuccessResponse(data=VersionSnapshotResponse(**result))


@router.post(
    "/{dashboard_id}/restore/{version}",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Restore Board Version",
    description="Restore a dashboard board to a previous version.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def restore_version(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
    version: int = Path(description="Version number to restore"),
) -> SuccessResponse[BoardResponse]:
    """Restore a board to a previous version (creates a new version)."""
    user_id = _user_id(current_user)
    board = await dashboard_service.restore_version(dashboard_id, version, user_id)
    return SuccessResponse(data=BoardResponse(**board))


# ── Single Dashboard Endpoints ─────────────────────────────────────


@router.get(
    "/{dashboard_id}",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Get Dashboard",
    description="Get detailed information about a specific dashboard.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def get_dashboard(
    dashboard_id: str = Path(description="Dashboard board ID"),
    *,
    dashboard_service: DashboardServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[BoardResponse]:
    """Retrieve a single dashboard by its identifier."""
    board = await dashboard_service.get_board_for_user(
        dashboard_id,
        _user_id(current_user),
        _user_role(current_user),
    )
    return SuccessResponse(data=BoardResponse(**board))


@router.put(
    "/{dashboard_id}",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Update Dashboard",
    description="Full replacement update: send all mutable fields you want applied.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def update_dashboard(
    request: UpdateBoardRequest,
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[BoardResponse]:
    """Update an existing dashboard board (PUT semantics)."""
    user_id = _user_id(current_user)
    board = await dashboard_service.update_board(dashboard_id, request, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.patch(
    "/{dashboard_id}",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Patch Dashboard",
    description="Apply discrete PATCH operations (update-settings, update-layout, update-widget, add-widget, remove-widget, reorder-widgets).",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def patch_dashboard(
    request: PatchBoardRequest,
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[BoardResponse]:
    """Apply PATCH operations to a dashboard in a single version bump."""
    user_id = _user_id(current_user)
    board = await dashboard_service.patch_board(dashboard_id, request.operations, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.delete(
    "/{dashboard_id}",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Delete Dashboard",
    description="Soft delete a dashboard board.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def delete_dashboard(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[BoardResponse]:
    """Soft delete a dashboard board. Admins can delete any board per spec §9.2."""
    user_id = _user_id(current_user)
    role = _user_role(current_user)
    board = await dashboard_service.delete_board(dashboard_id, user_id, user_role=role)
    return SuccessResponse(data=BoardResponse(**board))


@router.post(
    "/{dashboard_id}/clone",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Clone Dashboard",
    description="Clone an existing dashboard as a new private board owned by the current user.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def clone_dashboard(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID to clone"),
    request: CloneBoardRequest | None = None,
) -> SuccessResponse[BoardResponse]:
    """Clone a dashboard board with optional variable substitution."""
    user_id = _user_id(current_user)
    name = request.name if request else None
    variables = request.variables if request else None
    board = await dashboard_service.clone_board(dashboard_id, user_id, name, variables)
    return SuccessResponse(data=BoardResponse(**board))


@router.post(
    "/{dashboard_id}/set-home",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Set Home Dashboard",
    description="Mark a dashboard as the user's home board, clearing the previous home.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def set_home_dashboard(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[BoardResponse]:
    """Set a board as the current user's home dashboard."""
    user_id = _user_id(current_user)
    board = await dashboard_service.set_home_board(dashboard_id, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.post(
    "/{dashboard_id}/widgets",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Add Widget",
    description="Add a widget instance to a dashboard.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def add_widget(
    request: AddWidgetRequest,
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[BoardResponse]:
    """Add a new widget to a dashboard board."""
    user_id = _user_id(current_user)
    board = await dashboard_service.add_widget(dashboard_id, request, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.put(
    "/{dashboard_id}/widgets/{widget_id}",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Update Widget",
    description="Update a widget instance on a dashboard.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def update_widget(
    request: UpdateWidgetRequest,
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
    widget_id: str = Path(description="Widget instance ID"),
) -> SuccessResponse[BoardResponse]:
    """Update a widget's position, configuration, or data binding."""
    user_id = _user_id(current_user)
    board = await dashboard_service.update_widget(dashboard_id, widget_id, request, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.delete(
    "/{dashboard_id}/widgets/{widget_id}",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Delete Widget",
    description="Remove a widget instance from a dashboard.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def delete_widget(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
    widget_id: str = Path(description="Widget instance ID"),
) -> SuccessResponse[BoardResponse]:
    """Remove a widget from a dashboard board."""
    user_id = _user_id(current_user)
    board = await dashboard_service.delete_widget(dashboard_id, widget_id, user_id)
    return SuccessResponse(data=BoardResponse(**board))


# ── Per-Board Actions (template, share, export) ────────────────────


@router.post(
    "/{dashboard_id}/save-as-template",
    response_model=SuccessResponse[TemplateResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Save As Template",
    description="Save a dashboard as a reusable template. Requires admin role per spec §9.2.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def save_as_template(
    request: SaveAsTemplateRequest,
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[TemplateResponse]:
    """Save a board as a reusable template (admin only)."""
    role = _user_role(current_user)
    if role != "admin":
        from hydra.api.v1.core.exceptions import AdminOnlyError

        raise AdminOnlyError()
    user_id = _user_id(current_user)
    template = await dashboard_service.save_as_template(dashboard_id, request, user_id)
    return SuccessResponse(data=TemplateResponse(**template))


@router.post(
    "/{dashboard_id}/share",
    response_model=SuccessResponse[ShareBoardResponse],
    response_model_by_alias=True,
    summary="Share Dashboard",
    description="Update sharing settings for a dashboard. Requires admin or operator role per spec §9.2.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def share_dashboard(
    request: ShareBoardRequest,
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[ShareBoardResponse]:
    """Update sharing settings for a board (admin/operator only)."""
    role = _user_role(current_user)
    if role not in ("admin", "operator"):
        from hydra.api.v1.core.exceptions import AuthorizationError

        raise AuthorizationError("dashboards:share")
    user_id = _user_id(current_user)
    result = await dashboard_service.share_board(dashboard_id, request, user_id)
    return SuccessResponse(data=ShareBoardResponse(**result))


@router.get(
    "/{dashboard_id}/shares",
    response_model=SuccessResponse[ShareTarget],
    response_model_by_alias=True,
    summary="Get Dashboard Shares",
    description="Get sharing information for a dashboard.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def get_shares(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[ShareTarget]:
    """Get sharing target (roles + users) for a board."""
    user_id = _user_id(current_user)
    result = await dashboard_service.get_shares(dashboard_id, user_id)
    return SuccessResponse(data=ShareTarget(**result))


@router.delete(
    "/{dashboard_id}/shares",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Revoke Dashboard Shares",
    description="Revoke all shares on a dashboard, resetting to private.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def revoke_shares(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[BoardResponse]:
    """Revoke all shares, clearing shared users/roles and setting visibility to private."""
    user_id = _user_id(current_user)
    board = await dashboard_service.revoke_shares(dashboard_id, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.get(
    "/{dashboard_id}/export",
    summary="Export Dashboard",
    description="Export a dashboard as a portable JSON (default) or YAML definition.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def export_dashboard(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
    format: Literal["json", "yaml"] = Query(default="json", description="Export format"),
) -> Any:
    """Export a board as JSON (wrapped in SuccessResponse) or YAML (raw text)."""
    user_id = _user_id(current_user)
    result = await dashboard_service.export_board(dashboard_id, user_id, export_format=format)

    if result["format"] == "yaml":
        return Response(
            content=result["data"],
            media_type="application/yaml",
            headers={
                "Content-Disposition": f'attachment; filename="{dashboard_id}.yaml"',
            },
        )

    return SuccessResponse(data=BoardExport(**result["data"]))
