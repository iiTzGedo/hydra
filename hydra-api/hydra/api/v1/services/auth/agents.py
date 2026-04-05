"""Agent registration mixin: register agent system accounts."""

import secrets
import string
from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.core.exceptions import (
    RegistrationTokenError,
    UserNotFoundError,
    ValidationError,
)
from hydra.api.v1.core.security import hash_password
from hydra.api.v1.models.auth import Role
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class AgentRegistrationMixin:
    """Mixin providing agent system account registration."""
    db: MongoDB

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None: ...

    async def _use_registration_token(self, token: str, entity_id: str, entity_type: str) -> None: ...


    async def register_agent(
        self,
        parent_user_id: str | None,
        username: str | None = None,
        password: str | None = None,
        registration_token: str | None = None,
    ) -> dict[str, Any]:
        """Register an agent system account.

        Creates a special system account for hydra-agent with auto-generated credentials
        and automatically links it as a sub-account of the parent user.

        Args:
            parent_user_id: User ID of the authenticated admin/operator creating the agent.
            username: Optional custom username (auto-generated if not provided).
            password: Optional password (auto-generated if not provided).
            registration_token: Optional registration token for validation.

        Returns:
            Agent account details including user_id, username, role, and parent info.

        Raises:
            RegistrationTokenError: If token is invalid, expired, or wrong scope.
            ValidationError: If parent user lacks permission to create agent accounts.
            UserNotFoundError: If parent user does not exist.
        """
        now = datetime.now(UTC)

        token_doc = None
        if registration_token:
            token_doc = await self.db.tokens.find_one({
                "token": registration_token,
                "type": "registration",
            })
            if not token_doc:
                raise RegistrationTokenError(
                    "AUTH_REGISTRATION_TOKEN_INVALID",
                    "Invalid registration token",
                )

            token_scope = token_doc.get("scope", "user")
            if token_scope != "user":
                raise RegistrationTokenError(
                    "AUTH_REGISTRATION_TOKEN_SCOPE_MISMATCH",
                    f"This token is for '{token_scope}' registration, not user/agent registration",
                )

            expires_at = self._to_utc(token_doc.get("expiresAt"))
            if expires_at and expires_at < datetime.now(UTC):
                raise RegistrationTokenError(
                    "AUTH_REGISTRATION_TOKEN_EXPIRED",
                    "Registration token has expired",
                )

            max_uses = token_doc.get("maxUses")
            used_count = token_doc.get("usedCount", 0)
            if max_uses is not None and used_count >= max_uses:
                raise RegistrationTokenError(
                    "AUTH_REGISTRATION_TOKEN_USED",
                    "Registration token has reached maximum uses",
                )
            allowed_roles = token_doc.get("allowedRoles")
            if allowed_roles and Role.AGENT.value not in allowed_roles:
                raise RegistrationTokenError(
                    "AUTH_REGISTRATION_TOKEN_INVALID",
                    "Registration token does not allow role 'agent'",
                )
            token_parent_id = token_doc.get("createdBy")
            if parent_user_id and token_parent_id and parent_user_id != token_parent_id:
                raise ValidationError(
                    "Registration token does not match the authenticated parent user"
                )
            if not parent_user_id:
                parent_user_id = token_parent_id
            creator_role = token_doc.get("creatorRole")
            if creator_role not in ["admin", "operator"]:
                raise ValidationError(
                    "Only admin or operator registration tokens can create agent accounts"
                )

        if not parent_user_id:
            raise ValidationError("Parent user is required to create agent account")

        parent = await self.db.users.find_one({"userId": parent_user_id})
        if not parent:
            raise UserNotFoundError(parent_user_id)

        if parent["role"] not in ["admin", "operator"]:
            raise ValidationError(
                "Only admin or operator users can create agent accounts"
            )
        if parent.get("parentUserId"):
            raise ValidationError("Sub-accounts cannot create agent accounts")

        if not username:
            chars = string.ascii_uppercase + string.digits
            suffix = "".join(secrets.choice(chars) for _ in range(8))
            username = f"agent-{suffix}"

        existing = await self.db.users.find_one({"username": username})
        if existing:
            raise ValidationError(f"Username '{username}' is already taken")

        generated_password = None
        if not password:
            generated_password = secrets.token_urlsafe(16)
            password = generated_password

        user_id = f"user_{secrets.token_urlsafe(8)}"
        email = f"{username}@system.hydra.local"
        agent_permissions = [
            "profiles:write",
            "profiles:read",
            "nodes:create",
            "nodes:read",
            "nodes:update",
            "tokens:create",
            "tokens:read",
            "tokens:revoke",
            "commands:poll",
        ]

        user_doc = {
            "userId": user_id,
            "username": username,
            "email": email,
            "passwordHash": hash_password(password),
            "role": Role.AGENT.value,
            "temporaryRoles": [],
            "permissions": agent_permissions,
            "resourcePermissions": [],
            "registeredNodes": [],
            "preferences": {},
            "status": "active",
            "isSystemAccount": True,
            "parentUserId": parent_user_id,
            "lastLogin": None,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.users.insert_one(user_doc)

        sub_account_info = {
            "userId": user_id,
            "username": username,
            "role": Role.AGENT.value,
            "createdAt": now,
        }

        await self.db.users.update_one(
            {"userId": parent_user_id},
            {
                "$push": {"subAccounts": sub_account_info},
                "$set": {"updatedAt": now},
            },
        )

        if registration_token:
            await self._use_registration_token(registration_token, user_id, "agent")

        logger.info(
            "agent_registered",
            user_id=user_id,
            username=username,
            parent_user_id=parent_user_id,
        )

        return {
            "user_id": user_id,
            "username": username,
            "role": Role.AGENT.value,
            "is_system_account": True,
            "parent_user_id": parent_user_id,
            "created_at": now,
        }
