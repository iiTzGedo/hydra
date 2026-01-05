"""Hydra API root application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI

from hydra.v1 import __version__
from hydra.core.config import get_settings
from hydra.core.logging import configure_logging
from hydra.db.indexes import ensure_indexes
from hydra.db.mongodb import get_mongodb
from hydra.db.redis import get_redis
from hydra.v1.main import app as v1_app
from hydra.v1.routers import health

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

    # Set startup time for uptime tracking
    health.set_startup_time()

    logger.info("hydra_api_started")

    yield

    # Shutdown
    logger.info("shutting_down_hydra_api")
    await redis.disconnect()
    await mongodb.disconnect()
    logger.info("hydra_api_stopped")


def create_app() -> FastAPI:
    """Create the root application and mount versioned APIs."""
    app = FastAPI(
        title="Hydra API",
        description="AI-powered infrastructure management platform API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    app.mount("/api/v1", v1_app)

    return app


app = create_app()
