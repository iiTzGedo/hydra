"""Profile models for request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hydra.api.v1.core.validators import (
    IPV4_PATTERN,
    PROFILE_VERSION_PATTERN,
    validate_ipv4,
    validate_profile_version,
)


class CollectionLevel(str, Enum):
    """Profile collection depth level."""

    SHALLOW = "shallow"
    NEUTRAL = "neutral"
    DEEP = "deep"


# Hardware Profile Components
class CpuInfo(BaseModel):
    """CPU information."""

    model_config = ConfigDict(populate_by_name=True)

    model: str | None = None
    vendor: str | None = None
    cores_physical: int | None = Field(default=None, alias="coresPhysical")
    cores_logical: int | None = Field(default=None, alias="coresLogical")
    frequency_mhz: int | None = Field(default=None, alias="frequencyMhz")
    architecture: str | None = None
    features: list[str] = Field(default_factory=list)


class MemoryInfo(BaseModel):
    """Memory information."""

    model_config = ConfigDict(populate_by_name=True)

    total_bytes: int | None = Field(default=None, alias="totalBytes")
    type: str | None = None
    speed_mhz: int | None = Field(default=None, alias="speedMhz")
    slots_used: int | None = Field(default=None, alias="slotsUsed")
    slots_total: int | None = Field(default=None, alias="slotsTotal")


class GpuInfo(BaseModel):
    """GPU information."""

    model_config = ConfigDict(populate_by_name=True)

    model: str | None = None
    vendor: str | None = None
    memory_bytes: int | None = Field(default=None, alias="memoryBytes")
    driver_version: str | None = Field(default=None, alias="driverVersion")


class HardwareProfile(BaseModel):
    """Hardware profile section."""

    model_config = ConfigDict(populate_by_name=True)

    system_manufacturer: str | None = Field(default=None, alias="systemManufacturer")
    system_model: str | None = Field(default=None, alias="systemModel")
    system_serial: str | None = Field(default=None, alias="systemSerial")
    bios_vendor: str | None = Field(default=None, alias="biosVendor")
    bios_version: str | None = Field(default=None, alias="biosVersion")
    cpu: CpuInfo | None = None
    memory: MemoryInfo | None = None
    gpus: list[GpuInfo] = Field(default_factory=list)


# Network Profile Components
class NetworkInterface(BaseModel):
    """Network interface information."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    mac_address: str | None = Field(default=None, alias="macAddress")
    ipv4_addresses: list[str] = Field(default_factory=list, alias="ipv4Addresses")
    ipv6_addresses: list[str] = Field(default_factory=list, alias="ipv6Addresses")
    netmask: str | None = None
    gateway: str | None = None
    mtu: int | None = None
    state: Literal["up", "down", "unknown"] = "unknown"
    type: str | None = None  # ethernet, wifi, bridge, etc.
    speed_mbps: int | None = Field(default=None, alias="speedMbps")

    @field_validator("ipv4_addresses")
    @classmethod
    def validate_ipv4_addresses(cls, v: list[str]) -> list[str]:
        for address in v:
            if not validate_ipv4(address):
                raise ValueError(
                    f"Invalid IPv4 address '{address}'. Must match pattern: {IPV4_PATTERN}"
                )
        return v


class NetworkRoute(BaseModel):
    """Network route."""

    model_config = ConfigDict(populate_by_name=True)

    destination: str
    gateway: str | None = None
    interface: str | None = None
    metric: int | None = None


class NetworkProfile(BaseModel):
    """Network profile section."""

    model_config = ConfigDict(populate_by_name=True)

    hostname: str | None = None
    domain: str | None = None
    fqdn: str | None = None
    interfaces: list[NetworkInterface] = Field(default_factory=list)
    dns_servers: list[str] = Field(default_factory=list, alias="dnsServers")
    dns_search: list[str] = Field(default_factory=list, alias="dnsSearch")
    default_gateway: str | None = Field(default=None, alias="defaultGateway")
    routes: list[NetworkRoute] = Field(default_factory=list)


# Storage Profile Components
class BlockDevice(BaseModel):
    """Block device information."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    type: str | None = None  # disk, partition, lvm, etc.
    model: str | None = None
    serial: str | None = None
    rotational: bool | None = None
    transport: str | None = None  # sata, nvme, usb, etc.


class Filesystem(BaseModel):
    """Filesystem information."""

    model_config = ConfigDict(populate_by_name=True)

    mount_point: str = Field(alias="mountPoint")
    device: str
    fs_type: str = Field(alias="fsType")
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    used_bytes: int | None = Field(default=None, alias="usedBytes")
    options: list[str] = Field(default_factory=list)


class StorageProfile(BaseModel):
    """Storage profile section."""

    model_config = ConfigDict(populate_by_name=True)

    block_devices: list[BlockDevice] = Field(default_factory=list, alias="blockDevices")
    filesystems: list[Filesystem] = Field(default_factory=list)
    total_capacity_bytes: int | None = Field(default=None, alias="totalCapacityBytes")


# Software Profile Components
class OsInfo(BaseModel):
    """Operating system information."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    version: str | None = None
    kernel_version: str | None = Field(default=None, alias="kernelVersion")
    architecture: str | None = None
    family: str | None = None  # linux, windows, darwin, bsd


