"""Topology generation and management service."""

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from pymongo import DESCENDING

from hydra.api.v1.core.exceptions import TopologyNotFoundError, ValidationError
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.notifications import NotificationSource, NotificationType, SourceComponent
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.models.topologies import (
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
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class TopologiesService:
    """Service for topology generation and management."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_topology(self, topology_id: str, include_graph: bool = True) -> dict[str, Any]:
        """Retrieve a topology by its identifier.

        Args:
            topology_id: The unique topology identifier.
            include_graph: Whether to include the full graph data.

        Returns:
            The formatted topology document.

        Raises:
            TopologyNotFoundError: If no topology exists with the given ID.
        """
        topology = await self.db.topologies.find_one({"topologyId": topology_id})
        if not topology:
            raise TopologyNotFoundError(topology_id)
        return self._format_topology(topology, include_graph=include_graph)

    async def get_latest_topology(self, mode: TopologyMode, include_graph: bool = True) -> dict[str, Any]:
        """Get the most recent topology for a given mode.

        Args:
            mode: The topology mode (infrastructure, network, or service).
            include_graph: Whether to include the full graph data.

        Returns:
            The formatted topology document.

        Raises:
            ValidationError: If no topology exists for the given mode.
        """
        topology = await self.db.topologies.find_one(
            {"mode": mode.value, "validUntil": None},
            sort=[("generatedAt", DESCENDING)],
        )
        if not topology:
            topology = await self.db.topologies.find_one(
                {"mode": mode.value},
                sort=[("generatedAt", DESCENDING)],
            )
        if not topology:
            raise ValidationError(f"No topology found for mode '{mode.value}'")
        return self._format_topology(topology, include_graph=include_graph)

    async def list_topologies(self, params: TopologyListParams) -> tuple[list[dict[str, Any]], int]:
        """List topologies with filtering and pagination.

        Args:
            params: Filter and pagination parameters.

        Returns:
            Tuple of (topologies list, total count).
        """
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

    async def generate_topology(self, request: GenerateTopologyRequest) -> dict[str, Any]:
        """Generate a new topology graph.

        Args:
            request: Generation request with mode and scope.

        Returns:
            The generated topology document with graph and stats.
        """
        start_time = time.time()

        try:
            previous_id = await self._close_previous_topology(request.mode)

            if request.mode == TopologyMode.NETWORK:
                graph_nodes, graph_edges = await self._generate_network_topology(request.scope)
            elif request.mode == TopologyMode.SERVICE:
                graph_nodes, graph_edges = await self._generate_service_topology(request.scope)
            else:
                graph_nodes, graph_edges = await self._generate_infrastructure_topology(request.scope)

            positions = self._compute_layout(graph_nodes, graph_edges, request.mode)

            for node in graph_nodes:
                if node.id in positions:
                    node.position = positions[node.id]

            diff = None
            if previous_id:
                previous = await self.db.topologies.find_one({"topologyId": previous_id})
                if previous and previous.get("graph"):
                    diff = self._calculate_diff(
                        TopologyGraph(**previous["graph"]),
                        TopologyGraph(nodes=graph_nodes, edges=graph_edges),
                    )
        except Exception as exc:
            audit_id = await log_audit(
                action=AuditAction.CREATE,
                resource_type="topology",
                resource_id=f"topo-{request.mode.value}",
                actor_type="system",
                actor_id="topology_generator",
                success=False,
                details={
                    "mode": request.mode.value,
                    "error": str(exc),
                },
                error=str(exc),
            )
            safe_create_task(emit_notification(
                notification_type=NotificationType.TOPOLOGY_GENERATION_FAILED,
                source=NotificationSource(
                    component=SourceComponent.HYDRA_API,
                    service="topologies",
                ),
                title="Topology generation failed",
                message=f"Failed to generate {request.mode.value} topology: {exc}",
                details={
                    "mode": request.mode.value,
                    "error": str(exc),
                },
                audit_entry_id=audit_id,
            ))
            raise

        compute_time = int((time.time() - start_time) * 1000)
        version = await self._get_next_version(request.mode)

        now = datetime.now(UTC)
        topology_id = f"topo-{request.mode.value}-{now.strftime('%Y%m%dT%H%M%SZ')}"

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

        audit_id = await log_audit(
            action=AuditAction.CREATE,
            resource_type="topology",
            resource_id=topology_id,
            actor_type="system",
            actor_id="topology_generator",
            details={
                "mode": request.mode.value,
                "version": version,
                "nodeCount": len(graph_nodes),
                "edgeCount": len(graph_edges),
                "computeTimeMs": compute_time,
            },
        )
        safe_create_task(emit_notification(
            notification_type=NotificationType.TOPOLOGY_REGENERATED,
            source=NotificationSource(
                component=SourceComponent.HYDRA_API,
                service="topologies",
            ),
            title="Topology generated",
            message=f"Topology regenerated with {len(graph_nodes)} nodes",
            details={
                "topologyId": topology_id,
                "mode": request.mode.value,
                "version": version,
                "nodeCount": len(graph_nodes),
                "edgeCount": len(graph_edges),
                "computeTimeMs": compute_time,
            },
            audit_entry_id=audit_id,
        ))

        return self._format_topology(topology_doc)

    async def diff_topologies(
        self,
        from_id: str | None,
        to_id: str | None,
        mode: TopologyMode | None = None,
    ) -> dict[str, Any]:
        """Compare two topologies and compute their differences.

        Args:
            from_id: Source topology ID (or None to use second-to-last).
            to_id: Target topology ID (or None to use latest).
            mode: Topology mode (required if from_id is None).

        Returns:
            Diff result with summary and detailed changes.

        Raises:
            TopologyNotFoundError: If a specified topology does not exist.
            ValidationError: If insufficient topologies exist to compare.
        """
        if from_id:
            from_topo = await self.db.topologies.find_one({"topologyId": from_id})
            if not from_topo:
                raise TopologyNotFoundError(from_id)
        else:
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
            if not mode:
                mode = TopologyMode(from_topo["mode"])
            to_topo = await self.db.topologies.find_one(
                {"mode": mode.value},
                sort=[("generatedAt", DESCENDING)],
            )
            if not to_topo:
                raise ValidationError(f"No topology found for mode '{mode.value}'")

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

    async def get_subgraph(
        self,
        node_id: str,
        depth: int = 1,
        include_services: bool = True,
        include_networks: bool = True,
    ) -> dict[str, Any]:
        """Get a subgraph centered on a specific node.

        Args:
            node_id: The center node identifier.
            depth: Number of hops to include from center.
            include_services: Whether to include services on this node.
            include_networks: Whether to include networks this node belongs to.

        Returns:
            Subgraph containing center node and its neighbors.

        Raises:
            TopologyNotFoundError: If the center node does not exist.
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        visited_nodes: set[str] = set()

        center_node = await self.db.nodes.find_one({"nodeId": node_id})
        if not center_node:
            raise TopologyNotFoundError(f"Node '{node_id}' not found")

        center_graph_id = f"node::{node_id}"
        node_type = self._get_graph_node_type(center_node)
        nodes.append(GraphNode(
            id=center_graph_id,
            type=node_type,
            label=center_node.get("displayName", node_id),
            data={
                "nodeId": node_id,
                "class": center_node.get("class"),
                "type": center_node.get("type"),
                "kind": center_node.get("kind"),
                "status": center_node.get("status"),
                "isCenter": True,
            },
            position=GraphNodePosition(x=0, y=0, layer=0),
        ))
        visited_nodes.add(center_graph_id)

        if center_node.get("parentNodeId"):
            parent_id = center_node["parentNodeId"]
            parent_node = await self.db.nodes.find_one({"nodeId": parent_id})
            if parent_node:
                parent_graph_id = f"node::{parent_id}"
                if parent_graph_id not in visited_nodes:
                    nodes.append(GraphNode(
                        id=parent_graph_id,
                        type=self._get_graph_node_type(parent_node),
                        label=parent_node.get("displayName", parent_id),
                        data={
                            "nodeId": parent_id,
                            "class": parent_node.get("class"),
                            "type": parent_node.get("type"),
                            "kind": parent_node.get("kind"),
                            "status": parent_node.get("status"),
                        },
                        position=GraphNodePosition(x=0, y=-150, layer=-1),
                    ))
                    visited_nodes.add(parent_graph_id)
                edges.append(GraphEdge(
                    id=f"edge::{center_graph_id}::parent::{parent_graph_id}",
                    source=center_graph_id,
                    target=parent_graph_id,
                    type="parent-child",
                ))

        child_cursor = self.db.nodes.find({"parentNodeId": node_id, "status": {"$ne": "archived"}})
        child_index = 0
        async for child in child_cursor:
            child_id = child["nodeId"]
            child_graph_id = f"node::{child_id}"
            if child_graph_id not in visited_nodes:
                nodes.append(GraphNode(
                    id=child_graph_id,
                    type=self._get_graph_node_type(child),
                    label=child.get("displayName", child_id),
                    data={
                        "nodeId": child_id,
                        "class": child.get("class"),
                        "type": child.get("type"),
                        "kind": child.get("kind"),
                        "status": child.get("status"),
                    },
                    position=GraphNodePosition(x=-200 + (child_index * 150), y=150, layer=1),
                ))
                visited_nodes.add(child_graph_id)
                child_index += 1
            edges.append(GraphEdge(
                id=f"edge::{child_graph_id}::parent::{center_graph_id}",
                source=child_graph_id,
                target=center_graph_id,
                type="parent-child",
            ))

        if include_services:
            service_cursor = self.db.services.find({"nodeId": node_id, "status": {"$ne": "archived"}})
            service_index = 0
            async for service in service_cursor:
                service_id = service["serviceId"]
                nodes.append(GraphNode(
                    id=service_id,
                    type="service",
                    label=service.get("displayName", service["name"]),
                    data={
                        "serviceId": service_id,
                        "name": service.get("name"),
                        "runtime": service.get("runtime"),
                        "status": service.get("status"),
                        "nodeId": node_id,
                    },
                    position=GraphNodePosition(x=200, y=-100 + (service_index * 80), layer=1),
                ))
                edges.append(GraphEdge(
                    id=f"edge::{service_id}::host::{center_graph_id}",
                    source=service_id,
                    target=center_graph_id,
                    type="service-host",
                ))
                service_index += 1

        if include_networks:
            network_ids = center_node.get("networkIds", [])
            if network_ids:
                network_cursor = self.db.networks.find({"networkId": {"$in": network_ids}})
                network_index = 0
                async for network in network_cursor:
                    network_id = network["networkId"]
                    network_graph_id = f"net::{network_id}"
                    if network_graph_id not in visited_nodes:
                        nodes.append(GraphNode(
                            id=network_graph_id,
                            type="network",
                            label=network.get("name", network_id),
                            data={
                                "networkId": network_id,
                                "cidr": network.get("cidr"),
                                "type": network.get("type"),
                            },
                            position=GraphNodePosition(x=-200, y=-100 + (network_index * 80), layer=1),
                        ))
                        visited_nodes.add(network_graph_id)
                        network_index += 1
                    edges.append(GraphEdge(
                        id=f"edge::{center_graph_id}::net::{network_graph_id}",
                        source=center_graph_id,
                        target=network_graph_id,
                        type="network-connection",
                    ))

        return {
            "centerNodeId": node_id,
            "depth": depth,
            "graph": {
                "nodes": [n.model_dump() for n in nodes],
                "edges": [e.model_dump() for e in edges],
            },
            "stats": {
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
                "serviceCount": sum(1 for n in nodes if n.type == "service"),
                "networkCount": sum(1 for n in nodes if n.type == "network"),
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
                {"$set": {"validUntil": datetime.now(UTC)}},
            )
            return previous["topologyId"]  # type: ignore[no-any-return]
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
        """Generate network-centric topology with nodes grouped by network."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

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

        node_filter: dict[str, Any] = {"status": {"$ne": "archived"}}
        if scope and scope.node_ids:
            node_filter["nodeId"] = {"$in": scope.node_ids}

        async for node in self.db.nodes.find(node_filter):
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

            for network_id in node.get("networkIds", []):
                edges.append(GraphEdge(
                    id=f"edge::node::{node['nodeId']}::net::{network_id}",
                    source=f"node::{node['nodeId']}",
                    target=f"net::{network_id}",
                    type="network-connection",
                ))

        for network in networks:
            if network.get("routerNodeId"):
                edges.append(GraphEdge(
                    id=f"edge::net::{network['networkId']}::router::{network['routerNodeId']}",
                    source=f"net::{network['networkId']}",
                    target=f"node::{network['routerNodeId']}",
                    type="network-gateway",
                ))

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
        """Generate infrastructure topology with parent-child and service relationships."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        node_filter: dict[str, Any] = {"status": {"$ne": "archived"}}
        if scope and scope.node_ids:
            node_filter["nodeId"] = {"$in": scope.node_ids}

        async for node in self.db.nodes.find(node_filter):
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

            if node.get("parentNodeId"):
                edges.append(GraphEdge(
                    id=f"edge::node::{node['nodeId']}::parent::{node['parentNodeId']}",
                    source=f"node::{node['nodeId']}",
                    target=f"node::{node['parentNodeId']}",
                    type="parent-child",
                ))

        service_filter: dict[str, Any] = {"status": {"$ne": "archived"}}
        if scope and scope.node_ids:
            service_filter["nodeId"] = {"$in": scope.node_ids}

        async for service in self.db.services.find(service_filter):
            service_id = service["serviceId"]
            nodes.append(GraphNode(
                id=service_id,
                type="service",
                label=service.get("displayName", service["name"]),
                data={
                    "serviceId": service_id,
                    "runtime": service.get("runtime"),
                    "status": service.get("status"),
                    "nodeId": service["nodeId"],
                },
                position=GraphNodePosition(x=0, y=0),
            ))

            edges.append(GraphEdge(
                id=f"edge::{service_id}::host::{service['nodeId']}",
                source=service_id,
                target=f"node::{service['nodeId']}",
                type="service-host",
            ))

        return nodes, edges

    async def _generate_service_topology(
        self,
        scope: TopologyScope | None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Generate service-centric topology with host nodes and dependencies."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        node_ids_added: set[str] = set()

        service_filter: dict[str, Any] = {"status": {"$ne": "archived"}}
        if scope and scope.node_ids:
            service_filter["nodeId"] = {"$in": scope.node_ids}

        services_list = []
        async for service in self.db.services.find(service_filter):
            services_list.append(service)
            service_id = service["serviceId"]

            nodes.append(GraphNode(
                id=service_id,
                type="service",
                label=service.get("displayName", service["name"]),
                data={
                    "serviceId": service_id,
                    "name": service.get("name"),
                    "runtime": service.get("runtime"),
                    "status": service.get("status"),
                    "nodeId": service["nodeId"],
                    "ports": service.get("ports", []),
                },
                position=GraphNodePosition(x=0, y=0),
            ))

            node_ids_added.add(service["nodeId"])

        if node_ids_added:
            node_filter: dict[str, Any] = {
                "nodeId": {"$in": list(node_ids_added)},
                "status": {"$ne": "archived"}
            }

            async for node in self.db.nodes.find(node_filter):
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

        for service in services_list:
            edges.append(GraphEdge(
                id=f"edge::{service['serviceId']}::host::{service['nodeId']}",
                source=service["serviceId"],
                target=f"node::{service['nodeId']}",
                type="service-host",
            ))

        service_deps = await self._discover_service_dependencies(services_list)
        for dep in service_deps:
            edges.append(GraphEdge(
                id=f"edge::{dep['source']}::depends::{dep['target']}",
                source=dep["source"],
                target=dep["target"],
                type="service-dependency",
                data={"dependencyType": dep.get("type", "unknown")},
            ))

        return nodes, edges

    async def _discover_service_dependencies(
        self,
        services: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Discover service-to-service dependencies based on configuration."""
        dependencies: list[dict[str, Any]] = []

        port_to_service: dict[int, str] = {}
        name_to_service: dict[str, str] = {}

        for service in services:
            name_to_service[service.get("name", "").lower()] = service["serviceId"]
            for port in service.get("ports", []):
                if isinstance(port, dict):
                    port_to_service[port.get("port", 0)] = service["serviceId"]
                elif isinstance(port, int):
                    port_to_service[port] = service["serviceId"]

        for service in services:
            service_id = service["serviceId"]
            env_vars = service.get("config", {}).get("environment", {})

            for key, value in env_vars.items() if isinstance(env_vars, dict) else []:
                value_str = str(value).lower()
                if any(db in key.upper() for db in ["DATABASE", "DB_HOST", "MONGO", "REDIS", "POSTGRES", "MYSQL"]):
                    for name, target_id in name_to_service.items():
                        if name in value_str and target_id != service_id:
                            dependencies.append({
                                "source": service_id,
                                "target": target_id,
                                "type": "database",
                            })
                            break

        return dependencies

    def _get_graph_node_type(self, node: dict[str, Any]) -> str:
        """Determine the graph node type based on node class and type."""
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
        """Compute layout positions for nodes based on topology mode."""
        if mode == TopologyMode.NETWORK:
            return self._circular_layout(nodes, edges)
        elif mode == TopologyMode.SERVICE:
            return self._service_layout(nodes, edges)
        else:
            return self._hierarchical_layout(nodes, edges)

    def _circular_layout(
        self,
        nodes: list[GraphNode],
        _edges: list[GraphEdge],
    ) -> dict[str, GraphNodePosition]:
        """Circular layout with networks in center and devices in outer ring."""
        import math

        positions: dict[str, GraphNodePosition] = {}

        networks = [n for n in nodes if n.type == "network"]
        devices = [n for n in nodes if n.type != "network"]

        network_radius = 100
        for i, net in enumerate(networks):
            angle = (2 * math.pi * i) / max(len(networks), 1)
            x = network_radius * math.cos(angle)
            y = network_radius * math.sin(angle)
            positions[net.id] = GraphNodePosition(x=x, y=y, layer=0)

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
        _edges: list[GraphEdge],
    ) -> dict[str, GraphNodePosition]:
        """Hierarchical layout with physical nodes at top, logical in middle, services at bottom."""
        positions: dict[str, GraphNodePosition] = {}

        layers: dict[int, list[GraphNode]] = {0: [], 1: [], 2: []}

        for node in nodes:
            if node.type in ["compute-physical", "networking"]:
                layers[0].append(node)
            elif node.type in ["compute-logical", "iot"]:
                layers[1].append(node)
            else:
                layers[2].append(node)

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

    def _service_layout(
        self,
        nodes: list[GraphNode],
        _edges: list[GraphEdge],
    ) -> dict[str, GraphNodePosition]:
        """Service-centric layout with hosts at top and services fanned below."""
        import math

        positions: dict[str, GraphNodePosition] = {}

        host_nodes = [n for n in nodes if n.type != "service"]
        services = [n for n in nodes if n.type == "service"]

        services_by_host: dict[str, list[GraphNode]] = {}
        for service in services:
            host_id = service.data.get("nodeId", "")
            if host_id:
                if host_id not in services_by_host:
                    services_by_host[host_id] = []
                services_by_host[host_id].append(service)

        host_spacing = 300
        total_host_width = len(host_nodes) * host_spacing
        start_x = -total_host_width / 2

        for i, host in enumerate(host_nodes):
            x = start_x + (i * host_spacing) + (host_spacing / 2)
            positions[host.id] = GraphNodePosition(x=x, y=0, layer=0)

            host_node_id = host.id.replace("node::", "")
            host_services = services_by_host.get(host_node_id, [])

            if host_services:
                service_radius = 150
                service_arc = math.pi
                for j, service in enumerate(host_services):
                    if len(host_services) == 1:
                        angle = math.pi / 2
                    else:
                        angle = (service_arc * j) / (len(host_services) - 1)
                    sx = x + service_radius * math.cos(angle)
                    sy = 100 + service_radius * math.sin(angle)
                    positions[service.id] = GraphNodePosition(x=sx, y=sy, layer=1)

        orphan_x = 0
        for service in services:
            if service.id not in positions:
                positions[service.id] = GraphNodePosition(x=orphan_x, y=300, layer=2)
                orphan_x += 100

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

        prev_nodes = {n.id: n for n in prev_graph.nodes}
        curr_nodes = {n.id: n for n in curr_graph.nodes}

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

    def _format_topology(self, doc: dict[str, Any], include_graph: bool = True) -> dict[str, Any]:
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

    def _format_topology_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
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
