"""User management service."""

import secrets
from datetime import datetime, timedelta, timezone

import structlog

from hydra.api.v1.core.exceptions import (
    AlreadyHasParentError,
    BootstrapRequiresAdminError,
    CannotElevateAgentError,
    CannotHaveSubAccountsError,
    EmailExistsError,
    InvalidPasswordError,
    InvalidSubAccountRoleError,
    NodeNotFoundError,
    NotASubAccountError,
    PasswordResetTokenError,
    PendingUserNotFoundError,
    RegistrationTokenError,
    RoleLimitExceededError,
    TempRoleAlreadyActiveError,
    UserNotFoundError,
    UsernameExistsError,
    ValidationError,
)
from hydra.api.v1.core.role_utils import (
    get_active_temporary_roles as _get_active_temp_roles,
    to_utc,
)
from hydra.api.v1.core.security import hash_password, verify_password
from hydra.db.mongodb import MongoDB
from hydra.api.v1.models.auth import (
    ApproveUserRequest,
    CreateUserRequest,
    ElevateRoleRequest,
    GrantTemporaryRoleRequest,
    Role,
    ROLE_LIMITS,
    UserRegistrationRequest,
    can_have_sub_accounts,
    is_valid_sub_account_role,
)

logger = structlog.get_logger(__name__)


