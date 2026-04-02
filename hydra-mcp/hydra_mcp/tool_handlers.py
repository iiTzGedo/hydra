"""
MCP Tool Handler Implementations.

This module registers all MCP tools using the tool registry pattern.
Each tool's schema and implementation are defined together.

Import this module to register all tools with the registry.
"""

from datetime import datetime
from typing import Any

import structlog

from hydra_mcp.tools import tool
from hydra_mcp.shared import client, toon, safe_list, format_list_response
from hydra_mcp import dependency_analyzer

logger = structlog.get_logger(__name__)

# Aliases for backward compatibility within this module
_safe_list = safe_list
_format_list_response = format_list_response


# =============================================================================
# Node Tools
# =============================================================================

@tool(
    name="list_nodes",
    description="List infrastructure nodes with optional filters",
    schema={
        "type": "object",
        "properties": {
            "class": {
                "type": "string",
                "enum": ["compute", "networking", "iot"],
                "description": "Filter by node class",
            },
            "type": {
                "type": "string",
                "enum": ["physical", "logical"],
                "description": "Filter by node type",
            },
            "status": {
                "type": "string",
                "enum": ["active", "inactive", "archived"],
                "description": "Filter by status",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by tags (AND logic)",
            },
            "agentTier": {
                "type": "string",
                "enum": ["lite", "normal", "max"],
                "description": "Filter by agent tier",
            },
            "limit": {
                "type": "integer",
                "default": 50,
                "description": "Maximum results",
            },
        },
    },
    required_permission="nodes:read",
)
async def list_nodes(args: dict[str, Any]) -> str:
    """List infrastructure nodes with optional filters."""
    nodes, _ = await client.list_nodes(
        node_class=args.get("class"),
        node_type=args.get("type"),
        status=args.get("status"),
        tags=args.get("tags"),
        agent_tier=args.get("agentTier"),
        limit=args.get("limit", 50),
    )
    return _format_list_response("nodes", nodes)


@tool(
    name="get_node",
    description="Get detailed information about a specific node",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {
                "type": "string",
                "description": "The node ID",
            },
            "includeChildren": {
                "type": "boolean",
                "default": True,
                "description": "Include child nodes",
            },
            "includeServices": {
                "type": "boolean",
                "default": True,
                "description": "Include services",
            },
        },
        "required": ["nodeId"],
    },
    required_permission="nodes:read",
)
async def get_node(args: dict[str, Any]) -> str:
    """Get detailed information about a specific node."""
    node = await client.get_node(
        args["nodeId"],
        include_children=args.get("includeChildren", True),
        include_services=args.get("includeServices", True),
    )
    return toon.format(node)


@tool(
    name="get_node_profile",
    description="Get the latest profile for a node with hardware, network, storage details",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {
                "type": "string",
                "description": "The node ID",
            },
            "sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific sections to include (hardware, network, storage, software, configs)",
            },
        },
        "required": ["nodeId"],
    },
    required_permission="profiles:read",
)
async def get_node_profile(args: dict[str, Any]) -> str:
    """Get the latest profile for a node."""
    profile = await client.get_node_profile(
        args["nodeId"],
        sections=args.get("sections"),
    )
    return toon.format(profile)


# =============================================================================
# Service Tools
# =============================================================================

@tool(
    name="list_services",
    description="List services across the infrastructure",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {
                "type": "string",
                "description": "Filter by node",
            },
            "runtime": {
                "type": "string",
                "enum": ["systemd", "docker", "podman", "kubernetes"],
                "description": "Filter by runtime",
            },
            "status": {
                "type": "string",
                "enum": ["running", "stopped", "failed"],
                "description": "Filter by status",
            },
            "limit": {
                "type": "integer",
                "default": 50,
            },
        },
    },
    required_permission="services:read",
)
async def list_services(args: dict[str, Any]) -> str:
    """List services across the infrastructure."""
    services, _ = await client.list_services(
        node_id=args.get("nodeId"),
        runtime=args.get("runtime"),
        status=args.get("status"),
        limit=args.get("limit", 50),
    )
    return _format_list_response("services", services)


