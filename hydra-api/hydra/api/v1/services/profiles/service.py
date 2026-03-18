"""Profile management service with versioning and diff calculation."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from pymongo import DESCENDING

from hydra.api.v1.core.exceptions import NodeNotFoundError, ProfileNotFoundError
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationType,
    SourceComponent,
)
from hydra.api.v1.models.profiles import ProfileSubmission
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

from .diff import diff_config_files, diff_profiles
from .formatting import format_profile, format_profile_summary
from .network_processing import diff_network_config, process_networks
from .service_extraction import extract_services
from .versioning import (
    calculate_version,
    compute_profile_hash,
    compute_section_fingerprints,
)

logger = structlog.get_logger(__name__)


class ProfileService:
    """Service for profile management with versioning."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def submit_profile(self, submission: ProfileSubmission) -> dict:
        """Submit a new profile from an agent.

        Validates the node, computes fingerprints and version, stores the profile,
        extracts services, processes networks, and updates the node's lastProfileAt.

        Args:
            submission: The profile submission containing hardware, network,
                storage, software, configs, and services data.

        Returns:
            The created profile document.

        Raises:
            NodeNotFoundError: If the target node does not exist.
        """
        node = await self.db.nodes.find_one({"nodeId": submission.node_id})
        if not node:
            raise NodeNotFoundError(submission.node_id)

        previous = await self._get_latest_profile_meta(submission.node_id)
        previous_profile = None
        if previous:
            previous_profile = await self.db.profiles.find_one(
                {"profileId": previous.get("profileId")}
            )

        fingerprints = compute_section_fingerprints(submission)
        profile_hash = compute_profile_hash(fingerprints)

        if previous and previous.get("profileHash") == profile_hash:
            logger.info(
                "duplicate_profile_skipped",
                node_id=submission.node_id,
                profile_hash=profile_hash[:16],
            )
            existing = await self.db.profiles.find_one({"profileId": previous["profileId"]})
            return format_profile(existing)

        if previous:
            calculated_version = calculate_version(
                previous.get("version", "E0-0.0.0.0"),
                previous.get("sectionFingerprints", {}),
                fingerprints,
            )
        else:
            calculated_version = "E0-0.0.0.1"

        if submission.version and submission.version != calculated_version:
            logger.debug(
                "version_override",
                node_id=submission.node_id,
                agent_version=submission.version,
                calculated_version=calculated_version,
            )

        version = calculated_version

        now = datetime.now(timezone.utc)
        profile_id = f"prof_{secrets.token_urlsafe(12)}"

        profile_doc = {
            "profileId": profile_id,
            "nodeId": submission.node_id,
            "version": version,
            "collectedAt": submission.collected_at,
            "submittedAt": now,
            "agentVersion": submission.agent_version,
            "collectionLevel": submission.collection_level.value,
            "serviceIds": [],
            "hardware": submission.hardware.model_dump(by_alias=True) if submission.hardware else None,
            "network": submission.network.model_dump(by_alias=True) if submission.network else None,
            "storage": submission.storage.model_dump(by_alias=True) if submission.storage else None,
            "software": submission.software.model_dump(by_alias=True) if submission.software else None,
            "services": submission.services.model_dump(by_alias=True) if submission.services else None,
            "users": submission.users.model_dump(by_alias=True) if submission.users else None,
            "configs": submission.configs.model_dump(by_alias=True) if submission.configs else None,
            "metadata": submission.metadata,
        }

        service_ids = []
        if submission.services:
            service_ids = await extract_services(
                self.db,
                submission.node_id,
                profile_id,
                submission.services.services,
            )
            profile_doc["serviceIds"] = service_ids

        network_ids = await process_networks(
            self.db,
            submission.node_id,
            profile_id,
            submission.network,
        )

        await self.db.profiles.insert_one(profile_doc)

        meta_doc = {
            "profileId": profile_id,
            "nodeId": submission.node_id,
            "version": version,
            "sectionFingerprints": fingerprints,
            "profileHash": profile_hash,
            "computedAt": now,
        }
        await self.db.profile_meta.insert_one(meta_doc)

        node_update_fields: dict[str, Any] = {"lastProfileAt": now, "lastUpdated": now}
        if submission.agent_tier:
            node_update_fields["agentTier"] = submission.agent_tier
        await self.db.nodes.update_one(
            {"nodeId": submission.node_id},
            {"$set": node_update_fields},
        )

        logger.info(
            "profile_submitted",
            node_id=submission.node_id,
            profile_id=profile_id,
            version=version,
            service_count=len(service_ids),
            network_count=len(network_ids),
        )

        # --- Notifications ---
        _src = NotificationSource(
            component=SourceComponent.HYDRA_API,
            service="profile-service",
            node_id=submission.node_id,
        )

        # 1. Profile submitted (GREEN)
        audit_id = await log_audit(
            action=AuditAction.SUBMIT,
            resource_type="profile",
            resource_id=profile_id,
            actor_type="agent",
            actor_id=submission.node_id,
            details={
                "nodeId": submission.node_id,
                "profileId": profile_id,
                "version": version,
                "serviceCount": len(service_ids),
                "networkCount": len(network_ids),
            },
        )
        safe_create_task(emit_notification(
            notification_type=NotificationType.AGENT_PROFILE_SUBMITTED,
            source=_src,
            title="Profile submitted",
            message=f"Node {submission.node_id} submitted profile {profile_id}",
            details={
                "nodeId": submission.node_id,
                "profileId": profile_id,
                "version": version,
            },
            audit_entry_id=audit_id,
        ))

        # 2. Major version change (ORANGE) -- first two components (W or X) changed
        if previous:
            prev_version = previous.get("version", "E0-0.0.0.0")
            prev_parts = prev_version.split("-")[1].split(".")[:2]
            curr_parts = version.split("-")[1].split(".")[:2]
            if prev_parts != curr_parts:
                audit_id = await log_audit(
                    action=AuditAction.UPDATE,
                    resource_type="profile",
                    resource_id=profile_id,
                    actor_type="agent",
                    actor_id=submission.node_id,
                    details={
                        "nodeId": submission.node_id,
                        "profileId": profile_id,
                        "previousVersion": prev_version,
                        "newVersion": version,
                        "changeType": "major",
                    },
                )
                safe_create_task(emit_notification(
                    notification_type=NotificationType.PROFILE_MAJOR_CHANGE,
                    source=_src,
                    title="Major profile change detected",
                    message=(
                        f"Node {submission.node_id} profile changed significantly: "
                        f"{prev_version} -> {version}"
                    ),
                    details={
                        "nodeId": submission.node_id,
                        "profileId": profile_id,
                        "previousVersion": prev_version,
                        "newVersion": version,
                    },
                    audit_entry_id=audit_id,
                ))

        # 3. Config file changes (YELLOW)
        config_changes = diff_config_files(previous_profile, submission)
        if config_changes:
            audit_id = await log_audit(
                action=AuditAction.UPDATE,
                resource_type="profile",
                resource_id=profile_id,
                actor_type="system",
                actor_id="profile-service",
                details={
                    "nodeId": submission.node_id,
                    "profileId": profile_id,
                    "configChanges": config_changes,
                },
            )
            safe_create_task(emit_notification(
                notification_type=NotificationType.CONFIG_FILE_CHANGED,
                source=_src,
                title="Config files changed",
                message=(
                    f"Config files changed on node {submission.node_id}: "
                    f"{config_changes['counts']['changed']} modified, "
                    f"{config_changes['counts']['added']} added, "
                    f"{config_changes['counts']['removed']} removed"
                ),
                details={
                    "nodeId": submission.node_id,
                    "profileId": profile_id,
                    **config_changes,
                },
                audit_entry_id=audit_id,
            ))

        # 4. Network configuration changes (YELLOW)
        network_changes = diff_network_config(previous_profile, submission)
        if network_changes:
            audit_id = await log_audit(
                action=AuditAction.UPDATE,
                resource_type="profile",
                resource_id=profile_id,
                actor_type="system",
                actor_id="profile-service",
                details={
                    "nodeId": submission.node_id,
                    "profileId": profile_id,
                    "networkChanges": network_changes,
                },
            )
            safe_create_task(emit_notification(
                notification_type=NotificationType.NETWORK_CONFIG_CHANGED,
                source=_src,
                title="Network configuration changed",
                message=(
                    f"Network settings changed on node {submission.node_id}: "
                    f"{network_changes['counts']['interfacesChanged']} interface changes, "
                    f"{network_changes['counts']['routesChanged']} route changes"
                ),
                details={
                    "nodeId": submission.node_id,
                    "profileId": profile_id,
                    **network_changes,
                },
                audit_entry_id=audit_id,
            ))

        return format_profile(profile_doc)

    async def get_profile(self, profile_id: str) -> dict:
        """Retrieve a specific profile by its identifier.

        Args:
            profile_id: The unique profile identifier.

        Returns:
            The formatted profile document.

        Raises:
            ProfileNotFoundError: If no profile exists with the given ID.
        """
        profile = await self.db.profiles.find_one({"profileId": profile_id})
        if not profile:
            raise ProfileNotFoundError(profile_id)
        return format_profile(profile)

    async def get_latest_profile(self, node_id: str) -> dict:
        """Retrieve the most recent profile for a node.

        Args:
            node_id: The node identifier.

        Returns:
            The formatted latest profile document.

        Raises:
            NodeNotFoundError: If the node does not exist.
            ProfileNotFoundError: If the node has no profiles.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        profile = await self.db.profiles.find_one(
            {"nodeId": node_id},
            sort=[("submittedAt", DESCENDING)],
        )
        if not profile:
            raise ProfileNotFoundError(f"No profiles found for node {node_id}")

        return format_profile(profile)

    async def list_node_profiles(
        self,
        node_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List profiles for a node with pagination.

        Args:
            node_id: The node identifier.
            limit: Maximum number of results to return.
            offset: Number of results to skip.

        Returns:
            A tuple of (list of profile summaries, total count).

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        total = await self.db.profiles.count_documents({"nodeId": node_id})

        cursor = (
            self.db.profiles.find({"nodeId": node_id})
            .sort("submittedAt", DESCENDING)
            .skip(offset)
            .limit(limit)
        )

        profiles = []
        async for profile in cursor:
            profiles.append(format_profile_summary(profile))

        return profiles, total

    async def diff_profiles(
        self,
        node_id: str,
        from_version: str | None = None,
        to_version: str | None = None,
    ) -> dict:
        """Compare two profiles for a node. Delegates to diff module."""
        return await diff_profiles(self.db, node_id, from_version, to_version)

    async def _get_latest_profile_meta(self, node_id: str) -> dict | None:
        """Get the latest profile metadata for a node."""
        return await self.db.profile_meta.find_one(
            {"nodeId": node_id},
            sort=[("computedAt", DESCENDING)],
        )
