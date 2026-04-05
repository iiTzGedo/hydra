"""Service extraction from profiles and related notifications."""

import hashlib
from datetime import UTC, datetime

import structlog

from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationType,
    SourceComponent,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)

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


def _normalize_service_name(name: str) -> str:
    return name.strip().lower()


async def is_known_service(db: MongoDB, runtime: str, name: str) -> bool:
    normalized = _normalize_service_name(name)
    doc = await db.known_services.find_one(
        {"runtime": runtime, "normalizedName": normalized}
    )
    return doc is not None


async def extract_services(
    db: MongoDB,
    node_id: str,
    profile_id: str,
    services: list,  # type: ignore[type-arg]
) -> list[str]:
    """Extract services from profile and upsert them."""
    service_ids = []
    now = datetime.now(UTC)

    for svc in services:
        service_id = generate_service_id(node_id, svc.runtime, svc.name)
        service_ids.append(service_id)

        # Check existing service for new-discovery / state-change detection
        existing_svc = await db.services.find_one(
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

        await db.services.update_one(
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

        # New service discovered (GREEN)
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
            if not await is_known_service(db, svc.runtime, svc.name):
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
        # Service state changed (YELLOW)
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
