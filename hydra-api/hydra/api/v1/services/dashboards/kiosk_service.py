"""Kiosk token service — bcrypt-hashed, TTL-bounded, revocable.

Each kiosk token grants read-only (sanitized) access to a specific board
without requiring a user session. Tokens are stored as bcrypt hashes so
the raw secret cannot be recovered even with database access.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

from hydra.api.v1.models.dashboards import (
    KioskTokenCreated,
    KioskTokenDocument,
    KioskTokenSummary,
)

logger = structlog.get_logger(__name__)

COLLECTION = "kiosk_tokens"


# ── Token crypto helpers ────────────────────────────────────────────


def _generate_raw_token() -> str:
    """Generate a 32-byte URL-safe random token (~256 bits of entropy)."""
    return secrets.token_urlsafe(32)


def _hash_token(raw: str) -> str:
    """Hash a raw token with bcrypt (work factor 12 for security/latency balance)."""
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_token(raw: str, hashed: str) -> bool:
    """Verify a raw token against its bcrypt hash. Returns False on malformed hash."""
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Corrupted/malformed hash — treat as invalid token
        return False


# ── Service ────────────────────────────────────────────────────────


class KioskService:
    """Manage kiosk tokens for unauthenticated board access."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        self._db = db

    async def create(
        self,
        board_id: str,
        label: str,
        ttl_hours: int | None,
        created_by: str,
    ) -> KioskTokenCreated:
        """Create a new kiosk token for the given board.

        Args:
            board_id: The board this token grants access to.
            label: Human-readable descriptor.
            ttl_hours: Lifetime in hours. None means the token never expires.
            created_by: User ID of the token creator.

        Returns:
            KioskTokenCreated containing the raw token (shown exactly once).
        """
        token_id = f"kt_{secrets.token_hex(8)}"
        raw = _generate_raw_token()
        hashed = _hash_token(raw)
        now = datetime.now(UTC)
        expires_at = None if ttl_hours is None else now + timedelta(hours=ttl_hours)

        doc = {
            "tokenId": token_id,
            "boardId": board_id,
            "tokenHash": hashed,
            "label": label,
            "createdBy": created_by,
            "createdAt": now,
            "expiresAt": expires_at,
            "revokedAt": None,
            "lastUsedAt": None,
        }

        await self._db[COLLECTION].insert_one(doc)

        logger.info(
            "kiosk_token_created",
            token_id=token_id,
            board_id=board_id,
            created_by=created_by,
            ttl_hours=ttl_hours,
        )

        return KioskTokenCreated(
            token_id=token_id,
            board_id=board_id,
            label=label,
            created_by=created_by,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
            last_used_at=None,
            token=raw,
        )

    async def list_for_board(self, board_id: str) -> list[KioskTokenSummary]:
        """Return all kiosk tokens for a board (newest first), excluding the hash."""
        cursor = self._db[COLLECTION].find({"boardId": board_id}).sort("createdAt", -1)
        results: list[KioskTokenSummary] = []
        async for doc in cursor:
            results.append(
                KioskTokenSummary(
                    token_id=doc["tokenId"],
                    board_id=doc["boardId"],
                    label=doc["label"],
                    created_by=doc["createdBy"],
                    created_at=doc["createdAt"],
                    expires_at=doc.get("expiresAt"),
                    revoked_at=doc.get("revokedAt"),
                    last_used_at=doc.get("lastUsedAt"),
                )
            )
        return results

    async def revoke(self, board_id: str, token_id: str) -> bool:
        """Revoke a kiosk token by setting its revokedAt timestamp.

        Returns:
            True if the token was found and revoked; False if not found or already revoked.
        """
        now = datetime.now(UTC)
        result = await self._db[COLLECTION].update_one(
            {"boardId": board_id, "tokenId": token_id, "revokedAt": None},
            {"$set": {"revokedAt": now}},
        )
        if result.modified_count == 1:
            logger.info("kiosk_token_revoked", token_id=token_id, board_id=board_id)
            return True
        return False

    async def validate(self, board_id: str, raw_token: str) -> KioskTokenDocument | None:
        """Validate a raw token for a board and update lastUsedAt on success.

        Scans all active (non-revoked, non-expired) tokens for the board and
        verifies each one with bcrypt. Updates lastUsedAt on the matched token.

        Performance note: This iterates all active tokens and runs bcrypt verification per token.
        At work factor 12, this is ~250ms per bcrypt.checkpw. Acceptable for the expected cardinality
        (≤10 active tokens per board). If token count per board grows substantially, consider a
        deterministic token-ID prefix embedded in the URL (e.g., ``?token=kt_abc.SECRET``) to narrow
        the cursor to a single document before bcrypt.

        Args:
            board_id: Board the token should grant access to.
            raw_token: The bearer token to validate.

        Returns:
            KioskTokenDocument on success, or None if no valid token matched.
        """
        now = datetime.now(UTC)
        # Fetch all active, non-expired tokens for this board.
        # We cannot pre-filter by token value because tokens are stored hashed.
        cursor = self._db[COLLECTION].find(
            {
                "boardId": board_id,
                "revokedAt": None,
                "$or": [
                    {"expiresAt": None},
                    {"expiresAt": {"$gt": now}},
                ],
            }
        )
        async for doc in cursor:
            if _verify_token(raw_token, doc["tokenHash"]):
                # Update lastUsedAt without blocking the response
                await self._db[COLLECTION].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"lastUsedAt": now}},
                )
                logger.info(
                    "kiosk_token_validated",
                    token_id=doc["tokenId"],
                    board_id=board_id,
                )
                return KioskTokenDocument(
                    token_id=doc["tokenId"],
                    board_id=doc["boardId"],
                    token_hash=doc["tokenHash"],
                    label=doc["label"],
                    created_by=doc["createdBy"],
                    created_at=doc["createdAt"],
                    expires_at=doc.get("expiresAt"),
                    revoked_at=doc.get("revokedAt"),
                    last_used_at=now,
                )
        return None