@tool(
    name="get_service",
    description="Get detailed information about a specific service",
    schema={
        "type": "object",
        "properties": {
            "serviceId": {
                "type": "string",
                "description": "The service ID (e.g., svc-nginx-a1b2)",
            },
        },
        "required": ["serviceId"],
    },
    required_permission="services:read",
)
async def get_service(args: dict[str, Any]) -> str:
    """Get detailed information about a specific service."""
    service = await client.get_service(args["serviceId"])
    return toon.format(service)


@tool(
    name="control_service",
    description="Control a service (start, stop, restart, reload, logs, inspect)",
    schema={
        "type": "object",
        "properties": {
            "serviceId": {
                "type": "string",
                "description": "The service ID",
            },
            "action": {
                "type": "string",
                "enum": ["start", "stop", "restart", "reload", "logs", "inspect"],
                "description": "Action to perform",
            },
            "parameters": {
                "type": "object",
                "description": "Optional parameters (e.g., {lines: 100} for logs)",
            },
        },
        "required": ["serviceId", "action"],
    },
    required_permission="commands:execute",
    internal_only=True,
)
async def control_service(args: dict[str, Any]) -> str:
    """Control a service (start, stop, restart, reload, logs, inspect)."""
    service = await client.get_service(args["serviceId"])
    if not service:
        raise ValueError(f"Service not found: {args['serviceId']}")

    result = await client.control_service(
        node_id=service.get("nodeId"),
        service_id=args["serviceId"],
        action=args["action"],
        parameters=args.get("parameters"),
    )
    return toon.format(result)


@tool(
    name="control_node",
    description="Control a node (reboot, shutdown, update system packages)",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {
                "type": "string",
                "description": "The node ID",
            },
            "action": {
                "type": "string",
                "enum": ["reboot", "shutdown", "update-system"],
                "description": "Action to perform",
            },
            "confirm": {
                "type": "boolean",
                "default": False,
                "description": "Confirm destructive action",
            },
        },
        "required": ["nodeId", "action"],
    },
    required_permission="commands:execute",
    internal_only=True,
)
async def control_node(args: dict[str, Any]) -> str:
    """Control a node (reboot, shutdown, update-system)."""
    result = await client.control_node(
        node_id=args["nodeId"],
        action=args["action"],
        parameters={"confirm": args.get("confirm", False)},
    )
    return toon.format(result)


@tool(
    name="control_agent",
    description="Control the Hydra agent on a node",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {
                "type": "string",
                "description": "The node ID",
            },
            "action": {
                "type": "string",
                "enum": ["restart", "update", "config-reload", "collect-now", "probe-network", "status"],
                "description": "Action to perform",
            },
        },
        "required": ["nodeId", "action"],
    },
    required_permission="commands:execute",
    internal_only=True,
)
async def control_agent(args: dict[str, Any]) -> str:
    """Control the Hydra agent on a node."""
    result = await client.control_agent(
        node_id=args["nodeId"],
        action=args["action"],
    )
    return toon.format(result)


@tool(
    name="get_command_status",
    description="Get the status and result of a command",
    schema={
        "type": "object",
        "properties": {
            "commandId": {
                "type": "string",
                "description": "The command ID",
            },
        },
        "required": ["commandId"],
    },
    required_permission="commands:read",
)
async def get_command_status(args: dict[str, Any]) -> str:
    """Get the status and result of a command."""
    result = await client.get_command_status(args["commandId"])
    return toon.format(result)


# =============================================================================
# Command Catalog & Queue Tools
# =============================================================================

@tool(
    name="list_command_catalog",
    description="List available commands from the command registry/catalog",
    schema={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["service", "node", "agent"],
                "description": "Filter by command category",
            },
        },
    },
    required_permission="commands:read",
)
async def list_command_catalog(args: dict[str, Any]) -> str:
    """List available commands from the command registry/catalog."""
    catalog = await client.list_command_catalog(category=args.get("category"))
    return _format_list_response("commandCatalog", _safe_list(catalog))


