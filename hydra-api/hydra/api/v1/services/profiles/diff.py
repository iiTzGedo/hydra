"""Profile diff and config diff logic."""

from typing import Any

from pymongo import DESCENDING

from hydra.api.v1.core.exceptions import NodeNotFoundError, ProfileNotFoundError, ValidationError
from hydra.api.v1.models.profiles import ProfileSubmission
from hydra.api.v1.services.profiles.versioning import SECTION_WEIGHTS
from hydra.db.mongodb import MongoDB


async def diff_profiles(
    db: MongoDB,
    node_id: str,
    from_version: str | None = None,
    to_version: str | None = None,
) -> dict:
    """Compare two profiles for a node.

    If versions are not specified, compares the latest two profiles.

    Args:
        db: MongoDB instance.
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
    node = await db.nodes.find_one({"nodeId": node_id})
    if not node:
        raise NodeNotFoundError(node_id)

    if from_version and to_version:
        from_profile = await db.profiles.find_one(
            {"nodeId": node_id, "version": from_version}
        )
        to_profile = await db.profiles.find_one(
            {"nodeId": node_id, "version": to_version}
        )
    else:
        cursor = (
            db.profiles.find({"nodeId": node_id})
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

    from_meta = await db.profile_meta.find_one(
        {"profileId": from_profile["profileId"]}
    )
    to_meta = await db.profile_meta.find_one(
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


def diff_config_files(
    previous_profile: dict | None, submission: ProfileSubmission
) -> dict | None:
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
