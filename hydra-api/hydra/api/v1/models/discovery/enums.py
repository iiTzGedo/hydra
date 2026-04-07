"""Discovery-related enums."""

from enum import StrEnum


class ScanStatus(StrEnum):
    """Status of a network discovery scan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanMethod(StrEnum):
    """Network scanning methods."""

    ARP = "arp"
    TCP_PORT = "tcp_port"
    MDNS = "mdns"
    SSDP = "ssdp"
    SNMP = "snmp"


class DiscoveryStatus(StrEnum):
    """Status of a discovered device."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REGISTERED = "registered"
    DISMISSED = "dismissed"
