"""Profile versioning, fingerprinting, and hashing logic."""

import hashlib
import json
from collections.abc import Iterator, Mapping
from typing import Any

from hydra.api.v1.models.profiles import ProfileSubmission
from hydra.core.config import get_settings as _get_settings


class _SectionWeightsProxy(Mapping[str, float]):
    """Lazy proxy for profile section weights.

    This avoids instantiating the global settings object during module import.
    """

    def _weights(self) -> dict[str, float]:
        return _get_settings().profile_section_weights

    def __getitem__(self, key: str) -> float:
        return self._weights()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._weights())

    def __len__(self) -> int:
        return len(self._weights())


SECTION_WEIGHTS: Mapping[str, float] = _SectionWeightsProxy()


def compute_section_fingerprints(submission: ProfileSubmission) -> dict[str, list[str]]:
    """Compute hash fingerprints for each section of the profile."""
    fingerprints: dict[str, list[str]] = {}

    if submission.hardware:
        hashes = []
        hw = submission.hardware
        if hw.cpu:
            hashes.append(_hash_dict(hw.cpu.model_dump(by_alias=True)))
        if hw.memory:
            mem_data = hw.memory.model_dump(by_alias=True)
            mem_data.pop("usedBytes", None)
            hashes.append(_hash_dict(mem_data))
        for gpu in hw.gpus:
            hashes.append(_hash_dict(gpu.model_dump(by_alias=True)))
        if hashes:
            fingerprints["hardware"] = hashes

    if submission.network:
        hashes = []
        for iface in submission.network.interfaces:
            hashes.append(_hash_dict(iface.model_dump(by_alias=True)))
        for route in submission.network.routes:
            hashes.append(_hash_dict(route.model_dump(by_alias=True)))
        if hashes:
            fingerprints["network"] = hashes

    if submission.storage:
        hashes = []
        for device in submission.storage.block_devices:
            hashes.append(_hash_dict(device.model_dump(by_alias=True)))
        for fs in submission.storage.filesystems:
            hashes.append(_hash_dict(fs.model_dump(by_alias=True)))
        if hashes:
            fingerprints["storage"] = hashes

    if submission.software:
        hashes = []
        if submission.software.os:
            hashes.append(_hash_dict(submission.software.os.model_dump(by_alias=True)))
        for pkg in submission.software.packages:
            hashes.append(_hash_dict(pkg.model_dump(by_alias=True)))
        if hashes:
            fingerprints["software"] = hashes

    if submission.configs:
        hashes = []
        for config in submission.configs.files:
            hashes.append(config.hash)
        if hashes:
            fingerprints["configs"] = hashes

    return fingerprints


def compute_profile_hash(fingerprints: dict[str, list[str]]) -> str:
    """Compute overall profile hash from section fingerprints."""
    all_hashes = []
    for section in sorted(fingerprints.keys()):
        all_hashes.extend(sorted(fingerprints[section]))
    combined = ":".join(all_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()


def _hash_dict(data: dict[str, Any]) -> str:
    """Hash a dictionary to a fingerprint."""
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def calculate_version(
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

    return _increment_version(previous_version, position)


def _increment_version(version: str, position: int) -> str:
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