@tool(
    name="list_commands",
    description="List command execution history with optional filters",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {"type": "string", "description": "Filter by target node"},
            "status": {
                "type": "string",
                "enum": ["pending", "rejected", "queued", "executing", "completed", "failed", "timeout", "cancelled"],
                "description": "Filter by command status",
            },
            "limit": {"type": "integer", "default": 20, "description": "Maximum results"},
        },
    },
    required_permission="commands:read",
)
async def list_commands_tool(args: dict[str, Any]) -> str:
    """List command execution history with optional filters."""
    commands = await client.list_commands(
        node_id=args.get("nodeId"),
        status=args.get("status"),
        limit=args.get("limit", 20),
    )
    return _format_list_response("commands", _safe_list(commands))


@tool(
    name="get_queue_status",
    description="View the current command queue state and statistics",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {"type": "string", "description": "Filter queue by target node"},
        },
    },
    required_permission="commands:read",
)
async def get_queue_status(args: dict[str, Any]) -> str:
    """View the current command queue state and statistics."""
    result = await client.get_queue_status(node_id=args.get("nodeId"))
    return toon.format(result)


# =============================================================================
# Group Tools
# =============================================================================

@tool(
    name="list_groups",
    description="List logical groups",
    schema={
        "type": "object",
        "properties": {
            "types": {
                "type": "array",
                "items": {"type": "string", "enum": ["node", "service"]},
                "description": "Filter by group types",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by tags",
            },
            "limit": {
                "type": "integer",
                "default": 50,
            },
        },
    },
    required_permission="groups:read",
)
async def list_groups(args: dict[str, Any]) -> str:
    """List logical groups."""
    groups, _ = await client.list_groups(
        types=args.get("types"),
        tags=args.get("tags"),
        limit=args.get("limit", 50),
    )
    return _format_list_response("groups", groups)


@tool(
    name="get_group",
    description="Get group details with optional member resolution",
    schema={
        "type": "object",
        "properties": {
            "groupId": {
                "type": "string",
                "description": "The group ID",
            },
            "resolveMembers": {
                "type": "boolean",
                "default": False,
                "description": "Include resolved members",
            },
        },
        "required": ["groupId"],
    },
    required_permission="groups:read",
)
async def get_group(args: dict[str, Any]) -> str:
    """Get group details with optional member resolution."""
    group = await client.get_group(
        args["groupId"],
        resolve_members=args.get("resolveMembers", False),
    )
    return toon.format(group)


# =============================================================================
# Network Tools
# =============================================================================

@tool(
    name="list_networks",
    description="List networks",
    schema={
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["physical", "vlan", "overlay", "virtual"],
                "description": "Filter by network type",
            },
            "limit": {
                "type": "integer",
                "default": 50,
            },
        },
    },
    required_permission="networks:read",
)
async def list_networks(args: dict[str, Any]) -> str:
    """List networks."""
    networks, _ = await client.list_networks(
        network_type=args.get("type"),
        limit=args.get("limit", 50),
    )
    return _format_list_response("networks", networks)


@tool(
    name="get_network",
    description="Get network details",
    schema={
        "type": "object",
        "properties": {
            "networkId": {
                "type": "string",
                "description": "The network ID",
            },
            "includeNodes": {
                "type": "boolean",
                "default": False,
                "description": "Include nodes in this network",
            },
        },
        "required": ["networkId"],
    },
    required_permission="networks:read",
)
async def get_network(args: dict[str, Any]) -> str:
    """Get network details."""
    network = await client.get_network(
        args["networkId"],
        include_nodes=args.get("includeNodes", False),
    )
    return toon.format(network)


# =============================================================================
# Topology Tools
# =============================================================================

