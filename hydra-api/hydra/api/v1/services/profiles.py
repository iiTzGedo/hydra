"""Profile management service with versioning and diff calculation."""

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from pymongo import DESCENDING

from hydra.api.v1.core.exceptions import NodeNotFoundError, ProfileNotFoundError, ValidationError
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationType,
    SourceComponent,
)
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.api.v1.models.query import AuditAction
from hydra.db.mongodb import MongoDB
from hydra.api.v1.models.profiles import ProfileSubmission

logger = structlog.get_logger(__name__)

SECTION_WEIGHTS = {
    "hardware": 0.30,
    "configs": 0.25,
    "software": 0.20,
    "storage": 0.15,
    "network": 0.10,
}

CRASH_STATUSES = {"failed", "error", "crashed", "dead"}


def generate_service_id(node_id: str, runtime: str, name: str) -> str:
    """Generate a unique service ID from node, runtime, and service name.

    Args:
        node_id: The node ID where the service runs.
        runtime: The service runtime (e.g., docker, systemd, kubernetes).
        name: The service name.

    Returns:
        Service ID in format: svc-<sanitized_name>-<4 char hash>.
    """
    hash_input = f"{node_id}:{runtime}:{name}"
    hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()
    hash_suffix = hash_digest[:4]

    sanitized_name = name.lower().replace(".", "-")
    max_name_len = 40
    if len(sanitized_name) > max_name_len:
        sanitized_name = sanitized_name[:max_name_len]

    return f"svc-{sanitized_name}-{hash_suffix}"


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

        fingerprints = self._compute_section_fingerprints(submission)
        profile_hash = self._compute_profile_hash(fingerprints)

        if previous and previous.get("profileHash") == profile_hash:
            logger.info(
                "duplicate_profile_skipped",
                node_id=submission.node_id,
                profile_hash=profile_hash[:16],
            )
            existing = await self.db.profiles.find_one({"profileId": previous["profileId"]})
            return self._format_profile(existing)

        if previous:
            calculated_version = self._calculate_version(
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
            service_ids = await self._extract_services(
                submission.node_id,
                profile_id,
                submission.services.services,
            )
            profile_doc["serviceIds"] = service_ids

        network_ids = await self._process_networks(
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

        await self.db.nodes.update_one(
            {"nodeId": submission.node_id},
            {"$set": {"lastProfileAt": now, "lastUpdated": now}},
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

        # 2. Major version change (ORANGE) — first two components (W or X) changed
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
        config_changes = self._diff_config_files(previous_profile, submission)
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
        network_changes = self._diff_network_config(previous_profile, submission)
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

        return self._format_profile(profile_doc)

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
        return self._format_profile(profile)

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

        return self._format_profile(profile)

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
            profiles.append(self._format_profile_summary(profile))

        return profiles, total

    async def diff_profiles(
        self,
        node_id: str,
        from_version: str | None = None,
        to_version: str | None = None,
    ) -> dict:
        """Compare two profiles for a node.

        If versions are not specified, compares the latest two profiles.

        Args:
            node_id: The node identifier.
            from_version: The starting profile version (optional).
            to_version: The ending profile version (optional).

        Returns:
            A diff summary including changed sections and percentages.

        Raises:
            NodeNotFoundError: If the node does not exist.
            ValidationError: If fewer than 2 profiles exist for comparison.
            ProfileNotFoundError: If specified versions are not found.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        if from_version and to_version:
            from_profile = await self.db.profiles.find_one(
                {"nodeId": node_id, "version": from_version}
            )
            to_profile = await self.db.profiles.find_one(
                {"nodeId": node_id, "version": to_version}
            )
        else:
            cursor = (
                self.db.profiles.find({"nodeId": node_id})
                .sort("submittedAt", DESCENDING)
                .limit(2)
            )
            profiles = await cursor.to_list(length=2)

            if len(profiles) < 2:
                raise ValidationError("Need at least 2 profiles to compare")

            to_profile = profiles[0]
            from_profile = profiles[1]

        if not from_profile:
            raise ProfileNotFoundError(f"Profile version {from_version} not found")
        if not to_profile:
            raise ProfileNotFoundError(f"Profile version {to_version} not found")

        from_meta = await self.db.profile_meta.find_one(
            {"profileId": from_profile["profileId"]}
        )
        to_meta = await self.db.profile_meta.find_one(
            {"profileId": to_profile["profileId"]}
        )

        changed_sections = []
        change_summary: dict[str, Any] = {}

        from_fingerprints = from_meta.get("sectionFingerprints", {}) if from_meta else {}
        to_fingerprints = to_meta.get("sectionFingerprints", {}) if to_meta else {}

        all_sections = set(from_fingerprints.keys()) | set(to_fingerprints.keys())

        for section in all_sections:
            from_hashes = set(from_fingerprints.get(section, []))
            to_hashes = set(to_fingerprints.get(section, []))

            if from_hashes != to_hashes:
                changed_sections.append(section)
                added = len(to_hashes - from_hashes)
                removed = len(from_hashes - to_hashes)
                change_summary[section] = {
                    "added": added,
                    "removed": removed,
                    "changed": min(added, removed),
                }

        total_diff = 0.0
        for section in all_sections:
            from_hashes = set(from_fingerprints.get(section, []))
            to_hashes = set(to_fingerprints.get(section, []))
            union = from_hashes | to_hashes
            if union:
                intersection = from_hashes & to_hashes
                jaccard = 1 - (len(intersection) / len(union))
                total_diff += jaccard * SECTION_WEIGHTS.get(section, 0.1)

        return {
            "fromVersion": from_profile["version"],
            "toVersion": to_profile["version"],
            "fromProfileId": from_profile["profileId"],
            "toProfileId": to_profile["profileId"],
            "changedSections": changed_sections,
            "changeSummary": change_summary,
            "diffPercentage": round(total_diff * 100, 2),
        }

    async def _get_latest_profile_meta(self, node_id: str) -> dict | None:
        """Get the latest profile metadata for a node."""
        return await self.db.profile_meta.find_one(
            {"nodeId": node_id},
            sort=[("computedAt", DESCENDING)],
        )

    def _compute_section_fingerprints(self, submission: ProfileSubmission) -> dict[str, list[str]]:
        """Compute hash fingerprints for each section of the profile."""
        fingerprints: dict[str, list[str]] = {}

        if submission.hardware:
            hashes = []
            hw = submission.hardware
            if hw.cpu:
                hashes.append(self._hash_dict(hw.cpu.model_dump(by_alias=True)))
            if hw.memory:
                mem_data = hw.memory.model_dump(by_alias=True)
                mem_data.pop("usedBytes", None)
                hashes.append(self._hash_dict(mem_data))
            for gpu in hw.gpus:
                hashes.append(self._hash_dict(gpu.model_dump(by_alias=True)))
            if hashes:
                fingerprints["hardware"] = hashes

        if submission.network:
            hashes = []
            for iface in submission.network.interfaces:
                hashes.append(self._hash_dict(iface.model_dump(by_alias=True)))
            for route in submission.network.routes:
                hashes.append(self._hash_dict(route.model_dump(by_alias=True)))
            if hashes:
                fingerprints["network"] = hashes

        if submission.storage:
            hashes = []
            for device in submission.storage.block_devices:
                hashes.append(self._hash_dict(device.model_dump(by_alias=True)))
            for fs in submission.storage.filesystems:
                hashes.append(self._hash_dict(fs.model_dump(by_alias=True)))
            if hashes:
                fingerprints["storage"] = hashes

        if submission.software:
            hashes = []
            if submission.software.os:
                hashes.append(self._hash_dict(submission.software.os.model_dump(by_alias=True)))
            for pkg in submission.software.packages:
                hashes.append(self._hash_dict(pkg.model_dump(by_alias=True)))
            if hashes:
                fingerprints["software"] = hashes

        if submission.configs:
            hashes = []
            for config in submission.configs.files:
                hashes.append(config.hash)
            if hashes:
                fingerprints["configs"] = hashes

        return fingerprints

    def _compute_profile_hash(self, fingerprints: dict[str, list[str]]) -> str:
        """Compute overall profile hash from section fingerprints."""
        all_hashes = []
        for section in sorted(fingerprints.keys()):
            all_hashes.extend(sorted(fingerprints[section]))
        combined = ":".join(all_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _hash_dict(self, data: dict) -> str:
        """Hash a dictionary to a fingerprint."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def _calculate_version(
        self,
        previous_version: str,
        previous_fingerprints: dict[str, list[str]],
        current_fingerprints: dict[str, list[str]],
    ) -> str:
        """Calculate new version based on diff from previous.

        Version format: Ex-W.X.Y.Z (hexadecimal) where:
        - W increments for >75% change
        - X increments for >50% change
        - Y increments for >25% change
        - Z increments for any change
        """
        total_diff = 0.0
        sections_changed = 0

        all_sections = set(previous_fingerprints.keys()) | set(current_fingerprints.keys())

        for section in all_sections:
            prev_hashes = set(previous_fingerprints.get(section, []))
            curr_hashes = set(current_fingerprints.get(section, []))

            if prev_hashes != curr_hashes:
                sections_changed += 1
                union = prev_hashes | curr_hashes
                if union:
                    intersection = prev_hashes & curr_hashes
                    jaccard = 1 - (len(intersection) / len(union))
                    total_diff += jaccard * SECTION_WEIGHTS.get(section, 0.1)

        if total_diff > 0.75:
            position = 0
        elif total_diff > 0.50:
            position = 1
        elif total_diff > 0.25:
            position = 2
        else:
            position = 3

        return self._increment_version(previous_version, position)

    def _increment_version(self, version: str, position: int) -> str:
        """Increment version at specified position with hexadecimal overflow handling."""
        parts = version.split("-")
        epoch = int(parts[0][1:])
        components = parts[1].split(".")

        values = [int(c, 16) for c in components]

        values[position] += 1

        for i in range(3, -1, -1):
            if values[i] > 15:
                values[i] = 0
                if i > 0:
                    values[i - 1] += 1
                else:
                    epoch += 1
                    values = [0, 0, 0, 0]
                    break

        for i in range(position + 1, 4):
            values[i] = 0

        hex_components = [format(v, "X") for v in values]
        return f"E{epoch}-{'.'.join(hex_components)}"

    async def _extract_services(
        self,
        node_id: str,
        profile_id: str,
        services: list,
    ) -> list[str]:
        """Extract services from profile and upsert them."""
        service_ids = []
        now = datetime.now(timezone.utc)

        for svc in services:
            service_id = generate_service_id(node_id, svc.runtime, svc.name)
            service_ids.append(service_id)

            # Check existing service for new-discovery / state-change detection
            existing_svc = await self.db.services.find_one(
                {"serviceId": service_id},
                projection={"status": 1},
            )

            service_doc = {
                "serviceId": service_id,
                "runtime": svc.runtime,
                "name": svc.name,
                "displayName": svc.name,
                "status": svc.status,
                "version": svc.version,
                "image": svc.image,
                "nodeId": node_id,
                "profileId": profile_id,
                "exposure": {
                    "ports": svc.ports,
                    "endpoints": svc.endpoints,
                },
                "resources": svc.resources,
                "attachments": svc.attachments,
                "origin": {
                    "nativeId": svc.name,
                    "discoveredBy": "agent",
                    "collectedAt": now,
                },
                "tags": [],
                "firstSeen": now,
                "lastSeen": now,
            }

            await self.db.services.update_one(
                {"serviceId": service_id},
                {
                    "$set": {
                        "status": svc.status,
                        "version": svc.version,
                        "image": svc.image,
                        "profileId": profile_id,
                        "exposure": service_doc["exposure"],
                        "resources": svc.resources,
                        "attachments": svc.attachments,
                        "origin.collectedAt": now,
                        "lastSeen": now,
                    },
                    "$setOnInsert": {
                        "serviceId": service_id,
                        "runtime": svc.runtime,
                        "name": svc.name,
                        "displayName": svc.name,
                        "nodeId": node_id,
                        "origin.nativeId": svc.name,
                        "origin.discoveredBy": "agent",
                        "tags": [],
                        "firstSeen": now,
                    },
                },
                upsert=True,
            )

            # 3. New service discovered (GREEN)
            if existing_svc is None:
                audit_id = await log_audit(
                    action=AuditAction.CREATE,
                    resource_type="service",
                    resource_id=service_id,
                    actor_type="system",
                    actor_id="profile-service",
                    details={
                        "nodeId": node_id,
                        "serviceId": service_id,
                        "serviceName": svc.name,
                        "runtime": svc.runtime,
                        "status": svc.status,
                        "profileId": profile_id,
                    },
                )
                safe_create_task(emit_notification(
                    notification_type=NotificationType.SERVICE_DISCOVERED,
                    source=NotificationSource(
                        component=SourceComponent.HYDRA_API,
                        service="profile-service",
                        node_id=node_id,
                        service_id=service_id,
                    ),
                    title="New service discovered",
                    message=f"Service {svc.name} ({svc.runtime}) discovered on node {node_id}",
                    details={
                        "nodeId": node_id,
                        "serviceId": service_id,
                        "serviceName": svc.name,
                        "runtime": svc.runtime,
                        "status": svc.status,
                    },
                    audit_entry_id=audit_id,
                ))
                if not await self._is_known_service(svc.runtime, svc.name):
                    safe_create_task(emit_notification(
                        notification_type=NotificationType.UNKNOWN_SERVICE_DISCOVERED,
                        source=NotificationSource(
                            component=SourceComponent.HYDRA_API,
                            service="profile-service",
                            node_id=node_id,
                            service_id=service_id,
                        ),
                        title="Unknown service discovered",
                        message=(
                            f"Unknown service {svc.name} ({svc.runtime}) detected "
                            f"on node {node_id}"
                        ),
                        details={
                            "nodeId": node_id,
                            "serviceId": service_id,
                            "serviceName": svc.name,
                            "runtime": svc.runtime,
                            "status": svc.status,
                            "entityId": service_id,
                        },
                        audit_entry_id=audit_id,
                    ))
            # 4. Service state changed (YELLOW)
            elif existing_svc.get("status") != svc.status:
                prev_status = existing_svc.get("status")
                prev_norm = (prev_status or "").lower()
                new_norm = (svc.status or "").lower()

                if new_norm in CRASH_STATUSES and prev_norm not in CRASH_STATUSES:
                    audit_id = await log_audit(
                        action=AuditAction.UPDATE,
                        resource_type="service",
                        resource_id=service_id,
                        actor_type="system",
                        actor_id="profile-service",
                        details={
                            "nodeId": node_id,
                            "serviceId": service_id,
                            "serviceName": svc.name,
                            "previousStatus": prev_status,
                            "newStatus": svc.status,
                            "profileId": profile_id,
                        },
                    )
                    safe_create_task(emit_notification(
                        notification_type=NotificationType.SERVICE_CRASHED,
                        source=NotificationSource(
                            component=SourceComponent.HYDRA_API,
                            service="profile-service",
                            node_id=node_id,
                            service_id=service_id,
                        ),
                        title="Service crashed",
                        message=(
                            f"Service {svc.name} on node {node_id} crashed "
                            f"(status: {svc.status})"
                        ),
                        details={
                            "nodeId": node_id,
                            "serviceId": service_id,
                            "serviceName": svc.name,
                            "previousStatus": prev_status,
                            "newStatus": svc.status,
                        },
                        audit_entry_id=audit_id,
                    ))
                else:
                    audit_id = await log_audit(
                        action=AuditAction.UPDATE,
                        resource_type="service",
                        resource_id=service_id,
                        actor_type="system",
                        actor_id="profile-service",
                        details={
                            "nodeId": node_id,
                            "serviceId": service_id,
                            "serviceName": svc.name,
                            "previousStatus": existing_svc.get("status"),
                            "newStatus": svc.status,
                            "profileId": profile_id,
                        },
                    )
                    safe_create_task(emit_notification(
                        notification_type=NotificationType.SERVICE_STATE_CHANGED,
                        source=NotificationSource(
                            component=SourceComponent.HYDRA_API,
                            service="profile-service",
                            node_id=node_id,
                            service_id=service_id,
                        ),
                        title="Service state changed",
                        message=(
                            f"Service {svc.name} on node {node_id} changed from "
                            f"{existing_svc.get('status')} to {svc.status}"
                        ),
                        details={
                            "nodeId": node_id,
                            "serviceId": service_id,
                            "serviceName": svc.name,
                            "previousStatus": existing_svc.get("status"),
                            "newStatus": svc.status,
                        },
                        audit_entry_id=audit_id,
                    ))

        logger.info(
            "services_extracted",
            node_id=node_id,
            service_count=len(service_ids),
        )

        return service_ids

    async def _process_networks(
        self,
        node_id: str,
        profile_id: str,
        network_profile,
    ) -> list[str]:
        """Extract networks from profile and auto-create/update."""
        from hydra.api.v1.services.networks import NetworksService

        # Snapshot existing network IDs before processing for new-discovery detection
        existing_network_ids: set[str] = set()
        if network_profile and network_profile.interfaces:
            cursor = self.db.networks.find({}, projection={"networkId": 1})
            async for doc in cursor:
                existing_network_ids.add(doc["networkId"])

        networks_service = NetworksService(self.db)
        network_ids = await networks_service.process_profile_networks(
            node_id,
            profile_id,
            network_profile,
        )

        # 5. New networks discovered (GREEN)
        for nid in network_ids:
            if nid not in existing_network_ids:
                audit_id = await log_audit(
                    action=AuditAction.CREATE,
                    resource_type="network",
                    resource_id=nid,
                    actor_type="system",
                    actor_id="profile-service",
                    details={
                        "nodeId": node_id,
                        "networkId": nid,
                        "profileId": profile_id,
                        "discoveredVia": "profile-submission",
                    },
                )
                safe_create_task(emit_notification(
                    notification_type=NotificationType.NETWORK_DISCOVERED,
                    source=NotificationSource(
                        component=SourceComponent.HYDRA_API,
                        service="profile-service",
                        node_id=node_id,
                    ),
                    title="New network discovered",
                    message=f"Network {nid} discovered via node {node_id}",
                    details={
                        "nodeId": node_id,
                        "networkId": nid,
                        "profileId": profile_id,
                    },
                    audit_entry_id=audit_id,
                ))

        return network_ids

    @staticmethod
    def _diff_config_files(previous_profile: dict | None, submission: ProfileSubmission) -> dict | None:
        """Detect config file changes between previous profile and new submission."""
        if not previous_profile:
            return None
        prev_section = previous_profile.get("configs")
        if prev_section is None:
            return None
        prev_files = (prev_section.get("files") or []) if isinstance(prev_section, dict) else []
        new_configs = submission.configs.files if submission.configs else []
        if not new_configs:
            return None

        prev_map = {
            f.get("path"): f
            for f in prev_files
            if isinstance(f, dict) and f.get("path")
        }
        new_map = {
            f.path: f
            for f in new_configs
            if getattr(f, "path", None)
        }

        added = [path for path in new_map.keys() if path not in prev_map]
        removed = [path for path in prev_map.keys() if path not in new_map]
        changed = []
        for path in new_map.keys():
            if path in prev_map:
                if new_map[path].hash != prev_map[path].get("hash"):
                    changed.append(path)

        if not (added or removed or changed):
            return None

        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "counts": {
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
            },
        }

    @staticmethod
    def _normalize_interface(interface: dict) -> dict:
        return {
            "name": interface.get("name"),
            "macAddress": interface.get("macAddress"),
            "ipv4Addresses": sorted(interface.get("ipv4Addresses") or []),
            "ipv6Addresses": sorted(interface.get("ipv6Addresses") or []),
            "netmask": interface.get("netmask"),
            "gateway": interface.get("gateway"),
            "mtu": interface.get("mtu"),
            "state": interface.get("state"),
            "type": interface.get("type"),
            "speedMbps": interface.get("speedMbps"),
        }

    @staticmethod
    def _normalize_service_name(name: str) -> str:
        return name.strip().lower()

    async def _is_known_service(self, runtime: str, name: str) -> bool:
        normalized = self._normalize_service_name(name)
        doc = await self.db.known_services.find_one(
            {"runtime": runtime, "normalizedName": normalized}
        )
        return doc is not None

    @staticmethod
    def _route_key(route: dict) -> tuple:
        return (
            route.get("destination"),
            route.get("gateway"),
            route.get("interface"),
            route.get("metric"),
        )

    def _diff_network_config(self, previous_profile: dict | None, submission: ProfileSubmission) -> dict | None:
        """Detect network config changes between previous profile and new submission."""
        if not previous_profile or not submission.network:
            return None

        prev_network = previous_profile.get("network")
        if not prev_network:
            return None

        prev_interfaces = {
            iface.get("name"): self._normalize_interface(iface)
            for iface in (prev_network.get("interfaces") or [])
            if isinstance(iface, dict) and iface.get("name")
        }
        new_interfaces = {
            iface.name: self._normalize_interface(iface.model_dump(by_alias=True))
            for iface in submission.network.interfaces
            if iface.name
        }

        added_interfaces = [name for name in new_interfaces if name not in prev_interfaces]
        removed_interfaces = [name for name in prev_interfaces if name not in new_interfaces]
        changed_interfaces = [
            name
            for name in new_interfaces
            if name in prev_interfaces and new_interfaces[name] != prev_interfaces[name]
        ]

        prev_dns = set(prev_network.get("dnsServers") or [])
        new_dns = set(submission.network.dns_servers or [])
        dns_added = sorted(list(new_dns - prev_dns))
        dns_removed = sorted(list(prev_dns - new_dns))

        prev_search = set(prev_network.get("dnsSearch") or [])
        new_search = set(submission.network.dns_search or [])
        search_added = sorted(list(new_search - prev_search))
        search_removed = sorted(list(prev_search - new_search))

        prev_hostname = prev_network.get("hostname")
        new_hostname = submission.network.hostname
        prev_domain = prev_network.get("domain")
        new_domain = submission.network.domain
        prev_fqdn = prev_network.get("fqdn")
        new_fqdn = submission.network.fqdn

        hostname_changed = prev_hostname != new_hostname
        domain_changed = prev_domain != new_domain
        fqdn_changed = prev_fqdn != new_fqdn

        prev_gateway = prev_network.get("defaultGateway")
        new_gateway = submission.network.default_gateway
        gateway_changed = prev_gateway != new_gateway

        prev_routes = {
            self._route_key(route): route
            for route in (prev_network.get("routes") or [])
            if isinstance(route, dict)
        }
        new_routes = {
            self._route_key(route.model_dump(by_alias=True)): route.model_dump(by_alias=True)
            for route in submission.network.routes
        }
        added_routes = [new_routes[key] for key in new_routes.keys() if key not in prev_routes]
        removed_routes = [prev_routes[key] for key in prev_routes.keys() if key not in new_routes]

        if not (
            added_interfaces
            or removed_interfaces
            or changed_interfaces
            or dns_added
            or dns_removed
            or search_added
            or search_removed
            or hostname_changed
            or domain_changed
            or fqdn_changed
            or gateway_changed
            or added_routes
            or removed_routes
        ):
            return None

        return {
            "interfacesAdded": added_interfaces,
            "interfacesRemoved": removed_interfaces,
            "interfacesChanged": changed_interfaces,
            "dnsServersAdded": dns_added,
            "dnsServersRemoved": dns_removed,
            "dnsSearchAdded": search_added,
            "dnsSearchRemoved": search_removed,
            "hostname": {"from": prev_hostname, "to": new_hostname} if hostname_changed else None,
            "domain": {"from": prev_domain, "to": new_domain} if domain_changed else None,
            "fqdn": {"from": prev_fqdn, "to": new_fqdn} if fqdn_changed else None,
            "defaultGateway": {
                "from": prev_gateway,
                "to": new_gateway,
            }
            if gateway_changed
            else None,
            "routesAdded": added_routes,
            "routesRemoved": removed_routes,
            "counts": {
                "interfacesChanged": len(added_interfaces)
                + len(removed_interfaces)
                + len(changed_interfaces),
                "routesChanged": len(added_routes) + len(removed_routes),
            },
        }

    def _format_profile(self, doc: dict) -> dict:
        """Format a profile document for API response."""
        return {
            "profileId": doc["profileId"],
            "nodeId": doc["nodeId"],
            "version": doc["version"],
            "collectedAt": doc["collectedAt"],
            "submittedAt": doc["submittedAt"],
            "agentVersion": doc["agentVersion"],
            "collectionLevel": doc["collectionLevel"],
            "serviceIds": doc.get("serviceIds", []),
            "hardware": doc.get("hardware"),
            "network": doc.get("network"),
            "storage": doc.get("storage"),
            "software": doc.get("software"),
            "users": doc.get("users"),
            "configs": doc.get("configs"),
            "metadata": doc.get("metadata", {}),
        }

    def _format_profile_summary(self, doc: dict) -> dict:
        """Format a profile document for list response."""
        return {
            "profileId": doc["profileId"],
            "nodeId": doc["nodeId"],
            "version": doc["version"],
            "collectedAt": doc["collectedAt"],
            "submittedAt": doc["submittedAt"],
            "collectionLevel": doc["collectionLevel"],
            "serviceCount": len(doc.get("serviceIds", [])),
        }