class UsersService:
    """User management service."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None:
        """Convert datetime to UTC. Delegates to shared utility."""
        return to_utc(value)

    def get_active_temporary_roles(self, temp_roles: list) -> list:
        """Return active temporary roles for a user.

        Delegates to shared utility function for consistency across services.
        """
        return _get_active_temp_roles(temp_roles)

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

        if token_doc["maxUses"] and token_doc["usedCount"] >= token_doc["maxUses"]:
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

    async def elevate_role(
        self, user_id: str, request: ElevateRoleRequest, elevated_by: str
    ) -> dict:
        """Permanently elevate a user's role.

        Args:
            user_id: User to elevate.
            request: Elevation request with new role.
            elevated_by: User ID performing the elevation.

        Returns:
            Elevation result with previous and new roles.

        Raises:
            UserNotFoundError: If user not found.
            CannotElevateAgentError: If attempting to elevate an agent.
            RoleLimitExceededError: If new role limit has been reached.
        """
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise UserNotFoundError(user_id)

        current_role = user["role"]
        new_role = request.new_role.value

        if current_role == Role.AGENT.value:
            raise CannotElevateAgentError()

        await self._check_role_limit(new_role)

        now = datetime.now(timezone.utc)
        await self.db.users.update_one(
            {"userId": user_id},
            {
                "$set": {
                    "role": new_role,
                    "updatedAt": now,
                }
            },
        )

        logger.info(
            "role_elevated",
            user_id=user_id,
            previous_role=current_role,
            new_role=new_role,
            elevated_by=elevated_by,
        )

        return {
            "user_id": user_id,
            "previous_role": current_role,
            "new_role": new_role,
            "elevated_by": elevated_by,
            "elevated_at": now,
        }

    async def grant_temporary_role(
        self, user_id: str, request: GrantTemporaryRoleRequest, granted_by: str
    ) -> dict:
        """Grant a temporary role to a user.

        Args:
            user_id: User to grant role to.
            request: Grant request with role, expiration, and reason.
            granted_by: User ID granting the role.

        Returns:
            User's base role and active temporary roles.

        Raises:
            UserNotFoundError: If user not found.
            TempRoleAlreadyActiveError: If user already has this temporary role.
        """
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise UserNotFoundError(user_id)

        temp_roles = user.get("temporaryRoles", [])
        now = datetime.now(timezone.utc)
        for tr in temp_roles:
            expires_at = self._to_utc(tr.get("expiresAt"))
            if tr["role"] == request.role.value and expires_at and expires_at > now:
                raise TempRoleAlreadyActiveError(user_id, request.role.value)

        new_temp_role = {
            "role": request.role.value,
            "expiresAt": request.expires_at,
            "grantedBy": granted_by,
            "grantedAt": now,
            "reason": request.reason,
        }

        await self.db.users.update_one(
            {"userId": user_id},
            {
                "$push": {"temporaryRoles": new_temp_role},
                "$set": {"updatedAt": now},
            },
        )

        updated_user = await self.db.users.find_one({"userId": user_id})
        active_temp_roles = self.get_active_temporary_roles(
            updated_user.get("temporaryRoles", [])
        )

        logger.info(
            "temporary_role_granted",
            user_id=user_id,
            role=request.role.value,
            expires_at=request.expires_at.isoformat(),
            granted_by=granted_by,
        )

        return {
            "user_id": user_id,
            "base_role": user["role"],
            "temporary_roles": active_temp_roles,
        }

    async def revoke_temporary_role(
        self, user_id: str, role: str, revoked_by: str
    ) -> dict:
        """Revoke a temporary role from a user.

        Args:
            user_id: User to revoke role from.
            role: Role name to revoke.
            revoked_by: User ID performing the revocation.

        Returns:
            Revocation result with timestamp.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise UserNotFoundError(user_id)

        now = datetime.now(timezone.utc)

        await self.db.users.update_one(
            {"userId": user_id},
            {
                "$pull": {"temporaryRoles": {"role": role}},
                "$set": {"updatedAt": now},
            },
        )

        logger.info(
            "temporary_role_revoked",
            user_id=user_id,
            role=role,
            revoked_by=revoked_by,
        )

        return {
            "user_id": user_id,
            "revoked_role": role,
            "revoked_by": revoked_by,
            "revoked_at": now,
        }

    def _get_role_permissions(self, role: str) -> list[str]:
        """Get permissions for a role."""
        role_permissions = {
            Role.ADMIN.value: ["*:*"],
            Role.OPERATOR.value: [
                "nodes:*",
                "profiles:*",
                "services:*",
                "groups:*",
                "networks:*",
                "topologies:read",
                "docs:*",
                "commands:execute",
                "ha:*",
                "tokens:create",
                "tokens:create:user",
                "tokens:create:node",
            ],
            Role.VIEWER.value: [
                "nodes:read",
                "profiles:read",
                "services:read",
                "groups:read",
                "networks:read",
                "topologies:read",
                "docs:read",
                "ha:read",
            ],
            Role.FAMILY.value: [
                "iot:read",
                "iot:control",
                "ha:read",
                "ha:control",
                "tokens:create:user",
            ],
            Role.AGENT.value: [
                "profiles:write",
                "profiles:read",
                "nodes:create",
                "nodes:read",
                "nodes:update",
                "tokens:create",
                "tokens:read",
                "tokens:revoke",
                "commands:poll",
            ],
        }
        return role_permissions.get(role, [])

    async def create_user(self, request: CreateUserRequest) -> dict:
        """Create a new user (admin endpoint)."""
        await self._check_username_availability(request.username)
        await self._check_email_availability(request.email)
        await self._check_role_limit(request.role.value)

        user_id = f"user_{secrets.token_urlsafe(8)}"
        now = datetime.now(timezone.utc)

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

        return {
            "user_id": user_id,
            "username": request.username,
            "email": request.email,
            "role": request.role.value,
            "created_at": now,
        }

    async def archive_user(self, user_id: str) -> dict:
        """Archive a user (soft delete)."""
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise UserNotFoundError(user_id)

        if user.get("status") == "archived":
            raise ValidationError(f"User '{user_id}' is already archived")

        now = datetime.now(timezone.utc)
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

    async def list_users(self, limit: int = 50, offset: int = 0) -> dict:
        """List users."""
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

        return {
            "users": users,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def is_parent_of(self, parent_user_id: str, child_user_id: str) -> bool:
        """Check if parent_user_id is the direct parent of child_user_id."""
        child = await self.db.users.find_one({"userId": child_user_id})
        if not child:
            return False
        return child.get("parentUserId") == parent_user_id

    async def get_current_user(self, token_payload: dict) -> dict:
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
                    all_permissions.extend(self._get_role_permissions(role))
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

            all_permissions = self._get_role_permissions(user["role"])
            for tr in temp_roles:
                all_permissions.extend(self._get_role_permissions(tr["role"]))
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

    async def request_password_reset(self, email: str, settings) -> dict:
        """Request a password reset.

        Returns success even if email does not exist to prevent email enumeration.

        Args:
            email: Email address to send reset link to.
            settings: Application settings with SMTP configuration.

        Returns:
            Dict with email_sent boolean indicating if email was sent.
        """
        from hydra.api.v1.core.email import get_email_service

        user = await self.db.users.find_one({"email": email})

        if not user:
            logger.info("password_reset_requested_unknown_email", email=email)
            return {"email_sent": False}

        if user.get("status") != "active":
            logger.info(
                "password_reset_requested_inactive_user",
                user_id=user["userId"],
                status=user.get("status"),
            )
            return {"email_sent": False}

        reset_token = f"prt_{secrets.token_urlsafe(32)}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.password_reset_token_expire_hours)

        token_doc = {
            "token": reset_token,
            "userId": user["userId"],
            "email": email,
            "expiresAt": expires_at,
            "used": False,
            "createdAt": now,
        }
        await self.db.password_reset_tokens.insert_one(token_doc)

        email_service = get_email_service(settings)
        try:
            email_sent = await email_service.send_password_reset_email(
                to=email,
                username=user["username"],
                reset_token=reset_token,
                expires_hours=settings.password_reset_token_expire_hours,
            )
        except Exception as e:
            logger.error(
                "password_reset_email_failed",
                user_id=user["userId"],
                error=str(e),
            )
            email_sent = False

        logger.info(
            "password_reset_requested",
            user_id=user["userId"],
            email_sent=email_sent,
        )

        return {"email_sent": email_sent}

    async def reset_password(self, token: str, new_password: str) -> dict:
        """Reset password using a reset token.

        Args:
            token: Password reset token.
            new_password: New password to set.

        Returns:
            Dict with reset_at timestamp.

        Raises:
            PasswordResetTokenError: If token is invalid, used, or expired.
        """
        now = datetime.now(timezone.utc)

        token_doc = await self.db.password_reset_tokens.find_one({"token": token})

        if not token_doc:
            raise PasswordResetTokenError()

        if token_doc.get("used"):
            raise PasswordResetTokenError(
                "AUTH_RESET_TOKEN_USED",
                "This reset token has already been used",
            )

        expires_at = self._to_utc(token_doc.get("expiresAt"))
        if expires_at and expires_at < now:
            raise PasswordResetTokenError(
                "AUTH_RESET_TOKEN_EXPIRED",
                "This reset token has expired",
            )

        user = await self.db.users.find_one({"userId": token_doc["userId"]})
        if not user:
            raise PasswordResetTokenError()

        password_hash = hash_password(new_password)
        await self.db.users.update_one(
            {"userId": user["userId"]},
            {
                "$set": {
                    "passwordHash": password_hash,
                    "updatedAt": now,
                }
            },
        )

        await self.db.password_reset_tokens.update_one(
            {"token": token},
            {"$set": {"used": True, "usedAt": now}},
        )

        await self.db.password_reset_tokens.update_many(
            {"userId": user["userId"], "used": False, "token": {"$ne": token}},
            {"$set": {"used": True, "usedAt": now}},
        )

        logger.info("password_reset_completed", user_id=user["userId"])

        return {"reset_at": now}

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> dict:
        """Change password for authenticated user.

        Args:
            user_id: User changing their password.
            current_password: Current password for verification.
            new_password: New password to set.

        Returns:
            Dict with changed_at timestamp.

        Raises:
            UserNotFoundError: If user does not exist.
            InvalidPasswordError: If current password is wrong.
        """
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise UserNotFoundError(user_id)

        if not verify_password(current_password, user["passwordHash"]):
            raise InvalidPasswordError()

        now = datetime.now(timezone.utc)
        password_hash = hash_password(new_password)

        await self.db.users.update_one(
            {"userId": user_id},
            {
                "$set": {
                    "passwordHash": password_hash,
                    "updatedAt": now,
                }
            },
        )

        logger.info("password_changed", user_id=user_id)

        return {"changed_at": now}

    # ==================== Sub-Account Management ====================

    async def link_sub_account(
        self,
        parent_user_id: str,
        target_user_id: str,
        target_password: str,
        reset_password: bool = False,
    ) -> dict:
        """Link an existing user as a sub-account of the parent user.

        Args:
            parent_user_id: User ID of the parent (admin/operator).
            target_user_id: User ID of the target to become sub-account.
            target_password: Password of the target user (for verification).
            reset_password: If true, reset sub-account password to match parent.

        Returns:
            Sub-account linking result with timestamps.

        Raises:
            ValidationError: If attempting self-linking or parent is a sub-account.
            UserNotFoundError: If parent or target user not found.
            CannotHaveSubAccountsError: If parent role cannot have sub-accounts.
            InvalidSubAccountRoleError: If target role cannot be a sub-account.
            AlreadyHasParentError: If target already has a parent.
            InvalidPasswordError: If target password verification fails.
        """
        if parent_user_id == target_user_id:
            raise ValidationError("Cannot link a user as a sub-account of themselves")

        parent = await self.db.users.find_one({"userId": parent_user_id})
        if not parent:
            raise UserNotFoundError(parent_user_id)

        if not can_have_sub_accounts(parent["role"]):
            raise CannotHaveSubAccountsError(parent["role"])
        if parent.get("parentUserId"):
            raise ValidationError("Sub-accounts cannot have sub-accounts")

        target = await self.db.users.find_one({"userId": target_user_id})
        if not target:
            raise UserNotFoundError(target_user_id)

        if not is_valid_sub_account_role(target["role"]):
            raise InvalidSubAccountRoleError(target["role"])

        if target.get("parentUserId"):
            raise AlreadyHasParentError(target_user_id, target["parentUserId"])

        if not verify_password(target_password, target["passwordHash"]):
            raise InvalidPasswordError()

        now = datetime.now(timezone.utc)

        update_fields = {
            "parentUserId": parent_user_id,
            "updatedAt": now,
        }

        password_reset = False
        if reset_password:
            update_fields["passwordHash"] = parent["passwordHash"]
            password_reset = True

        await self.db.users.update_one(
            {"userId": target_user_id},
            {"$set": update_fields},
        )

        sub_account_info = {
            "userId": target_user_id,
            "username": target["username"],
            "role": target["role"],
            "createdAt": now,
        }

        await self.db.users.update_one(
            {"userId": parent_user_id},
            {
                "$push": {"subAccounts": sub_account_info},
                "$set": {"updatedAt": now},
            },
        )

        logger.info(
            "sub_account_linked",
            parent_user_id=parent_user_id,
            sub_account_user_id=target_user_id,
            password_reset=password_reset,
        )

        return {
            "parent_user_id": parent_user_id,
            "sub_account_user_id": target_user_id,
            "sub_account_username": target["username"],
            "sub_account_role": target["role"],
            "linked_at": now,
            "password_reset": password_reset,
        }

    async def unlink_sub_account(
        self,
        parent_user_id: str,
        sub_account_user_id: str,
    ) -> dict:
        """Unlink a sub-account from its parent.

        Args:
            parent_user_id: User ID of the parent.
            sub_account_user_id: User ID of the sub-account to unlink.

        Returns:
            Unlinking result with timestamp.

        Raises:
            UserNotFoundError: If parent or sub-account not found.
            NotASubAccountError: If target is not a sub-account of parent.
        """
        parent = await self.db.users.find_one({"userId": parent_user_id})
        if not parent:
            raise UserNotFoundError(parent_user_id)

        sub_account = await self.db.users.find_one({"userId": sub_account_user_id})
        if not sub_account:
            raise UserNotFoundError(sub_account_user_id)

        if sub_account.get("parentUserId") != parent_user_id:
            raise NotASubAccountError(sub_account_user_id)

        now = datetime.now(timezone.utc)

        await self.db.users.update_one(
            {"userId": sub_account_user_id},
            {
                "$unset": {"parentUserId": ""},
                "$set": {"updatedAt": now},
            },
        )

        await self.db.users.update_one(
            {"userId": parent_user_id},
            {
                "$pull": {"subAccounts": {"userId": sub_account_user_id}},
                "$set": {"updatedAt": now},
            },
        )

        logger.info(
            "sub_account_unlinked",
            parent_user_id=parent_user_id,
            sub_account_user_id=sub_account_user_id,
        )

        return {
            "parent_user_id": parent_user_id,
            "sub_account_user_id": sub_account_user_id,
            "unlinked_at": now,
        }

    async def list_sub_accounts(self, user_id: str) -> dict:
        """List sub-accounts of a user.

        Args:
            user_id: User ID to list sub-accounts for.

        Returns:
            List of sub-accounts with current status and details.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise UserNotFoundError(user_id)

        sub_accounts = user.get("subAccounts", [])

        enriched_subs = []
        for sub in sub_accounts:
            sub_user = await self.db.users.find_one({"userId": sub["userId"]})
            if sub_user:
                enriched_subs.append({
                    "user_id": sub["userId"],
                    "username": sub_user["username"],
                    "role": sub_user["role"],
                    "status": sub_user.get("status", "active"),
                    "is_system_account": sub_user.get("isSystemAccount", False),
                    "created_at": sub.get("createdAt"),
                    "last_login": sub_user.get("lastLogin"),
                })

        return {
            "parent_user_id": user_id,
            "sub_accounts": enriched_subs,
            "total": len(enriched_subs),
        }

    async def get_user_detail(self, user_id: str) -> dict:
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
