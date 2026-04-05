"""User authentication mixin: login, token refresh, brute-force tracking, device tracking."""


import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.core.auth_session import (
    access_blacklist_key,
    load_json,
    refresh_key,
    session_key,
    store_json,
    ttl_from_exp,
)
from hydra.api.v1.core.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    NodeNotFoundError,
    PendingApprovalError,
    SystemAccountLoginBlockedError,
    UserNotFoundError,
)
from hydra.api.v1.core.role_utils import get_active_temporary_roles
from hydra.api.v1.core.security import (
    create_token_pair,
    decode_token,
)
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.notifications import (
    ActorType,
    NotificationActor,
    NotificationSource,
    NotificationType,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.core.config import Settings
from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient

from .constants import (
    BRUTE_FORCE_NOTIFY_COOLDOWN_SECONDS,
    BRUTE_FORCE_THRESHOLD,
    BRUTE_FORCE_WINDOW_SECONDS,
)

logger = structlog.get_logger(__name__)


class LoginMixin:
    """Mixin providing user authentication, token refresh, and login tracking."""
    db: MongoDB
    redis: RedisClient | None
    settings: Settings


    @property
    def _refresh_ttl_seconds(self) -> int:
        """Return the configured refresh-token TTL in seconds."""
        return self.settings.jwt_refresh_expire_days * 24 * 60 * 60

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None:
        """Convert a datetime to UTC timezone."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

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
                        source=NotificationSource(component="hydra-api", service="auth"),  # type: ignore[arg-type]
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
                        actor=NotificationActor(  # type: ignore[call-arg]
                            type=ActorType.SYSTEM,
                            id="auth_service",
                            ip=ip,
                            userAgent=user_agent,
                        ),
                        audit_entry_id=audit_id,
                        mongodb=self.db,
                        redis=self.redis,
                        resolve_dependencies=False,
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
        user: dict[str, Any],
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[bool, str | None]:
        """Update login device tracking and return (is_new_device, device_id)."""
        device_id = self._device_fingerprint(ip, user_agent)
        if not device_id:
            return False, None

        now = datetime.now(UTC)
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

    async def _persist_refresh_session(
        self,
        *,
        subject: str,
        sub_type: str,
        session_id: str,
        refresh_jti: str,
        csrf_token: str,
        expires_at: int,
    ) -> None:
        """Persist refresh-session state for rotation and revocation checks."""
        if not self.redis:
            raise RuntimeError("Redis is required for Hydra auth sessions")

        session_record = {
            "sessionId": session_id,
            "familyId": session_id,
            "subject": subject,
            "subType": sub_type,
            "currentRefreshJti": refresh_jti,
            "csrfToken": csrf_token,
            "expiresAt": expires_at,
            "revoked": False,
        }
        refresh_record = {
            "sessionId": session_id,
            "subject": subject,
            "subType": sub_type,
            "jti": refresh_jti,
            "expiresAt": expires_at,
        }
        ttl_seconds = ttl_from_exp(expires_at)
        await store_json(self.redis.client, session_key(session_id), session_record, ttl_seconds)
        await store_json(self.redis.client, refresh_key(refresh_jti), refresh_record, ttl_seconds)

    async def _write_session_record(self, session_record: dict[str, Any]) -> None:
        """Rewrite an existing session record with its remaining TTL."""
        if not self.redis:
            raise RuntimeError("Redis is required for Hydra auth sessions")
        ttl_seconds = max(ttl_from_exp(session_record.get("expiresAt")), 1)
        await store_json(
            self.redis.client,
            session_key(session_record["sessionId"]),
            session_record,
            ttl_seconds,
        )

    async def _issue_token_bundle(
        self,
        *,
        subject: str,
        sub_type: str,
        additional_claims: dict[str, Any] | None = None,
        session_id: str | None = None,
        csrf_token: str | None = None,
    ) -> dict[str, Any]:
        """Issue a fresh access/refresh pair and persist rotation state."""
        current_session_id = session_id or secrets.token_urlsafe(24)
        current_csrf_token = csrf_token or secrets.token_urlsafe(32)
        refresh_jti = secrets.token_urlsafe(24)
        access_token, refresh_token = create_token_pair(
            subject=subject,
            additional_claims=additional_claims,
            session_id=current_session_id,
            refresh_token_id=refresh_jti,
        )
        refresh_payload = decode_token(refresh_token)
        await self._persist_refresh_session(
            subject=subject,
            sub_type=sub_type,
            session_id=current_session_id,
            refresh_jti=refresh_jti,
            csrf_token=current_csrf_token,
            expires_at=int(refresh_payload["exp"]),
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "csrf_token": current_csrf_token,
            "session_id": current_session_id,
            "expires_in": self.settings.jwt_expire_minutes * 60,
        }

    async def _load_active_refresh_state(self, refresh_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Load refresh-session state and detect reuse or revocation."""
        if not self.redis:
            raise InvalidTokenError("Refresh tokens require Redis-backed session state")

        session_id = refresh_payload.get("sid")
        refresh_jti = refresh_payload.get("jti")
        if not session_id or not refresh_jti:
            raise InvalidTokenError("Refresh token is missing session metadata")

        session_record = await load_json(self.redis.client, session_key(session_id))
        refresh_record = await load_json(self.redis.client, refresh_key(refresh_jti))
        if not session_record or not refresh_record:
            raise InvalidTokenError("Refresh token session not found")

        if session_record.get("revoked"):
            raise InvalidTokenError("Refresh session has been revoked")

        if session_record.get("currentRefreshJti") != refresh_jti:
            await self.revoke_session(session_id)
            raise InvalidTokenError("Refresh token reuse detected")

        return session_record, refresh_record

    async def revoke_session(self, session_id: str | None) -> None:
        """Mark a session as revoked so all attached tokens are rejected."""
        if not self.redis or not session_id:
            return

        session_record = await load_json(self.redis.client, session_key(session_id))
        if not session_record:
            return

        session_record["revoked"] = True
        session_record["currentRefreshJti"] = None
        await self._write_session_record(session_record)

    async def blacklist_access_token(self, token_payload: dict[str, Any]) -> None:
        """Blacklist an access token until its natural expiry."""
        if not self.redis:
            return
        token_jti = token_payload.get("jti")
        if not token_jti:
            return
        ttl_seconds = ttl_from_exp(token_payload.get("exp"))
        if ttl_seconds > 0:
            await self.redis.client.setex(access_blacklist_key(token_jti), ttl_seconds, "1")

    async def ensure_access_token_active(self, token_payload: dict[str, Any]) -> None:
        """Reject blacklisted or session-revoked access tokens."""
        if not self.redis:
            return

        token_jti = token_payload.get("jti")
        if token_jti and await self.redis.client.get(access_blacklist_key(token_jti)):
            raise InvalidTokenError("Token has been revoked")

        session_id = token_payload.get("sid")
        if not session_id:
            return

        session_record = await load_json(self.redis.client, session_key(session_id))
        if session_record and session_record.get("revoked"):
            raise InvalidTokenError("Session has been revoked")

    # ==================== User Authentication ====================

    async def authenticate_user(
        self,
        username: str,
        password: str,
        allow_system_accounts: bool = False,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
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

        # SEC-016: Block IPs that have exceeded the brute force threshold
        if self.redis and ip:
            ip_count = await self.redis.client.get(f"auth:failed:ip:{ip}")
            if ip_count and int(ip_count) >= BRUTE_FORCE_THRESHOLD:
                logger.warning("brute_force_blocked", ip=ip, attempts=int(ip_count))
                raise InvalidCredentialsError()

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
            {"$set": {"lastLogin": datetime.now(UTC)}},
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
                        source=NotificationSource(component="hydra-api", service="auth"),  # type: ignore[arg-type]
                        title="New login device detected",
                        message=f"New login detected for {user['username']}",
                        details={
                            "userId": user["userId"],
                            "username": user["username"],
                            "ip": ip,
                            "userAgent": user_agent,
                            "deviceId": device_id,
                        },
                        actor=NotificationActor(  # type: ignore[call-arg]
                            type=ActorType.USER,
                            id=user["userId"],
                            ip=ip,
                            userAgent=user_agent,
                        ),
                        target_user_id=user["userId"],
                        audit_entry_id=audit_id,
                        mongodb=self.db,
                        redis=self.redis,
                        resolve_dependencies=False,
                    )
                )

        temp_roles = get_active_temporary_roles(user.get("temporaryRoles", []))

        token_bundle = await self._issue_token_bundle(
            subject=user["userId"],
            sub_type="user",
            additional_claims={
                "sub_type": "user",
                "role": user["role"],
                "permissions": user.get("permissions", []),
            },
        )

        return {
            **token_bundle,
            "user": {
                "user_id": user["userId"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
                "temporary_roles": temp_roles,
                "permissions": user.get("permissions", []),
            },
        }

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
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

        session_record, refresh_record = await self._load_active_refresh_state(payload)
        subject = payload["sub"]
        sub_type = payload.get("sub_type", "user")
        session_id = session_record["sessionId"]
        csrf_token = session_record["csrfToken"]

        if sub_type == "user":
            user = await self.db.users.find_one({"userId": subject})
            if not user:
                raise UserNotFoundError(subject)

            token_bundle = await self._issue_token_bundle(
                subject=subject,
                sub_type="user",
                additional_claims={
                    "sub_type": "user",
                    "role": user["role"],
                    "permissions": user.get("permissions", []),
                },
                session_id=session_id,
                csrf_token=csrf_token,
            )
        else:  # agent
            node = await self.db.nodes.find_one({"nodeId": subject})
            if not node:
                raise NodeNotFoundError(subject)

            token_bundle = await self._issue_token_bundle(
                subject=subject,
                sub_type="agent",
                additional_claims={"sub_type": "agent"},
                session_id=session_id,
                csrf_token=csrf_token,
            )

        refresh_record["rotatedTo"] = decode_token(token_bundle["refresh_token"])["jti"]
        ttl_seconds = max(ttl_from_exp(refresh_record.get("expiresAt")), 1)
        await store_json(
            self.redis.client,  # type: ignore[union-attr]
            refresh_key(refresh_record["jti"]),
            refresh_record,
            ttl_seconds,
        )

        return {
            **token_bundle,
        }
