"""Time Machine service for historical state reconstruction."""

import secrets
from datetime import datetime
from typing import Any

import structlog
from pymongo import DESCENDING

from hydra.api.v1.core.exceptions import NodeNotFoundError, ValidationError
from hydra.api.v1.models.timemachine import TimelineEventType
from hydra.api.v1.models.topologies import TopologyMode
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class TimeMachineService:
    """Service for historical state reconstruction."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_node_state_at(
        self,
        node_id: str,
        timestamp: datetime,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """Reconstruct node state at a specific timestamp.

        Finds the latest profile before the timestamp and merges node,
        profile, and service data into a unified state snapshot.

        Args:
            node_id: The node identifier.
            timestamp: Target timestamp for reconstruction.
            sections: Optional list of profile sections to include.

        Returns:
            State snapshot with node, profile, services, and metadata.

        Raises:
            NodeNotFoundError: If the node does not exist.
            ValidationError: If the node did not exist at the requested time.
        """
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        if node.get("registeredAt") and node["registeredAt"] > timestamp:
            raise ValidationError(
                f"Node '{node_id}' did not exist at {timestamp.isoformat()}",
                {"nodeId": node_id, "registeredAt": node["registeredAt"].isoformat()},
            )

        profile = await self.db.profiles.find_one(
            {"nodeId": node_id, "submittedAt": {"$lte": timestamp}},
            sort=[("submittedAt", DESCENDING)],
        )

        delta_minutes = 0
        profile_at = None
        if profile:
            profile_at = profile["submittedAt"]
            delta = timestamp - profile_at
            delta_minutes = int(delta.total_seconds() // 60)

        services = []
        if profile:
            service_ids = profile.get("serviceIds", [])
            if service_ids:
                cursor = self.db.services.find({
                    "serviceId": {"$in": service_ids},
                    "nodeId": node_id,
                })
                async for svc in cursor:
                    services.append(self._format_service_snapshot(svc))

        state = {
            "node": self._format_node_snapshot(node),
            "profile": self._format_profile_snapshot(profile, sections) if profile else None,
            "services": services,
        }

        return {
            "nodeId": node_id,
            "timestamp": timestamp,
            "state": state,
            "closestSnapshot": {
                "profileAt": profile_at,
                "deltaMinutes": delta_minutes,
            },
        }

    async def get_topology_at(
        self,
        mode: TopologyMode,
        timestamp: datetime,
        include_graph: bool = True,
    ) -> dict[str, Any]:
        """Get topology valid at a specific timestamp.

        Finds topology where validFrom <= timestamp < validUntil.

        Args:
            mode: The topology mode (infrastructure, network).
            timestamp: Target timestamp for lookup.
            include_graph: Whether to include the full graph data.

        Returns:
            Topology snapshot with metadata and optionally graph data.

        Raises:
            ValidationError: If no topology exists for the mode at the timestamp.
        """
        topology = await self.db.topologies.find_one({
            "mode": mode.value,
            "validFrom": {"$lte": timestamp},
            "$or": [
                {"validUntil": None},
                {"validUntil": {"$gt": timestamp}},
            ],
        })

        if not topology:
            topology = await self.db.topologies.find_one(
                {"mode": mode.value, "validFrom": {"$lte": timestamp}},
                sort=[("validFrom", DESCENDING)],
            )

            if not topology:
                raise ValidationError(
                    f"No topology found for mode '{mode.value}' at {timestamp.isoformat()}"
                )

        note = None
        if topology.get("validUntil") and topology["validUntil"] <= timestamp:
            note = "Using closest available topology (no valid topology at exact timestamp)"

        result = {
            "topologyId": topology["topologyId"],
            "timestamp": timestamp,
            "mode": topology["mode"],
            "version": topology["version"],
            "generatedAt": topology["generatedAt"],
            "stats": topology.get("stats", {}),
            "note": note,
        }

        if include_graph:
            result["graph"] = topology.get("graph")

        return result

    async def get_timeline(
        self,
        since: datetime,
        until: datetime,
        node_id: str | None = None,
        event_types: list[TimelineEventType] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get timeline events for Time Machine visualization.

        Aggregates events from profile submissions, topology generations,
        node registrations, and network creations within the time range.

        Args:
            since: Start of the time range.
            until: End of the time range.
            node_id: Optional node filter for profile and node events.
            event_types: Optional filter for specific event types.
            limit: Maximum events to return.
            offset: Pagination offset.

        Returns:
            Tuple of (timeline events, total count).
        """
        events: list[dict[str, Any]] = []

        profile_filter: dict[str, Any] = {
            "submittedAt": {"$gte": since, "$lte": until}
        }
        if node_id:
            profile_filter["nodeId"] = node_id

        if not event_types or TimelineEventType.PROFILE_SUBMITTED in event_types:
            async for profile in self.db.profiles.find(profile_filter).sort("submittedAt", DESCENDING):
                events.append({
                    "eventId": f"evt_{secrets.token_urlsafe(8)}",
                    "eventType": TimelineEventType.PROFILE_SUBMITTED.value,
                    "timestamp": profile["submittedAt"],
                    "entityType": "profile",
                    "entityId": profile["profileId"],
                    "description": f"Profile {profile['version']} submitted for {profile['nodeId']}",
                    "metadata": {
                        "nodeId": profile["nodeId"],
                        "version": profile["version"],
                        "serviceCount": len(profile.get("serviceIds", [])),
                    },
                })

        if not event_types or TimelineEventType.TOPOLOGY_GENERATED in event_types:
            topo_filter: dict[str, Any] = {
                "generatedAt": {"$gte": since, "$lte": until}
            }
            async for topo in self.db.topologies.find(topo_filter).sort("generatedAt", DESCENDING):
                events.append({
                    "eventId": f"evt_{secrets.token_urlsafe(8)}",
                    "eventType": TimelineEventType.TOPOLOGY_GENERATED.value,
                    "timestamp": topo["generatedAt"],
                    "entityType": "topology",
                    "entityId": topo["topologyId"],
                    "description": f"Topology v{topo['version']} generated ({topo['mode']} mode)",
                    "metadata": {
                        "mode": topo["mode"],
                        "version": topo["version"],
                        "nodeCount": topo.get("stats", {}).get("nodeCount", 0),
                        "edgeCount": topo.get("stats", {}).get("edgeCount", 0),
                    },
                })

        if not event_types or TimelineEventType.NODE_REGISTERED in event_types:
            node_filter: dict[str, Any] = {
                "registeredAt": {"$gte": since, "$lte": until}
            }
            if node_id:
                node_filter["nodeId"] = node_id

            async for node in self.db.nodes.find(node_filter).sort("registeredAt", DESCENDING):
                events.append({
                    "eventId": f"evt_{secrets.token_urlsafe(8)}",
                    "eventType": TimelineEventType.NODE_REGISTERED.value,
                    "timestamp": node["registeredAt"],
                    "entityType": "node",
                    "entityId": node["nodeId"],
                    "description": f"Node {node['displayName']} registered",
                    "metadata": {
                        "nodeId": node["nodeId"],
                        "class": node.get("class"),
                        "type": node.get("type"),
                    },
                })

        if not event_types or TimelineEventType.NETWORK_CREATED in event_types:
            network_filter: dict[str, Any] = {
                "createdAt": {"$gte": since, "$lte": until}
            }
            async for network in self.db.networks.find(network_filter).sort("createdAt", DESCENDING):
                events.append({
                    "eventId": f"evt_{secrets.token_urlsafe(8)}",
                    "eventType": TimelineEventType.NETWORK_CREATED.value,
                    "timestamp": network["createdAt"],
                    "entityType": "network",
                    "entityId": network["networkId"],
                    "description": f"Network {network['name']} created",
                    "metadata": {
                        "networkId": network["networkId"],
                        "cidr": network.get("cidr"),
                        "origin": network.get("origin", {}).get("createdBy"),
                    },
                })

        events.sort(key=lambda x: x["timestamp"], reverse=True)
        total = len(events)
        paginated_events = events[offset:offset + limit]

        logger.info(
            "timeline_queried",
            since=since.isoformat(),
            until=until.isoformat(),
            total_events=total,
            returned=len(paginated_events),
        )

        return paginated_events, total

    def _format_node_snapshot(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format node for snapshot."""
        return {
            "nodeId": doc["nodeId"],
            "displayName": doc["displayName"],
            "class": doc.get("class"),
            "type": doc.get("type"),
            "kind": doc.get("kind"),
            "status": doc.get("status"),
            "tags": doc.get("tags", []),
            "registeredAt": doc.get("registeredAt"),
        }

    def _format_profile_snapshot(self, doc: dict[str, Any], sections: list[str] | None = None) -> dict[str, Any]:
        """Format profile for snapshot."""
        result = {
            "profileId": doc["profileId"],
            "version": doc["version"],
            "submittedAt": doc["submittedAt"],
        }

        all_sections = ["hardware", "network", "storage", "software"]
        include_sections = sections if sections else all_sections

        for section in include_sections:
            if section in doc:
                result[section] = doc[section]

        return result

    def _format_service_snapshot(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format service for snapshot."""
        return {
            "serviceId": doc["serviceId"],
            "name": doc["name"],
            "runtime": doc["runtime"],
            "status": doc.get("status"),
            "version": doc.get("version"),
        }
