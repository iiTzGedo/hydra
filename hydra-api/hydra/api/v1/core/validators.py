"""Shared validation patterns and utilities.

Centralized validation patterns for consistent validation across API models.
These patterns are aligned with the agent-side validation for consistency.
"""

import re
from typing import Callable

import structlog

logger = structlog.get_logger(__name__)

NODE_ID_PATTERN_NEW = r"^[a-z]+([._-][a-z0-9]+){0,2}$"
NODE_ID_PATTERN_LEGACY = r"^[a-z0-9][a-z0-9.-]{2,63}$"

_NODE_ID_NEW_RE = re.compile(NODE_ID_PATTERN_NEW)
_NODE_ID_LEGACY_RE = re.compile(NODE_ID_PATTERN_LEGACY)

TAG_PATTERN = r"^[a-z]+[_:]?[a-z]+$"
_TAG_RE = re.compile(TAG_PATTERN)

NETWORK_ID_PATTERN = r"^[a-z]{1,}[0-9a-z]*([-]?net)$"
_NETWORK_ID_RE = re.compile(NETWORK_ID_PATTERN)

IPV4_PATTERN = r"^(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])(\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}$"
CIDR_PATTERN = r"^(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])(\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}\/(3[0-2]|[12]?[0-9])$"
_IPV4_RE = re.compile(IPV4_PATTERN)
_CIDR_RE = re.compile(CIDR_PATTERN)

PROFILE_VERSION_PATTERN = r"^E([0-9]|[1-9][0-9]+)-([0-9A-F]\.){3}[0-9A-F]$"
_PROFILE_VERSION_RE = re.compile(PROFILE_VERSION_PATTERN)

SERVICE_ID_PATTERN = r"^svc-[a-z0-9-_]+-[a-zA-Z0-9]{4}$"
_SERVICE_ID_RE = re.compile(SERVICE_ID_PATTERN)

AGENT_USERNAME_PATTERN = r"^agent-[0-9A-Z]{8}$"
_AGENT_USERNAME_RE = re.compile(AGENT_USERNAME_PATTERN)


def validate_node_id(value: str, strict: bool = True) -> tuple[bool, str | None]:
    """Validate a node ID.

    Args:
        value: The node ID to validate.
        strict: If True, only accept new pattern. If False, accept legacy with warning.

    Returns:
        Tuple of (is_valid, warning_message). warning_message is set if using
        deprecated legacy format, None otherwise.
    """
    if not value:
        return False, None

    if _NODE_ID_NEW_RE.match(value):
        return True, None

    if not strict and _NODE_ID_LEGACY_RE.match(value):
        warning = (
            f"Node ID '{value}' uses deprecated format. "
            f"New node IDs should match pattern: {NODE_ID_PATTERN_NEW}"
        )
        logger.warning("deprecated_node_id_format", node_id=value, pattern=NODE_ID_PATTERN_NEW)
        return True, warning

    return False, None


def validate_node_id_strict(value: str) -> bool:
    """Validate a node ID using only the new strict pattern.

    Args:
        value: The node ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    return bool(_NODE_ID_NEW_RE.match(value)) if value else False


def validate_node_id_lenient(value: str) -> bool:
    """Validate a node ID using either pattern (for existing data).

    Args:
        value: The node ID to validate.

    Returns:
        True if valid under either pattern, False otherwise.
    """
    if not value:
        return False
    return bool(_NODE_ID_NEW_RE.match(value) or _NODE_ID_LEGACY_RE.match(value))


def validate_tag(value: str) -> bool:
    """Validate a single tag value.

    Args:
        value: The tag to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not value or len(value) > 64:
        return False
    return bool(_TAG_RE.match(value))


def validate_tags(values: list[str]) -> tuple[bool, list[str]]:
    """Validate a list of tags.

    Args:
        values: List of tags to validate.

    Returns:
        Tuple of (all_valid, invalid_tags).
    """
    if not values:
        return True, []

    invalid = []
    for tag in values:
        if not validate_tag(tag):
            invalid.append(tag)

    return len(invalid) == 0, invalid


