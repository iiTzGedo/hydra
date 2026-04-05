"""Network processing and network diff logic for profiles."""


from typing import Any

import structlog

from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationType,
    SourceComponent,
)
from hydra.api.v1.models.profiles import ProfileSubmission
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


async def process_networks(
    db: MongoDB,
    node_id: str,
    profile_id: str,
    network_profile: dict[str, Any] | None,
) -> list[str]:
    """Extract networks from profile and auto-create/update."""
    from hydra.api.v1.services.networks import NetworksService

    # Snapshot existing network IDs before processing for new-discovery detection
    existing_network_ids: set[str] = set()
    if network_profile and network_profile.interfaces:  # type: ignore[attr-defined]
        cursor = db.networks.find({}, projection={"networkId": 1})
        async for doc in cursor:
            existing_network_ids.add(doc["networkId"])

    networks_service = NetworksService(db)
    network_ids = await networks_service.process_profile_networks(
        node_id,
        profile_id,
        network_profile,  # type: ignore[arg-type]
    )

    # New networks discovered (GREEN)
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


def _normalize_interface(interface: dict[str, Any]) -> dict[str, Any]:
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


def _route_key(route: dict[str, Any]) -> tuple:  # type: ignore[type-arg]
    return (
        route.get("destination"),
        route.get("gateway"),
        route.get("interface"),
        route.get("metric"),
    )


def diff_network_config(
    previous_profile: dict[str, Any] | None, submission: ProfileSubmission
) -> dict[str, Any] | None:
    """Detect network config changes between previous profile and new submission."""
    if not previous_profile or not submission.network:
        return None

    prev_network = previous_profile.get("network")
    if not prev_network:
        return None

    prev_interfaces = {
        iface.get("name"): _normalize_interface(iface)
        for iface in (prev_network.get("interfaces") or [])
        if isinstance(iface, dict) and iface.get("name")
    }
    new_interfaces = {
        iface.name: _normalize_interface(iface.model_dump(by_alias=True))
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
    dns_added = sorted(new_dns - prev_dns)
    dns_removed = sorted(prev_dns - new_dns)

    prev_search = set(prev_network.get("dnsSearch") or [])
    new_search = set(submission.network.dns_search or [])
    search_added = sorted(new_search - prev_search)
    search_removed = sorted(prev_search - new_search)

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
        _route_key(route): route
        for route in (prev_network.get("routes") or [])
        if isinstance(route, dict)
    }
    new_routes = {
        _route_key(route.model_dump(by_alias=True)): route.model_dump(by_alias=True)
        for route in submission.network.routes
    }
    added_routes = [new_routes[key] for key in new_routes if key not in prev_routes]
    removed_routes = [prev_routes[key] for key in prev_routes if key not in new_routes]

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
