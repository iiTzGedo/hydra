"""Health check and service info endpoints."""

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends

from hydra.api.v1 import __version__
from hydra.api.v1.core.deps import StorageServiceDep
from hydra.api.v1.models.common import HealthCheck, ServiceInfo
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis

router = APIRouter(tags=["Health"])
logger = structlog.get_logger(__name__)

_startup_time: float | None = None


def set_startup_time() -> None:
    """Set the startup time for uptime calculation. Called during application startup."""
    global _startup_time
    _startup_time = time.time()


def get_uptime() -> float:
    """Get the service uptime in seconds.

    Returns:
        Uptime in seconds, or 0.0 if startup time not set.
    """
    if _startup_time is None:
        return 0.0
    return time.time() - _startup_time


@router.get(
    "/health",
    response_model=HealthCheck,
    response_model_by_alias=True,
    summary="Health Check",
    description="Check the health status of the API and its dependencies.",
)
async def health_check(
    mongodb: MongoDB = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis),
    storage: StorageServiceDep = None,  # type: ignore[assignment]
) -> HealthCheck:
    """Check health status of the API and all dependencies.

    Performs connectivity checks against MongoDB, Redis, and object storage (if configured).
    Returns healthy if required dependencies (database, redis) are operational.

    Args:
        mongodb: MongoDB database dependency.
        redis: Redis client dependency.
        storage: Optional storage service dependency.

    Returns:
        Health status with individual component check results and uptime.
    """
    checks: dict[str, str] = {}

    try:
        if await mongodb.health_check():
            checks["database"] = "ok"
        else:
            checks["database"] = "error"
    except Exception as e:
        logger.warning("health_check_mongodb_failed", error=str(e))
        checks["database"] = "error"

    try:
        if await redis.health_check():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "error"
    except Exception as e:
        logger.warning("health_check_redis_failed", error=str(e))
        checks["redis"] = "error"

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

    required_checks = [checks.get("database"), checks.get("redis")]
    all_required_ok = all(v == "ok" for v in required_checks)
    status = "healthy" if all_required_ok else "degraded"

    return HealthCheck(
        status=status,
        version=__version__,
        timestamp=datetime.now(UTC),
        checks=checks,
        uptime_seconds=get_uptime(),
    )


@router.get(
    "/info",
    response_model=ServiceInfo,
    response_model_by_alias=True,
    summary="Service Information",
    description="Get information about the service and its statistics.",
)
async def service_info(
    mongodb: MongoDB = Depends(get_mongodb),
) -> ServiceInfo:
    """Get service metadata and infrastructure statistics.

    Aggregates counts for nodes, services, networks, groups, profiles, and users.
    Includes feature flags for enabled capabilities.

    Args:
        mongodb: MongoDB database dependency.

    Returns:
        Service information with version, API version, statistics, and feature flags.
    """
    stats: dict[str, Any] = {
        "nodes": {"total": 0, "active": 0, "byClass": {}},
        "services": {"total": 0, "running": 0},
        "networks": {"total": 0},
        "groups": {"total": 0},
        "profiles": {"total": 0},
        "users": {"total": 0},
    }

    try:
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
            "writeOperations": False,
            "homeAssistant": False,
        },
    )
