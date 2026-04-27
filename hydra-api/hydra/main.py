"""Hydra API root application entry point."""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from hydra.api.v1 import __version__
from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers import chat_ws, discovery_ws, health, notifications_ws
from hydra.api.v1.services.health_scanner import HealthScanner
from hydra.core.config import get_settings
from hydra.core.logging import configure_logging
from hydra.db.indexes import ensure_indexes
from hydra.db.mongodb import get_mongodb
from hydra.db.redis import get_redis

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
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

    # Heal known enum-drift in legacy MongoDB documents BEFORE any list
    # endpoint becomes reachable. Idempotent — safe to run every boot.
    from hydra.db.migrations import heal_enum_drift
    await heal_enum_drift(mongodb.db)

    # Seed Network records from local host interfaces (spec §2.2.1).
    # Failures here must not abort startup.
    from hydra.api.v1.services.discovery.host_interfaces import introspect_and_seed
    await introspect_and_seed(mongodb.db)

    # Seed built-in command definitions
    from hydra.api.v1.services.commands.registry import CommandRegistryService
    registry_service = CommandRegistryService(mongodb)
    await registry_service.seed_builtin_commands()

    # Seed built-in dashboard templates
    from hydra.api.v1.services.dashboards import DashboardService
    dashboard_service = DashboardService(mongodb)
    await dashboard_service.seed_builtin_templates()

    # Seed system-default entity panel boards (node, service, network).
    # Failures here must not abort startup — panel endpoints will raise
    # RuntimeError on GET if panels aren't seeded, which is preferable to
    # a crashed server.
    try:
        from hydra.api.v1.services.dashboards.seed_panels import seed_system_panels
        await seed_system_panels(mongodb.db)
        logger.info("seeded_system_panels")
    except Exception as exc:  # noqa: BLE001
        logger.warning("system_panel_seed_failed", error=str(exc))

    # Seed core plugin manifests and their contributed commands
    from hydra.api.v1.models.plugins import PluginManifest
    from hydra.api.v1.services.plugins import PLUGIN_REGISTRY
    if PLUGIN_REGISTRY:
        plugins_col = mongodb.plugins
        cmd_defs_col = mongodb.command_definitions
        seeded = 0
        for plugin_id, handler_cls in PLUGIN_REGISTRY.items():
            # Validate manifest through Pydantic and serialize with camelCase aliases
            manifest_model = PluginManifest(**handler_cls.MANIFEST)
            manifest = manifest_model.model_dump(by_alias=True)
            now = datetime.now(UTC)
            # Upsert plugin manifest (idempotent, starts as "installed")
            result = await plugins_col.update_one(
                {"pluginId": plugin_id},
                {
                    "$set": {"manifest": manifest, "updatedAt": now},
                    "$setOnInsert": {
                        "pluginId": plugin_id,
                        "status": "installed",
                        "config": {},
                        "nodeBindings": [],
                        "health": {
                            "status": "unknown",
                            "lastCheck": None,
                            "consecutiveFailures": 0,
                            "lastError": None,
                            "responseTimeMs": None,
                        },
                        "createdAt": now,
                    },
                },
                upsert=True,
            )
            if result.upserted_id or result.modified_count:
                seeded += 1
            # Upsert contributed command definitions with plugin source markers
            for cmd_def in handler_cls.COMMAND_DEFINITIONS:
                enriched = {**cmd_def, "source": "plugin", "pluginId": plugin_id}
                await cmd_defs_col.update_one(
                    {"registryId": enriched["registryId"]},
                    {"$set": enriched},
                    upsert=True,
                )
        if seeded:
            logger.info("core_plugins_seeded", total=len(PLUGIN_REGISTRY), upserted=seeded)

    # Set startup time for uptime tracking
    health.set_startup_time()

    logger.info("hydra_api_started")

    # Start background health scanner
    scanner = HealthScanner(mongodb, redis)
    scanner_task = asyncio.create_task(scanner.run())

    # Start background command timeout checker
    from hydra.api.v1.services.commands import CommandsService

    async def command_timeout_loop() -> None:
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

    async def auto_retry_loop() -> None:
        """Periodically schedule retries for failed commands with auto-retry."""
        while True:
            try:
                await asyncio.sleep(60)
                svc = CommandsService(mongodb)
                count = await svc.schedule_auto_retries()
                if count > 0:
                    logger.info("auto_retries_scheduled_background", count=count)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("auto_retry_loop_error", error=str(e))

    auto_retry_task = asyncio.create_task(auto_retry_loop())

    yield

    # Shutdown
    logger.info("shutting_down_hydra_api")
    auto_retry_task.cancel()
    timeout_task.cancel()
    scanner_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await auto_retry_task
    with contextlib.suppress(asyncio.CancelledError):
        await timeout_task
    with contextlib.suppress(asyncio.CancelledError):
        await scanner_task
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
    async def landing_page() -> HTMLResponse:
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
    async def favicon() -> FileResponse:
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
    app.include_router(discovery_ws.router, prefix="/api/v1")

    # Mount versioned API
    app.mount("/api/v1", v1_app)

    return app


app = create_app()
