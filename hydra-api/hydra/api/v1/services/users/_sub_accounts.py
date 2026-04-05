"""Sub-account management mixin - handles linking, unlinking, and listing sub-accounts."""

from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.core.exceptions import (
    AlreadyHasParentError,
    CannotHaveSubAccountsError,
    InvalidPasswordError,
    InvalidSubAccountRoleError,
    NotASubAccountError,
    UserNotFoundError,
    ValidationError,
)
from hydra.api.v1.core.security import verify_password
from hydra.api.v1.models.auth import can_have_sub_accounts, is_valid_sub_account_role
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


class SubAccountsMixin:
    """Mixin providing sub-account management functionality."""
    db: MongoDB


    async def link_sub_account(
        self,
        parent_user_id: str,
        target_user_id: str,
        target_password: str,
        reset_password: bool = False,
    ) -> dict[str, Any]:
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

        now = datetime.now(UTC)

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

        audit_id = await log_audit(
            AuditAction.UPDATE,
            "user",
            parent_user_id,
            "user",
            parent_user_id,
            True,
            details={
                "action": "sub_account_linked",
                "userId": parent_user_id,
                "subAccountUserId": target_user_id,
                "subAccountUsername": target["username"],
                "subAccountRole": target["role"],
                "passwordReset": password_reset,
            },
        )
        await emit_notification(
            NotificationType.SUB_ACCOUNT_LINKED,
            NotificationSource(component=SourceComponent.HYDRA_API, service="users"),
            "Sub-account linked",
            f"Sub-account {target['username']} linked to your account",
            target_user_id=parent_user_id,
            details={
                "userId": parent_user_id,
                "subAccountUserId": target_user_id,
                "subAccountUsername": target["username"],
                "subAccountRole": target["role"],
                "passwordReset": password_reset,
            },
            audit_entry_id=audit_id,
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
    ) -> dict[str, Any]:
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

        now = datetime.now(UTC)

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

    async def list_sub_accounts(self, user_id: str) -> tuple[list[dict[str, Any]], int]:
        """List sub-accounts of a user.

        Args:
            user_id: User ID to list sub-accounts for.

        Returns:
            Tuple of (sub-accounts list, total count).

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

        return enriched_subs, len(enriched_subs)
