"""Dashboard management endpoints."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import (
    CurrentUser,
    MongoDBDep,
    require_permission,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.dashboards import (
    AddWidgetRequest,
    BoardResponse,
    BoardSummary,
    BoardType,
    BoardVisibility,
    CloneBoardRequest,
    CreateBoardRequest,
    DashboardListParams,
    UpdateBoardRequest,
    UpdateWidgetRequest,
    WidgetRegistryResponse,
)
from hydra.api.v1.services.dashboards import DashboardService

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])
logger = structlog.get_logger(__name__)


def get_dashboard_service(mongodb: MongoDBDep) -> DashboardService:
    """Get dashboard service dependency."""
    return DashboardService(mongodb)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


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
    visibility: BoardVisibility | None = None,
    tags: list[str] | None = Query(default=None),
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["name", "createdAt", "updatedAt"] = Query(default="updatedAt", alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[BoardSummary]]:
    """Retrieve a paginated list of dashboards.

    Users see their own boards plus shared and public boards.

    Args:
        dashboard_service: Dashboard service instance.
        current_user: Authenticated user context.
        board_type: Filter by board type.
        visibility: Filter by visibility scope.
        tags: Filter by tags (boards must have all specified tags).
        search: Search query for board name or description.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        sort_by: Field to sort by.
        sort_order: Sort direction.

    Returns:
        Paginated list of board summaries with metadata.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")

    params = DashboardListParams(
        board_type=board_type,
        visibility=visibility,
        tags=tags,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    boards, total = await dashboard_service.list_boards(params, user_id)

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
    """Create a new dashboard board owned by the current user.

    Args:
        request: Board creation details.
        dashboard_service: Dashboard service instance.
        current_user: Authenticated user context.

    Returns:
        The created board.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    board = await dashboard_service.create_board(request, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.get(
    "/widgets/registry",
    response_model=SuccessResponse[WidgetRegistryResponse],
    response_model_by_alias=True,
    summary="Widget Registry",
    description="Get available widget types for the dashboard widget picker.",
    dependencies=[Depends(require_permission("dashboards:read"))],
)
async def get_widget_registry(
    dashboard_service: DashboardServiceDep,
    category: str | None = Query(default=None, description="Filter by widget category"),
) -> SuccessResponse[WidgetRegistryResponse]:
    """Get available widget types from the registry.

    Returns all registered widget type definitions with their default sizes,
    constraints, and category information.

    Args:
        dashboard_service: Dashboard service instance.
        category: Optional category filter.

    Returns:
        Widget registry with type definitions and category summaries.
    """
    registry = dashboard_service.get_widget_registry(category)
    return SuccessResponse(data=WidgetRegistryResponse(**registry))


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
    """Retrieve a single dashboard by its identifier.

    Args:
        dashboard_id: Unique identifier of the dashboard.
        dashboard_service: Dashboard service instance.

    Returns:
        Complete dashboard details including all widgets.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    board = await dashboard_service.get_board_for_user(dashboard_id, user_id)
    return SuccessResponse(data=BoardResponse(**board))


@router.put(
    "/{dashboard_id}",
    response_model=SuccessResponse[BoardResponse],
    response_model_by_alias=True,
    summary="Update Dashboard",
    description="Update dashboard metadata, layout, widgets, and settings.",
    dependencies=[Depends(require_permission("dashboards:write"))],
)
async def update_dashboard(
    request: UpdateBoardRequest,
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    dashboard_id: str = Path(description="Dashboard board ID"),
) -> SuccessResponse[BoardResponse]:
    """Update an existing dashboard board.

    Args:
        request: Fields to update.
        current_user: Authenticated user context.
        dashboard_service: Dashboard service instance.
        dashboard_id: Unique identifier of the dashboard.

    Returns:
        Updated dashboard details.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    board = await dashboard_service.update_board(dashboard_id, request, user_id)
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
    """Soft delete a dashboard board.

    The board is archived and can be recovered.

    Args:
        current_user: Authenticated user context.
        dashboard_service: Dashboard service instance.
        dashboard_id: Unique identifier of the dashboard.

    Returns:
        The archived dashboard details.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    board = await dashboard_service.delete_board(dashboard_id, user_id)
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
    """Clone a dashboard board.

    Creates a deep copy with a new board ID and fresh widget instance IDs.

    Args:
        current_user: Authenticated user context.
        dashboard_service: Dashboard service instance.
        dashboard_id: Unique identifier of the source dashboard.
        request: Optional clone configuration (name override).

    Returns:
        The newly created cloned dashboard.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    name = request.name if request else None
    board = await dashboard_service.clone_board(dashboard_id, user_id, name)
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
    """Add a new widget to a dashboard board.

    Args:
        request: Widget details including type, position, and configuration.
        current_user: Authenticated user context.
        dashboard_service: Dashboard service instance.
        dashboard_id: Unique identifier of the dashboard.

    Returns:
        The updated dashboard with the new widget.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
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
    """Update a widget's position, configuration, or data binding.

    Args:
        request: Widget update details.
        current_user: Authenticated user context.
        dashboard_service: Dashboard service instance.
        dashboard_id: Unique identifier of the dashboard.
        widget_id: Unique identifier of the widget instance.

    Returns:
        The updated dashboard.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
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
    """Remove a widget from a dashboard board.

    Args:
        current_user: Authenticated user context.
        dashboard_service: Dashboard service instance.
        dashboard_id: Unique identifier of the dashboard.
        widget_id: Unique identifier of the widget instance to remove.

    Returns:
        The updated dashboard without the removed widget.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    board = await dashboard_service.delete_widget(dashboard_id, widget_id, user_id)
    return SuccessResponse(data=BoardResponse(**board))
