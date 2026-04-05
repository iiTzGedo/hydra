"""API key mixin: create, list, revoke, and validate API keys."""

import secrets
from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.core.exceptions import (
    ApiKeyNotFoundError,
    InvalidTokenError,
)
from hydra.api.v1.core.security import hash_password, verify_password
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.auth import CreateApiKeyRequest
from hydra.api.v1.models.notifications import (
    ActorType,
    NotificationActor,
    NotificationSource,
    NotificationType,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient

logger = structlog.get_logger(__name__)


class ApiKeysMixin:
    """Mixin providing API key management."""
    db: MongoDB
    redis: RedisClient | None

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None: ...


    async def create_api_key(
        self, request: CreateApiKeyRequest, user_id: str
    ) -> dict[str, Any]:
        """Create an API key for a user.

        Args:
            request: API key creation payload with name, optional roles, permissions, expiry.
            user_id: The owning user's identifier.

        Returns:
            The created API key details including the key string (shown only once).
        """
        key_id = f"key_{secrets.token_urlsafe(8)}"
        key = f"hyk_{key_id}.{secrets.token_urlsafe(32)}"
        now = datetime.now(UTC)

        roles = None
        if request.roles:
            roles = [r.value for r in request.roles]

        key_doc = {
            "keyId": key_id,
            "keyHash": hash_password(key),
            "name": request.name,
            "type": "user",
            "ownerId": user_id,
            "ownerType": "user",
            "nodeId": None,
            "roles": roles,
            "permissions": request.permissions,
            "expiresAt": request.expires_at,
            "lastUsedAt": None,
            "usageCount": 0,
            "createdAt": now,
            "revokedAt": None,
        }

        await self.db.api_keys.insert_one(key_doc)
        logger.info("api_key_created", key_id=key_id, user_id=user_id)

        audit_id = await log_audit(
            AuditAction.CREATE, "api_key", key_id,
            "user", user_id, True,
            details={"keyId": key_id, "name": request.name, "userId": user_id},
        )

        safe_create_task(emit_notification(
            notification_type=NotificationType.API_KEY_CREATED,
            source=NotificationSource(component="hydra-api", service="auth"),  # type: ignore[arg-type]
            title="API key created",
            message=f"API key '{request.name}' created",
            details={"keyId": key_id, "entityId": key_id, "name": request.name, "userId": user_id},
            actor=NotificationActor(type=ActorType.USER, id=user_id),
            target_user_id=user_id,
            audit_entry_id=audit_id,
            mongodb=self.db,
            redis=self.redis,
            resolve_dependencies=False,
        ))

        return {
            "key_id": key_id,
            "key": key,
            "name": request.name,
            "roles": request.roles,
            "permissions": request.permissions,
            "expires_at": request.expires_at,
            "created_by": user_id,
            "created_at": now,
        }

    async def list_api_keys(
        self, user_id: str, include_sub_account_ids: list[str] | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """List active API keys for a user and optionally their sub-accounts.

        Args:
            user_id: The user identifier.
            include_sub_account_ids: Optional list of sub-account user IDs to include.

        Returns:
            Tuple of (api_keys list, total count).
        """
        owner_ids = [user_id]
        if include_sub_account_ids:
            owner_ids.extend(include_sub_account_ids)

        cursor = self.db.api_keys.find({
            "ownerId": {"$in": owner_ids},
            "revokedAt": None,
        }).sort("createdAt", -1)

        api_keys = []
        async for doc in cursor:
            api_keys.append({
                "key_id": doc["keyId"],
                "name": doc["name"],
                "type": doc.get("type", "user"),
                "owner_id": doc["ownerId"],
                "node_id": doc.get("nodeId"),
                "permissions": doc.get("permissions", []),
                "expires_at": doc.get("expiresAt"),
                "last_used_at": doc.get("lastUsedAt"),
                "usage_count": doc.get("usageCount", 0),
                "created_at": doc["createdAt"],
            })

        return api_keys, len(api_keys)

    async def revoke_api_key(self, key_id: str, user_id: str, user_role: str | None = None) -> dict[str, Any]:
        """Revoke an API key.

        Args:
            key_id: The API key identifier.
            user_id: The user requesting revocation.
            user_role: The user's role (admins can revoke any key).

        Returns:
            Dict with 'key_id', 'revoked' status, and 'revoked_at' timestamp.

        Raises:
            ApiKeyNotFoundError: If the key does not exist or user lacks permission.
        """
        key_doc = await self.db.api_keys.find_one({"keyId": key_id})
        if not key_doc:
            raise ApiKeyNotFoundError(key_id)

        if key_doc["ownerId"] != user_id and user_role != "admin":
            owner = await self.db.users.find_one({"userId": key_doc["ownerId"]})
            if not owner or owner.get("parentUserId") != user_id:
                raise ApiKeyNotFoundError(key_id)

        now = datetime.now(UTC)
        await self.db.api_keys.update_one(
            {"keyId": key_id},
            {"$set": {"revokedAt": now}},
        )

        logger.info("api_key_revoked", key_id=key_id, user_id=user_id)

        audit_id = await log_audit(
            AuditAction.REVOKE, "api_key", key_id,
            "user", user_id, True,
            details={"keyId": key_id, "keyName": key_doc.get("name"), "userId": user_id},
        )

        safe_create_task(emit_notification(
            notification_type=NotificationType.API_KEY_REVOKED,
            source=NotificationSource(component="hydra-api", service="auth"),  # type: ignore[arg-type]
            title="API key revoked",
            message=f"API key '{key_id}' revoked",
            details={"keyId": key_id, "entityId": key_id, "userId": user_id},
            actor=NotificationActor(type=ActorType.USER, id=user_id),
            target_user_id=user_id,
            audit_entry_id=audit_id,
            mongodb=self.db,
            redis=self.redis,
            resolve_dependencies=False,
        ))

        return {
            "key_id": key_id,
            "revoked": True,
            "revoked_at": now,
        }

    async def validate_api_key(self, api_key: str) -> dict[str, Any]:
        """Validate an API key and return its associated data.

        Hydra API keys embed the keyId for O(1) lookup:
            hyk_<keyId>.<secret>

        Args:
            api_key: The API key string (must start with 'hyk_').

        Returns:
            The API key document if valid.

        Raises:
            InvalidTokenError: If the key is invalid, expired, or revoked.
        """
        if not api_key.startswith("hyk_"):
            raise InvalidTokenError("Invalid API key format")

        key_id = self._extract_key_id(api_key)
        if not key_id:
            raise InvalidTokenError("Invalid API key format")

        key_doc = await self.db.api_keys.find_one(
            {"keyId": key_id, "revokedAt": None}
        )
        if key_doc and verify_password(api_key, key_doc["keyHash"]):
            return await self._validate_and_touch(key_doc)

        raise InvalidTokenError("Invalid API key")

    @staticmethod
    def _extract_key_id(api_key: str) -> str | None:
        """Extract the embedded keyId from the new key format.

        New format: hyk_<keyId>.<secret>
        """
        if api_key.startswith("hyk_") and "." in api_key:
            key_part = api_key[4:].split(".", 1)[0]
            if key_part:
                return key_part
        return None

    async def _validate_and_touch(self, key_doc: dict[str, Any]) -> dict[str, Any]:
        """Validate expiry and update usage tracking for a matched key."""
        expires_at = self._to_utc(key_doc.get("expiresAt"))
        if expires_at and expires_at < datetime.now(UTC):
            raise InvalidTokenError("API key has expired")

        await self.db.api_keys.update_one(
            {"keyId": key_doc["keyId"]},
            {
                "$set": {"lastUsedAt": datetime.now(UTC)},
                "$inc": {"usageCount": 1},
            },
        )
        return key_doc
