"""Registration token mixin: create, validate, use, and list registration tokens."""

import secrets
from datetime import datetime, timedelta, timezone

import structlog

from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.core.exceptions import (
    RegistrationTokenError,
    ValidationError,
)
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.models.notifications import (
    NotificationType,
    NotificationSource,
    NotificationActor,
    ActorType,
)
from hydra.api.v1.services.query import log_audit
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.models.auth import (
    CreateRegistrationTokenRequest,
    Role,
    ROLE_LEVELS,
    can_create_token_for_role,
    get_role_level,
)

logger = structlog.get_logger(__name__)


class TokensMixin:
    """Mixin providing registration token management."""

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

        import hashlib

        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        masked_token = f"{token[:8]}...{token_hash}"

        audit_id = await log_audit(
            AuditAction.CREATE,
            "registration_token",
            masked_token,
            "user",
            created_by,
            True,
            details={
                "tokenPrefix": token[:8],
                "tokenHash": token_hash,
                "userId": created_by,
                "scope": request.scope.value,
                "expiresAt": expires_at.isoformat(),
                "maxUses": max_uses,
            },
        )
        safe_create_task(emit_notification(
            notification_type=NotificationType.REGISTRATION_TOKEN_CREATED,
            source=NotificationSource(component="hydra-api", service="auth"),
            title="Registration token created",
            message=f"Registration token created for {request.scope.value} scope",
            details={
                "tokenPrefix": token[:8],
                "entityId": masked_token,
                "userId": created_by,
                "scope": request.scope.value,
                "expiresAt": expires_at.isoformat(),
                "maxUses": max_uses,
            },
            target_user_id=created_by,
            audit_entry_id=audit_id,
        ))

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

        max_uses = token_doc.get("maxUses")
        used_count = token_doc.get("usedCount", 0) or 0
        if max_uses is not None and used_count >= max_uses:
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