@tool(
    name="get_topology",
    description="Get infrastructure topology graph",
    schema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["network", "infrastructure", "service"],
                "default": "network",
                "description": "Topology view mode",
            },
            "scope": {
                "type": "string",
                "description": "Limit scope to specific group or network",
            },
        },
    },
    required_permission="topologies:read",
)
async def get_topology(args: dict[str, Any]) -> str:
    """Get infrastructure topology graph."""
    topology = await client.get_topology(
        mode=args.get("mode", "network"),
        scope=args.get("scope"),
    )
    return toon.format(topology)


# =============================================================================
# Search & Query Tools
# =============================================================================

@tool(
    name="search_infrastructure",
    description="Full-text search across infrastructure",
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "types": {
                "type": "array",
                "items": {"type": "string", "enum": ["node", "service", "network", "group"]},
                "description": "Entity types to search",
            },
            "limit": {
                "type": "integer",
                "default": 20,
            },
        },
        "required": ["query"],
    },
    required_permission="nodes:read",
)
async def search_infrastructure(args: dict[str, Any]) -> str:
    """Full-text search across infrastructure."""
    results = await client.search(
        query=args["query"],
        types=args.get("types"),
        limit=args.get("limit", 20),
    )
    return toon.format({"results": results})


@tool(
    name="query_infrastructure",
    description="Direct query against infrastructure data (admin only)",
    schema={
        "type": "object",
        "properties": {
            "collection": {
                "type": "string",
                "enum": ["nodes", "services", "profiles", "networks", "groups"],
                "description": "Collection to query",
            },
            "filter": {
                "type": "object",
                "description": "MongoDB-style filter",
            },
            "projection": {
                "type": "object",
                "description": "Fields to include/exclude",
            },
        },
        "required": ["collection"],
    },
    required_permission="*:*",
)
async def query_infrastructure(args: dict[str, Any]) -> str:
    """Direct query against infrastructure data (admin only)."""
    from hydra_mcp.query_sanitizer import BlockedOperatorError, sanitize_mongo_filter

    filter_query = args.get("filter")
    if filter_query:
        try:
            sanitize_mongo_filter(filter_query)
        except BlockedOperatorError as exc:
            return toon.format_error("VALIDATION_ERROR", str(exc))

    result = await client.query(
        collection=args["collection"],
        filter_query=filter_query,
        projection=args.get("projection"),
    )
    return toon.format(result)


# =============================================================================
# Profile & Comparison Tools
# =============================================================================

@tool(
    name="compare_profiles",
    description="Compare profiles to see changes over time",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {
                "type": "string",
                "description": "The node ID",
            },
            "fromVersion": {
                "type": "string",
                "description": "Starting version (default: previous)",
            },
            "toVersion": {
                "type": "string",
                "description": "Ending version (default: latest)",
            },
        },
        "required": ["nodeId"],
    },
    required_permission="profiles:read",
)
async def compare_profiles(args: dict[str, Any]) -> str:
    """Compare profiles to see changes over time."""
    diff = await client.compare_profiles(
        args["nodeId"],
        from_version=args.get("fromVersion"),
        to_version=args.get("toVersion"),
    )
    return toon.format(diff)


@tool(
    name="get_capacity",
    description="Get infrastructure capacity overview",
    schema={
        "type": "object",
        "properties": {
            "groupBy": {
                "type": "string",
                "enum": ["class", "type", "location", "network"],
                "description": "Group capacity by attribute",
            },
            "includeLogical": {
                "type": "boolean",
                "default": False,
                "description": "Include logical nodes in calculations",
            },
        },
    },
    required_permission="nodes:read",
)
async def get_capacity(args: dict[str, Any]) -> str:
    """Get infrastructure capacity overview."""
    capacity = await client.get_capacity(
        group_by=args.get("groupBy"),
        include_logical=args.get("includeLogical", False),
    )
    return toon.format(capacity)


# =============================================================================
# Time Machine Tools
# =============================================================================