def validate_network_id(value: str) -> bool:
    """Validate a network ID.

    Args:
        value: The network ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not value:
        return False
    return bool(_NETWORK_ID_RE.match(value))


def validate_ipv4(value: str) -> bool:
    """Validate an IPv4 address.

    Args:
        value: The IPv4 address string.

    Returns:
        True if valid, False otherwise.
    """
    if not value:
        return False
    return bool(_IPV4_RE.match(value))


def validate_cidr(value: str) -> bool:
    """Validate a CIDR notation (IPv4).

    Args:
        value: The CIDR string (e.g., "192.168.1.0/24").

    Returns:
        True if valid, False otherwise.
    """
    if not value:
        return False
    return bool(_CIDR_RE.match(value))


def validate_profile_version(value: str) -> bool:
    """Validate a profile version string.

    Args:
        value: The profile version (e.g., "E0-0.0.1.4").

    Returns:
        True if valid, False otherwise.
    """
    if not value:
        return False
    return bool(_PROFILE_VERSION_RE.match(value))


def validate_service_id(value: str) -> bool:
    """Validate a service ID.

    Args:
        value: The service ID (e.g., "svc-nginx-a1b2").

    Returns:
        True if valid, False otherwise.
    """
    if not value:
        return False
    return bool(_SERVICE_ID_RE.match(value))


def validate_agent_username(value: str) -> bool:
    """Validate an agent username.

    Args:
        value: The agent username (e.g., "agent-ABC12345").

    Returns:
        True if valid, False otherwise.
    """
    if not value:
        return False
    return bool(_AGENT_USERNAME_RE.match(value))


def node_id_validator(strict: bool = True) -> Callable:
    """Create a Pydantic field validator for node IDs.

    Args:
        strict: If True, only accept new pattern. If False, accept legacy with warning.

    Returns:
        A validator function for use with Pydantic.
    """
    def validator(v: str) -> str:
        if not v:
            raise ValueError("Node ID is required")

        is_valid, warning = validate_node_id(v, strict=strict)
        if not is_valid:
            if strict:
                raise ValueError(
                    f"Invalid node ID format. Must match pattern: {NODE_ID_PATTERN_NEW}"
                )
            else:
                raise ValueError(
                    f"Invalid node ID format. Must match pattern: {NODE_ID_PATTERN_LEGACY}"
                )

        if warning:
            logger.warning("node_id_validation_warning", warning=warning)

        return v

    return validator


def tags_validator() -> Callable:
    """Create a Pydantic field validator for tags.

    Returns:
        A validator function for use with Pydantic.
    """
    def validator(v: list[str] | None) -> list[str] | None:
        if v is None:
            return v

        all_valid, invalid = validate_tags(v)
        if not all_valid:
            raise ValueError(
                f"Invalid tags: {invalid}. Tags must match pattern: {TAG_PATTERN}"
            )
        return v

    return validator


def network_id_validator() -> Callable:
    """Create a Pydantic field validator for network IDs.

    Returns:
        A validator function for use with Pydantic.
    """
    def validator(v: str) -> str:
        if not validate_network_id(v):
            raise ValueError(
                f"Invalid network ID format. Must match pattern: {NETWORK_ID_PATTERN}"
            )
        return v

    return validator


def profile_version_validator() -> Callable:
    """Create a Pydantic field validator for profile versions.

    Returns:
        A validator function for use with Pydantic.
    """
    def validator(v: str) -> str:
        if not validate_profile_version(v):
            raise ValueError(
                f"Invalid profile version format. Must match pattern: {PROFILE_VERSION_PATTERN}"
            )
        return v

    return validator


VALIDATION_PATTERNS = {
    "node_id_new": NODE_ID_PATTERN_NEW,
    "node_id_legacy": NODE_ID_PATTERN_LEGACY,
    "tag": TAG_PATTERN,
    "network_id": NETWORK_ID_PATTERN,
    "ipv4": IPV4_PATTERN,
    "cidr": CIDR_PATTERN,
    "profile_version": PROFILE_VERSION_PATTERN,
    "service_id": SERVICE_ID_PATTERN,
    "agent_username": AGENT_USERNAME_PATTERN,
}
