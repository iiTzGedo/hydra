"""MongoDB index definitions and setup."""

from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel

logger = structlog.get_logger(__name__)

INDEXES: dict[str, list[IndexModel]] = {
    "nodes": [
        IndexModel([("nodeId", ASCENDING)], unique=True),
        IndexModel([("class", ASCENDING), ("type", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("tags", ASCENDING)]),
        IndexModel([("parentNodeId", ASCENDING)]),
        IndexModel([("networkIds", ASCENDING)]),
        IndexModel([("lastProfileAt", DESCENDING)]),
        IndexModel([("lastSeenAt", DESCENDING)]),
        IndexModel(
            [("displayName", TEXT), ("description", TEXT)],
            default_language="english",
        ),
    ],
    "profiles": [
        IndexModel([("profileId", ASCENDING)], unique=True),
        IndexModel([("nodeId", ASCENDING), ("submittedAt", DESCENDING)]),
        IndexModel([("nodeId", ASCENDING), ("version", ASCENDING)], unique=True),
        IndexModel([("submittedAt", DESCENDING)]),
        IndexModel([("serviceIds", ASCENDING)]),
    ],
    "profile_meta": [
        IndexModel([("profileId", ASCENDING)], unique=True),
        IndexModel([("nodeId", ASCENDING), ("version", ASCENDING)]),
        IndexModel([("profileHash", ASCENDING)]),
    ],
    "services": [
        IndexModel([("serviceId", ASCENDING)], unique=True),
        IndexModel([("nodeId", ASCENDING)]),
        IndexModel([("runtime", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("tags", ASCENDING)]),
        IndexModel([("lastSeen", DESCENDING)]),
        IndexModel(
            [("name", TEXT), ("displayName", TEXT), ("description", TEXT)],
            default_language="english",
        ),
    ],
    "known_services": [
        IndexModel([("knownServiceId", ASCENDING)], unique=True),
        IndexModel([("runtime", ASCENDING), ("normalizedName", ASCENDING)], unique=True),
        IndexModel(
            [("name", TEXT), ("description", TEXT)],
            default_language="english",
        ),
    ],
    "groups": [
        IndexModel([("groupId", ASCENDING)], unique=True),
        IndexModel([("parentGroupIds", ASCENDING)]),
        IndexModel([("tags", ASCENDING)]),
        IndexModel([("types", ASCENDING)]),
    ],
    "networks": [
        IndexModel([("networkId", ASCENDING)], unique=True),
        IndexModel([("type", ASCENDING)]),
        IndexModel([("cidr", ASCENDING)]),
        IndexModel([("parentNetworkId", ASCENDING)]),
        IndexModel([("routerNodeId", ASCENDING)]),
        IndexModel([("tags", ASCENDING)]),
    ],
    "topologies": [
        IndexModel([("topologyId", ASCENDING)], unique=True),
        IndexModel([("mode", ASCENDING), ("generatedAt", DESCENDING)]),
        IndexModel([("mode", ASCENDING), ("validFrom", ASCENDING), ("validUntil", ASCENDING)]),
    ],
    "users": [
        IndexModel([("userId", ASCENDING)], unique=True),
        IndexModel([("username", ASCENDING)], unique=True),
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("role", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("temporaryRoles.expiresAt", ASCENDING)], sparse=True),
    ],
    "users_pending": [
        IndexModel([("userId", ASCENDING)], unique=True),
        IndexModel([("username", ASCENDING)], unique=True),
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("role", ASCENDING)]),
        IndexModel([("requestedAt", ASCENDING)], expireAfterSeconds=604800),
    ],
    "tokens": [
        IndexModel([("token", ASCENDING)], unique=True),
        IndexModel([("type", ASCENDING)]),
        IndexModel([("expiresAt", ASCENDING)], expireAfterSeconds=0),
        IndexModel([("createdBy", ASCENDING)]),
    ],
    "api_keys": [
        IndexModel([("keyId", ASCENDING)], unique=True),
        IndexModel([("ownerId", ASCENDING)]),
        IndexModel([("type", ASCENDING)]),
        IndexModel([("nodeId", ASCENDING)], sparse=True),
        IndexModel([("expiresAt", ASCENDING)], expireAfterSeconds=0, sparse=True),
        IndexModel([("revokedAt", ASCENDING)], sparse=True),
    ],
    "commands": [
        IndexModel([("commandId", ASCENDING)], unique=True),
        IndexModel([("target.nodeId", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("status", ASCENDING), ("createdAt", ASCENDING)]),
        IndexModel([("createdAt", DESCENDING)]),
        IndexModel([("registryId", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("chain.chainId", ASCENDING)], sparse=True),
    ],
    "command_definitions": [
        IndexModel([("registryId", ASCENDING)], unique=True),
        IndexModel([("category", ASCENDING)]),
        IndexModel([("metadata.builtIn", ASCENDING)]),
    ],
    "workflows": [
        IndexModel([("chainId", ASCENDING)], unique=True),
        IndexModel([("createdBy", ASCENDING), ("createdAt", DESCENDING)]),
    ],
    "workflow_executions": [
        IndexModel([("executionId", ASCENDING)], unique=True),
        IndexModel([("chainId", ASCENDING), ("startedAt", DESCENDING)]),
        IndexModel([("status", ASCENDING)]),
    ],
    "audit_log": [
        IndexModel([("timestamp", DESCENDING)]),
        IndexModel([("action", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("resource.type", ASCENDING), ("resource.id", ASCENDING)]),
        IndexModel([("actor.id", ASCENDING)]),
    ],
    "ai_models": [
        IndexModel([("providerId", ASCENDING)], unique=True),
        IndexModel([("createdBy", ASCENDING), ("createdAt", DESCENDING)]),
        IndexModel([("type", ASCENDING)]),
        IndexModel([("isDefault", ASCENDING)], sparse=True),
    ],
    "chat_projects": [
        IndexModel([("projectId", ASCENDING)], unique=True),
        IndexModel([("ownerId", ASCENDING), ("createdAt", DESCENDING)]),
        IndexModel([("updatedAt", DESCENDING)]),
    ],
    "chat_sessions": [
        IndexModel([("sessionId", ASCENDING)], unique=True),
        IndexModel([("projectId", ASCENDING), ("lastMessageAt", DESCENDING)]),
        IndexModel([("ownerId", ASCENDING), ("lastMessageAt", DESCENDING)]),
        IndexModel([("status", ASCENDING)]),
    ],
    "chat_messages": [
        IndexModel([("messageId", ASCENDING)], unique=True),
        IndexModel([("sessionId", ASCENDING), ("order", ASCENDING)]),
        IndexModel([("sessionId", ASCENDING), ("createdAt", ASCENDING)]),
    ],
    "mcp_servers": [
        IndexModel([("serverId", ASCENDING)], unique=True),
        IndexModel([("ownerId", ASCENDING), ("createdAt", DESCENDING)]),
        IndexModel([("category", ASCENDING)]),
        IndexModel([("enabled", ASCENDING)]),
    ],
    "user_settings": [
        IndexModel([("userId", ASCENDING)], unique=True),
    ],
    "notifications": [
        IndexModel([("notificationId", ASCENDING)], unique=True),
        IndexModel(
            [("targetRoles", ASCENDING), ("status", ASCENDING), ("createdAt", DESCENDING)]
        ),
        IndexModel(
            [("targetUserId", ASCENDING), ("status", ASCENDING), ("createdAt", DESCENDING)]
        ),
        IndexModel([("groupKey", ASCENDING), ("status", ASCENDING)]),
        IndexModel(
            [("tier", ASCENDING), ("status", ASCENDING), ("createdAt", DESCENDING)]
        ),
        IndexModel([("source.component", ASCENDING), ("createdAt", DESCENDING)]),
        IndexModel([("source.nodeId", ASCENDING), ("createdAt", DESCENDING)]),
        IndexModel([("expiresAt", ASCENDING)], expireAfterSeconds=0),
        IndexModel([("correlationId", ASCENDING)], sparse=True),
        IndexModel([("auditEntryId", ASCENDING)], sparse=True),
    ],
    "notification_reads": [
        IndexModel(
            [("notificationId", ASCENDING), ("userId", ASCENDING)], unique=True
        ),
        IndexModel([("userId", ASCENDING), ("readAt", DESCENDING)]),
    ],
    "plugins": [
        IndexModel([("pluginId", ASCENDING)], unique=True),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("manifest.classification", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("manifest.category", ASCENDING)]),
        IndexModel([("nodeBindings.nodeId", ASCENDING)]),
    ],
    "installations": [
        IndexModel([("installationId", ASCENDING)], unique=True),
        IndexModel([("status", ASCENDING), ("createdAt", DESCENDING)]),
        IndexModel([("discoveryId", ASCENDING)], sparse=True),
        IndexModel([("targetIp", ASCENDING)]),
    ],
    "dashboards": [
        IndexModel([("boardId", ASCENDING)], unique=True),
        IndexModel([("ownerId", ASCENDING), ("boardType", ASCENDING)]),
        IndexModel([("ownerId", ASCENDING), ("isHome", ASCENDING)]),
        IndexModel(
            [("visibility.scope", ASCENDING), ("visibility.sharedWith.roles", ASCENDING)]
        ),
        IndexModel([("visibility.sharedWith.users", ASCENDING)]),
        IndexModel([("boardType", ASCENDING)]),
        IndexModel([("tags", ASCENDING)]),
        IndexModel([("archivedAt", ASCENDING)], expireAfterSeconds=2592000, sparse=True),
        IndexModel([("updatedAt", DESCENDING)]),
        IndexModel(
            [("name", TEXT), ("description", TEXT), ("tags", TEXT)],
            default_language="english",
        ),
    ],
    "dashboard_templates": [
        IndexModel([("templateId", ASCENDING)], unique=True),
        IndexModel([("category", ASCENDING)]),
        IndexModel([("source", ASCENDING)]),
        IndexModel([("targetRoles", ASCENDING)]),
        IndexModel([("tags", ASCENDING)]),
        IndexModel([("createdBy", ASCENDING), ("createdAt", DESCENDING)]),
        IndexModel(
            [("name", TEXT), ("description", TEXT), ("tags", TEXT)],
            default_language="english",
        ),
    ],
    "dashboard_versions": [
        IndexModel([("boardId", ASCENDING), ("version", ASCENDING)], unique=True),
        IndexModel([("boardId", ASCENDING), ("version", DESCENDING)]),
        IndexModel([("savedAt", DESCENDING)]),
    ],
}


async def ensure_indexes(db: "AsyncIOMotorDatabase[Any]") -> None:
    """Create all indexes for all collections.

    Args:
        db: MongoDB database instance.
    """
    logger.info("ensuring_indexes")

    for collection_name, indexes in INDEXES.items():
        collection = db[collection_name]
        try:
            await collection.create_indexes(indexes)
            logger.info("indexes_created", collection=collection_name, count=len(indexes))
        except Exception as e:
            logger.error(
                "index_creation_failed",
                collection=collection_name,
                error=str(e),
            )
            raise

    logger.info("all_indexes_created")


async def drop_indexes(db: "AsyncIOMotorDatabase[Any]", exclude_id: bool = True) -> None:
    """Drop all indexes (for testing/reset).

    Args:
        db: MongoDB database instance.
        exclude_id: If True, keeps the _id index.
    """
    logger.warning("dropping_indexes")

    for collection_name in INDEXES:
        collection = db[collection_name]
        try:
            if exclude_id:
                async for index in collection.list_indexes():
                    if index["name"] != "_id_":
                        await collection.drop_index(index["name"])
            else:
                await collection.drop_indexes()
            logger.info("indexes_dropped", collection=collection_name)
        except Exception as e:
            logger.error(
                "index_drop_failed",
                collection=collection_name,
                error=str(e),
            )

    logger.info("all_indexes_dropped")
