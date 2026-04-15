"""Discovery exclusion management.

Provides CRUD for exclusion rules (by MAC, IP, or IP range) and an
``is_excluded`` check consumed by the scan upsert pipeline.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from ipaddress import IPv4Address, ip_address
from typing import Any

import structlog
from pymongo import DESCENDING

from hydra.api.v1.core.exceptions import NotFoundError
from hydra.api.v1.models.discovery.requests import (
    CreateExclusionRequest,
    ExclusionListParams,
)
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class ExclusionNotFoundError(NotFoundError):
    """Exclusion not found."""

    def __init__(self, exclusion_id: str) -> None:
        super().__init__("exclusion", exclusion_id)


class ExclusionService:
    """CRUD and enforcement for discovery exclusion rules."""

    def __init__(self, mongodb: MongoDB) -> None:
        self.db = mongodb
        self.exclusions = mongodb.db["discovery_exclusions"]

    async def create_exclusion(
        self,
        request: CreateExclusionRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Create a new exclusion rule.

        Args:
            request: Exclusion parameters.
            user_id: ID of the creating user.

        Returns:
            The created exclusion document.
        """
        now = datetime.now(UTC)
        exclusion_id = f"excl_{secrets.token_hex(8)}"

        doc: dict[str, Any] = {
            "exclusionId": exclusion_id,
            "type": request.type,
            "value": self._normalize_value(request.type, request.value),
            "label": request.label,
            "reason": request.reason,
            "createdBy": user_id,
            "createdAt": now,
        }

        await self.exclusions.insert_one(doc)
        logger.info(
            "discovery.exclusion_created",
            exclusion_id=exclusion_id,
            type=request.type,
            value=request.value,
        )
        return doc

    async def list_exclusions(
        self,
        params: ExclusionListParams,
    ) -> tuple[list[dict[str, Any]], int]:
        """List exclusion rules with pagination.

        Args:
            params: Pagination parameters.

        Returns:
            Tuple of (exclusions, total_count).
        """
        total = await self.exclusions.count_documents({})
        cursor = (
            self.exclusions.find({})
            .sort("createdAt", DESCENDING)
            .skip(params.offset)
            .limit(params.limit)
        )
        exclusions = await cursor.to_list(length=params.limit)
        return exclusions, total

    async def delete_exclusion(self, exclusion_id: str) -> None:
        """Delete an exclusion rule.

        Args:
            exclusion_id: The exclusion to delete.

        Raises:
            ExclusionNotFoundError: If the exclusion does not exist.
        """
        result = await self.exclusions.delete_one({"exclusionId": exclusion_id})
        if result.deleted_count == 0:
            raise ExclusionNotFoundError(exclusion_id)
        logger.info("discovery.exclusion_deleted", exclusion_id=exclusion_id)

    async def is_excluded(
        self,
        mac: str | None,
        ip: str | None,
    ) -> bool:
        """Check whether a device should be excluded from discovery results.

        Args:
            mac: Device MAC address (any format).
            ip: Device IP address.

        Returns:
            True if the device matches any exclusion rule.
        """
        exclusions = await self.exclusions.find({}).to_list(length=500)
        if not exclusions:
            return False

        normalized_mac = mac.lower().replace("-", ":") if mac else None

        for rule in exclusions:
            rule_type = rule["type"]
            rule_value = rule["value"]

            if rule_type == "mac" and normalized_mac:
                if normalized_mac == rule_value.lower().replace("-", ":"):
                    return True

            elif rule_type == "ip" and ip:
                if ip == rule_value:
                    return True

            elif rule_type == "ip-range" and ip and self._ip_in_range(ip, rule_value):
                return True

        return False

    @staticmethod
    def _ip_in_range(ip: str, range_str: str) -> bool:
        """Check if an IP address falls within a range.

        Range format: ``start_ip-end_ip`` (e.g. ``192.168.0.200-192.168.0.254``).
        """
        parts = range_str.split("-", 1)
        if len(parts) != 2:
            return False
        try:
            addr = ip_address(ip)
            start = ip_address(parts[0].strip())
            end = ip_address(parts[1].strip())
        except ValueError:
            return False

        if (
            not isinstance(addr, IPv4Address)
            or not isinstance(start, IPv4Address)
            or not isinstance(end, IPv4Address)
        ):
            return False

        return start <= addr <= end

    @staticmethod
    def _normalize_value(exclusion_type: str, value: str) -> str:
        """Normalize the exclusion value for consistent storage."""
        if exclusion_type == "mac":
            return value.lower().replace("-", ":")
        return value.strip()
