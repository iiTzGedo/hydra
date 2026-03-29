"""Hydra API root application entry point."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from hydra.api.v1 import __version__
from hydra.core.config import get_settings
from hydra.core.logging import configure_logging
from hydra.db.indexes import ensure_indexes
from hydra.db.mongodb import get_mongodb
from hydra.db.redis import get_redis
from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers import chat_ws, health, notifications_ws
from hydra.api.v1.services.health_scanner import HealthScanner

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Root application lifespan handler for startup and shutdown."""
    settings = get_settings()

    # Configure logging
    configure_logging(settings)
    logger.info("starting_hydra_api", version=__version__, env=settings.env)

    # Connect to databases
    mongodb = get_mongodb()
    await mongodb.connect()

    redis = get_redis()
    await redis.connect()

    # Ensure indexes
    await ensure_indexes(mongodb.db)

    # Seed built-in command definitions
    from hydra.api.v1.services.commands.registry import CommandRegistryService
    registry_service = CommandRegistryService(mongodb)
    await registry_service.seed_builtin_commands()

    # Set startup time for uptime tracking
    health.set_startup_time()

    logger.info("hydra_api_started")

    # Start background health scanner
    scanner = HealthScanner(mongodb, redis)
    scanner_task = asyncio.create_task(scanner.run())

    # Start background command timeout checker
    from hydra.api.v1.services.commands import CommandsService

    async def command_timeout_loop():
        """Periodically mark stale executing commands as timed out."""
        while True:
            try:
                await asyncio.sleep(60)
                svc = CommandsService(mongodb)
                count = await svc.timeout_stale_commands(timeout_minutes=10)
                if count > 0:
                    logger.info("commands_timed_out_background", count=count)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("command_timeout_loop_error", error=str(e))

    timeout_task = asyncio.create_task(command_timeout_loop())

    yield

    # Shutdown
    logger.info("shutting_down_hydra_api")
    timeout_task.cancel()
    scanner_task.cancel()
    try:
        await timeout_task
    except asyncio.CancelledError:
        pass
    try:
        await scanner_task
    except asyncio.CancelledError:
        pass
    await redis.disconnect()
    await mongodb.disconnect()
    logger.info("hydra_api_stopped")


def create_app() -> FastAPI:
    """Create the root application and mount versioned APIs."""
    settings = get_settings()

    app = FastAPI(
        title="Hydra API",
        description="AI-powered infrastructure management platform API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    # CORS middleware on root app for WebSocket support
    # WebSocket upgrade requests are HTTP, so they need CORS at the root level
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Landing page route
    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    async def landing_page():
        """Serve the API landing page with documentation links."""
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(), status_code=200)
        return HTMLResponse(
            content="<h1>Hydra API</h1><p>Visit <a href='/api/v1/_docs'>/api/v1/_docs</a> for API documentation</p>",
            status_code=200
        )

    # Favicon route
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        """Serve favicon for browser requests and API docs."""
        favicon_path = STATIC_DIR / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(
                favicon_path,
                media_type="image/x-icon",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        return FileResponse(favicon_path, status_code=404)

    # Mount static files (logo, etc.)
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Include WebSocket routers at root level (before mount)
    # This ensures WebSocket connections bypass the sub-application routing issues
    app.include_router(chat_ws.router, prefix="/api/v1")
    app.include_router(notifications_ws.router, prefix="/api/v1")

    # Mount versioned API
    app.mount("/api/v1", v1_app)

    return app


app = create_app()