class Package(BaseModel):
    """Installed package."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    version: str | None = None
    manager: str | None = None  # apt, yum, pacman, brew, etc.


class SoftwareProfile(BaseModel):
    """Software profile section."""

    model_config = ConfigDict(populate_by_name=True)

    os: OsInfo | None = None
    packages: list[Package] = Field(default_factory=list)
    package_count: int | None = Field(default=None, alias="packageCount")


# Service Components (for extraction)
class ServiceInfo(BaseModel):
    """Discovered service information."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    runtime: str  # systemd, docker, kubernetes, etc.
    status: str
    version: str | None = None
    image: str | None = None
    ports: list[dict] = Field(default_factory=list)
    endpoints: list[dict] = Field(default_factory=list)
    resources: dict = Field(default_factory=dict)
    attachments: dict = Field(default_factory=dict)


class ServicesProfile(BaseModel):
    """Services discovered on the node."""

    model_config = ConfigDict(populate_by_name=True)

    services: list[ServiceInfo] = Field(default_factory=list)


# User Profile Components
class UserInfo(BaseModel):
    """User account information."""

    model_config = ConfigDict(populate_by_name=True)

    username: str
    uid: int | None = None
    gid: int | None = None
    home: str | None = None
    shell: str | None = None
    groups: list[str] = Field(default_factory=list)


class SshKey(BaseModel):
    """SSH key information."""

    model_config = ConfigDict(populate_by_name=True)

    username: str
    key_type: str = Field(alias="keyType")
    fingerprint: str
    comment: str | None = None


class UsersProfile(BaseModel):
    """Users profile section."""

    model_config = ConfigDict(populate_by_name=True)

    users: list[UserInfo] = Field(default_factory=list)
    ssh_keys: list[SshKey] = Field(default_factory=list, alias="sshKeys")


# Config Profile Components
class ConfigFile(BaseModel):
    """Configuration file metadata."""

    model_config = ConfigDict(populate_by_name=True)

    path: str
    hash: str
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    modified_at: datetime | None = Field(default=None, alias="modifiedAt")


class ConfigsProfile(BaseModel):
    """Configuration files profile section."""

    model_config = ConfigDict(populate_by_name=True)

    files: list[ConfigFile] = Field(default_factory=list)


# Full Profile Request/Response
class ProfileSubmission(BaseModel):
    """Profile submission from agent."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="nodeId")
    version: str | None = Field(default=None, alias="version")
    collected_at: datetime = Field(alias="collectedAt")
    agent_version: str = Field(alias="agentVersion")
    collection_level: CollectionLevel = Field(default=CollectionLevel.NEUTRAL, alias="collectionLevel")
    hardware: HardwareProfile | None = None
    network: NetworkProfile | None = None
    storage: StorageProfile | None = None
    software: SoftwareProfile | None = None
    services: ServicesProfile | None = None
    users: UsersProfile | None = None
    configs: ConfigsProfile | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str | None) -> str | None:
        # Version is optional - API will calculate if not provided
        if v is not None and not validate_profile_version(v):
            raise ValueError(
                f"Invalid profile version format. Must match pattern: {PROFILE_VERSION_PATTERN}"
            )
        return v


class ProfileResponse(BaseModel):
    """Full profile response."""

    model_config = ConfigDict(populate_by_name=True)

    profile_id: str = Field(alias="profileId")
    node_id: str = Field(alias="nodeId")
    version: str
    collected_at: datetime = Field(alias="collectedAt")
    submitted_at: datetime = Field(alias="submittedAt")
    agent_version: str = Field(alias="agentVersion")
    collection_level: CollectionLevel = Field(alias="collectionLevel")
    service_ids: list[str] = Field(default_factory=list, alias="serviceIds")
    hardware: HardwareProfile | None = None
    network: NetworkProfile | None = None
    storage: StorageProfile | None = None
    software: SoftwareProfile | None = None
    users: UsersProfile | None = None
    configs: ConfigsProfile | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfileSummary(BaseModel):
    """Abbreviated profile for lists."""

    model_config = ConfigDict(populate_by_name=True)

    profile_id: str = Field(alias="profileId")
    node_id: str = Field(alias="nodeId")
    version: str
    collected_at: datetime = Field(alias="collectedAt")
    submitted_at: datetime = Field(alias="submittedAt")
    collection_level: CollectionLevel = Field(alias="collectionLevel")
    service_count: int = Field(default=0, alias="serviceCount")


class ProfileDiff(BaseModel):
    """Profile diff response."""

    model_config = ConfigDict(populate_by_name=True)

    from_version: str = Field(alias="fromVersion")
    to_version: str = Field(alias="toVersion")
    from_profile_id: str = Field(alias="fromProfileId")
    to_profile_id: str = Field(alias="toProfileId")
    changed_sections: list[str] = Field(alias="changedSections")
    change_summary: dict[str, Any] = Field(alias="changeSummary")
    diff_percentage: float = Field(alias="diffPercentage")
