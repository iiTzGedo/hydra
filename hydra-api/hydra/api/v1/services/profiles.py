"""Profile management service with versioning and diff calculation."""

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from pymongo import DESCENDING

from hydra.api.v1.core.exceptions import NodeNotFoundError, ProfileNotFoundError, ValidationError
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
                hashes.append(self._hash_dict(hw.memory.model_dump(by_alias=True)))
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

        networks_service = NetworksService(self.db)
        return await networks_service.process_profile_networks(
            node_id,
            profile_id,
            network_profile,
        )

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
