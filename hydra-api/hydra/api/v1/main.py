"""Hydra API - Main application entry point."""

import uuid

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hydra.api.v1 import __version__
from hydra.core.config import get_settings
from hydra.api.v1.core.exceptions import HydraError
from hydra.api.v1.routers import auth, commands, docs, groups, ha, health, install, networks, nodes, profiles, query, services, timemachine, topologies, users

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Hydra API",
        description="AI-powered infrastructure management platform API",
        version=__version__,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
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
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
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
    async def hydra_error_handler(request: Request, exc: HydraError) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "unknown")
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
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "unknown")
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
        request_id = request.headers.get("X-Request-ID", "unknown")
        logger.exception("unhandled_error", error=str(exc))
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

    # Include routers at the v1 root (mounted by the parent app)
    app.include_router(health.router)
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
    app.include_router(commands.nodes_commands_router)
    app.include_router(docs.router)
    app.include_router(query.router)
    app.include_router(ha.router)
    app.include_router(install.router)

    return app


# Create the application instance
app = create_app()
