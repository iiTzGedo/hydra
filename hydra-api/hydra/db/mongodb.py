"""MongoDB client and connection management."""

from contextlib import asynccontextmanager
from datetime import timezone
from typing import AsyncGenerator

import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
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
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    @property
    def client(self) -> AsyncIOMotorClient:
        """Get the MongoDB client.

        Raises:
            RuntimeError: If client not initialized.
        """
        if self._client is None:
            raise RuntimeError("MongoDB client not initialized. Call connect() first.")
        return self._client

    @property
    def db(self) -> AsyncIOMotorDatabase:
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
            tzinfo=timezone.utc,
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
    def nodes(self):
        """Nodes collection."""
        return self.db.nodes

    @property
    def profiles(self):
        """Profiles collection."""
        return self.db.profiles

    @property
    def profile_meta(self):
        """Profile metadata collection."""
        return self.db.profile_meta

    @property
    def services(self):
        """Services collection."""
        return self.db.services

    @property
    def known_services(self):
        """Known services registry collection."""
        return self.db.known_services

    @property
    def groups(self):
        """Groups collection."""
        return self.db.groups

    @property
    def networks(self):
        """Networks collection."""
        return self.db.networks

    @property
    def topologies(self):
        """Topologies collection."""
        return self.db.topologies

    @property
    def users(self):
        """Users collection."""
        return self.db.users

    @property
    def users_pending(self):
        """Pending users collection (for approval workflow)."""
        return self.db.users_pending

    @property
    def tokens(self):
        """Tokens collection (registration tokens)."""
        return self.db.tokens

    @property
    def api_keys(self):
        """API keys collection."""
        return self.db.api_keys

    @property
    def commands(self):
        """Commands collection."""
        return self.db.commands

    @property
    def command_definitions(self):
        """Command definitions (registry/catalog) collection."""
        return self.db.command_definitions

    @property
    def workflows(self):
        """Workflow definitions collection."""
        return self.db.workflows

    @property
    def workflow_executions(self):
        """Workflow execution records collection."""
        return self.db.workflow_executions

    @property
    def audit_log(self):
        """Audit log collection."""
        return self.db.audit_log

    @property
    def password_reset_tokens(self):
        """Password reset tokens collection."""
        return self.db.password_reset_tokens

    @property
    def docs(self):
        """Documentation collection."""
        return self.db.docs

    @property
    def ai_models(self):
        """AI/LLM provider configurations collection."""
        return self.db.ai_models

    @property
    def global_api_keys(self):
        """Global API keys collection for LLM providers."""
        return self.db.global_api_keys

    @property
    def mcp_servers(self):
        """MCP server configurations collection."""
        return self.db.mcp_servers

    @property
    def chat_projects(self):
        """Chat projects collection."""
        return self.db.chat_projects

    @property
    def chat_sessions(self):
        """Chat sessions collection."""
        return self.db.chat_sessions

    @property
    def chat_messages(self):
        """Chat messages collection."""
        return self.db.chat_messages

    @property
    def user_settings(self):
        """User settings collection."""
        return self.db.user_settings

    @property
    def system_settings(self):
        """System settings collection."""
        return self.db.system_settings

    @property
    def notifications(self):
        """Notifications collection."""
        return self.db.notifications

    @property
    def notification_reads(self):
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
