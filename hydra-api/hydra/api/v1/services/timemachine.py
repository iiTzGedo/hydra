"""Time Machine service for historical state reconstruction."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import NodeNotFoundError, ValidationError
from hydra.db.mongodb import MongoDB
from hydra.api.v1.models.timemachine import TimelineEventType
from hydra.api.v1.models.topologies import TopologyMode

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
    ) -> dict:
        """
        Reconstruct node state at a specific timestamp.

        This will:
        1. Verify node existed at that time
        2. Find the latest profile before the timestamp
        3. Find services from that profile
        4. Return merged state
        """
        # Find node
        node = await self.db.nodes.find_one({"nodeId": node_id})
        if not node:
            raise NodeNotFoundError(node_id)

        # Check node existed at that time
        if node.get("registeredAt") and node["registeredAt"] > timestamp:
            raise ValidationError(
                f"Node '{node_id}' did not exist at {timestamp.isoformat()}",
                {"nodeId": node_id, "registeredAt": node["registeredAt"].isoformat()},
            )

        # Find closest profile at or before timestamp
        profile = await self.db.profiles.find_one(
            {"nodeId": node_id, "submittedAt": {"$lte": timestamp}},
            sort=[("submittedAt", DESCENDING)],
        )

        # Calculate delta from requested timestamp
        delta_minutes = 0
        profile_at = None
        if profile:
            profile_at = profile["submittedAt"]
            delta = timestamp - profile_at
            delta_minutes = int(delta.total_seconds() // 60)

        # Find services from that profile (if it exists)
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

        # Build state
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
    ) -> dict:
        """
        Get topology valid at a specific timestamp.

        Finds topology where validFrom <= timestamp < validUntil (or validUntil is null).
        """
        # Find topology valid at timestamp
        topology = await self.db.topologies.find_one({
            "mode": mode.value,
            "validFrom": {"$lte": timestamp},
            "$or": [
                {"validUntil": None},
                {"validUntil": {"$gt": timestamp}},
            ],
        })

        if not topology:
            # Try to find closest topology
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
    ) -> tuple[list[dict], int]:
        """
        Get timeline events for Time Machine visualization.

        Aggregates events from:
        - Profile submissions
        - Topology generations
        - Node registrations
        """
        events: list[dict] = []

        # Query profiles
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

        # Query topologies
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

        # Query nodes for registration events
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

        # Query networks for creation events
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

        # Sort all events by timestamp
        events.sort(key=lambda x: x["timestamp"], reverse=True)

        total = len(events)

        # Apply pagination
        paginated_events = events[offset:offset + limit]

        logger.info(
            "timeline_queried",
            since=since.isoformat(),
            until=until.isoformat(),
            total_events=total,
            returned=len(paginated_events),
        )

        return paginated_events, total

    def _format_node_snapshot(self, doc: dict) -> dict:
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

    def _format_profile_snapshot(self, doc: dict, sections: list[str] | None = None) -> dict:
        """Format profile for snapshot."""
        result = {
            "profileId": doc["profileId"],
            "version": doc["version"],
            "submittedAt": doc["submittedAt"],
        }

        # Include requested sections or all by default
        all_sections = ["hardware", "network", "storage", "software"]
        include_sections = sections if sections else all_sections

        for section in include_sections:
            if section in doc:
                result[section] = doc[section]

        return result

    def _format_service_snapshot(self, doc: dict) -> dict:
        """Format service for snapshot."""
        return {
            "serviceId": doc["serviceId"],
            "name": doc["name"],
            "runtime": doc["runtime"],
            "status": doc.get("status"),
            "version": doc.get("version"),
        }
