"""Command execution enums."""

from enum import Enum


class CommandType(str, Enum):
    """Types of commands that can be executed."""

    METADATA = "metadata"
    SERVICE = "service"
    NODE = "node"
    AGENT = "agent"
    PACKAGE = "package"
    CONFIG = "config"
    SYSTEM = "system"
    CUSTOM = "custom"


class CommandStatus(str, Enum):
    """Status of a command in the execution pipeline."""

    PENDING = "pending"
    PENDING_CONFIRMATION = "pending_confirmation"
    REJECTED = "rejected"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class CommandSource(str, Enum):
    """Source of the command request."""

    WEB = "web"
    API = "api"
    MCP = "mcp"
    AUTOMATION = "automation"


class CommandExecutionMethod(str, Enum):
    """How a command was or will be executed."""

    AGENT_DIRECT = "agent-direct"
    AGENT_POLL = "agent-poll"
    INTEGRATION = "integration"


class DangerLevel(str, Enum):
    """Danger level classification for command safety controls.

    Determines the confirmation UX tier and rate-limiting behavior.
    """

    SAFE = "safe"          # Read-only (logs, inspect, status)
    LOW = "low"            # Non-destructive writes (IoT toggles, probe)
    MEDIUM = "medium"      # Service state changes (start, stop, restart)
    HIGH = "high"          # Destructive/impactful (reboot, agent update)
    CRITICAL = "critical"  # Potentially catastrophic (shutdown, update-system)


class ServiceAction(str, Enum):
    """Actions that can be performed on services."""

    START = "start"
    STOP = "stop"
    RESTART = "restart"
    RELOAD = "reload"
