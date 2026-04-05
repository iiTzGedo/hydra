"""Core user service - base class with CRUD operations and user retrieval."""

import secrets
from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.core.exceptions import (
    NodeNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from hydra.api.v1.core.role_utils import (
    get_active_temporary_roles as _get_active_temp_roles,
)
from hydra.api.v1.core.role_utils import (
    to_utc,
)
from hydra.api.v1.core.security import hash_password
from hydra.api.v1.models.auth import CreateUserRequest
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class CoreMixin:
    """Mixin providing core user CRUD and retrieval functionality."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None:
        """Convert datetime to UTC. Delegates to shared utility."""
        return to_utc(value)

    def get_active_temporary_roles(self, temp_roles: list) -> list:  # type: ignore[type-arg]
        """Return active temporary roles for a user.

        Delegates to shared utility function for consistency across services.
        """
        return _get_active_temp_roles(temp_roles)

    async def create_user(self, request: CreateUserRequest) -> dict[str, Any]:
        """Create a new user (admin endpoint)."""
        await self._check_username_availability(request.username)  # type: ignore[attr-defined]
        await self._check_email_availability(request.email)  # type: ignore[attr-defined]
        await self._check_role_limit(request.role.value)  # type: ignore[attr-defined]

        user_id = f"user_{secrets.token_urlsafe(8)}"
        now = datetime.now(UTC)

        user_doc = {
            "userId": user_id,
            "username": request.username,
            "email": request.email,
            "passwordHash": hash_password(request.password),
            "role": request.role.value,
            "temporaryRoles": [],
            "permissions": request.permissions,
            "resourcePermissions": [],
            "registeredNodes": [],
            "preferences": request.preferences,
            "status": "active",
            "lastLogin": None,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.users.insert_one(user_doc)
        logger.info("user_created", user_id=user_id, username=request.username)

        await log_audit(
            AuditAction.CREATE, "user", user_id, "user", "admin",
            True, details={"username": request.username, "role": request.role.value},
        )

        return {
            "user_id": user_id,
            "username": request.username,
            "email": request.email,
            "role": request.role.value,
            "created_at": now,
        }

    async def archive_user(self, user_id: str) -> dict[str, Any]:
        """Archive a user (soft delete)."""
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise UserNotFoundError(user_id)

        if user.get("status") == "archived":
            raise ValidationError(f"User '{user_id}' is already archived")

        now = datetime.now(UTC)
        await self.db.users.update_one(
            {"userId": user_id},
            {"$set": {"status": "archived", "updatedAt": now}},
        )

        # Remove from all parent users' subAccounts lists
        result = await self.db.users.update_many(
            {"subAccounts.userId": user_id},
            {
                "$pull": {"subAccounts": {"userId": user_id}},
                "$set": {"updatedAt": now},
            },
        )
        if result.modified_count > 0:
            logger.info(
                "user_removed_from_parent_subaccounts",
                user_id=user_id,
                parents_updated=result.modified_count,
            )

        logger.info("user_archived", user_id=user_id)

        await log_audit(
            AuditAction.DELETE, "user", user_id, "user", user_id, True,
        )

        user["status"] = "archived"
        user["updatedAt"] = now
        return {
            "user_id": user["userId"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "status": user.get("status", "active"),
            "last_login": user.get("lastLogin"),
            "created_at": user["createdAt"],
        }

    async def list_users(self, limit: int = 50, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        """List users.

        Returns:
            Tuple of (users list, total count).
        """
        cursor = self.db.users.find({}).sort("createdAt", -1).skip(offset).limit(limit)

        users = []
        async for doc in cursor:
            users.append({
                "user_id": doc["userId"],
                "username": doc["username"],
                "email": doc["email"],
                "role": doc["role"],
                "status": doc.get("status", "active"),
                "last_login": doc.get("lastLogin"),
                "created_at": doc["createdAt"],
            })

        total = await self.db.users.count_documents({})

        return users, total

    async def is_parent_of(self, parent_user_id: str, child_user_id: str) -> bool:
        """Check if parent_user_id is the direct parent of child_user_id."""
        child = await self.db.users.find_one({"userId": child_user_id})
        if not child:
            return False
        return child.get("parentUserId") == parent_user_id  # type: ignore[no-any-return]

    async def get_current_user(self, token_payload: dict[str, Any]) -> dict[str, Any]:
        """Get current user/agent info from token payload.

        Args:
            token_payload: Decoded JWT payload with subject and type.

        Returns:
            User or agent info with permissions.

        Raises:
            NodeNotFoundError: If agent node not found.
            UserNotFoundError: If user not found.
        """
        sub_type = token_payload.get("sub_type", "user")
        subject = token_payload["sub"]

        if sub_type == "agent":
            node = await self.db.nodes.find_one({"nodeId": subject})
            if not node:
                raise NodeNotFoundError(subject)

            return {
                "type": "agent",
                "node_id": subject,
                "permissions": ["profiles:write", "commands:poll"],
            }
        elif sub_type == "api_key":
            permissions = token_payload.get("permissions", [])
            roles = token_payload.get("roles", [])
            node_id = token_payload.get("node_id")

            if node_id:
                return {
                    "type": "agent",
                    "node_id": node_id,
                    "permissions": permissions,
                }
            else:
                user = await self.db.users.find_one({"userId": subject})
                if not user:
                    raise UserNotFoundError(subject)

                all_permissions = []
                for role in roles or []:
                    all_permissions.extend(self._get_role_permissions(role))  # type: ignore[attr-defined]
                all_permissions.extend(permissions)

                return {
                    "type": "user",
                    "user_id": user["userId"],
                    "username": user["username"],
                    "email": user["email"],
                    "role": user["role"],
                    "permissions": list(set(all_permissions)),
                }
        else:
            user = await self.db.users.find_one({"userId": subject})
            if not user:
                raise UserNotFoundError(subject)

            temp_roles = self.get_active_temporary_roles(user.get("temporaryRoles", []))

            all_permissions = self._get_role_permissions(user["role"])  # type: ignore[attr-defined]
            for tr in temp_roles:
                all_permissions.extend(self._get_role_permissions(tr["role"]))  # type: ignore[attr-defined]
            all_permissions.extend(user.get("permissions", []))

            return {
                "type": "user",
                "user_id": user["userId"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
                "temporary_roles": temp_roles,
                "permissions": list(set(all_permissions)),
            }

    async def get_user_detail(self, user_id: str) -> dict[str, Any]:
        """Get detailed user information including sub-accounts.

        Args:
            user_id: User ID to retrieve.

        Returns:
            Full user details including roles, permissions, and sub-accounts.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise UserNotFoundError(user_id)

        temp_roles = self.get_active_temporary_roles(user.get("temporaryRoles", []))

        sub_accounts = []
        for sub in user.get("subAccounts", []):
            sub_accounts.append({
                "user_id": sub["userId"],
                "username": sub.get("username"),
                "role": sub.get("role"),
                "created_at": sub.get("createdAt"),
            })

        return {
            "user_id": user["userId"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "temporary_roles": temp_roles,
            "permissions": user.get("permissions", []),
            "resource_permissions": user.get("resourcePermissions", []),
            "registered_nodes": user.get("registeredNodes", []),
            "preferences": user.get("preferences", {}),
            "status": user.get("status", "active"),
            "is_system_account": user.get("isSystemAccount", False),
            "parent_user_id": user.get("parentUserId"),
            "sub_accounts": sub_accounts,
            "last_login": user.get("lastLogin"),
            "created_at": user["createdAt"],
            "updated_at": user.get("updatedAt"),
        }
