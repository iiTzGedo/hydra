"""User registration mixin - handles registration, approval, and pending user flows."""

import secrets
from datetime import datetime, timezone

import structlog

from hydra.api.v1.core.exceptions import (
    BootstrapRequiresAdminError,
    EmailExistsError,
    PendingUserNotFoundError,
    RegistrationTokenError,
    RoleLimitExceededError,
    UsernameExistsError,
)
from hydra.api.v1.core.security import hash_password
from hydra.api.v1.models.auth import (
    ApproveUserRequest,
    Role,
    ROLE_LIMITS,
    UserRegistrationRequest,
)

logger = structlog.get_logger(__name__)


class RegistrationMixin:
    """Mixin providing user registration and approval functionality."""

    async def register_user(self, request: UserRegistrationRequest) -> dict:
        """Register a new user account.

        Handles bootstrap (first user must be admin), token-based registration,
        and pending approval flows.

        Args:
            request: Registration request with username, email, password, role,
                and optional registration token.

        Returns:
            User registration result with status and user details.

        Raises:
            BootstrapRequiresAdminError: If first user is not admin role.
            UsernameExistsError: If username is already taken.
            EmailExistsError: If email is already registered.
            RoleLimitExceededError: If role limit has been reached.
            RegistrationTokenError: If provided token is invalid.
        """
        user_count = await self.db.users.count_documents({})
        is_bootstrap = user_count == 0

        if is_bootstrap:
            if request.role != Role.ADMIN:
                raise BootstrapRequiresAdminError()
            return await self._create_active_user(request, is_bootstrap=True)

        await self._check_username_availability(request.username)
        await self._check_email_availability(request.email)
        await self._check_role_limit(request.role.value)

        if request.registration_token:
            await self._validate_user_registration_token(
                request.registration_token, request.role
            )
            result = await self._create_active_user(request, is_bootstrap=False)
            await self._use_registration_token(
                request.registration_token,
                result["user_id"],
                "user",
            )
            return result

        return await self._create_pending_user(request)

    async def _check_username_availability(self, username: str) -> None:
        """Check if username is available in both users and users_pending."""
        existing_user = await self.db.users.find_one({"username": username})
        if existing_user:
            raise UsernameExistsError(username)

        existing_pending = await self.db.users_pending.find_one({"username": username})
        if existing_pending:
            raise UsernameExistsError(username)

    async def _check_email_availability(self, email: str) -> None:
        """Check if email is available in both users and users_pending."""
        existing_user = await self.db.users.find_one({"email": email})
        if existing_user:
            raise EmailExistsError(email)

        existing_pending = await self.db.users_pending.find_one({"email": email})
        if existing_pending:
            raise EmailExistsError(email)

    async def _check_role_limit(self, role: str) -> None:
        """Check if role limit has been reached."""
        limit = ROLE_LIMITS.get(role)
        if limit is None:
            return

        count = await self.db.users.count_documents({"role": role})
        if count >= limit:
            raise RoleLimitExceededError(role, limit)

    async def _create_active_user(
        self, request: UserRegistrationRequest, is_bootstrap: bool = False
    ) -> dict:
        """Create an active user account."""
        user_id = f"user_{secrets.token_urlsafe(8)}"
        now = datetime.now(timezone.utc)

        user_doc = {
            "userId": user_id,
            "username": request.username,
            "email": request.email,
            "passwordHash": hash_password(request.password),
            "role": request.role.value,
            "temporaryRoles": [],
            "permissions": [],
            "resourcePermissions": [],
            "registeredNodes": [],
            "preferences": {},
            "status": "active",
            "lastLogin": None,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.users.insert_one(user_doc)
        logger.info(
            "user_created",
            user_id=user_id,
            username=request.username,
            role=request.role.value,
            is_bootstrap=is_bootstrap,
        )

        return {
            "user_id": user_id,
            "username": request.username,
            "email": request.email,
            "role": request.role.value,
            "status": "active",
            "is_bootstrap": is_bootstrap if is_bootstrap else None,
            "created_at": now,
        }

    async def _create_pending_user(self, request: UserRegistrationRequest) -> dict:
        """Create a pending user awaiting approval."""
        user_id = f"user_pending_{secrets.token_urlsafe(8)}"
        now = datetime.now(timezone.utc)

        pending_doc = {
            "userId": user_id,
            "username": request.username,
            "email": request.email,
            "passwordHash": hash_password(request.password),
            "role": request.role.value,
            "requestedAt": now,
        }

        await self.db.users_pending.insert_one(pending_doc)
        logger.info(
            "pending_user_created",
            user_id=user_id,
            username=request.username,
            role=request.role.value,
        )

        return {
            "user_id": user_id,
            "username": request.username,
            "email": request.email,
            "role": request.role.value,
            "status": "pending_approval",
            "message": "Registration submitted. Awaiting admin approval.",
            "created_at": now,
        }

    async def _validate_user_registration_token(
        self, token: str, requested_role: Role
    ) -> dict:
        """Validate a registration token for user registration.

        Args:
            token: The registration token string.
            requested_role: The role being requested.

        Returns:
            The validated token document.

        Raises:
            RegistrationTokenError: If token is invalid, expired, exhausted,
                wrong scope, or does not allow the requested role.
        """
        token_doc = await self.db.tokens.find_one({"token": token, "type": "registration"})

        if not token_doc:
            raise RegistrationTokenError(
                "AUTH_REGISTRATION_TOKEN_INVALID",
                "Invalid registration token",
            )

        token_scope = token_doc.get("scope", "user")
        if token_scope != "user":
            raise RegistrationTokenError(
                "AUTH_REGISTRATION_TOKEN_SCOPE_MISMATCH",
                f"This token is for '{token_scope}' registration, not user registration",
            )

        expires_at = self._to_utc(token_doc.get("expiresAt"))
        if expires_at and expires_at < datetime.now(timezone.utc):
            raise RegistrationTokenError(
                "AUTH_REGISTRATION_TOKEN_EXPIRED",
                "Registration token has expired",
            )

        max_uses = token_doc.get("maxUses")
        used_count = token_doc.get("usedCount", 0) or 0
        if max_uses is not None and used_count >= max_uses:
            raise RegistrationTokenError(
                "AUTH_REGISTRATION_TOKEN_USED",
                "Registration token has reached maximum uses",
            )

        allowed_roles = token_doc.get("allowedRoles")
        if allowed_roles and requested_role.value not in allowed_roles:
            raise RegistrationTokenError(
                "AUTH_REGISTRATION_TOKEN_INVALID",
                f"Registration token does not allow role '{requested_role.value}'",
            )

        return token_doc

    async def _use_registration_token(
        self, token: str, entity_id: str, entity_type: str
    ) -> None:
        """Mark a registration token as used."""
        await self.db.tokens.update_one(
            {"token": token},
            {
                "$inc": {"usedCount": 1},
                "$push": {
                    "usedBy": {
                        "entityId": entity_id,
                        "entityType": entity_type,
                        "usedAt": datetime.now(timezone.utc),
                    }
                },
            },
        )

    async def list_pending_users(
        self,
        role: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List pending user registrations."""
        query = {}
        if role:
            query["role"] = role

        cursor = (
            self.db.users_pending.find(query)
            .sort("requestedAt", -1)
            .skip(offset)
            .limit(limit)
        )

        pending_users = []
        async for doc in cursor:
            pending_users.append({
                "user_id": doc["userId"],
                "username": doc["username"],
                "email": doc["email"],
                "role": doc["role"],
                "requested_at": doc["requestedAt"],
            })

        total = await self.db.users_pending.count_documents(query)

        return {
            "pending_users": pending_users,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def approve_user(
        self, request: ApproveUserRequest, approved_by: str
    ) -> dict:
        """Approve a pending user registration.

        Args:
            request: Approval request with user_id or username.
            approved_by: User ID of the approving admin.

        Returns:
            Approved user details with status and approval timestamp.

        Raises:
            PendingUserNotFoundError: If pending user not found.
            RoleLimitExceededError: If role limit has been reached.
        """
        query = {}
        if request.user_id:
            query["userId"] = request.user_id
        elif request.username:
            query["username"] = request.username

        pending = await self.db.users_pending.find_one(query)
        if not pending:
            identifier = request.user_id or request.username
            raise PendingUserNotFoundError(identifier)

        await self._check_role_limit(pending["role"])

        now = datetime.now(timezone.utc)
        new_user_id = f"user_{secrets.token_urlsafe(8)}"

        user_doc = {
            "userId": new_user_id,
            "username": pending["username"],
            "email": pending["email"],
            "passwordHash": pending["passwordHash"],
            "role": pending["role"],
            "temporaryRoles": [],
            "permissions": [],
            "resourcePermissions": [],
            "registeredNodes": [],
            "preferences": {},
            "status": "active",
            "lastLogin": None,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.users.insert_one(user_doc)
        await self.db.users_pending.delete_one({"userId": pending["userId"]})

        logger.info(
            "user_approved",
            user_id=new_user_id,
            username=pending["username"],
            approved_by=approved_by,
        )

        return {
            "user_id": new_user_id,
            "username": pending["username"],
            "email": pending["email"],
            "role": pending["role"],
            "status": "active",
            "approved_by": approved_by,
            "approved_at": now,
        }

    async def reject_user(self, user_id: str, rejected_by: str) -> dict:
        """Reject and delete a pending user registration."""
        pending = await self.db.users_pending.find_one({"userId": user_id})
        if not pending:
            raise PendingUserNotFoundError(user_id)

        await self.db.users_pending.delete_one({"userId": user_id})
        now = datetime.now(timezone.utc)

        logger.info(
            "user_rejected",
            user_id=user_id,
            username=pending["username"],
            rejected_by=rejected_by,
        )

        return {
            "user_id": user_id,
            "rejected": True,
            "rejected_by": rejected_by,
            "rejected_at": now,
        }