@tool(
    name="time_machine_node",
    description="Get historical node state at a specific point in time",
    schema={
        "type": "object",
        "properties": {
            "nodeId": {
                "type": "string",
                "description": "The node ID",
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "ISO timestamp to query",
            },
        },
        "required": ["nodeId", "timestamp"],
    },
    required_permission="profiles:read",
)
async def time_machine_node(args: dict[str, Any]) -> str:
    """Get historical node state at a specific point in time."""
    timestamp = datetime.fromisoformat(args["timestamp"].replace("Z", "+00:00"))
    state = await client.get_node_at_time(args["nodeId"], timestamp)
    return toon.format(state)


@tool(
    name="time_machine_topology",
    description="Get historical topology at a specific point in time",
    schema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["network", "infrastructure", "service"],
                "description": "Topology mode",
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "ISO timestamp to query",
            },
        },
        "required": ["mode", "timestamp"],
    },
    required_permission="topologies:read",
)
async def time_machine_topology(args: dict[str, Any]) -> str:
    """Get historical topology at a specific point in time."""
    timestamp = datetime.fromisoformat(args["timestamp"].replace("Z", "+00:00"))
    topology = await client.get_topology_at_time(args["mode"], timestamp)
    return toon.format(topology)


# =============================================================================
# IoT / Home Assistant Tools
# =============================================================================

@tool(
    name="control_device",
    description="Control a Home Assistant device",
    schema={
        "type": "object",
        "properties": {
            "entityId": {
                "type": "string",
                "description": "Home Assistant entity ID (e.g., light.living_room)",
            },
            "service": {
                "type": "string",
                "description": "Service to call (e.g., turn_on, turn_off)",
            },
            "parameters": {
                "type": "object",
                "description": "Additional service parameters",
            },
        },
        "required": ["entityId", "service"],
    },
    required_permission="iot:control",
)
async def control_device(args: dict[str, Any]) -> str:
    """Control a Home Assistant device."""
    result = await client.control_device(
        entity_id=args["entityId"],
        service=args["service"],
        data=args.get("parameters"),
    )
    return toon.format(result)


# =============================================================================
# Service Dependency Map Tool
# =============================================================================

@tool(
    name="service_dependency_map",
    description="Analyze service dependencies and identify critical services",
    schema={
        "type": "object",
        "properties": {
            "serviceId": {
                "type": "string",
                "description": "Specific service to analyze (optional, analyzes all if not provided)",
            },
            "depth": {
                "type": "integer",
                "default": 3,
                "description": "How many levels of dependencies to traverse",
            },
            "includeNetworkAnalysis": {
                "type": "boolean",
                "default": True,
                "description": "Include network topology in dependency analysis",
            },
        },
    },
    required_permission="services:read",
)
async def service_dependency_map(args: dict[str, Any]) -> str:
    """Analyze service dependencies and identify critical services."""
    service_id = args.get("serviceId")
    include_network = args.get("includeNetworkAnalysis", True)

    if service_id:
        service = await client.get_service(service_id)
        services = [service] if service else []
    else:
        services, _ = await client.list_services(limit=200)
        if not isinstance(services, list):
            services = []

    # Build service entries and parse runtime-specific dependencies
    dep_map, service_deps, service_dependents = dependency_analyzer.build_service_entries(services)

    # Build cross-service dependency graph
    dependency_analyzer.build_dependency_graph(dep_map, service_dependents)

    # Identify critical services, isolated services, single points of failure
    dependency_analyzer.analyze_services(dep_map, service_deps, service_dependents)

    # Network communication pattern analysis
    if include_network:
        try:
            await client.get_topology(mode="network")
            dependency_analyzer.analyze_network_patterns(dep_map)
        except Exception as e:
            logger.warning("network_analysis_failed", error=str(e))

    return toon.format(dep_map)


# =============================================================================
# Notification Tools
# =============================================================================

