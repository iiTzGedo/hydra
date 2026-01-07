"""Settings service for user and system configuration."""

from datetime import datetime, timezone

import structlog

from hydra.api.v1.models.settings import (
    DefaultSettings,
    NotificationSettings,
    ObjectStorageSettings,
    SmtpSettings,
    SystemSettingsUpdate,
    UISettings,
    UserSettingsUpdate,
    ViewSettings,
)
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class SettingsService:
    """Settings management service."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    # ==================== User Settings ====================

    async def get_user_settings(self, user_id: str) -> dict:
        """Get settings for a user, creating defaults if not exist."""
        doc = await self.db.user_settings.find_one({"userId": user_id})

        if not doc:
            # Create default settings
            doc = await self._create_default_user_settings(user_id)

        return self._user_settings_doc_to_response(doc)

    async def update_user_settings(
        self,
        user_id: str,
        request: UserSettingsUpdate,
    ) -> dict:
        """Update user settings."""
        now = datetime.now(timezone.utc)

        # Get existing or create default
        existing = await self.db.user_settings.find_one({"userId": user_id})
        if not existing:
            existing = await self._create_default_user_settings(user_id)

        update_fields = {"updatedAt": now}

        # Merge UI settings
        if request.ui is not None:
            existing_ui = existing.get("ui", {})
            for key, value in request.ui.model_dump(by_alias=True, exclude_none=True).items():
                existing_ui[key] = value
            update_fields["ui"] = existing_ui

        # Merge view settings
        if request.views is not None:
            existing_views = existing.get("views", {})
            for page_key, page_settings in request.views.model_dump(by_alias=True, exclude_none=True).items():
                if page_key not in existing_views:
                    existing_views[page_key] = {}
                for key, value in page_settings.items():
                    existing_views[page_key][key] = value
            update_fields["views"] = existing_views

        # Merge notification settings
        if request.notifications is not None:
            existing_notif = existing.get("notifications", {})
            for key, value in request.notifications.model_dump(by_alias=True, exclude_none=True).items():
                existing_notif[key] = value
            update_fields["notifications"] = existing_notif

        await self.db.user_settings.update_one(
            {"userId": user_id},
            {"$set": update_fields},
        )

        updated_doc = await self.db.user_settings.find_one({"userId": user_id})

        logger.info("user_settings_updated", user_id=user_id)

        return self._user_settings_doc_to_response(updated_doc)

    async def _create_default_user_settings(self, user_id: str) -> dict:
        """Create default settings for a new user."""
        now = datetime.now(timezone.utc)

        doc = {
            "userId": user_id,
            "ui": UISettings().model_dump(by_alias=True),
            "views": ViewSettings().model_dump(by_alias=True),
            "notifications": NotificationSettings().model_dump(by_alias=True),
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.user_settings.insert_one(doc)

        logger.info("user_settings_created", user_id=user_id)

        return doc

    def _user_settings_doc_to_response(self, doc: dict) -> dict:
        """Convert user settings document to response."""
        return {
            "user_id": doc["userId"],
            "ui": doc.get("ui", UISettings().model_dump(by_alias=True)),
            "views": doc.get("views", ViewSettings().model_dump(by_alias=True)),
            "notifications": doc.get("notifications", NotificationSettings().model_dump(by_alias=True)),
            "updated_at": doc.get("updatedAt", doc.get("createdAt")),
        }

    # ==================== System Settings ====================

    async def get_system_settings(self) -> dict:
        """Get system-wide settings."""
        doc = await self.db.system_settings.find_one({"_id": "system"})

        if not doc:
            # Create default system settings
            doc = await self._create_default_system_settings()

        return self._system_settings_doc_to_response(doc)

    async def update_system_settings(
        self,
        request: SystemSettingsUpdate,
        admin_user_id: str,
    ) -> dict:
        """Update system settings (admin only)."""
        now = datetime.now(timezone.utc)

        # Get existing or create default
        existing = await self.db.system_settings.find_one({"_id": "system"})
        if not existing:
            existing = await self._create_default_system_settings()

        update_fields = {
            "updatedAt": now,
            "updatedBy": admin_user_id,
        }

        # Merge SMTP settings
        if request.smtp is not None:
            existing_smtp = existing.get("smtp", {})
            for key, value in request.smtp.model_dump(by_alias=True, exclude_none=True).items():
                existing_smtp[key] = value
            update_fields["smtp"] = existing_smtp

        # Merge object storage settings
        if request.object_storage is not None:
            existing_storage = existing.get("objectStorage", {})
            for key, value in request.object_storage.model_dump(by_alias=True, exclude_none=True).items():
                existing_storage[key] = value
            update_fields["objectStorage"] = existing_storage

        # Merge default settings
        if request.defaults is not None:
            existing_defaults = existing.get("defaults", {})
            for key, value in request.defaults.model_dump(by_alias=True, exclude_none=True).items():
                existing_defaults[key] = value
            update_fields["defaults"] = existing_defaults

        await self.db.system_settings.update_one(
            {"_id": "system"},
            {"$set": update_fields},
        )

        updated_doc = await self.db.system_settings.find_one({"_id": "system"})

        logger.info(
            "system_settings_updated",
            updated_by=admin_user_id,
        )

        return self._system_settings_doc_to_response(updated_doc)

    async def _create_default_system_settings(self) -> dict:
        """Create default system settings."""
        now = datetime.now(timezone.utc)

        doc = {
            "_id": "system",
            "smtp": SmtpSettings().model_dump(by_alias=True),
            "objectStorage": ObjectStorageSettings().model_dump(by_alias=True),
            "defaults": DefaultSettings().model_dump(by_alias=True),
            "createdAt": now,
            "updatedAt": now,
            "updatedBy": None,
        }

        await self.db.system_settings.insert_one(doc)

        logger.info("system_settings_created")

        return doc

    def _system_settings_doc_to_response(self, doc: dict) -> dict:
        """Convert system settings document to response."""
        return {
            "smtp": doc.get("smtp", SmtpSettings().model_dump(by_alias=True)),
            "object_storage": doc.get("objectStorage", ObjectStorageSettings().model_dump(by_alias=True)),
            "defaults": doc.get("defaults", DefaultSettings().model_dump(by_alias=True)),
            "updated_at": doc.get("updatedAt", doc.get("createdAt")),
            "updated_by": doc.get("updatedBy"),
        }
