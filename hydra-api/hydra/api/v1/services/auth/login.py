"""User authentication mixin: login, token refresh, brute-force tracking, device tracking."""

import hashlib
from datetime import datetime, timezone

import structlog

from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.core.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    NodeNotFoundError,
    PendingApprovalError,
    SystemAccountLoginBlockedError,
    UserNotFoundError,
)
from hydra.api.v1.core.security import (
    create_access_token,
    create_token_pair,
    decode_token,
)
from hydra.api.v1.core.role_utils import get_active_temporary_roles
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.models.notifications import (
    NotificationType,
    NotificationSource,
    NotificationActor,
    ActorType,
)
from hydra.api.v1.services.query import log_audit
from hydra.api.v1.models.query import AuditAction

from .constants import (
    BRUTE_FORCE_WINDOW_SECONDS,
    BRUTE_FORCE_THRESHOLD,
    BRUTE_FORCE_NOTIFY_COOLDOWN_SECONDS,
)

logger = structlog.get_logger(__name__)


class LoginMixin:
    """Mixin providing user authentication, token refresh, and login tracking."""

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None:
        """Convert a datetime to UTC timezone."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _device_fingerprint(ip: str | None, user_agent: str | None) -> str | None:
        """Build a stable device fingerprint from IP + User-Agent."""
        if not ip and not user_agent:
            return None
        seed = f"{ip or 'unknown'}|{user_agent or 'unknown'}".strip().lower()
        return hashlib.sha256(seed.encode()).hexdigest()[:16]

    async def _record_failed_login(
        self,
        username: str | None,
        ip: str | None,
        user_agent: str | None,
        user_id: str | None = None,
    ) -> None:
        """Track failed logins and emit brute force detection when threshold is exceeded."""
        if not self.redis or not ip:
            return

        ip_key = f"auth:failed:ip:{ip}"
        user_key = f"auth:failed:user:{username}" if username else None

        try:
            pipe = self.redis.client.pipeline()
            pipe.incr(ip_key)
            pipe.expire(ip_key, BRUTE_FORCE_WINDOW_SECONDS)
            if user_key:
                pipe.incr(user_key)
                pipe.expire(user_key, BRUTE_FORCE_WINDOW_SECONDS)
            results = await pipe.execute()

            ip_count = results[0] if results else 0

            if ip_count >= BRUTE_FORCE_THRESHOLD:
                notify_key = f"auth:bruteforce:notified:{ip}"
                already_notified = await self.redis.client.get(notify_key)
                if already_notified:
                    return

                await self.redis.client.setex(
                    notify_key, BRUTE_FORCE_NOTIFY_COOLDOWN_SECONDS, "1"
                )

                audit_id = await log_audit(
                    AuditAction.CREATE,
                    "auth",
                    ip,
                    "system",
                    "auth_service",
                    True,
                    details={
                        "ip": ip,
                        "username": username,
                        "userId": user_id,
                        "attempts": ip_count,
                        "windowSeconds": BRUTE_FORCE_WINDOW_SECONDS,
                    },
                    ip=ip,
                )

                safe_create_task(
                    emit_notification(
                        notification_type=NotificationType.AUTH_BRUTE_FORCE_DETECTED,
                        source=NotificationSource(component="hydra-api", service="auth"),
                        title="Brute force login attempts detected",
                        message=(
                            f"Multiple failed login attempts detected from {ip} "
                            f"({ip_count} attempts in {BRUTE_FORCE_WINDOW_SECONDS // 60}m)"
                        ),
                        details={
                            "ip": ip,
                            "username": username,
                            "userId": user_id,
                            "attempts": ip_count,
                            "windowSeconds": BRUTE_FORCE_WINDOW_SECONDS,
                            "userAgent": user_agent,
                        },
                        actor=NotificationActor(
                            type=ActorType.SYSTEM,
                            id="auth_service",
                            ip=ip,
                            userAgent=user_agent,
                        ),
                        audit_entry_id=audit_id,
                    )
                )
        except Exception:
            logger.exception("failed_login_tracking_failed", username=username, ip=ip)

    async def _clear_failed_login(self, username: str | None, ip: str | None) -> None:
        """Clear failed login counters after a successful login."""
        if not self.redis:
            return
        keys = []
        if ip:
            keys.append(f"auth:failed:ip:{ip}")
            keys.append(f"auth:bruteforce:notified:{ip}")
        if username:
            keys.append(f"auth:failed:user:{username}")
        if keys:
            try:
                await self.redis.client.delete(*keys)
            except Exception:
                logger.exception("failed_login_clear_failed", username=username, ip=ip)

    async def _update_login_device(
        self,
        user: dict,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[bool, str | None]:
        """Update login device tracking and return (is_new_device, device_id)."""
        device_id = self._device_fingerprint(ip, user_agent)
        if not device_id:
            return False, None

        now = datetime.now(timezone.utc)
        user_id = user.get("userId")
        devices = user.get("loginDevices", [])
        existing = next(
            (d for d in devices if d.get("deviceId") == device_id),
            None,
        )

        if existing:
            await self.db.users.update_one(
                {"userId": user_id, "loginDevices.deviceId": device_id},
                {
                    "$set": {
                        "loginDevices.$.lastSeenAt": now,
                        "loginDevices.$.ip": ip,
                        "loginDevices.$.userAgent": user_agent,
                    }
                },
            )
            return False, device_id

        await self.db.users.update_one(
            {"userId": user_id},
            {
                "$push": {
                    "loginDevices": {
                        "deviceId": device_id,
                        "ip": ip,
                        "userAgent": user_agent,
                        "firstSeenAt": now,
                        "lastSeenAt": now,
                    }
                }
            },
        )
        return True, device_id

    # ==================== User Authentication ====================

    async def authenticate_user(
        self,
        username: str,
        password: str,
        allow_system_accounts: bool = False,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Authenticate a user and return access/refresh tokens.

        Args:
            username: User's username.
            password: User's password.
            allow_system_accounts: If False, block system accounts (agent users) from login.
            ip: Client IP address for audit and device tracking.
            user_agent: User-Agent string for audit and device tracking.

        Returns:
            Dict with access_token, refresh_token, expires_in, and user details.

        Raises:
            PendingApprovalError: If user is pending approval.
            InvalidCredentialsError: If credentials are invalid.
            SystemAccountLoginBlockedError: If system account tries to login via web.
        """
        from hydra.api.v1.core.security import verify_password

        pending = await self.db.users_pending.find_one({"username": username})
        if pending:
            raise PendingApprovalError(username)

        user = await self.db.users.find_one({"username": username})
        if not user:
            await self._record_failed_login(username, ip, user_agent)
            raise InvalidCredentialsError()

        password_valid = verify_password(password, user["passwordHash"])
        if not password_valid:
            parent_id = user.get("parentUserId")
            if parent_id:
                parent = await self.db.users.find_one({"userId": parent_id})
                if parent and parent.get("status") == "active":
                    password_valid = verify_password(password, parent["passwordHash"])

            if not password_valid:
                await self._record_failed_login(username, ip, user_agent, user_id=user.get("userId"))
                raise InvalidCredentialsError()

        if user.get("status") != "active":
            raise InvalidCredentialsError()

        if not allow_system_accounts and user.get("isSystemAccount", False):
            raise SystemAccountLoginBlockedError(username)

        await self.db.users.update_one(
            {"userId": user["userId"]},
            {"$set": {"lastLogin": datetime.now(timezone.utc)}},
        )
        await self._clear_failed_login(username, ip)

        audit_id = await log_audit(
            AuditAction.LOGIN,
            "user",
            user["userId"],
            "user",
            user["userId"],
            True,
            details={
                "username": user["username"],
                "userId": user["userId"],
                "ip": ip,
                "userAgent": user_agent,
            },
            ip=ip,
        )

        if not user.get("isSystemAccount", False):
            is_new_device, device_id = await self._update_login_device(user, ip, user_agent)
            if is_new_device:
                safe_create_task(
                    emit_notification(
                        notification_type=NotificationType.USER_LOGIN_NEW_DEVICE,
                        source=NotificationSource(component="hydra-api", service="auth"),
                        title="New login device detected",
                        message=f"New login detected for {user['username']}",
                        details={
                            "userId": user["userId"],
                            "username": user["username"],
                            "ip": ip,
                            "userAgent": user_agent,
                            "deviceId": device_id,
                        },
                        actor=NotificationActor(
                            type=ActorType.USER,
                            id=user["userId"],
                            ip=ip,
                            userAgent=user_agent,
                        ),
                        target_user_id=user["userId"],
                        audit_entry_id=audit_id,
                    )
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
