"""User credentials mixin - handles password reset, change, and email flows."""

import secrets
from datetime import datetime, timedelta, timezone

import structlog

from hydra.api.v1.core.exceptions import (
    InvalidPasswordError,
    PasswordResetTokenError,
    UserNotFoundError,
)
from hydra.api.v1.core.security import hash_password, verify_password
from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationType,
    SourceComponent,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit

logger = structlog.get_logger(__name__)


class CredentialsMixin:
    """Mixin providing password and credential management functionality."""

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
        except ConnectionRefusedError:
            logger.error(
                "password_reset_email_connection_refused",
                user_id=user["userId"],
                error="SMTP server refused connection",
            )
            email_sent = False
        except OSError as e:
            logger.error(
                "password_reset_email_network_error",
                user_id=user["userId"],
                error=str(e),
                error_type="os_error",
            )
            email_sent = False
        except Exception as e:
            logger.error(
                "password_reset_email_failed",
                user_id=user["userId"],
                error=str(e),
                error_type=type(e).__name__,
            )
            email_sent = False

        logger.info(
            "password_reset_requested",
            user_id=user["userId"],
            email_sent=email_sent,
        )

        audit_id = await log_audit(
            AuditAction.CREATE, "password_reset", email, "user", user["userId"], True,
            details={"userId": user["userId"], "email": email},
        )
        await emit_notification(
            NotificationType.PASSWORD_RESET_REQUESTED,
            NotificationSource(component=SourceComponent.HYDRA_API, service="users"),
            "Password reset requested",
            "A password reset was requested",
            target_user_id=user["userId"],
            details={"userId": user["userId"], "email": email},
            audit_entry_id=audit_id,
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

        audit_id = await log_audit(
            AuditAction.UPDATE, "user", user_id, "user", user_id, True,
            details={"action": "password_change", "userId": user_id},
        )
        await emit_notification(
            NotificationType.PASSWORD_CHANGED,
            NotificationSource(component=SourceComponent.HYDRA_API, service="users"),
            "Password changed",
            "Your password was changed successfully",
            target_user_id=user_id,
            details={"userId": user_id},
            audit_entry_id=audit_id,
        )

        return {"changed_at": now}
