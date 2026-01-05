"""Authentication service for user and node authentication."""

import secrets
from datetime import datetime, timedelta, timezone

import structlog

from hydra_api.core.config import get_settings
from hydra_api.core.exceptions import (
    ApiKeyNotFoundError,
    InvalidCredentialsError,
    InvalidTokenError,
    NodeAlreadyRegisteredError,
    NodeNotFoundError,
    PendingApprovalError,
    RegistrationTokenError,
    ValidationError,
)
from hydra_api.core.security import (
    create_access_token,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from hydra_api.db.mongodb import MongoDB
from hydra_api.models.auth import (
    CreateApiKeyRequest,
    CreateRegistrationTokenRequest,
    NodeRegistrationRequest,
    Role,
    ROLE_LEVELS,
    can_create_token_for_role,
    get_role_level,
)
from hydra_api.services.users import UsersService

logger = structlog.get_logger(__name__)


class AuthService:
    """Authentication and authorization service."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb
        self.settings = get_settings()
        self.users = UsersService(mongodb)

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # ==================== User Authentication ====================

    async def authenticate_user(self, username: str, password: str) -> dict:
        """Authenticate a user and return tokens."""
        # Check if user is pending approval
        pending = await self.db.users_pending.find_one({"username": username})
        if pending:
            raise PendingApprovalError(username)

        user = await self.db.users.find_one({"username": username})
        if not user:
            raise InvalidCredentialsError()

        if not verify_password(password, user["passwordHash"]):
            raise InvalidCredentialsError()

        if user.get("status") != "active":
            raise InvalidCredentialsError()

        # Update last login
        await self.db.users.update_one(
            {"userId": user["userId"]},
            {"$set": {"lastLogin": datetime.now(timezone.utc)}},
        )

        # Get active temporary roles
        temp_roles = self.users.get_active_temporary_roles(user.get("temporaryRoles", []))

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
        """Refresh an access token."""
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
        """
        Create a new registration token.

        Role-based restrictions:
        - Admin can create tokens for any role
        - Operator can create tokens for operator, viewer, family (same level or below)
        - Family can create tokens for family only
        - Viewer cannot create user tokens (only node tokens if permitted)

        Args:
            request: Token creation request
            created_by: User ID of the creator
            creator_role: Role of the creator (for validation)
        """
        token = f"reg_{secrets.token_urlsafe(32)}"

        expires_in = request.expires_in or (
            self.settings.registration_token_expire_days * 24 * 60 * 60
        )
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        max_uses = request.max_uses or self.settings.registration_token_max_uses

        # For user scope tokens, validate role restrictions
        allowed_roles = None
        creator_role_level = get_role_level(creator_role) if creator_role else 100  # Admin level if not specified

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

        # If no explicit allowed_roles but user scope, default based on creator's role
        if request.scope.value == "user" and not allowed_roles and creator_role:
            # Non-admin creators must restrict roles to their level or below
            if creator_role != "admin":
                # Get all roles at or below creator's level
                allowed_roles = [
                    role for role, level in ROLE_LEVELS.items()
                    if level <= creator_role_level and role != "agent"
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
        """Validate a registration token for node registration."""
        token_doc = await self.db.tokens.find_one({"token": token, "type": "registration"})

        if not token_doc:
            raise RegistrationTokenError(
                "AUTH_REGISTRATION_TOKEN_INVALID",
                "Invalid registration token",
            )

        # Check scope - must be "node" for node registration
        # Legacy tokens without scope are assumed to be user tokens
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

    # Legacy method for backwards compatibility
    async def use_registration_token(self, token: str, node_id: str) -> None:
        """Mark a registration token as used (legacy - for nodes)."""
        await self._use_registration_token(token, node_id, "node")

    # ==================== Node Registration ====================

    async def register_node(
        self, request: NodeRegistrationRequest, registered_by: str
    ) -> dict:
        """Register a new node and return API key credentials."""
        # Check if node already exists
        existing = await self.db.nodes.find_one({"nodeId": request.node_id})
        if existing:
            raise NodeAlreadyRegisteredError(request.node_id)

        now = datetime.now(timezone.utc)

        # Create node document
        node_doc = {
            "nodeId": request.node_id,
            "class": request.node_class,
            "type": request.node_type,
            "kind": request.kind,
            "displayName": request.display_name,
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

        # Create API key for the node
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

        # Add node to user's registeredNodes
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
        """Refresh the API key for a node."""
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        now = datetime.now(timezone.utc)

        # Revoke existing API key
        await self.db.api_keys.update_many(
            {"nodeId": node_id, "revokedAt": None},
            {"$set": {"revokedAt": now}},
        )

        # Create new API key
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
        """Create an API key for a user."""
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

    async def list_api_keys(self, user_id: str) -> dict:
        """List API keys for a user."""
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

        return {
            "api_keys": api_keys,
            "total": len(api_keys),
        }

    async def revoke_api_key(self, key_id: str, user_id: str) -> dict:
        """Revoke an API key."""
        key_doc = await self.db.api_keys.find_one({"keyId": key_id})
        if not key_doc:
            raise ApiKeyNotFoundError(key_id)

        # Check ownership (unless admin - handled at router level)
        if key_doc["ownerId"] != user_id:
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
        """Validate an API key and return its data."""
        # API keys start with hyk_
        if not api_key.startswith("hyk_"):
            raise InvalidTokenError("Invalid API key format")

        # Check in api_keys collection
        async for key_doc in self.db.api_keys.find({"revokedAt": None}):
            if verify_password(api_key, key_doc["keyHash"]):
                expires_at = self._to_utc(key_doc.get("expiresAt"))
                if expires_at and expires_at < datetime.now(timezone.utc):
                    raise InvalidTokenError("API key has expired")

                # Update last used
                await self.db.api_keys.update_one(
                    {"keyId": key_doc["keyId"]},
                    {"$set": {"lastUsedAt": datetime.now(timezone.utc)}},
                )

                return key_doc

        raise InvalidTokenError("Invalid API key")
