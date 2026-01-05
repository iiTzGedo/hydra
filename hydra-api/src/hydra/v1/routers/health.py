"""Health check and service info endpoints."""

import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends

from hydra.v1 import __version__
from hydra.v1.core.deps import StorageServiceDep
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis
from hydra.v1.models.common import HealthCheck, ServiceInfo

router = APIRouter(tags=["Health"])
logger = structlog.get_logger(__name__)

# Track startup time for uptime calculation
_startup_time: float | None = None


def set_startup_time() -> None:
    """Set the startup time. Called during application startup."""
    global _startup_time
    _startup_time = time.time()


def get_uptime() -> float:
    """Get the uptime in seconds."""
    if _startup_time is None:
        return 0.0
    return time.time() - _startup_time


@router.get(
    "/health",
    response_model=HealthCheck,
    summary="Health Check",
    description="Check the health status of the API and its dependencies.",
)
async def health_check(
    mongodb: MongoDB = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis),
    storage: StorageServiceDep = None,
) -> HealthCheck:
    """
    Health check endpoint.

    Checks the status of:
    - MongoDB connection
    - Redis connection
    - Object storage (if configured)
    - Agent binary availability
    """
    checks: dict[str, str] = {}

    # Check MongoDB
    try:
        if await mongodb.health_check():
            checks["database"] = "ok"
        else:
            checks["database"] = "error"
    except Exception as e:
        logger.warning("health_check_mongodb_failed", error=str(e))
        checks["database"] = "error"

    # Check Redis
    try:
        if await redis.health_check():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "error"
    except Exception as e:
        logger.warning("health_check_redis_failed", error=str(e))
        checks["redis"] = "error"

    # Check Object Storage / Agent Binaries
    if storage is not None:
        try:
            if await storage.health_check():
                checks["storage"] = "ok"
            else:
                checks["storage"] = "error"
        except Exception as e:
            logger.warning("health_check_storage_failed", error=str(e))
            checks["storage"] = "error"
    else:
        checks["storage"] = "not_configured"

    # Determine overall status
    # Only database and redis are required for healthy status
    required_checks = [checks.get("database"), checks.get("redis")]
    all_required_ok = all(v == "ok" for v in required_checks)
    status = "healthy" if all_required_ok else "degraded"

    return HealthCheck(
        status=status,
        version=__version__,
        timestamp=datetime.now(timezone.utc),
        checks=checks,
        uptime_seconds=get_uptime(),
    )


@router.get(
    "/info",
    response_model=ServiceInfo,
    summary="Service Information",
    description="Get information about the service and its statistics.",
)
async def service_info(
    mongodb: MongoDB = Depends(get_mongodb),
) -> ServiceInfo:
    """
    Service information endpoint.

    Returns service metadata and statistics about:
    - Node counts by class and status
    - Service counts by runtime and status
    - Network and group counts
    - Profile and user counts
    - Enabled features
    """
    stats: dict = {
        "nodes": {"total": 0, "active": 0, "byClass": {}},
        "services": {"total": 0, "running": 0},
        "networks": {"total": 0},
        "groups": {"total": 0},
        "profiles": {"total": 0},
        "users": {"total": 0},
    }

    try:
        # Node statistics
        node_pipeline = [
            {
                "$facet": {
                    "total": [{"$count": "count"}],
                    "active": [{"$match": {"status": "active"}}, {"$count": "count"}],
                    "byClass": [
                        {"$group": {"_id": "$class", "count": {"$sum": 1}}},
                    ],
                }
            }
        ]
        async for result in mongodb.nodes.aggregate(node_pipeline):
            stats["nodes"]["total"] = (
                result["total"][0]["count"] if result["total"] else 0
            )
            stats["nodes"]["active"] = (
                result["active"][0]["count"] if result["active"] else 0
            )
            stats["nodes"]["byClass"] = {
                item["_id"]: item["count"] for item in result["byClass"]
            }

        # Service statistics
        service_pipeline = [
            {
                "$facet": {
                    "total": [{"$count": "count"}],
                    "running": [{"$match": {"status": "running"}}, {"$count": "count"}],
                }
            }
        ]
        async for result in mongodb.services.aggregate(service_pipeline):
            stats["services"]["total"] = (
                result["total"][0]["count"] if result["total"] else 0
            )
            stats["services"]["running"] = (
                result["running"][0]["count"] if result["running"] else 0
            )

        # Simple counts for other collections
        stats["networks"]["total"] = await mongodb.networks.count_documents({})
        stats["groups"]["total"] = await mongodb.groups.count_documents({})
        stats["profiles"]["total"] = await mongodb.profiles.count_documents({})
        stats["users"]["total"] = await mongodb.users.count_documents({})

    except Exception as e:
        logger.warning("service_info_stats_failed", error=str(e))

    return ServiceInfo(
        name="hydra-api",
        version=__version__,
        api_version="v1",
        stats=stats,
        features={
            "topologyGeneration": True,
            "timeMachine": True,
            "autoNetworkCreation": True,
            "rbac": True,
            "writeOperations": False,  # Phase 4
            "homeAssistant": False,  # Phase 5
        },
    )
