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
    INSTALLING = "installing"
    INSTALLED = "installed"
    DISMISSED = "dismissed"


class HostnameSource(StrEnum):
    """How a hostname was resolved for a discovered device."""

    DNS_REVERSE = "dns-reverse"
    MDNS = "mdns"
    NETBIOS = "netbios"
    SNMP = "snmp"
    HTTP_TITLE = "http-title"
    SSH_BANNER = "ssh-banner"


class ScanTrigger(StrEnum):
    """How a scan was triggered."""

    API = "api"
    WEB = "web"
    MCP = "mcp"


class ProfilingStrategy(StrEnum):
    """How a discovered device should be profiled after registration."""

    AGENT = "agent"
    SNMP = "snmp"
    INTEGRATION = "integration"
    HOMEASSISTANT = "homeassistant"
    MANUAL = "manual"
    NONE = "none"
