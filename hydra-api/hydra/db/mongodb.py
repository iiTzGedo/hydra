"""MongoDB client and connection management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError

from hydra.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class MongoDB:
    """MongoDB connection manager with health checks and retry logic."""

    def __init__(self, settings: Settings | None = None):
        """Initialize MongoDB connection manager.

        Args:
            settings: Application settings (uses global if not provided).
        """
        self.settings = settings or get_settings()
        self._client: AsyncIOMotorClient[Any] | None = None
        self._db: AsyncIOMotorDatabase[Any] | None = None

    @property
    def client(self) -> AsyncIOMotorClient[Any]:
        """Get the MongoDB client.

        Raises:
            RuntimeError: If client not initialized.
        """
        if self._client is None:
            raise RuntimeError("MongoDB client not initialized. Call connect() first.")
        return self._client

    @property
    def db(self) -> AsyncIOMotorDatabase[Any]:
        """Get the database instance.

        Raises:
            RuntimeError: If database not initialized.
        """
        if self._db is None:
            raise RuntimeError("MongoDB database not initialized. Call connect() first.")
        return self._db

    async def connect(self) -> None:
        """Establish connection to MongoDB."""
        hosts = self.settings.mongodb_uri.hosts()
        masked_host = hosts[0]["host"] if hosts else ""
        masked_uri = str(self.settings.mongodb_uri).replace(masked_host, "***") if masked_host else str(self.settings.mongodb_uri)
        logger.info(
            "connecting_to_mongodb",
            uri=masked_uri,
            database=self.settings.mongodb_database,
        )

        self._client = AsyncIOMotorClient(
            str(self.settings.mongodb_uri),
            minPoolSize=self.settings.mongodb_min_pool_size,
            maxPoolSize=self.settings.mongodb_max_pool_size,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            tz_aware=True,
            tzinfo=UTC,
        )
        self._db = self._client[self.settings.mongodb_database]

        healthy = await self.health_check()
        if not healthy:
            logger.error(
                "mongodb_connection_unhealthy",
                database=self.settings.mongodb_database,
            )
            raise ConnectionFailure("MongoDB health check failed")
        logger.info("mongodb_connected", database=self.settings.mongodb_database)

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("mongodb_disconnected")

    async def health_check(self) -> bool:
        """Check if MongoDB connection is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            await self.client.admin.command("ping")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError, OperationFailure) as e:
            logger.error("mongodb_health_check_failed", error=str(e))
            return False

    @property
    def nodes(self) -> AsyncIOMotorCollection[Any]:
        """Nodes collection."""
        return self.db.nodes

    @property
    def profiles(self) -> AsyncIOMotorCollection[Any]:
        """Profiles collection."""
        return self.db.profiles

    @property
    def profile_meta(self) -> AsyncIOMotorCollection[Any]:
        """Profile metadata collection."""
        return self.db.profile_meta

    @property
    def services(self) -> AsyncIOMotorCollection[Any]:
        """Services collection."""
        return self.db.services

    @property
    def known_services(self) -> AsyncIOMotorCollection[Any]:
        """Known services registry collection."""
        return self.db.known_services

    @property
    def groups(self) -> AsyncIOMotorCollection[Any]:
        """Groups collection."""
        return self.db.groups

    @property
    def networks(self) -> AsyncIOMotorCollection[Any]:
        """Networks collection."""
        return self.db.networks

    @property
    def topologies(self) -> AsyncIOMotorCollection[Any]:
        """Topologies collection."""
        return self.db.topologies

    @property
    def users(self) -> AsyncIOMotorCollection[Any]:
        """Users collection."""
        return self.db.users

    @property
    def users_pending(self) -> AsyncIOMotorCollection[Any]:
        """Pending users collection (for approval workflow)."""
        return self.db.users_pending

    @property
    def tokens(self) -> AsyncIOMotorCollection[Any]:
        """Tokens collection (registration tokens)."""
        return self.db.tokens

    @property
    def api_keys(self) -> AsyncIOMotorCollection[Any]:
        """API keys collection."""
        return self.db.api_keys

    @property
    def commands(self) -> AsyncIOMotorCollection[Any]:
        """Commands collection."""
        return self.db.commands

    @property
    def command_definitions(self) -> AsyncIOMotorCollection[Any]:
        """Command definitions (registry/catalog) collection."""
        return self.db.command_definitions

    @property
    def workflows(self) -> AsyncIOMotorCollection[Any]:
        """Workflow definitions collection."""
        return self.db.workflows

    @property
    def workflow_executions(self) -> AsyncIOMotorCollection[Any]:
        """Workflow execution records collection."""
        return self.db.workflow_executions

    @property
    def audit_log(self) -> AsyncIOMotorCollection[Any]:
        """Audit log collection."""
        return self.db.audit_log

    @property
    def password_reset_tokens(self) -> AsyncIOMotorCollection[Any]:
        """Password reset tokens collection."""
        return self.db.password_reset_tokens

    @property
    def docs(self) -> AsyncIOMotorCollection[Any]:
        """Documentation collection."""
        return self.db.docs

    @property
    def ai_models(self) -> AsyncIOMotorCollection[Any]:
        """AI/LLM provider configurations collection."""
        return self.db.ai_models

    @property
    def global_api_keys(self) -> AsyncIOMotorCollection[Any]:
        """Global API keys collection for LLM providers."""
        return self.db.global_api_keys

    @property
    def mcp_servers(self) -> AsyncIOMotorCollection[Any]:
        """MCP server configurations collection."""
        return self.db.mcp_servers

    @property
    def chat_projects(self) -> AsyncIOMotorCollection[Any]:
        """Chat projects collection."""
        return self.db.chat_projects

    @property
    def chat_sessions(self) -> AsyncIOMotorCollection[Any]:
        """Chat sessions collection."""
        return self.db.chat_sessions

    @property
    def chat_messages(self) -> AsyncIOMotorCollection[Any]:
        """Chat messages collection."""
        return self.db.chat_messages

    @property
    def user_settings(self) -> AsyncIOMotorCollection[Any]:
        """User settings collection."""
        return self.db.user_settings

    @property
    def system_settings(self) -> AsyncIOMotorCollection[Any]:
        """System settings collection."""
        return self.db.system_settings

    @property
    def notifications(self) -> AsyncIOMotorCollection[Any]:
        """Notifications collection."""
        return self.db.notifications

    @property
    def notification_reads(self) -> AsyncIOMotorCollection[Any]:
        """Per-user notification read state collection."""
        return self.db.notification_reads


_mongodb: MongoDB | None = None


def get_mongodb() -> MongoDB:
    """Get the global MongoDB instance.

    Returns:
        Singleton MongoDB instance.
    """
    global _mongodb
    if _mongodb is None:
        _mongodb = MongoDB()
    return _mongodb


@asynccontextmanager
async def mongodb_lifespan() -> AsyncGenerator[MongoDB, None]:
    """Context manager for MongoDB lifecycle.

    Yields:
        Connected MongoDB instance.
    """
    mongo = get_mongodb()
    await mongo.connect()
    try:
        yield mongo
    finally:
        await mongo.disconnect()
