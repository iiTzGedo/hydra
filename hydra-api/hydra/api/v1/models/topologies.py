"""Topology models for request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TopologyMode(str, Enum):
    """Topology generation mode."""

    NETWORK = "network"
    INFRASTRUCTURE = "infrastructure"
    SERVICE = "service"


class GraphNodeType(str, Enum):
    """Types of nodes in the topology graph."""

    COMPUTE_PHYSICAL = "compute-physical"
    COMPUTE_LOGICAL = "compute-logical"
    NETWORKING = "networking"
    IOT = "iot"
    SERVICE = "service"
    NETWORK = "network"
    GROUP = "group"


class GraphEdgeType(str, Enum):
    """Types of edges in the topology graph."""

    NETWORK_CONNECTION = "network-connection"
    PARENT_CHILD = "parent-child"
    SERVICE_HOST = "service-host"
    SERVICE_DEPENDENCY = "service-dependency"
    NETWORK_GATEWAY = "network-gateway"
    VLAN_TRUNK = "vlan-trunk"
    GROUP_MEMBER = "group-member"


# Graph Components
class GraphNodePosition(BaseModel):
    """Position of a node in the graph visualization."""

    x: float
    y: float
    layer: int | None = None


class GraphNode(BaseModel):
    """A node in the topology graph."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    label: str
    data: dict[str, Any] = Field(default_factory=dict)
    position: GraphNodePosition


class GraphEdge(BaseModel):
    """An edge in the topology graph."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    source: str
    target: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class TopologyGraph(BaseModel):
    """The complete topology graph."""

    model_config = ConfigDict(populate_by_name=True)

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class TopologyStats(BaseModel):
    """Statistics about a topology."""

    model_config = ConfigDict(populate_by_name=True)

    node_count: int = Field(alias="nodeCount")
    edge_count: int = Field(alias="edgeCount")
    network_count: int = Field(default=0, alias="networkCount")
    service_count: int = Field(default=0, alias="serviceCount")
    compute_time_ms: int = Field(default=0, alias="computeTimeMs")


class TopologyScope(BaseModel):
    """Scope filter for topology generation."""

    model_config = ConfigDict(populate_by_name=True)

    network_ids: list[str] | None = Field(default=None, alias="networkIds")
    group_ids: list[str] | None = Field(default=None, alias="groupIds")
    node_ids: list[str] | None = Field(default=None, alias="nodeIds")


class TopologyDiff(BaseModel):
    """Difference between two topologies."""

    model_config = ConfigDict(populate_by_name=True)

    nodes_added: list[str] = Field(default_factory=list, alias="nodesAdded")
    nodes_removed: list[str] = Field(default_factory=list, alias="nodesRemoved")
    nodes_modified: list[str] = Field(default_factory=list, alias="nodesModified")
    edges_added: list[str] = Field(default_factory=list, alias="edgesAdded")
    edges_removed: list[str] = Field(default_factory=list, alias="edgesRemoved")


# Response Models
class TopologyResponse(BaseModel):
    """Full topology response model."""

    model_config = ConfigDict(populate_by_name=True)

    topology_id: str = Field(alias="topologyId")
    mode: TopologyMode
    version: int
    scope: TopologyScope | None = None
    generated_at: datetime = Field(alias="generatedAt")
    valid_from: datetime = Field(alias="validFrom")
    valid_until: datetime | None = Field(default=None, alias="validUntil")
    graph: TopologyGraph | None = None
    stats: TopologyStats
    previous_topology_id: str | None = Field(default=None, alias="previousTopologyId")
    diff: TopologyDiff | None = None


class TopologySummary(BaseModel):
    """Abbreviated topology response for lists."""

    model_config = ConfigDict(populate_by_name=True)

    topology_id: str = Field(alias="topologyId")
    mode: TopologyMode
    version: int
    generated_at: datetime = Field(alias="generatedAt")
    valid_from: datetime = Field(alias="validFrom")
    valid_until: datetime | None = Field(default=None, alias="validUntil")
    stats: TopologyStats


class TopologyDiffResponse(BaseModel):
    """Response for topology diff comparison."""

    model_config = ConfigDict(populate_by_name=True)

    from_topology: TopologySummary = Field(alias="from")
    to_topology: TopologySummary = Field(alias="to")
    diff: TopologyDiff
    summary: dict[str, int]


# Request Models
class GenerateTopologyRequest(BaseModel):
    """Request to generate a new topology."""

    model_config = ConfigDict(populate_by_name=True)

    mode: TopologyMode
    scope: TopologyScope | None = None


# Subgraph Response
class SubgraphStats(BaseModel):
    """Statistics about a subgraph."""

    model_config = ConfigDict(populate_by_name=True)

    node_count: int = Field(alias="nodeCount")
    edge_count: int = Field(alias="edgeCount")
    service_count: int = Field(default=0, alias="serviceCount")
    network_count: int = Field(default=0, alias="networkCount")


class SubgraphResponse(BaseModel):
    """Response for node-centric subgraph query."""

    model_config = ConfigDict(populate_by_name=True)

    center_node_id: str = Field(alias="centerNodeId")
    depth: int
    graph: TopologyGraph
    stats: SubgraphStats


# Query Parameters
class TopologyListParams(BaseModel):
    """Query parameters for listing topologies."""

    model_config = ConfigDict(populate_by_name=True)

    mode: TopologyMode | None = None
    since: datetime | None = None
    until: datetime | None = None

    # Pagination
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
