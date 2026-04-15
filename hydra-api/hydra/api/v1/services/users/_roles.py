"""User roles mixin - handles role elevation, temporary roles, and permissions."""

from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.core.exceptions import (
    CannotElevateAgentError,
    TempRoleAlreadyActiveError,
    UserNotFoundError,
)
from hydra.api.v1.models.auth import (
    ROLE_LEVELS,
    ElevateRoleRequest,
    GrantTemporaryRoleRequest,
    Role,
)
from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationType,
    SourceComponent,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class RolesMixin:
    """Mixin providing role management functionality."""
    db: MongoDB

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None: ...

    def get_active_temporary_roles(self, temp_roles: list[dict[str, Any]]) -> list[dict[str, Any]]: ...  # type: ignore[empty-body]

    async def _check_role_limit(self, role: str) -> None: ...


    async def elevate_role(
        self, user_id: str, request: ElevateRoleRequest, elevated_by: str
    ) -> dict[str, Any]:
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

        now = datetime.now(UTC)
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

        current_level = ROLE_LEVELS.get(current_role, 0)
        new_level = ROLE_LEVELS.get(new_role, 0)
        is_elevation = new_level > current_level
        notification_type = (
            NotificationType.ROLE_ELEVATION_GRANTED if is_elevation
            else NotificationType.ROLE_ELEVATION_REVOKED
        )

        audit_id = await log_audit(
            AuditAction.UPDATE, "user", user_id, "user", elevated_by, True,
            details={"previous_role": current_role, "new_role": new_role, "userId": user_id},
        )
        await emit_notification(
            notification_type,
            NotificationSource(component=SourceComponent.HYDRA_API, service="users"),
            "Role changed" if is_elevation else "Role downgraded",
            f"User role changed from {current_role} to {new_role}",
            target_user_id=user_id,
            details={"userId": user_id, "previousRole": current_role, "newRole": new_role},
            audit_entry_id=audit_id,
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
    ) -> dict[str, Any]:
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
        now = datetime.now(UTC)
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
            updated_user.get("temporaryRoles", [])  # type: ignore[union-attr]
        )

        logger.info(
            "temporary_role_granted",
            user_id=user_id,
            role=request.role.value,
            expires_at=request.expires_at.isoformat(),
            granted_by=granted_by,
        )

        audit_id = await log_audit(
            AuditAction.UPDATE, "user", user_id, "user", granted_by, True,
            details={"action": "grant_temporary_role", "role": request.role.value, "userId": user_id},
        )
        await emit_notification(
            NotificationType.ROLE_ELEVATION_GRANTED,
            NotificationSource(component=SourceComponent.HYDRA_API, service="users"),
            "Temporary role granted",
            f"Temporary role '{request.role.value}' granted until {request.expires_at.isoformat()}",
            target_user_id=user_id,
            details={"userId": user_id, "role": request.role.value, "expiresAt": request.expires_at.isoformat()},
            audit_entry_id=audit_id,
        )

        return {
            "user_id": user_id,
            "base_role": user["role"],
            "temporary_roles": active_temp_roles,
        }

    async def revoke_temporary_role(
        self, user_id: str, role: str, revoked_by: str
    ) -> dict[str, Any]:
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

        now = datetime.now(UTC)

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

        audit_id = await log_audit(
            AuditAction.UPDATE, "user", user_id, "user", revoked_by, True,
            details={"action": "revoke_temporary_role", "role": role, "userId": user_id},
        )
        await emit_notification(
            NotificationType.ROLE_ELEVATION_REVOKED,
            NotificationSource(component=SourceComponent.HYDRA_API, service="users"),
            "Temporary role revoked",
            f"Temporary role '{role}' has been revoked",
            target_user_id=user_id,
            details={"userId": user_id, "role": role},
            audit_entry_id=audit_id,
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
                # Node CRUD (no destructive controls — reboot/shutdown/update-system are admin-only)
                "nodes:read",
                "nodes:write",
                "nodes:create",
                "nodes:update",
                "nodes:delete",
                "nodes:control:set-hostname",
                # Services — all controls via wildcard
                "services:*",
                "profiles:*",
                "groups:*",
                "networks:*",
                "topologies:read",
                "docs:*",
                "dashboards:read",
                "dashboards:write",
                "commands:execute",
                "commands:read",
                "discovery:read",
                "discovery:scan",
                "discovery:dismiss",
                "plugins:read",
                "plugins:write",
                "installations:read",
                "installations:write",
                "ha:*",
                "tokens:create",
                "tokens:create:user",
                "tokens:create:node",
                "notifications:read",
                "notifications:write",
                "audit:read",
                "query:read",
                # Agent controls (subset — no restart/update/uninstall)
                "agent:control:status",
                "agent:control:config-reload",
                "agent:control:collect-now",
                "agent:control:probe-network",
            ],
            Role.VIEWER.value: [
                "nodes:read",
                "profiles:read",
                "services:read",
                "groups:read",
                "networks:read",
                "topologies:read",
                "docs:read",
                "dashboards:read",
                "discovery:read",
                "plugins:read",
                "installations:read",
                "ha:read",
                "notifications:read",
                "audit:read",
                # Viewer can see command history and check agent status
                "commands:read",
                "agent:control:status",
            ],
            Role.FAMILY.value: [
                "iot:read",
                "iot:control",
                "ha:read",
                "ha:control",
                "dashboards:read",
                "tokens:create:user",
                "notifications:read",
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