@tool(
    name="list_notifications",
    description="List notifications with optional filtering by tier, status, source, and node. Returns notifications visible to the current user.",
    schema={
        "type": "object",
        "properties": {
            "tier": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "Filter by exact tier: 1=User(Blue), 2=System(Green), 3=Warning(Yellow), 4=High(Orange), 5=Critical(Red)",
            },
            "tierMin": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "Filter by minimum tier (inclusive). E.g. tierMin=3 returns Warning, High, and Critical.",
            },
            "status": {
                "type": "string",
                "enum": ["active", "resolved", "expired"],
                "description": "Filter by notification status. Defaults to 'active'.",
            },
            "source": {
                "type": "string",
                "enum": ["hydra-api", "hydra-agent", "hydra-mcp", "hydra-web", "system"],
                "description": "Filter by source component",
            },
            "nodeId": {
                "type": "string",
                "description": "Filter by originating node ID",
            },
            "type": {
                "type": "string",
                "description": "Filter by notification type (e.g. 'node_offline', 'service_crashed')",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "description": "Max results to return (default 50)",
            },
        },
    },
    required_permission="notifications:read",
)
async def list_notifications_tool(args: dict[str, Any]) -> str:
    """List notifications with filtering."""
    notifications, _ = await client.list_notifications(
        tier=args.get("tier"),
        tier_min=args.get("tierMin"),
        status=args.get("status"),
        source=args.get("source"),
        node_id=args.get("nodeId"),
        notification_type=args.get("type"),
        limit=args.get("limit", 50),
    )

    items = _safe_list(notifications)
    return _format_list_response("notifications", items)


@tool(
    name="get_notification_stats",
    description="Get aggregated notification statistics: total count, unread count, and breakdowns by tier, status, and source component.",
    schema={
        "type": "object",
        "properties": {},
    },
    required_permission="notifications:read",
)
async def get_notification_stats_tool(args: dict[str, Any]) -> str:
    """Get notification statistics."""
    stats = await client.get_notification_stats()
    return toon.format(stats)


# =============================================================================
# Audit Log Tools
# =============================================================================

@tool(
    name="list_audit_entries",
    description="List audit log entries with optional filtering by action, resource type, resource ID, actor, and time range. Returns a chronological record of write operations performed on the system.",
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Filter by action (e.g. 'create', 'update', 'delete')",
            },
            "resourceType": {
                "type": "string",
                "description": "Filter by resource type (e.g. 'node', 'service', 'group', 'network', 'user')",
            },
            "resourceId": {
                "type": "string",
                "description": "Filter by specific resource ID",
            },
            "actorId": {
                "type": "string",
                "description": "Filter by actor (user) ID who performed the action",
            },
            "since": {
                "type": "string",
                "format": "date-time",
                "description": "ISO timestamp for start of time range",
            },
            "until": {
                "type": "string",
                "format": "date-time",
                "description": "ISO timestamp for end of time range",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "description": "Max results to return (default 100)",
            },
            "offset": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of results to skip for pagination",
            },
        },
    },
    required_permission="audit:read",
)
async def list_audit_entries_tool(args: dict[str, Any]) -> str:
    """List audit log entries with optional filtering."""
    entries = await client.list_audit_entries(
        action=args.get("action"),
        resource_type=args.get("resourceType"),
        resource_id=args.get("resourceId"),
        actor_id=args.get("actorId"),
        since=args.get("since"),
        until=args.get("until"),
        limit=args.get("limit", 100),
        offset=args.get("offset", 0),
    )

    items = _safe_list(entries)
    return _format_list_response("auditEntries", items)


@tool(
    name="delete_audit_entries",
    description="Delete audit log entries within a specified time range. Both 'since' and 'until' are required to prevent accidental bulk deletion.",
    schema={
        "type": "object",
        "properties": {
            "since": {
                "type": "string",
                "format": "date-time",
                "description": "ISO timestamp for start of deletion range (required)",
            },
            "until": {
                "type": "string",
                "format": "date-time",
                "description": "ISO timestamp for end of deletion range (required)",
            },
        },
        "required": ["since", "until"],
    },
    required_permission="audit:delete",
)
async def delete_audit_entries_tool(args: dict[str, Any]) -> str:
    """Delete audit log entries within a time range."""
    result = await client.delete_audit_entries(
        since=args["since"],
        until=args["until"],
    )
    return toon.format(result)
