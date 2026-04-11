"""Hydra API - Main application entry point."""

import asyncio
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from hydra.api.v1 import __version__
from hydra.api.v1.core.context import get_request_id, set_request_id
from hydra.api.v1.core.exceptions import HydraError
from hydra.api.v1.routers import (
    ai,
    auth,
    chat,
    commands,
    dashboards,
    discovery,
    docs,
    groups,
    ha,
    health,
    icons,
    install,
    installations,
    mcp,
    networks,
    nodes,
    notifications,
    plugins,
    profiles,
    query,
    search,
    services,
    timemachine,
    topologies,
    users,
    workflows,
)
from hydra.api.v1.routers import settings as settings_router
from hydra.core.config import get_settings

# Static files directory (shared with root app)
STATIC_DIR = Path(__file__).parent.parent.parent / "static"

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Hydra API",
        description="AI-powered infrastructure management platform API",
        version=__version__,
        # Use /_docs to avoid conflict with /docs router (documentation endpoints)
        docs_url="/_docs" if settings.is_development else None,
        redoc_url="/_redoc" if settings.is_development else None,
        openapi_url="/_openapi.json" if settings.is_development else None,
        swagger_favicon_url="/static/favicon.ico",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(request_id)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Any) -> Any:
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        return response

    # Exception handlers
    @app.exception_handler(HydraError)
    async def hydra_error_handler(_request: Request, exc: HydraError) -> JSONResponse:
        request_id = get_request_id()
        logger.warning(
            "hydra_error",
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
                "requestId": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = get_request_id()
        errors = exc.errors()
        logger.warning("validation_error", errors=errors)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"errors": errors},
                },
                "requestId": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = get_request_id()
        logger.exception("unhandled_error", error=str(exc))

        # Fire-and-forget notification for unhandled errors (rate-limited via group_key)
        try:
            from hydra.api.v1.models.notifications import (
                NotificationSource,
                NotificationType,
                SourceComponent,
            )
            from hydra.api.v1.services.notifications import emit_notification

            asyncio.create_task(
                emit_notification(
                    notification_type=NotificationType.API_INTERNAL_ERROR,
                    source=NotificationSource(
                        component=SourceComponent.HYDRA_API, service="api"
                    ),
                    title="Internal API error",
                    message=f"Unhandled error on {request.method} {request.url.path}: {type(exc).__name__}",
                    group_key="api_internal_error",
                )
            )
        except Exception:
            pass  # Never let notification emission interfere with error response

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                    "details": {},
                },
                "requestId": request_id,
            },
        )

    # Favicon route for swagger docs (ensures proper favicon in API docs)
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Any:
        """Serve favicon for swagger docs."""
        favicon_path = STATIC_DIR / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(
                favicon_path,
                media_type="image/x-icon",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        # Return empty response if not found
        return FileResponse(favicon_path, status_code=404)

    # Include routers at the v1 root (mounted by the parent app)
    app.include_router(health.router)
    app.include_router(icons.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(nodes.router)
    app.include_router(nodes.node_router)
    app.include_router(profiles.router)
    app.include_router(profiles.nodes_router)
    app.include_router(services.router)
    app.include_router(services.nodes_services_router)
    app.include_router(networks.router)
    app.include_router(groups.router)
    app.include_router(topologies.router)
    app.include_router(timemachine.router)
    app.include_router(commands.router)
    app.include_router(commands.catalog_router)
    app.include_router(commands.nodes_commands_router)
    app.include_router(workflows.router)
    app.include_router(dashboards.router)
    app.include_router(docs.router)
    app.include_router(query.router)
    app.include_router(ha.router)
    app.include_router(install.router)
    app.include_router(ai.router)
    app.include_router(chat.router)
    # Note: chat_ws.router and notifications_ws.router are included at root app level for WebSocket compatibility
    app.include_router(mcp.router)
    app.include_router(notifications.router)
    app.include_router(discovery.router)
    app.include_router(plugins.router)
    app.include_router(installations.router)
    app.include_router(search.router)
    app.include_router(settings_router.router)

    return app


# Create the application instance
app = create_app()
