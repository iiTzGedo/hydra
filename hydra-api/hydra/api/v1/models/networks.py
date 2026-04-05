"""Network models for request/response validation."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hydra.api.v1.core.validators import (
    CIDR_PATTERN,
    IPV4_PATTERN,
    NETWORK_ID_PATTERN,
    TAG_PATTERN,
    validate_cidr,
    validate_ipv4,
    validate_network_id,
    validate_tag,
)


class NetworkType(StrEnum):
    """Network type."""

    PHYSICAL = "physical"
    VIRTUAL = "virtual"
    OVERLAY = "overlay"
    VLAN = "vlan"
    VXLAN = "vxlan"
    BRIDGE = "bridge"
    TUNNEL = "tunnel"


class NetworkOriginType(StrEnum):
    """How the network was created."""

    AUTO = "auto"
    MANUAL = "manual"
    IMPORT = "import"


class DhcpConfig(BaseModel):
    """DHCP configuration."""

    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = False
    range_start: str | None = Field(default=None, alias="rangeStart")
    range_end: str | None = Field(default=None, alias="rangeEnd")
    server_node_id: str | None = Field(default=None, alias="serverNodeId")

    @field_validator("range_start", "range_end")
    @classmethod
    def validate_ranges(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not validate_ipv4(v):
            raise ValueError(f"Invalid IPv4 address. Must match pattern: {IPV4_PATTERN}")
        return v


class DnsConfig(BaseModel):
    """DNS configuration."""

    model_config = ConfigDict(populate_by_name=True)

    servers: list[str] = Field(default_factory=list)
    domain: str | None = None
    search_domains: list[str] = Field(default_factory=list, alias="searchDomains")


class NetworkOrigin(BaseModel):
    """Network origin metadata."""

    model_config = ConfigDict(populate_by_name=True)

    created_by: str = Field(alias="createdBy")
    source_node_id: str | None = Field(default=None, alias="sourceNodeId")
    source_profile_id: str | None = Field(default=None, alias="sourceProfileId")


class NetworkNodeInfo(BaseModel):
    """Node information within a network."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="nodeId")
    display_name: str = Field(alias="displayName")
    node_class: str = Field(alias="class")
    ip_addresses: list[str] = Field(default_factory=list, alias="ipAddresses")


class NetworkSubnetInfo(BaseModel):
    """Subnet information for network hierarchies."""

    model_config = ConfigDict(populate_by_name=True)

    network_id: str = Field(alias="networkId")
    name: str
    cidr: str | None = None


class NetworkResponse(BaseModel):
    """Full network response model."""

    model_config = ConfigDict(populate_by_name=True)

    network_id: str = Field(alias="networkId")
    type: NetworkType
    name: str
    description: str | None = None
    cidr: str | None = None
    cidr_v6: str | None = Field(default=None, alias="cidrV6")
    gateway_v4: str | None = Field(default=None, alias="gatewayV4")
    gateway_v6: str | None = Field(default=None, alias="gatewayV6")
    vlan_id: int | None = Field(default=None, alias="vlanId")
    parent_network_id: str | None = Field(default=None, alias="parentNetworkId")
    subnet_ids: list[str] = Field(default_factory=list, alias="subnetIds")
    router_node_id: str | None = Field(default=None, alias="routerNodeId")
    dhcp: DhcpConfig | None = None
    dns: DnsConfig | None = None
    node_count: int = Field(default=0, alias="nodeCount")
    origin: NetworkOrigin
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class NetworkSummary(BaseModel):
    """Abbreviated network response for lists."""

    model_config = ConfigDict(populate_by_name=True)

    network_id: str = Field(alias="networkId")
    type: NetworkType
    name: str
    cidr: str | None = None
    gateway_v4: str | None = Field(default=None, alias="gatewayV4")
    router_node_id: str | None = Field(default=None, alias="routerNodeId")
    node_count: int = Field(default=0, alias="nodeCount")
    tags: list[str] = Field(default_factory=list)


class CreateNetworkRequest(BaseModel):
    """Create network request."""

    model_config = ConfigDict(populate_by_name=True)

    network_id: str = Field(alias="networkId", min_length=3, max_length=64)
    type: NetworkType
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    cidr: str | None = None
    cidr_v6: str | None = Field(default=None, alias="cidrV6")
    gateway_v4: str | None = Field(default=None, alias="gatewayV4")
    gateway_v6: str | None = Field(default=None, alias="gatewayV6")
    vlan_id: int | None = Field(default=None, alias="vlanId", ge=1, le=4094)
    parent_network_id: str | None = Field(default=None, alias="parentNetworkId")
    router_node_id: str | None = Field(default=None, alias="routerNodeId")
    dhcp: DhcpConfig | None = None
    dns: DnsConfig | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("network_id")
    @classmethod
    def validate_network_id(cls, v: str) -> str:
        if not validate_network_id(v):
            raise ValueError(f"Network ID must match pattern: {NETWORK_ID_PATTERN}")
        return v

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not validate_cidr(v):
            raise ValueError(f"Invalid CIDR format. Must match pattern: {CIDR_PATTERN}")
        return v

    @field_validator("gateway_v4")
    @classmethod
    def validate_gateway_v4(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not validate_ipv4(v):
            raise ValueError(f"Invalid IPv4 address. Must match pattern: {IPV4_PATTERN}")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for tag in v:
                if not validate_tag(tag):
                    raise ValueError(
                        f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}"
                    )
        return v


class UpdateNetworkRequest(BaseModel):
    """Update network request."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    gateway_v4: str | None = Field(default=None, alias="gatewayV4")
    gateway_v6: str | None = Field(default=None, alias="gatewayV6")
    router_node_id: str | None = Field(default=None, alias="routerNodeId")
    dhcp: DhcpConfig | None = None
    dns: DnsConfig | None = None
    tags: list[str] | None = None

    @field_validator("gateway_v4")
    @classmethod
    def validate_gateway_v4(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not validate_ipv4(v):
            raise ValueError(f"Invalid IPv4 address. Must match pattern: {IPV4_PATTERN}")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for tag in v:
                if not validate_tag(tag):
                    raise ValueError(
                        f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}"
                    )
        return v


class NetworkListParams(BaseModel):
    """Query parameters for listing networks."""

    model_config = ConfigDict(populate_by_name=True)

    type: NetworkType | None = None
    parent_network_id: str | None = Field(default=None, alias="parentNetworkId")
    router_node_id: str | None = Field(default=None, alias="routerNodeId")
    cidr: str | None = None
    tags: list[str] | None = None

    search: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["networkId", "name", "createdAt", "updatedAt", "nodeCount"] = Field(
        default="updatedAt", alias="sortBy"
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not validate_cidr(v):
            raise ValueError(f"Invalid CIDR format. Must match pattern: {CIDR_PATTERN}")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for tag in v:
            if not validate_tag(tag):
                raise ValueError(f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}")
        return v
