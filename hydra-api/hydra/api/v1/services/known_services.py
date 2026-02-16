"""Known services registry for filtering unknown service notifications."""

import re
import secrets
from datetime import UTC, datetime

import structlog
from pymongo import DESCENDING

from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.services import KnownServiceCreateRequest
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class KnownServicesService:
    """Service for managing known service registry entries."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    @staticmethod
    def _normalize_name(name: str) -> str:
        return name.strip().lower()

    @staticmethod
    def _format_known_service(doc: dict) -> dict:
        return {
            "knownServiceId": doc["knownServiceId"],
            "runtime": doc["runtime"],
            "name": doc["name"],
            "description": doc.get("description"),
            "tags": doc.get("tags", []),
            "createdAt": doc.get("createdAt"),
            "updatedAt": doc.get("updatedAt"),
            "createdBy": doc.get("createdBy"),
        }

    async def list_known_services(
        self,
        runtime: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List known services with optional filtering."""
        query: dict = {}
        if runtime:
            query["runtime"] = runtime
        if search:
            escaped = re.escape(search)
            query["$or"] = [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"normalizedName": {"$regex": escaped, "$options": "i"}},
            ]

        total = await self.db.known_services.count_documents(query)
        cursor = (
            self.db.known_services.find(query)
            .sort("updatedAt", DESCENDING)
            .skip(offset)
            .limit(limit)
        )

        results = []
        async for doc in cursor:
            results.append(self._format_known_service(doc))

        logger.info(
            "known_services_listed",
            total=total,
            returned=len(results),
            runtime=runtime,
        )
        return results, total

    async def create_known_service(
        self,
        request: KnownServiceCreateRequest,
        created_by: str | None = None,
    ) -> dict:
        """Create a known service entry."""
        normalized = self._normalize_name(request.name)
        existing = await self.db.known_services.find_one(
            {"runtime": request.runtime.value, "normalizedName": normalized}
        )
        if existing:
            raise ValidationError("Known service already exists for this runtime and name")

        now = datetime.now(UTC)
        known_service_id = f"ksvc_{secrets.token_urlsafe(6)}"
        doc = {
            "knownServiceId": known_service_id,
            "runtime": request.runtime.value,
            "name": request.name,
            "normalizedName": normalized,
            "description": request.description,
            "tags": request.tags,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": created_by,
        }

        await self.db.known_services.insert_one(doc)
        logger.info(
            "known_service_created",
            known_service_id=known_service_id,
            runtime=request.runtime.value,
            name=request.name,
        )

        return self._format_known_service(doc)

    async def delete_known_service(self, known_service_id: str) -> dict:
        """Delete a known service entry."""
        existing = await self.db.known_services.find_one(
            {"knownServiceId": known_service_id}
        )
        if not existing:
            raise NotFoundError("known_service", known_service_id)

        await self.db.known_services.delete_one({"knownServiceId": known_service_id})
        logger.info("known_service_deleted", known_service_id=known_service_id)
        return self._format_known_service(existing)
