"""Topology generation and management service."""

import time
from datetime import datetime, timezone
from typing import Any

import structlog
from pymongo import DESCENDING

from hydra_api.core.exceptions import TopologyNotFoundError, ValidationError
from hydra_api.db.mongodb import MongoDB
from hydra_api.models.topologies import (
    GenerateTopologyRequest,
    GraphEdge,
    GraphNode,
    GraphNodePosition,
    TopologyDiff,
    TopologyGraph,
    TopologyListParams,
    TopologyMode,
    TopologyScope,
)

logger = structlog.get_logger(__name__)


class TopologiesService:
    """Service for topology generation and management."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_topology(self, topology_id: str, include_graph: bool = True) -> dict:
        """Get a single topology by ID."""
        topology = await self.db.topologies.find_one({"topologyId": topology_id})
        if not topology:
            raise TopologyNotFoundError(topology_id)
        return self._format_topology(topology, include_graph=include_graph)

    async def get_latest_topology(self, mode: TopologyMode, include_graph: bool = True) -> dict:
        """Get the latest topology for a mode."""
        topology = await self.db.topologies.find_one(
            {"mode": mode.value, "validUntil": None},
            sort=[("generatedAt", DESCENDING)],
        )
        if not topology:
            # Try to find any topology for this mode
            topology = await self.db.topologies.find_one(
                {"mode": mode.value},
                sort=[("generatedAt", DESCENDING)],
            )
        if not topology:
            raise ValidationError(f"No topology found for mode '{mode.value}'")
        return self._format_topology(topology, include_graph=include_graph)

    async def list_topologies(self, params: TopologyListParams) -> tuple[list[dict], int]:
        """List topologies with filters and pagination."""
        filter_query: dict[str, Any] = {}

        if params.mode:
            filter_query["mode"] = params.mode.value
        if params.since:
            filter_query["generatedAt"] = {"$gte": params.since}
        if params.until:
            if "generatedAt" in filter_query:
                filter_query["generatedAt"]["$lte"] = params.until
            else:
                filter_query["generatedAt"] = {"$lte": params.until}

        total = await self.db.topologies.count_documents(filter_query)

        cursor = (
            self.db.topologies.find(filter_query)
            .sort("generatedAt", DESCENDING)
            .skip(params.offset)
            .limit(params.limit)
        )

        topologies = []
        async for topology in cursor:
            topologies.append(self._format_topology_summary(topology))

        return topologies, total

    async def generate_topology(self, request: GenerateTopologyRequest) -> dict:
        """Generate a new topology."""
        start_time = time.time()

        # Close previous topology for this mode
        previous_id = await self._close_previous_topology(request.mode)

        # Generate the graph
        if request.mode == TopologyMode.NETWORK:
            graph_nodes, graph_edges = await self._generate_network_topology(request.scope)
        else:
            graph_nodes, graph_edges = await self._generate_infrastructure_topology(request.scope)

        # Compute layout
        positions = self._compute_layout(graph_nodes, graph_edges, request.mode)

        # Apply positions to nodes
        for node in graph_nodes:
            if node.id in positions:
                node.position = positions[node.id]

        # Calculate diff if there's a previous topology
        diff = None
        if previous_id:
            previous = await self.db.topologies.find_one({"topologyId": previous_id})
            if previous and previous.get("graph"):
                diff = self._calculate_diff(
                    TopologyGraph(**previous["graph"]),
                    TopologyGraph(nodes=graph_nodes, edges=graph_edges),
                )

        compute_time = int((time.time() - start_time) * 1000)

        # Get next version
        version = await self._get_next_version(request.mode)

        now = datetime.now(timezone.utc)
        topology_id = f"topo-{request.mode.value}-{now.strftime('%Y%m%dT%H%M%SZ')}"

        # Count networks and services
        network_count = sum(1 for n in graph_nodes if n.type == "network")
        service_count = sum(1 for n in graph_nodes if n.type == "service")

        topology_doc = {
            "topologyId": topology_id,
            "mode": request.mode.value,
            "version": version,
            "scope": request.scope.model_dump(by_alias=True, exclude_none=True) if request.scope else None,
            "generatedAt": now,
            "validFrom": now,
            "validUntil": None,
            "graph": {
                "nodes": [n.model_dump() for n in graph_nodes],
                "edges": [e.model_dump() for e in graph_edges],
            },
            "stats": {
                "nodeCount": len(graph_nodes),
                "edgeCount": len(graph_edges),
                "networkCount": network_count,
                "serviceCount": service_count,
                "computeTimeMs": compute_time,
            },
            "previousTopologyId": previous_id,
            "diff": diff.model_dump(by_alias=True) if diff else None,
        }

        await self.db.topologies.insert_one(topology_doc)

        logger.info(
            "topology_generated",
            topology_id=topology_id,
            mode=request.mode.value,
            version=version,
            node_count=len(graph_nodes),
            edge_count=len(graph_edges),
            compute_time_ms=compute_time,
        )

        return self._format_topology(topology_doc)

    async def diff_topologies(
        self,
        from_id: str | None,
        to_id: str | None,
        mode: TopologyMode | None = None,
    ) -> dict:
        """Compare two topologies."""
        # Get topologies
        if from_id:
            from_topo = await self.db.topologies.find_one({"topologyId": from_id})
            if not from_topo:
                raise TopologyNotFoundError(from_id)
        else:
            # Get second-to-last for this mode
            if not mode:
                raise ValidationError("Either from_id or mode is required")
            cursor = self.db.topologies.find({"mode": mode.value}).sort("generatedAt", DESCENDING).limit(2)
            topos = await cursor.to_list(2)
            if len(topos) < 2:
                raise ValidationError("Not enough topologies to compare")
            from_topo = topos[1]

        if to_id:
            to_topo = await self.db.topologies.find_one({"topologyId": to_id})
            if not to_topo:
                raise TopologyNotFoundError(to_id)
        else:
            # Get latest for this mode
            if not mode:
                mode = TopologyMode(from_topo["mode"])
            to_topo = await self.db.topologies.find_one(
                {"mode": mode.value},
                sort=[("generatedAt", DESCENDING)],
            )
            if not to_topo:
                raise ValidationError(f"No topology found for mode '{mode.value}'")

        # Calculate diff
        from_graph = TopologyGraph(**from_topo.get("graph", {"nodes": [], "edges": []}))
        to_graph = TopologyGraph(**to_topo.get("graph", {"nodes": [], "edges": []}))
        diff = self._calculate_diff(from_graph, to_graph)

        return {
            "from": self._format_topology_summary(from_topo),
            "to": self._format_topology_summary(to_topo),
            "diff": diff.model_dump(by_alias=True),
            "summary": {
                "nodesAdded": len(diff.nodes_added),
                "nodesRemoved": len(diff.nodes_removed),
                "nodesModified": len(diff.nodes_modified),
                "edgesAdded": len(diff.edges_added),
                "edgesRemoved": len(diff.edges_removed),
                "totalChanges": (
                    len(diff.nodes_added) + len(diff.nodes_removed) + len(diff.nodes_modified) +
                    len(diff.edges_added) + len(diff.edges_removed)
                ),
            },
        }

    async def _close_previous_topology(self, mode: TopologyMode) -> str | None:
        """Close the previous topology's validity window."""
        previous = await self.db.topologies.find_one(
            {"mode": mode.value, "validUntil": None},
            sort=[("generatedAt", DESCENDING)],
        )
        if previous:
            await self.db.topologies.update_one(
                {"topologyId": previous["topologyId"]},
                {"$set": {"validUntil": datetime.now(timezone.utc)}},
            )
            return previous["topologyId"]
        return None

    async def _get_next_version(self, mode: TopologyMode) -> int:
        """Get the next version number for a mode."""
        latest = await self.db.topologies.find_one(
            {"mode": mode.value},
            sort=[("version", DESCENDING)],
        )
        return (latest.get("version", 0) + 1) if latest else 1

    async def _generate_network_topology(
        self,
        scope: TopologyScope | None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Generate network-centric topology."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # Get networks
        network_filter: dict[str, Any] = {}
        if scope and scope.network_ids:
            network_filter["networkId"] = {"$in": scope.network_ids}

        networks = []
        async for network in self.db.networks.find(network_filter):
            networks.append(network)
            nodes.append(GraphNode(
                id=f"net::{network['networkId']}",
                type="network",
                label=network.get("name", network["networkId"]),
                data={
                    "networkId": network["networkId"],
                    "cidr": network.get("cidr"),
                    "type": network.get("type"),
                    "nodeCount": network.get("nodeCount", 0),
                },
                position=GraphNodePosition(x=0, y=0),
            ))

        # Get nodes
        node_filter: dict[str, Any] = {"status": {"$ne": "archived"}}
        if scope and scope.node_ids:
            node_filter["nodeId"] = {"$in": scope.node_ids}

        infra_nodes = []
        async for node in self.db.nodes.find(node_filter):
            infra_nodes.append(node)

            # Determine node type
            node_type = self._get_graph_node_type(node)

            nodes.append(GraphNode(
                id=f"node::{node['nodeId']}",
                type=node_type,
                label=node.get("displayName", node["nodeId"]),
                data={
                    "nodeId": node["nodeId"],
                    "class": node.get("class"),
                    "type": node.get("type"),
                    "kind": node.get("kind"),
                    "status": node.get("status"),
                },
                position=GraphNodePosition(x=0, y=0),
            ))

            # Create edges for network connections
            for network_id in node.get("networkIds", []):
                edges.append(GraphEdge(
                    id=f"edge::node::{node['nodeId']}::net::{network_id}",
                    source=f"node::{node['nodeId']}",
                    target=f"net::{network_id}",
                    type="network-connection",
                ))

        # Create gateway edges
        for network in networks:
            if network.get("routerNodeId"):
                edges.append(GraphEdge(
                    id=f"edge::net::{network['networkId']}::router::{network['routerNodeId']}",
                    source=f"net::{network['networkId']}",
                    target=f"node::{network['routerNodeId']}",
                    type="network-gateway",
                ))

            # VLAN parent-child edges
            if network.get("parentNetworkId"):
                edges.append(GraphEdge(
                    id=f"edge::net::{network['networkId']}::parent::{network['parentNetworkId']}",
                    source=f"net::{network['networkId']}",
                    target=f"net::{network['parentNetworkId']}",
                    type="vlan-trunk",
                ))

        return nodes, edges

    async def _generate_infrastructure_topology(
        self,
        scope: TopologyScope | None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Generate infrastructure (parent-child + services) topology."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # Get nodes
        node_filter: dict[str, Any] = {"status": {"$ne": "archived"}}
        if scope and scope.node_ids:
            node_filter["nodeId"] = {"$in": scope.node_ids}

        infra_nodes = []
        async for node in self.db.nodes.find(node_filter):
            infra_nodes.append(node)

            node_type = self._get_graph_node_type(node)

            nodes.append(GraphNode(
                id=f"node::{node['nodeId']}",
                type=node_type,
                label=node.get("displayName", node["nodeId"]),
                data={
                    "nodeId": node["nodeId"],
                    "class": node.get("class"),
                    "type": node.get("type"),
                    "kind": node.get("kind"),
                    "status": node.get("status"),
                },
                position=GraphNodePosition(x=0, y=0),
            ))

            # Create parent-child edges
            if node.get("parentNodeId"):
                edges.append(GraphEdge(
                    id=f"edge::node::{node['nodeId']}::parent::{node['parentNodeId']}",
                    source=f"node::{node['nodeId']}",
                    target=f"node::{node['parentNodeId']}",
                    type="parent-child",
                ))

        # Get services
        service_filter: dict[str, Any] = {"status": {"$ne": "archived"}}
        if scope and scope.node_ids:
            service_filter["nodeId"] = {"$in": scope.node_ids}

        async for service in self.db.services.find(service_filter):
            nodes.append(GraphNode(
                id=f"svc::{service['serviceId']}",
                type="service",
                label=service.get("displayName", service["name"]),
                data={
                    "serviceId": service["serviceId"],
                    "runtime": service.get("runtime"),
                    "status": service.get("status"),
                    "nodeId": service["nodeId"],
                },
                position=GraphNodePosition(x=0, y=0),
            ))

            # Service-host edge
            edges.append(GraphEdge(
                id=f"edge::svc::{service['serviceId']}::host::{service['nodeId']}",
                source=f"svc::{service['serviceId']}",
                target=f"node::{service['nodeId']}",
                type="service-host",
            ))

        return nodes, edges

    def _get_graph_node_type(self, node: dict) -> str:
        """Determine the graph node type based on node class/type."""
        node_class = node.get("class", "")
        node_type = node.get("type", "")

        if node_class == "networking":
            return "networking"
        elif node_class == "iot":
            return "iot"
        elif node_type == "physical":
            return "compute-physical"
        else:
            return "compute-logical"

    def _compute_layout(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        mode: TopologyMode,
    ) -> dict[str, GraphNodePosition]:
        """Compute layout positions for nodes."""
        positions: dict[str, GraphNodePosition] = {}

        if mode == TopologyMode.NETWORK:
            positions = self._circular_layout(nodes, edges)
        else:
            positions = self._hierarchical_layout(nodes, edges)

        return positions

    def _circular_layout(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> dict[str, GraphNodePosition]:
        """Circular layout with networks in center."""
        import math

        positions: dict[str, GraphNodePosition] = {}

        # Separate networks and devices
        networks = [n for n in nodes if n.type == "network"]
        devices = [n for n in nodes if n.type != "network"]

        # Place networks in inner circle
        network_radius = 100
        for i, net in enumerate(networks):
            angle = (2 * math.pi * i) / max(len(networks), 1)
            x = network_radius * math.cos(angle)
            y = network_radius * math.sin(angle)
            positions[net.id] = GraphNodePosition(x=x, y=y, layer=0)

        # Place devices in outer circle
        device_radius = 300
        for i, device in enumerate(devices):
            angle = (2 * math.pi * i) / max(len(devices), 1)
            x = device_radius * math.cos(angle)
            y = device_radius * math.sin(angle)
            positions[device.id] = GraphNodePosition(x=x, y=y, layer=1)

        return positions

    def _hierarchical_layout(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> dict[str, GraphNodePosition]:
        """Hierarchical layout: physical -> logical -> services."""
        positions: dict[str, GraphNodePosition] = {}

        # Categorize nodes by layer
        layers: dict[int, list[GraphNode]] = {0: [], 1: [], 2: []}

        for node in nodes:
            if node.type in ["compute-physical", "networking"]:
                layers[0].append(node)
            elif node.type in ["compute-logical", "iot"]:
                layers[1].append(node)
            else:  # service
                layers[2].append(node)

        # Position nodes in each layer
        layer_height = 200
        node_spacing = 150

        for layer_idx, layer_nodes in layers.items():
            y = layer_idx * layer_height
            total_width = len(layer_nodes) * node_spacing
            start_x = -total_width / 2

            for i, node in enumerate(layer_nodes):
                x = start_x + (i * node_spacing) + (node_spacing / 2)
                positions[node.id] = GraphNodePosition(x=x, y=y, layer=layer_idx)

        return positions

    def _calculate_diff(
        self,
        prev_graph: TopologyGraph,
        curr_graph: TopologyGraph,
    ) -> TopologyDiff:
        """Calculate difference between two topology graphs."""
        prev_node_ids = {n.id for n in prev_graph.nodes}
        curr_node_ids = {n.id for n in curr_graph.nodes}

        prev_edge_ids = {e.id for e in prev_graph.edges}
        curr_edge_ids = {e.id for e in curr_graph.edges}

        # Create lookup for comparison
        prev_nodes = {n.id: n for n in prev_graph.nodes}
        curr_nodes = {n.id: n for n in curr_graph.nodes}

        # Find modified nodes (same ID but different data)
        modified = []
        for node_id in prev_node_ids & curr_node_ids:
            if prev_nodes[node_id].data != curr_nodes[node_id].data:
                modified.append(node_id)

        return TopologyDiff(
            nodes_added=list(curr_node_ids - prev_node_ids),
            nodes_removed=list(prev_node_ids - curr_node_ids),
            nodes_modified=modified,
            edges_added=list(curr_edge_ids - prev_edge_ids),
            edges_removed=list(prev_edge_ids - curr_edge_ids),
        )

    def _format_topology(self, doc: dict, include_graph: bool = True) -> dict:
        """Format a topology document for API response."""
        result = {
            "topologyId": doc["topologyId"],
            "mode": doc["mode"],
            "version": doc["version"],
            "scope": doc.get("scope"),
            "generatedAt": doc["generatedAt"],
            "validFrom": doc["validFrom"],
            "validUntil": doc.get("validUntil"),
            "stats": doc.get("stats", {}),
            "previousTopologyId": doc.get("previousTopologyId"),
            "diff": doc.get("diff"),
        }

        if include_graph:
            result["graph"] = doc.get("graph")

        return result

    def _format_topology_summary(self, doc: dict) -> dict:
        """Format a topology document for list response."""
        return {
            "topologyId": doc["topologyId"],
            "mode": doc["mode"],
            "version": doc["version"],
            "generatedAt": doc["generatedAt"],
            "validFrom": doc["validFrom"],
            "validUntil": doc.get("validUntil"),
            "stats": doc.get("stats", {}),
        }
