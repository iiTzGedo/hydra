"""Time Machine models for historical state queries."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TimelineEventType(StrEnum):
    """Types of events in the timeline."""

    PROFILE_SUBMITTED = "profile_submitted"
    SERVICE_DISCOVERED = "service_discovered"
    SERVICE_REMOVED = "service_removed"
    TOPOLOGY_GENERATED = "topology_generated"
    NODE_REGISTERED = "node_registered"
    NODE_ARCHIVED = "node_archived"
    NETWORK_CREATED = "network_created"
    GROUP_CREATED = "group_created"


# Snapshot Models
class ClosestSnapshot(BaseModel):
    """Information about the closest available snapshot."""

    model_config = ConfigDict(populate_by_name=True)

    profile_at: datetime | None = Field(alias="profileAt")
    delta_minutes: int = Field(alias="deltaMinutes")


class NodeStateSnapshot(BaseModel):
    """Node state at a point in time."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="nodeId")
    display_name: str = Field(alias="displayName")
    node_class: str = Field(alias="class")
    node_type: str = Field(alias="type")
    kind: str | None = None
    status: str
    tags: list[str] = Field(default_factory=list)
    registered_at: datetime = Field(alias="registeredAt")


class ProfileStateSnapshot(BaseModel):
    """Profile state at a point in time."""

    model_config = ConfigDict(populate_by_name=True)

    profile_id: str = Field(alias="profileId")
    version: str
    submitted_at: datetime = Field(alias="submittedAt")
    hardware: dict[str, Any] | None = None
    network: dict[str, Any] | None = None
    storage: dict[str, Any] | None = None
    software: dict[str, Any] | None = None


class ServiceStateSnapshot(BaseModel):
    """Service state at a point in time."""

    model_config = ConfigDict(populate_by_name=True)

    service_id: str = Field(alias="serviceId")
    name: str
    runtime: str
    status: str
    version: str | None = None


# Response Models
class NodeTimeMachineState(BaseModel):
    """Reconstructed state for a node at a point in time."""

    model_config = ConfigDict(populate_by_name=True)

    node: NodeStateSnapshot | None = None
    profile: ProfileStateSnapshot | None = None
    services: list[ServiceStateSnapshot] = Field(default_factory=list)


class NodeTimeMachineResponse(BaseModel):
    """Response for node state at a point in time."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="nodeId")
    timestamp: datetime
    state: NodeTimeMachineState
    closest_snapshot: ClosestSnapshot = Field(alias="closestSnapshot")


class TopologyTimeMachineResponse(BaseModel):
    """Response for topology at a point in time."""

    model_config = ConfigDict(populate_by_name=True)

    topology_id: str = Field(alias="topologyId")
    timestamp: datetime
    mode: str
    version: int
    generated_at: datetime = Field(alias="generatedAt")
    graph: dict[str, Any] | None = None
    stats: dict[str, Any]
    note: str | None = None


# Timeline Models
class TimelineEvent(BaseModel):
    """An event in the infrastructure timeline."""

    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(alias="eventId")
    event_type: TimelineEventType = Field(alias="eventType")
    timestamp: datetime
    entity_type: str = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    """Response for timeline queries."""

    model_config = ConfigDict(populate_by_name=True)

    since: datetime
    until: datetime
    events: list[TimelineEvent]
    total: int
