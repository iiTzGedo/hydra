"""Authentication service for user and node authentication."""

import secrets
from datetime import datetime, timedelta, timezone

import structlog

from hydra.core.config import get_settings
from hydra.api.v1.core.exceptions import (
    ApiKeyNotFoundError,
    InvalidCredentialsError,
    InvalidTokenError,
    NodeAlreadyRegisteredError,
    NodeNotFoundError,
    PendingApprovalError,
    RegistrationTokenError,
    SystemAccountLoginBlockedError,
    ValidationError,
    UserNotFoundError
)
from hydra.api.v1.core.security import (
    create_access_token,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from hydra.db.mongodb import MongoDB
from hydra.api.v1.models.auth import (
    CreateApiKeyRequest,
    CreateRegistrationTokenRequest,
    NodeRegistrationRequest,
    Role,
    ROLE_LEVELS,
    can_create_token_for_role,
    get_role_level,
)
from hydra.api.v1.core.role_utils import get_active_temporary_roles

logger = structlog.get_logger(__name__)


class AuthService:
    """Authentication and authorization service."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb
        self.settings = get_settings()

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None:
        """Convert a datetime to UTC timezone."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # ==================== User Authentication ====================

    async def authenticate_user(
        self, username: str, password: str, allow_system_accounts: bool = False
    ) -> dict:
        """Authenticate a user and return access/refresh tokens.

        Args:
            username: User's username.
            password: User's password.
            allow_system_accounts: If False, block system accounts (agent users) from login.

        Returns:
            Dict with access_token, refresh_token, expires_in, and user details.

        Raises:
            PendingApprovalError: If user is pending approval.
            InvalidCredentialsError: If credentials are invalid.
            SystemAccountLoginBlockedError: If system account tries to login via web.
        """
        pending = await self.db.users_pending.find_one({"username": username})
        if pending:
            raise PendingApprovalError(username)

        user = await self.db.users.find_one({"username": username})
        if not user:
            raise InvalidCredentialsError()

        if not verify_password(password, user["passwordHash"]):
            parent_id = user.get("parentUserId")
            if not parent_id:
                raise InvalidCredentialsError()

            parent = await self.db.users.find_one({"userId": parent_id})
            if not parent or parent.get("status") != "active":
                raise InvalidCredentialsError()

            if not verify_password(password, parent["passwordHash"]):
                raise InvalidCredentialsError()

        if user.get("status") != "active":
            raise InvalidCredentialsError()

        if not allow_system_accounts and user.get("isSystemAccount", False):
            raise SystemAccountLoginBlockedError(username)

        await self.db.users.update_one(
            {"userId": user["userId"]},
            {"$set": {"lastLogin": datetime.now(timezone.utc)}},
        )

        temp_roles = get_active_temporary_roles(user.get("temporaryRoles", []))

        access_token, refresh_token = create_token_pair(
            subject=user["userId"],
            additional_claims={
                "sub_type": "user",
                "role": user["role"],
                "permissions": user.get("permissions", []),
            },
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": self.settings.jwt_expire_minutes * 60,
            "user": {
                "user_id": user["userId"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
                "temporary_roles": temp_roles,
                "permissions": user.get("permissions", []),
            },
        }

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an access token using a valid refresh token.

        Args:
            refresh_token: The refresh token from initial authentication.

        Returns:
            Dict with new 'access_token' and 'expires_in'.

        Raises:
            InvalidTokenError: If the refresh token is invalid or expired.
            UserNotFoundError: If the user no longer exists.
            NodeNotFoundError: If the agent node no longer exists.
        """
        try:
            payload = decode_token(refresh_token)
        except InvalidTokenError:
            raise InvalidTokenError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Invalid token type")

        subject = payload["sub"]
        sub_type = payload.get("sub_type", "user")

        if sub_type == "user":
            user = await self.db.users.find_one({"userId": subject})
            if not user:
                raise UserNotFoundError(subject)

            access_token = create_access_token(
                subject=subject,
                token_type="access",
                additional_claims={
                    "sub_type": "user",
                    "role": user["role"],
                    "permissions": user.get("permissions", []),
                },
            )
        else:  # agent
            node = await self.db.nodes.find_one({"nodeId": subject})
            if not node:
                raise NodeNotFoundError(subject)

            access_token = create_access_token(
                subject=subject,
                token_type="access",
                additional_claims={"sub_type": "agent"},
            )

        return {
            "access_token": access_token,
            "expires_in": self.settings.jwt_expire_minutes * 60,
        }

    # ==================== Registration Tokens ====================

    async def create_registration_token(
        self, request: CreateRegistrationTokenRequest, created_by: str, creator_role: str | None = None
    ) -> dict:
        """Create a new registration token for user or node registration.

        Role-based restrictions apply: users can only create tokens for roles
        at or below their permission level.

        Args:
            request: Token creation request with scope, description, expiry, and allowed roles.
            created_by: User ID of the creator.
            creator_role: Role of the creator for permission validation.

        Returns:
            The created token details including the token string (shown only once).

        Raises:
            ValidationError: If creator lacks permission to grant specified roles.
        """
        token = f"reg_{secrets.token_urlsafe(32)}"

        expires_in = request.expires_in or (
            self.settings.registration_token_expire_days * 24 * 60 * 60
        )
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        max_uses = request.max_uses or self.settings.registration_token_max_uses

        allowed_roles = None
        creator_role_level = get_role_level(creator_role) if creator_role else 100

        if request.scope.value == "user" and request.allowed_roles:
            allowed_roles = []
            for role in request.allowed_roles:
                # Check if creator can create tokens for this role
                if not can_create_token_for_role(creator_role or "admin", role.value):
                    raise ValidationError(
                        f"Cannot create token for role '{role.value}': "
                        f"Your role '{creator_role}' cannot grant this role level"
                    )
                allowed_roles.append(role.value)

        if request.scope.value == "user" and not allowed_roles and creator_role:
            if creator_role != "admin":
                allowed_roles = [
                    role for role, level in ROLE_LEVELS.items()
                    if level <= creator_role_level
                ]

        token_doc = {
            "token": token,
            "type": "registration",
            "scope": request.scope.value,
            "description": request.description,
            "expiresAt": expires_at,
            "maxUses": max_uses,
            "usedCount": 0,
            "usedBy": [],
            "allowedRoles": allowed_roles,
            "createdBy": created_by,
            "creatorRole": creator_role,
            "maxRoleLevel": creator_role_level,
            "createdAt": datetime.now(timezone.utc),
        }

        await self.db.tokens.insert_one(token_doc)
        logger.info(
            "registration_token_created",
            scope=request.scope.value,
            max_uses=max_uses,
            created_by=created_by,
            creator_role=creator_role,
            allowed_roles=allowed_roles,
        )

        return {
            "token": token,
            "scope": request.scope,
            "expires_at": expires_at,
            "max_uses": max_uses,
            "used_count": 0,
            "allowed_roles": [Role(r) for r in allowed_roles] if allowed_roles else None,
            "created_by": created_by,
        }

    async def validate_registration_token(self, token: str) -> dict:
        """Validate a registration token for node registration.

        Args:
            token: The registration token string.

        Returns:
            The token document if valid.

        Raises:
            RegistrationTokenError: If token is invalid, expired, exhausted, or wrong scope.
        """
        token_doc = await self.db.tokens.find_one({"token": token, "type": "registration"})

        if not token_doc:
            raise RegistrationTokenError(
                "AUTH_REGISTRATION_TOKEN_INVALID",
                "Invalid registration token",
            )

        token_scope = token_doc.get("scope", "user")
        if token_scope != "node":
            raise RegistrationTokenError(
                "AUTH_REGISTRATION_TOKEN_SCOPE_MISMATCH",
                f"This token is for '{token_scope}' registration, not node registration",
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

        return token_doc

    async def _use_registration_token(
        self, token: str, entity_id: str, entity_type: str
    ) -> None:
        """Mark a registration token as used by incrementing usage count."""
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

    async def use_registration_token(self, token: str, node_id: str) -> None:
        """Mark a registration token as used for node registration."""
        await self._use_registration_token(token, node_id, "node")

    async def list_registration_tokens(
        self,
        user_id: str,
        scope: str | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List registration tokens created by a user.

        Args:
            user_id: User ID to filter by (creator).
            scope: Optional scope filter ('user' or 'node').
            active_only: Only return tokens that are still usable.
            limit: Maximum results to return.
            offset: Pagination offset.

        Returns:
            Tuple of (tokens list, total count).
        """
        now = datetime.now(timezone.utc)

        query: dict = {"type": "registration", "createdBy": user_id}

        if scope:
            query["scope"] = scope

        total = await self.db.tokens.count_documents(query)
        cursor = self.db.tokens.find(query).sort("createdAt", -1).skip(offset).limit(limit)

        tokens = []
        async for doc in cursor:
            expires_at = self._to_utc(doc.get("expiresAt"))
            max_uses = doc.get("maxUses")
            used_count = doc.get("usedCount", 0)

            is_expired = expires_at and expires_at < now
            is_exhausted = max_uses is not None and used_count >= max_uses
            is_active = not is_expired and not is_exhausted

            if active_only and not is_active:
                continue

            token_value = doc.get("token", "")
            token_id = f"...{token_value[-8:]}" if len(token_value) > 8 else token_value

            tokens.append({
                "token_id": token_id,
                "scope": doc.get("scope", "user"),
                "description": doc.get("description"),
                "expires_at": expires_at,
                "max_uses": max_uses,
                "used_count": used_count,
                "used_by": doc.get("usedBy", []),
                "allowed_roles": doc.get("allowedRoles"),
                "created_by": doc.get("createdBy"),
                "created_at": doc.get("createdAt"),
                "is_active": is_active,
            })

        return tokens, total

    # ==================== Node Registration ====================

    async def register_node(
        self, request: NodeRegistrationRequest, registered_by: str
    ) -> dict:
        """Register a new node and return API key credentials.

        Args:
            request: Node registration payload with node_id, class, type, etc.
            registered_by: User ID of the registering user.

        Returns:
            Registration details including the API key (shown only once).

        Raises:
            NodeAlreadyRegisteredError: If a node with this ID already exists.
        """
        existing = await self.db.nodes.find_one({"nodeId": request.node_id})
        if existing:
            raise NodeAlreadyRegisteredError(request.node_id)

        now = datetime.now(timezone.utc)

        node_doc = {
            "nodeId": request.node_id,
            "class": request.node_class,
            "type": request.node_type,
            "kind": request.kind,
            "displayName": request.display_name or request.node_id,
            "description": request.description,
            "tags": request.tags,
            "parentNodeId": request.parent_node_id,
            "networkIds": [],
            "location": request.location,
            "registeredAt": now,
            "registeredBy": registered_by,
            "lastUpdated": now,
            "lastProfileAt": None,
            "status": "active",
        }

        await self.db.nodes.insert_one(node_doc)

        api_key = f"hyk_node_{secrets.token_urlsafe(32)}"
        key_id = f"key_node_{secrets.token_urlsafe(8)}"

        key_doc = {
            "keyId": key_id,
            "keyHash": hash_password(api_key),
            "name": f"{request.node_id}-agent",
            "type": "node",
            "ownerId": registered_by,
            "ownerType": "user",
            "nodeId": request.node_id,
            "permissions": [
                f"profiles:write:{request.node_id}",
                f"commands:poll:{request.node_id}",
            ],
            "expiresAt": None,
            "lastUsedAt": None,
            "createdAt": now,
            "revokedAt": None,
        }

        await self.db.api_keys.insert_one(key_doc)

        await self.db.users.update_one(
            {"userId": registered_by},
            {"$addToSet": {"registeredNodes": request.node_id}},
        )

        logger.info(
            "node_registered",
            node_id=request.node_id,
            node_class=request.node_class,
            registered_by=registered_by,
        )

        return {
            "node_id": request.node_id,
            "api_key": api_key,
            "api_key_id": key_id,
            "registered_by": registered_by,
            "registered_at": now,
            "status": "active",
        }

    async def refresh_node_api_key(
        self, node_id: str, refreshed_by: str | None = None
    ) -> dict:
        """Refresh the API key for a node, revoking the previous key.

        Args:
            node_id: The node identifier.
            refreshed_by: User ID performing the refresh.

        Returns:
            New API key details (the key is shown only once).

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        now = datetime.now(timezone.utc)

        await self.db.api_keys.update_many(
            {"nodeId": node_id, "revokedAt": None},
            {"$set": {"revokedAt": now}},
        )

        api_key = f"hyk_node_{secrets.token_urlsafe(32)}"
        key_id = f"key_node_{secrets.token_urlsafe(8)}"

        key_doc = {
            "keyId": key_id,
            "keyHash": hash_password(api_key),
            "name": f"{node_id}-agent",
            "type": "node",
            "ownerId": node.get("registeredBy", refreshed_by),
            "ownerType": "user",
            "nodeId": node_id,
            "permissions": [
                f"profiles:write:{node_id}",
                f"commands:poll:{node_id}",
            ],
            "expiresAt": None,
            "lastUsedAt": None,
            "createdAt": now,
            "revokedAt": None,
        }

        await self.db.api_keys.insert_one(key_doc)

        logger.info(
            "node_api_key_refreshed",
            node_id=node_id,
            key_id=key_id,
        )

        return {
            "node_id": node_id,
            "api_key_id": key_id,
            "api_key": api_key,
            "previous_key_revoked": True,
            "refreshed_at": now,
        }

    # ==================== API Keys ====================

    async def create_api_key(
        self, request: CreateApiKeyRequest, user_id: str
    ) -> dict:
        """Create an API key for a user.

        Args:
            request: API key creation payload with name, optional roles, permissions, expiry.
            user_id: The owning user's identifier.

        Returns:
            The created API key details including the key string (shown only once).
        """
        key = f"hyk_live_{secrets.token_urlsafe(32)}"
        key_id = f"key_{secrets.token_urlsafe(8)}"
        now = datetime.now(timezone.utc)

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
            "createdAt": now,
            "revokedAt": None,
        }

        await self.db.api_keys.insert_one(key_doc)
        logger.info("api_key_created", key_id=key_id, user_id=user_id)

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

    async def list_api_keys(self, user_id: str) -> tuple[list[dict], int]:
        """List active API keys for a user.

        Args:
            user_id: The user identifier.

        Returns:
            Tuple of (api_keys list, total count).
        """
        cursor = self.db.api_keys.find({
            "ownerId": user_id,
            "type": "user",
            "revokedAt": None,
        }).sort("createdAt", -1)

        api_keys = []
        async for doc in cursor:
            api_keys.append({
                "key_id": doc["keyId"],
                "name": doc["name"],
                "permissions": doc.get("permissions", []),
                "expires_at": doc.get("expiresAt"),
                "last_used_at": doc.get("lastUsedAt"),
                "created_at": doc["createdAt"],
            })

        return api_keys, len(api_keys)

    async def revoke_api_key(self, key_id: str, user_id: str, user_role: str | None = None) -> dict:
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

        now = datetime.now(timezone.utc)
        await self.db.api_keys.update_one(
            {"keyId": key_id},
            {"$set": {"revokedAt": now}},
        )

        logger.info("api_key_revoked", key_id=key_id, user_id=user_id)

        return {
            "key_id": key_id,
            "revoked": True,
            "revoked_at": now,
        }

    async def validate_api_key(self, api_key: str) -> dict:
        """Validate an API key and return its associated data.

        Args:
            api_key: The API key string (must start with 'hyk_').

        Returns:
            The API key document if valid.

        Raises:
            InvalidTokenError: If the key is invalid, expired, or revoked.
        """
        if not api_key.startswith("hyk_"):
            raise InvalidTokenError("Invalid API key format")

        async for key_doc in self.db.api_keys.find({"revokedAt": None}):
            if verify_password(api_key, key_doc["keyHash"]):
                expires_at = self._to_utc(key_doc.get("expiresAt"))
                if expires_at and expires_at < datetime.now(timezone.utc):
                    raise InvalidTokenError("API key has expired")

                await self.db.api_keys.update_one(
                    {"keyId": key_doc["keyId"]},
                    {"$set": {"lastUsedAt": datetime.now(timezone.utc)}},
                )

                return key_doc

        raise InvalidTokenError("Invalid API key")

    # ==================== Agent Registration ====================

    async def register_agent(
        self,
        parent_user_id: str | None,
        username: str | None = None,
        password: str | None = None,
        registration_token: str | None = None,
    ) -> dict:
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
        import string

        now = datetime.now(timezone.utc)

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
            if expires_at and expires_at < datetime.now(timezone.utc):
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
