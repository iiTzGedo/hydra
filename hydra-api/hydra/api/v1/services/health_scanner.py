"""Background health scanner — periodic infrastructure health checks.

Runs as a background asyncio task during the API lifespan. Checks:
- Stale node profiles (no profile update within expected interval)
- Offline node detection (nodes stale for 3x the expected interval)
- Storage thresholds (>70% warning, >85% critical)
- Memory thresholds (>90% critical)
- Node health degradation (multiple concurrent warnings)
- Expiring registration tokens and API keys
- Service instability (frequent state changes)
"""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from hydra.api.v1.models.notifications import (
    DEDUP_WINDOW,
    NotificationActor,
    NotificationSource,
    NotificationStatus,
    NotificationType,
    build_group_key,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import NotificationService
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient

logger = structlog.get_logger(__name__)

# Scanner configuration
SCAN_INTERVAL_SECONDS = 60
DEFAULT_SCHEDULE_INTERVAL = timedelta(hours=24)
STALE_PROFILE_MULTIPLIER = 2
OFFLINE_PROFILE_MULTIPLIER = 3
STORAGE_WARNING_PERCENT = 70
STORAGE_CRITICAL_PERCENT = 85
MEMORY_CRITICAL_PERCENT = 90
TOKEN_EXPIRY_WINDOW = timedelta(hours=48)
API_KEY_EXPIRY_WINDOW = timedelta(hours=48)
SERVICE_INSTABILITY_LOOKBACK = timedelta(hours=24)
SERVICE_INSTABILITY_THRESHOLD = 3  # minimum state changes to flag
NODE_HEALTH_DEGRADED_THRESHOLD = 2  # minimum concurrent warnings
PENDING_APPROVAL_THRESHOLD = timedelta(hours=48)
HEALTH_CHECK_PASS_COOLDOWN = timedelta(hours=24)
AGENT_OUTDATED_THRESHOLD = 2  # versions behind latest


class HealthScanner:
    """Periodically scans infrastructure health and emits notifications."""

    def __init__(self, mongodb: MongoDB, redis: RedisClient):
        self.db = mongodb
        self.redis = redis
        self.notif = NotificationService(mongodb, redis)
        self._source = NotificationSource(component="hydra-api", service="health-scanner")

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        """Ensure datetime is timezone-aware in UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    async def _get_schedule_intervals(self, node_ids: list[str]) -> dict[str, timedelta]:
        """Fetch schedule intervals from latest profiles for nodes."""
        if not node_ids:
            return {}
        pipeline = [
            {"$match": {"nodeId": {"$in": node_ids}}},
            {"$sort": {"submittedAt": -1}},
            {"$group": {"_id": "$nodeId", "latestProfile": {"$first": "$$ROOT"}}},
            {"$project": {"nodeId": "$_id", "metadata": "$latestProfile.metadata"}},
        ]
        results = await self.db.profiles.aggregate(pipeline).to_list(length=500)
        intervals: dict[str, timedelta] = {}
        for doc in results:
            meta = doc.get("metadata") or {}
            seconds = meta.get("scheduleIntervalSeconds")
            try:
                if seconds and int(seconds) > 0:
                    intervals[doc["nodeId"]] = timedelta(seconds=int(seconds))
            except Exception:
                continue
        return intervals

    async def _has_recent_dedup_candidate(self, group_key: str) -> bool:
        """Check if a notification exists that would be deduplicated right now."""
        window_start = datetime.now(UTC) - DEDUP_WINDOW
        existing = await self.db.notifications.find_one(
            {
                "groupKey": group_key,
                "status": NotificationStatus.ACTIVE.value,
                "$or": [
                    {"event.lastSeenAt": {"$gte": window_start}},
                    {"createdAt": {"$gte": window_start}},
                ],
            },
            {"notificationId": 1},
        )
        return existing is not None

    async def _has_active_notification(self, notification_type: NotificationType, group_key: str) -> bool:
        """Check if any active notification exists for this type/group key."""
        existing = await self.db.notifications.find_one(
            {
                "type": notification_type.value,
                "groupKey": group_key,
                "status": NotificationStatus.ACTIVE.value,
            },
            {"notificationId": 1},
        )
        return existing is not None

    async def _emit_with_audit(
        self,
        *,
        notification_type: NotificationType,
        source: NotificationSource,
        title: str,
        message: str,
        details: dict,
        resource_type: str,
        resource_id: str,
        actor: NotificationActor | None = None,
        action: AuditAction = AuditAction.UPDATE,
        group_key: str | None = None,
        target_user_id: str | None = None,
    ) -> None:
        # Only suppress audit when this event would deduplicate within DEDUP_WINDOW.
        resolved_key = group_key or build_group_key(
            notification_type, source, details
        )
        dedup_candidate_exists = await self._has_recent_dedup_candidate(resolved_key)

        audit_id = None
        if not dedup_candidate_exists:
            audit_id = await log_audit(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                actor_type="system",
                actor_id="health_scanner",
                success=True,
                details=details,
            )

        await self.notif.emit(
            notification_type=notification_type,
            source=source,
            title=title,
            message=message,
            details=details,
            actor=actor or NotificationActor(type="system", id="health_scanner"),
            audit_entry_id=audit_id,
            group_key=group_key,
            target_user_id=target_user_id,
        )

    async def run(self) -> None:
        """Run the scanner loop indefinitely."""
        logger.info("health_scanner_started", interval=SCAN_INTERVAL_SECONDS)
        while True:
            try:
                await self._scan()
            except asyncio.CancelledError:
                logger.info("health_scanner_stopped")
                raise
            except Exception:
                logger.exception("health_scanner_error")
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)

    async def _scan(self) -> None:
        """Execute a single scan cycle.

        Node-level checks (stale, offline, storage, memory) run first so we can
        accumulate per-node warning counts.  After those complete we evaluate
        NODE_HEALTH_DEGRADED.  Independent checks (tokens, API keys, service
        instability) run in parallel with the node checks.
        """
        # Track per-node warnings for health-degraded evaluation.
        # key = nodeId, value = list of warning descriptions
        node_warnings: dict[str, list[str]] = {}

        active_nodes = await self.db.nodes.find(
            {"status": "active"},
            {"nodeId": 1, "displayName": 1, "lastProfileAt": 1},
        ).to_list(length=500)
        node_ids = [node["nodeId"] for node in active_nodes]
        schedule_intervals = await self._get_schedule_intervals(node_ids)

        # Phase 1 — run all individual checks in parallel
        checks = [
            ("stale_nodes", self._check_stale_nodes(node_warnings, active_nodes, schedule_intervals)),
            ("offline_nodes", self._check_offline_nodes(node_warnings, active_nodes, schedule_intervals)),
            ("storage_thresholds", self._check_storage_thresholds(node_warnings, active_nodes)),
            ("memory_thresholds", self._check_memory_thresholds(node_warnings, active_nodes)),
            ("expiring_tokens", self._check_expiring_tokens()),
            ("expiring_api_keys", self._check_expiring_api_keys()),
            ("service_instability", self._check_service_instability()),
            ("pending_users", self._check_pending_users()),
            ("agent_version_outdated", self._check_agent_version_outdated(node_ids)),
        ]

        results = await asyncio.gather(
            *(coro for _, coro in checks),
            return_exceptions=True,
        )
        for (name, _), result in zip(checks, results, strict=False):
            if isinstance(result, Exception):
                logger.error(
                    "health_scanner_check_failed",
                    check=name,
                    error=str(result),
                    exc_info=result,
                )

        # Phase 2 — evaluate health degradation from accumulated warnings
        await self._check_node_health_degraded(node_warnings)
        await self._check_health_check_passed(active_nodes, node_warnings, schedule_intervals)

    # ------------------------------------------------------------------
    # Stale node detection
    # ------------------------------------------------------------------

    async def _check_stale_nodes(
        self,
        node_warnings: dict[str, list[str]],
        active_nodes: list[dict],
        schedule_intervals: dict[str, timedelta],
    ) -> None:
        """Find active nodes whose last profile is older than the threshold.

        Only flags nodes that are stale but NOT offline (offline uses a
        separate, longer threshold via ``_check_offline_nodes``).
        """
        now = datetime.now(UTC)

        for node in active_nodes:
            node_id = node["nodeId"]
            last_seen = node.get("lastProfileAt")
            if not isinstance(last_seen, datetime):
                continue
            last_seen = self._coerce_utc(last_seen)

            expected = schedule_intervals.get(node_id, DEFAULT_SCHEDULE_INTERVAL)
            stale_cutoff = now - (expected * STALE_PROFILE_MULTIPLIER)
            offline_cutoff = now - (expected * OFFLINE_PROFILE_MULTIPLIER)

            if not (last_seen < stale_cutoff and last_seen >= offline_cutoff):
                continue

            display = node.get("displayName") or node_id
            delta = now - last_seen
            mins = int(delta.total_seconds() / 60)

            node_warnings.setdefault(node_id, []).append("stale_profile")

            await self._emit_with_audit(
                notification_type=NotificationType.NODE_PROFILE_STALE,
                source=NotificationSource(
                    component="hydra-api",
                    service="health-scanner",
                    node_id=node_id,
                ),
                title=f"Stale profile: {display}",
                message=f"Node {display} has not submitted a profile recently (last seen {mins}m ago)",
                details={
                    "nodeId": node_id,
                    "lastProfileAt": last_seen.isoformat(),
                    "expectedIntervalSeconds": int(expected.total_seconds()),
                    "staleThresholdSeconds": int((expected * STALE_PROFILE_MULTIPLIER).total_seconds()),
                },
                resource_type="node",
                resource_id=node_id,
            )

    # ------------------------------------------------------------------
    # Offline node detection
    # ------------------------------------------------------------------

    async def _check_offline_nodes(
        self,
        node_warnings: dict[str, list[str]],
        active_nodes: list[dict],
        schedule_intervals: dict[str, timedelta],
    ) -> None:
        """Detect nodes that have been stale for 3x the expected interval.

        These nodes are considered truly offline — a more severe condition
        than merely stale.
        """
        now = datetime.now(UTC)

        for node in active_nodes:
            node_id = node["nodeId"]
            last_seen = node.get("lastProfileAt")
            if not isinstance(last_seen, datetime):
                continue
            last_seen = self._coerce_utc(last_seen)

            expected = schedule_intervals.get(node_id, DEFAULT_SCHEDULE_INTERVAL)
            offline_cutoff = now - (expected * OFFLINE_PROFILE_MULTIPLIER)

            if not last_seen < offline_cutoff:
                continue

            display = node.get("displayName") or node_id
            delta = now - last_seen
            mins = int(delta.total_seconds() / 60)

            node_warnings.setdefault(node_id, []).append("offline")

            await self._emit_with_audit(
                notification_type=NotificationType.NODE_OFFLINE,
                source=NotificationSource(
                    component="hydra-api",
                    service="health-scanner",
                    node_id=node_id,
                ),
                title=f"Node offline: {display}",
                message=(
                    f"Node {display} appears to be offline — no profile "
                    f"received for over {int((expected * OFFLINE_PROFILE_MULTIPLIER).total_seconds() / 60)} minutes "
                    f"(last seen {mins}m ago)"
                ),
                details={
                    "nodeId": node_id,
                    "lastProfileAt": last_seen.isoformat(),
                    "expectedIntervalSeconds": int(expected.total_seconds()),
                    "offlineThresholdSeconds": int(
                        (expected * OFFLINE_PROFILE_MULTIPLIER).total_seconds()
                    ),
                },
                resource_type="node",
                resource_id=node_id,
            )

    # ------------------------------------------------------------------
    # Storage threshold checks
    # ------------------------------------------------------------------

    async def _check_storage_thresholds(
        self,
        node_warnings: dict[str, list[str]],
        active_nodes: list[dict] | None = None,
    ) -> None:
        """Check latest profiles for filesystem usage above thresholds."""
        # Get nodes with active status
        if active_nodes is None:
            active_nodes = await self.db.nodes.find(
                {"status": "active"},
                {"nodeId": 1},
            ).to_list(length=500)

        if not active_nodes:
            return

        node_ids = [n["nodeId"] for n in active_nodes]

        # For each active node, get their latest profile's storage section
        pipeline = [
            {"$match": {"nodeId": {"$in": node_ids}}},
            {"$sort": {"submittedAt": -1}},
            {"$group": {
                "_id": "$nodeId",
                "latestProfile": {"$first": "$$ROOT"},
            }},
            {"$project": {
                "nodeId": "$_id",
                "filesystems": "$latestProfile.storage.filesystems",
            }},
        ]

        results = await self.db.profiles.aggregate(pipeline).to_list(length=500)

        for doc in results:
            node_id = doc["nodeId"]
            filesystems = doc.get("filesystems") or []

            for fs in filesystems:
                size = fs.get("size_bytes") or fs.get("sizeBytes")
                used = fs.get("used_bytes") or fs.get("usedBytes")
                mount = fs.get("mount_point") or fs.get("mountPoint") or "/"

                if not size or not used or size == 0:
                    continue

                pct = (used / size) * 100

                if pct >= STORAGE_CRITICAL_PERCENT:
                    node_warnings.setdefault(node_id, []).append(
                        f"storage_critical:{mount}"
                    )
                    await self._emit_with_audit(
                        notification_type=NotificationType.STORAGE_CRITICAL,
                        source=NotificationSource(
                            component="hydra-api",
                            service="health-scanner",
                            node_id=node_id,
                        ),
                        title=f"Storage critical on {node_id}",
                        message=f"Filesystem {mount} on {node_id} is at {pct:.0f}% capacity",
                        details={
                            "nodeId": node_id,
                            "mountPoint": mount,
                            "usagePercent": round(pct, 1),
                            "usedBytes": used,
                            "totalBytes": size,
                        },
                        resource_type="node",
                        resource_id=node_id,
                    )
                elif pct >= STORAGE_WARNING_PERCENT:
                    node_warnings.setdefault(node_id, []).append(
                        f"storage_warning:{mount}"
                    )
                    await self._emit_with_audit(
                        notification_type=NotificationType.STORAGE_WARNING,
                        source=NotificationSource(
                            component="hydra-api",
                            service="health-scanner",
                            node_id=node_id,
                        ),
                        title=f"Storage warning on {node_id}",
                        message=f"Filesystem {mount} on {node_id} is at {pct:.0f}% capacity",
                        details={
                            "nodeId": node_id,
                            "mountPoint": mount,
                            "usagePercent": round(pct, 1),
                            "usedBytes": used,
                            "totalBytes": size,
                        },
                        resource_type="node",
                        resource_id=node_id,
                    )

    # ------------------------------------------------------------------
    # Memory threshold checks
    # ------------------------------------------------------------------

    async def _check_memory_thresholds(
        self,
        node_warnings: dict[str, list[str]],
        active_nodes: list[dict] | None = None,
    ) -> None:
        """Check latest profiles for memory usage above thresholds."""
        if active_nodes is None:
            active_nodes = await self.db.nodes.find(
                {"status": "active"},
                {"nodeId": 1},
            ).to_list(length=500)

        if not active_nodes:
            return

        node_ids = [n["nodeId"] for n in active_nodes]

        pipeline = [
            {"$match": {"nodeId": {"$in": node_ids}}},
            {"$sort": {"submittedAt": -1}},
            {"$group": {
                "_id": "$nodeId",
                "latestProfile": {"$first": "$$ROOT"},
            }},
            {"$project": {
                "nodeId": "$_id",
                "memory": "$latestProfile.hardware.memory",
            }},
        ]

        results = await self.db.profiles.aggregate(pipeline).to_list(length=500)

        for doc in results:
            node_id = doc["nodeId"]
            memory = doc.get("memory") or {}

            total = memory.get("total_bytes") or memory.get("totalBytes")
            used = memory.get("used_bytes") or memory.get("usedBytes")

            if not total or not used or total == 0:
                continue

            pct = (used / total) * 100

            if pct >= MEMORY_CRITICAL_PERCENT:
                node_warnings.setdefault(node_id, []).append("memory_critical")
                await self._emit_with_audit(
                    notification_type=NotificationType.MEMORY_CRITICAL,
                    source=NotificationSource(
                        component="hydra-api",
                        service="health-scanner",
                        node_id=node_id,
                    ),
                    title=f"Memory critical on {node_id}",
                    message=f"Memory usage on {node_id} is at {pct:.0f}%",
                    details={
                        "nodeId": node_id,
                        "usagePercent": round(pct, 1),
                        "usedBytes": used,
                        "totalBytes": total,
                    },
                    resource_type="node",
                    resource_id=node_id,
                )

    # ------------------------------------------------------------------
    # Node health degradation (multiple concurrent warnings)
    # ------------------------------------------------------------------

    async def _check_node_health_degraded(
        self, node_warnings: dict[str, list[str]]
    ) -> None:
        """Emit NODE_HEALTH_DEGRADED for nodes with multiple concurrent warnings.

        A node is considered degraded when it has >= NODE_HEALTH_DEGRADED_THRESHOLD
        active warnings (e.g. stale + storage warning, or storage critical +
        memory critical).
        """
        for node_id, warnings in node_warnings.items():
            if len(warnings) < NODE_HEALTH_DEGRADED_THRESHOLD:
                continue

            await self._emit_with_audit(
                notification_type=NotificationType.NODE_HEALTH_DEGRADED,
                source=NotificationSource(
                    component="hydra-api",
                    service="health-scanner",
                    node_id=node_id,
                ),
                title=f"Health degraded: {node_id}",
                message=(
                    f"Node {node_id} has {len(warnings)} concurrent health "
                    f"warnings: {', '.join(warnings)}"
                ),
                details={
                    "nodeId": node_id,
                    "warningCount": len(warnings),
                    "activeWarnings": warnings,
                },
                resource_type="node",
                resource_id=node_id,
            )

    # ------------------------------------------------------------------
    # Expiring registration tokens
    # ------------------------------------------------------------------

    async def _check_expiring_tokens(self) -> None:
        """Flag registration tokens expiring within TOKEN_EXPIRY_WINDOW."""
        now = datetime.now(UTC)
        expiry_horizon = now + TOKEN_EXPIRY_WINDOW

        expiring = await self.db.tokens.find(
            {
                "expiresAt": {"$gt": now, "$lte": expiry_horizon},
                "revoked": {"$ne": True},
            },
            {
                "token": 1,
                "scope": 1,
                "description": 1,
                "expiresAt": 1,
                "createdBy": 1,
            },
        ).to_list(length=100)

        for tok in expiring:
            token_value = tok.get("token", "unknown")
            # Use last 8 chars for safe identification
            token_hint = f"...{token_value[-8:]}" if len(token_value) > 8 else token_value
            scope = tok.get("scope", "unknown")
            description = tok.get("description") or "No description"
            expires_at = tok["expiresAt"]
            remaining = expires_at - now
            hours_left = int(remaining.total_seconds() / 3600)

            await self._emit_with_audit(
                notification_type=NotificationType.TOKEN_EXPIRING,
                source=self._source,
                title=f"Registration token expiring ({scope})",
                message=(
                    f"Registration token ({scope}) \"{description}\" expires "
                    f"in ~{hours_left}h — {token_hint}"
                ),
                details={
                    "tokenId": token_hint,
                    "scope": scope,
                    "description": description,
                    "expiresAt": expires_at.isoformat(),
                    "hoursRemaining": hours_left,
                    "createdBy": tok.get("createdBy"),
                },
                resource_type="token",
                resource_id=token_hint,
            )

    # ------------------------------------------------------------------
    # Expiring API keys
    # ------------------------------------------------------------------

    async def _check_expiring_api_keys(self) -> None:
        """Flag API keys expiring within API_KEY_EXPIRY_WINDOW."""
        now = datetime.now(UTC)
        expiry_horizon = now + API_KEY_EXPIRY_WINDOW

        # Check both user-scoped and global API keys
        for collection in (self.db.api_keys, self.db.global_api_keys):
            expiring = await collection.find(
                {
                    "expiresAt": {"$gt": now, "$lte": expiry_horizon},
                    "revoked": {"$ne": True},
                },
                {
                    "keyId": 1,
                    "name": 1,
                    "expiresAt": 1,
                    "createdBy": 1,
                    "userId": 1,
                },
            ).to_list(length=100)

            for key in expiring:
                key_id = key.get("keyId", "unknown")
                name = key.get("name") or key_id
                expires_at = key["expiresAt"]
                remaining = expires_at - now
                hours_left = int(remaining.total_seconds() / 3600)

                await self._emit_with_audit(
                    notification_type=NotificationType.API_KEY_EXPIRING,
                    source=self._source,
                    title=f"API key expiring: {name}",
                    message=(
                        f"API key \"{name}\" (ID: {key_id}) expires in "
                        f"~{hours_left}h"
                    ),
                    details={
                        "keyId": key_id,
                        "name": name,
                        "expiresAt": expires_at.isoformat(),
                        "hoursRemaining": hours_left,
                        "createdBy": key.get("createdBy"),
                        "userId": key.get("userId"),
                    },
                    resource_type="api_key",
                    resource_id=key_id,
                )

    # ------------------------------------------------------------------
    # Service instability (frequent state changes)
    # ------------------------------------------------------------------

    async def _check_service_instability(self) -> None:
        """Detect services with frequent state changes in the lookback window.

        Since services don't store a state-change history, we inspect recent
        profiles for the same node and count how many times each service's
        status value changed across consecutive profile submissions within
        the SERVICE_INSTABILITY_LOOKBACK window.
        """
        now = datetime.now(UTC)
        lookback_cutoff = now - SERVICE_INSTABILITY_LOOKBACK

        # Get active nodes
        active_nodes = await self.db.nodes.find(
            {"status": "active"},
            {"nodeId": 1},
        ).to_list(length=500)

        if not active_nodes:
            return

        node_ids = [n["nodeId"] for n in active_nodes]

        # For each node, get recent profiles ordered by submission time
        pipeline = [
            {
                "$match": {
                    "nodeId": {"$in": node_ids},
                    "submittedAt": {"$gte": lookback_cutoff},
                },
            },
            {"$sort": {"submittedAt": 1}},
            {
                "$project": {
                    "nodeId": 1,
                    "services": "$services.services",
                    "submittedAt": 1,
                },
            },
        ]

        profiles = await self.db.profiles.aggregate(pipeline).to_list(length=5000)

        # Group profiles by node
        node_profiles: dict[str, list[dict]] = {}
        for p in profiles:
            node_profiles.setdefault(p["nodeId"], []).append(p)

        # For each node, track per-service status across profiles
        for node_id, ordered_profiles in node_profiles.items():
            # service_key -> {name, runtime, statuses}
            service_statuses: dict[str, dict] = {}

            for prof in ordered_profiles:
                svc_list = prof.get("services") or []
                for svc in svc_list:
                    svc_name = svc.get("name") or "unknown"
                    svc_runtime = svc.get("runtime") or "unknown"
                    svc_key = f"{svc_runtime}:{svc_name}"
                    status = svc.get("status") or "unknown"
                    entry = service_statuses.setdefault(
                        svc_key,
                        {"name": svc_name, "runtime": svc_runtime, "statuses": []},
                    )
                    entry["statuses"].append(status)

            # Count transitions (consecutive different statuses)
            for svc_key, entry in service_statuses.items():
                statuses = entry["statuses"]
                if len(statuses) < 2:
                    continue
                transitions = sum(
                    1 for i in range(1, len(statuses)) if statuses[i] != statuses[i - 1]
                )
                if transitions >= SERVICE_INSTABILITY_THRESHOLD:
                    svc_name = entry["name"]
                    svc_runtime = entry["runtime"]
                    await self._emit_with_audit(
                        notification_type=NotificationType.SERVICE_INSTABILITY,
                        source=NotificationSource(
                            component="hydra-api",
                            service="health-scanner",
                            node_id=node_id,
                        ),
                        title=f"Service instability: {svc_name} on {node_id}",
                        message=(
                            f"Service {svc_name} on {node_id} had "
                            f"{transitions} state changes in the last "
                            f"{int(SERVICE_INSTABILITY_LOOKBACK.total_seconds() / 3600)}h"
                        ),
                        details={
                            "nodeId": node_id,
                            "serviceName": svc_name,
                            "runtime": svc_runtime,
                            "stateChanges": transitions,
                            "lookbackHours": int(
                                SERVICE_INSTABILITY_LOOKBACK.total_seconds() / 3600
                            ),
                            "recentStatuses": statuses[-10:],  # last 10 for context
                        },
                        resource_type="service",
                        resource_id=f"{node_id}:{svc_key}",
                    )

    # ------------------------------------------------------------------
    # Pending user approvals
    # ------------------------------------------------------------------

    async def _check_pending_users(self) -> None:
        """Emit USER_PENDING_APPROVAL for pending users beyond threshold."""
        now = datetime.now(UTC)
        cutoff = now - PENDING_APPROVAL_THRESHOLD

        pending = await self.db.users_pending.find(
            {"requestedAt": {"$lte": cutoff}},
            {"userId": 1, "username": 1, "email": 1, "role": 1, "requestedAt": 1},
        ).to_list(length=200)

        for user in pending:
            user_id = user.get("userId")
            if not user_id:
                continue
            group_key = f"{NotificationType.USER_PENDING_APPROVAL.value}:{user_id}"
            if await self._has_active_notification(NotificationType.USER_PENDING_APPROVAL, group_key):
                continue

            requested_at = user.get("requestedAt")
            await self._emit_with_audit(
                notification_type=NotificationType.USER_PENDING_APPROVAL,
                source=self._source,
                title="User pending approval",
                message=(
                    f"User {user.get('username')} has been pending approval for "
                    f"more than {int(PENDING_APPROVAL_THRESHOLD.total_seconds() / 3600)}h"
                ),
                details={
                    "userId": user_id,
                    "username": user.get("username"),
                    "email": user.get("email"),
                    "role": user.get("role"),
                    "requestedAt": requested_at.isoformat() if requested_at else None,
                },
                resource_type="user_pending",
                resource_id=user_id,
                group_key=group_key,
            )

    # ------------------------------------------------------------------
    # Agent version outdated
    # ------------------------------------------------------------------

    async def _check_agent_version_outdated(self, node_ids: list[str]) -> None:
        """Detect agents that are more than N versions behind latest."""
        if not node_ids:
            return

        try:
            from hydra.api.v1.services.storage import StorageSource, get_cached_storage_service
            from hydra.core.config import get_settings
        except Exception:
            return

        storage = get_cached_storage_service(get_settings())
        if not storage or not storage.is_source_available(StorageSource.BINARY):
            return

        pipeline = [
            {"$match": {"nodeId": {"$in": node_ids}}},
            {"$sort": {"submittedAt": -1}},
            {"$group": {"_id": "$nodeId", "latestProfile": {"$first": "$$ROOT"}}},
            {
                "$project": {
                    "nodeId": "$_id",
                    "agentVersion": "$latestProfile.agentVersion",
                    "metadata": "$latestProfile.metadata",
                }
            },
        ]
        profiles = await self.db.profiles.aggregate(pipeline).to_list(length=500)

        targets = {
            (doc.get("metadata") or {}).get("agentTarget")
            for doc in profiles
            if (doc.get("metadata") or {}).get("agentTarget")
        }

        def version_key(value: str) -> list[int]:
            import re

            parts = re.split(r"[.-]", value)
            key: list[int] = []
            for part in parts:
                if part.isdigit():
                    key.append(int(part))
                else:
                    key.append(0)
            return key

        versions_by_target: dict[str, list[str]] = {}
        backend = storage.get_backend(StorageSource.BINARY)
        for target in targets:
            try:
                versions = await backend.list_versions(target)
            except Exception:
                continue
            versions_by_target[target] = [v["version"] for v in versions if v.get("version")]

        for doc in profiles:
            node_id = doc.get("nodeId")
            current = doc.get("agentVersion")
            meta = doc.get("metadata") or {}
            target = meta.get("agentTarget")

            if not node_id or not current or not target:
                continue
            if str(current).lower() == "latest":
                continue

            available = versions_by_target.get(target) or []
            if not available:
                continue

            ordered = sorted(set(available + [current]), key=version_key, reverse=True)
            if current not in ordered:
                continue

            index = ordered.index(current)
            if index < AGENT_OUTDATED_THRESHOLD:
                continue

            latest = ordered[0]
            group_key = f"{NotificationType.AGENT_VERSION_OUTDATED.value}:{node_id}:{current}"
            if await self._has_active_notification(NotificationType.AGENT_VERSION_OUTDATED, group_key):
                continue

            await self._emit_with_audit(
                notification_type=NotificationType.AGENT_VERSION_OUTDATED,
                source=NotificationSource(
                    component="hydra-api",
                    service="health-scanner",
                    node_id=node_id,
                ),
                title="Agent version outdated",
                message=(
                    f"Agent on node {node_id} is {index} versions behind "
                    f"(current: {current}, latest: {latest})"
                ),
                details={
                    "nodeId": node_id,
                    "currentVersion": current,
                    "latestVersion": latest,
                    "versionsBehind": index,
                    "target": target,
                },
                resource_type="node",
                resource_id=node_id,
                group_key=group_key,
            )

    # ------------------------------------------------------------------
    # Health check passed
    # ------------------------------------------------------------------

    async def _check_health_check_passed(
        self,
        active_nodes: list[dict],
        node_warnings: dict[str, list[str]],
        schedule_intervals: dict[str, timedelta],
    ) -> None:
        """Emit HEALTH_CHECK_PASSED when nodes are healthy and quiet."""
        now = datetime.now(UTC)
        for node in active_nodes:
            node_id = node.get("nodeId")
            if not node_id or node_id in node_warnings:
                continue

            last_seen = node.get("lastProfileAt")
            if not isinstance(last_seen, datetime):
                continue
            last_seen = self._coerce_utc(last_seen)

            expected = schedule_intervals.get(node_id, DEFAULT_SCHEDULE_INTERVAL)
            stale_cutoff = now - (expected * STALE_PROFILE_MULTIPLIER)
            if last_seen < stale_cutoff:
                continue

            group_key = f"{NotificationType.HEALTH_CHECK_PASSED.value}:{node_id}"
            recent = await self.db.notifications.find_one(
                {
                    "type": NotificationType.HEALTH_CHECK_PASSED.value,
                    "groupKey": group_key,
                    "createdAt": {"$gte": now - HEALTH_CHECK_PASS_COOLDOWN},
                },
                {"notificationId": 1},
            )
            if recent:
                continue

            await self._emit_with_audit(
                notification_type=NotificationType.HEALTH_CHECK_PASSED,
                source=NotificationSource(
                    component="hydra-api",
                    service="health-scanner",
                    node_id=node_id,
                ),
                title="Health check passed",
                message=f"Health check passed for node {node_id}",
                details={
                    "nodeId": node_id,
                    "lastProfileAt": last_seen.isoformat(),
                    "expectedIntervalSeconds": int(expected.total_seconds()),
                },
                resource_type="node",
                resource_id=node_id,
                group_key=group_key,
            )
