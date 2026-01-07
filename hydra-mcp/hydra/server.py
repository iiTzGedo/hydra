"""Hydra MCP Server implementation.

This module implements the Model Context Protocol server for Hydra,
exposing infrastructure data through tools, resources, and prompts.
"""

from datetime import datetime
from typing import Any

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    ReadResourceResult,
    Resource,
    TextContent,
    Tool,
)

from hydra.client import HydraAPIError, HydraClient
from hydra.config import get_settings
from hydra.toon import TOONFormatter

logger = structlog.get_logger(__name__)

# Initialize the MCP server
server = Server("hydra-mcp")
settings = get_settings()
client = HydraClient(settings)
toon = TOONFormatter(
    delimiter=settings.toon_delimiter,
    indent=settings.toon_indent,
    length_marker=settings.toon_length_marker,
)


# ==================== Tools ====================


@server.list_tools()
async def list_tools() -> ListToolsResult:
    """List all available tools."""
    tools = [
        Tool(
            name="list_nodes",
            description="List infrastructure nodes with optional filters",
            inputSchema={
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
                    "limit": {
                        "type": "integer",
                        "default": 50,
                        "description": "Maximum results",
                    },
                },
            },
        ),
        Tool(
            name="get_node",
            description="Get detailed information about a specific node",
            inputSchema={
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
        ),
        Tool(
            name="get_node_profile",
            description="Get the latest profile for a node with hardware, network, storage details",
            inputSchema={
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
        ),
        Tool(
            name="list_services",
            description="List services across the infrastructure",
            inputSchema={
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
        ),
        Tool(
            name="get_service",
            description="Get detailed information about a specific service",
            inputSchema={
                "type": "object",
                "properties": {
                    "serviceId": {
                        "type": "string",
                        "description": "The service ID (e.g., svc-nginx-a1b2)",
                    },
                },
                "required": ["serviceId"],
            },
        ),
        Tool(
            name="list_groups",
            description="List logical groups",
            inputSchema={
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
        ),
        Tool(
            name="get_group",
            description="Get group details with optional member resolution",
            inputSchema={
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
        ),
        Tool(
            name="list_networks",
            description="List networks",
            inputSchema={
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
        ),
        Tool(
            name="get_network",
            description="Get network details",
            inputSchema={
                "type": "object",
                "properties": {
                    "networkId": {
                        "type": "string",
                        "description": "The network ID",
                    },
                    "includeNodes": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include nodes in network",
                    },
                },
                "required": ["networkId"],
            },
        ),
        Tool(
            name="get_topology",
            description="Get the current infrastructure or network topology graph",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["network", "infrastructure"],
                        "default": "network",
                        "description": "Topology mode",
                    },
                    "scope": {
                        "type": "object",
                        "description": "Optional scope filter",
                    },
                },
            },
        ),
        Tool(
            name="search_infrastructure",
            description="Search across nodes, services, and other entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Entity types to search",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="compare_profiles",
            description="Compare two profiles to see what changed",
            inputSchema={
                "type": "object",
                "properties": {
                    "nodeId": {
                        "type": "string",
                        "description": "The node ID",
                    },
                    "fromVersion": {
                        "type": "string",
                        "description": "From version (default: previous)",
                    },
                    "toVersion": {
                        "type": "string",
                        "description": "To version (default: latest)",
                    },
                },
                "required": ["nodeId"],
            },
        ),
        Tool(
            name="get_capacity",
            description="Get infrastructure capacity summary",
            inputSchema={
                "type": "object",
                "properties": {
                    "groupBy": {
                        "type": "string",
                        "enum": ["node", "class", "location", "network", "group"],
                        "description": "Group results by",
                    },
                    "includeLogical": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include logical nodes (may double-count)",
                    },
                },
            },
        ),
        Tool(
            name="time_machine_node",
            description="Get a node's state at a specific point in time",
            inputSchema={
                "type": "object",
                "properties": {
                    "nodeId": {
                        "type": "string",
                        "description": "The node ID",
                    },
                    "timestamp": {
                        "type": "string",
                        "description": "ISO 8601 timestamp",
                    },
                },
                "required": ["nodeId", "timestamp"],
            },
        ),
        Tool(
            name="time_machine_topology",
            description="Get the topology at a specific point in time",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["network", "infrastructure"],
                        "description": "Topology mode",
                    },
                    "timestamp": {
                        "type": "string",
                        "description": "ISO 8601 timestamp",
                    },
                },
                "required": ["mode", "timestamp"],
            },
        ),
        Tool(
            name="query_infrastructure",
            description="Execute a raw query against infrastructure data",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "enum": ["nodes", "profiles", "services", "groups", "networks"],
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
        ),
        Tool(
            name="control_service",
            description="Control a service (start, stop, restart)",
            inputSchema={
                "type": "object",
                "properties": {
                    "serviceId": {
                        "type": "string",
                        "description": "The service ID",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "restart", "reload"],
                        "description": "Action to perform",
                    },
                },
                "required": ["serviceId", "action"],
            },
        ),
        Tool(
            name="control_device",
            description="Control an IoT device via Home Assistant",
            inputSchema={
                "type": "object",
                "properties": {
                    "entityId": {
                        "type": "string",
                        "description": "Home Assistant entity ID",
                    },
                    "service": {
                        "type": "string",
                        "description": "Service to call (e.g., turn_on, set_temperature)",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Service parameters",
                    },
                },
                "required": ["entityId", "service"],
            },
        ),
    ]
    return ListToolsResult(tools=tools)


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Handle tool calls."""
    try:
        result = await _execute_tool(name, arguments)
        return CallToolResult(content=[TextContent(type="text", text=result)])
    except HydraAPIError as e:
        error_text = toon.format_error(e.code, e.message, e.details)
        return CallToolResult(content=[TextContent(type="text", text=error_text)], isError=True)
    except Exception as e:
        logger.exception("tool_execution_error", tool=name, error=str(e))
        error_text = toon.format_error("TOOL_ERROR", str(e))
        return CallToolResult(content=[TextContent(type="text", text=error_text)], isError=True)


async def _execute_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a tool and return TOON-formatted result."""
    if name == "list_nodes":
        nodes, _ = await client.list_nodes(
            node_class=args.get("class"),
            node_type=args.get("type"),
            status=args.get("status"),
            tags=args.get("tags"),
            limit=args.get("limit", 50),
        )
        return toon.format({"nodes": nodes if isinstance(nodes, list) else []})

    elif name == "get_node":
        node = await client.get_node(
            args["nodeId"],
            include_children=args.get("includeChildren", True),
            include_services=args.get("includeServices", True),
        )
        return toon.format(node)

    elif name == "get_node_profile":
        profile = await client.get_node_profile(
            args["nodeId"],
            sections=args.get("sections"),
        )
        return toon.format(profile)

    elif name == "list_services":
        services, _ = await client.list_services(
            node_id=args.get("nodeId"),
            runtime=args.get("runtime"),
            status=args.get("status"),
            limit=args.get("limit", 50),
        )
        return toon.format({"services": services if isinstance(services, list) else []})

    elif name == "get_service":
        service = await client.get_service(args["serviceId"])
        return toon.format(service)

    elif name == "list_groups":
        groups, _ = await client.list_groups(
            types=args.get("types"),
            tags=args.get("tags"),
            limit=args.get("limit", 50),
        )
        return toon.format({"groups": groups if isinstance(groups, list) else []})

    elif name == "get_group":
        group = await client.get_group(
            args["groupId"],
            resolve_members=args.get("resolveMembers", False),
        )
        return toon.format(group)

    elif name == "list_networks":
        networks, _ = await client.list_networks(
            network_type=args.get("type"),
            limit=args.get("limit", 50),
        )
        return toon.format({"networks": networks if isinstance(networks, list) else []})

    elif name == "get_network":
        network = await client.get_network(
            args["networkId"],
            include_nodes=args.get("includeNodes", False),
        )
        return toon.format(network)

    elif name == "get_topology":
        topology = await client.get_topology(
            mode=args.get("mode", "network"),
            scope=args.get("scope"),
        )
        return toon.format(topology)

    elif name == "search_infrastructure":
        results = await client.search(
            query=args["query"],
            types=args.get("types"),
            limit=args.get("limit", 20),
        )
        return toon.format({"results": results})

    elif name == "compare_profiles":
        diff = await client.compare_profiles(
            args["nodeId"],
            from_version=args.get("fromVersion"),
            to_version=args.get("toVersion"),
        )
        return toon.format(diff)

    elif name == "get_capacity":
        capacity = await client.get_capacity(
            group_by=args.get("groupBy"),
            include_logical=args.get("includeLogical", False),
        )
        return toon.format(capacity)

    elif name == "time_machine_node":
        timestamp = datetime.fromisoformat(args["timestamp"].replace("Z", "+00:00"))
        state = await client.get_node_at_time(args["nodeId"], timestamp)
        return toon.format(state)

    elif name == "time_machine_topology":
        timestamp = datetime.fromisoformat(args["timestamp"].replace("Z", "+00:00"))
        topology = await client.get_topology_at_time(args["mode"], timestamp)
        return toon.format(topology)

    elif name == "query_infrastructure":
        result = await client.query(
            collection=args["collection"],
            filter_query=args.get("filter"),
            projection=args.get("projection"),
        )
        return toon.format(result)

    elif name == "control_service":
        # Fetch the service to get the node ID
        # Service ID format: svc-<name>-<hash>
        service = await client.get_service(args["serviceId"])
        if not service:
            raise ValueError(f"Service not found: {args['serviceId']}")

        result = await client.control_service(
            node_id=service.get("nodeId"),
            service_id=args["serviceId"],
            action=args["action"],
        )
        return toon.format(result)

    elif name == "control_device":
        result = await client.control_device(
            entity_id=args["entityId"],
            service=args["service"],
            data=args.get("parameters"),
        )
        return toon.format(result)

    else:
        raise ValueError(f"Unknown tool: {name}")


# ==================== Resources ====================


@server.list_resources()
async def list_resources() -> ListResourcesResult:
    """List available resources."""
    resources = [
        Resource(
            uri="infrastructure://overview",
            name="Infrastructure Overview",
            description="High-level summary of infrastructure status",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://nodes",
            name="All Nodes",
            description="List of all infrastructure nodes",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://services",
            name="All Services",
            description="List of all services",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://networks",
            name="All Networks",
            description="List of all networks",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://topology/network",
            name="Network Topology",
            description="Current network topology graph",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://topology/infrastructure",
            name="Infrastructure Topology",
            description="Current infrastructure topology graph",
            mimeType="text/plain",
        ),
    ]
    return ListResourcesResult(resources=resources)


@server.read_resource()
async def read_resource(uri: str) -> ReadResourceResult:
    """Read a resource."""
    try:
        content = await _read_resource(uri)
        return ReadResourceResult(contents=[TextContent(type="text", text=content)])
    except Exception as e:
        logger.exception("resource_read_error", uri=uri, error=str(e))
        return ReadResourceResult(contents=[TextContent(type="text", text=f"Error: {e}")])


async def _read_resource(uri: str) -> str:
    """Read a resource and return content."""
    if uri == "infrastructure://overview":
        info = await client.get_info()
        return toon.format(info)

    elif uri == "infrastructure://nodes":
        nodes, _ = await client.list_nodes(limit=200)
        return toon.format({"nodes": nodes if isinstance(nodes, list) else []})

    elif uri == "infrastructure://services":
        services, _ = await client.list_services(limit=200)
        return toon.format({"services": services if isinstance(services, list) else []})

    elif uri == "infrastructure://networks":
        networks, _ = await client.list_networks(limit=50)
        return toon.format({"networks": networks if isinstance(networks, list) else []})

    elif uri == "infrastructure://topology/network":
        topology = await client.get_topology(mode="network")
        return toon.format(topology)

    elif uri == "infrastructure://topology/infrastructure":
        topology = await client.get_topology(mode="infrastructure")
        return toon.format(topology)

    elif uri.startswith("infrastructure://node/"):
        node_id = uri.split("/")[-1]
        node = await client.get_node(node_id)
        return toon.format(node)

    elif uri.startswith("infrastructure://service/"):
        service_id = uri.split("/")[-1]
        service = await client.get_service(service_id)
        return toon.format(service)

    else:
        raise ValueError(f"Unknown resource: {uri}")


# ==================== Prompts ====================


@server.list_prompts()
async def list_prompts() -> ListPromptsResult:
    """List available prompts."""
    prompts = [
        Prompt(
            name="capacity_planning",
            description="Analyze infrastructure capacity for new workloads",
            arguments=[
                PromptArgument(
                    name="workload",
                    description="Description of the workload to plan for",
                    required=True,
                ),
                PromptArgument(
                    name="requirements",
                    description="Resource requirements (CPU, memory, storage)",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="troubleshoot_network",
            description="Diagnose network connectivity issues",
            arguments=[
                PromptArgument(
                    name="symptoms",
                    description="Description of the network issue",
                    required=True,
                ),
                PromptArgument(
                    name="affected_nodes",
                    description="Node IDs experiencing issues",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="infrastructure_audit",
            description="Security and configuration audit",
            arguments=[
                PromptArgument(
                    name="scope",
                    description="Scope of audit (all, compute, networking, iot)",
                    required=False,
                ),
                PromptArgument(
                    name="focus",
                    description="Specific focus area (security, compliance, performance)",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="service_dependency_map",
            description="Map dependencies between services",
            arguments=[
                PromptArgument(
                    name="service",
                    description="Service ID to analyze",
                    required=False,
                ),
                PromptArgument(
                    name="depth",
                    description="Dependency depth to explore",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="migration_planning",
            description="Plan infrastructure migration",
            arguments=[
                PromptArgument(
                    name="source",
                    description="Source node or group",
                    required=True,
                ),
                PromptArgument(
                    name="target",
                    description="Target node or environment",
                    required=True,
                ),
            ],
        ),
        Prompt(
            name="documentation_generator",
            description="Generate documentation for infrastructure entities",
            arguments=[
                PromptArgument(
                    name="entity_type",
                    description="Type of entity (node, service, network, group)",
                    required=True,
                ),
                PromptArgument(
                    name="entity_id",
                    description="Entity ID to document",
                    required=True,
                ),
            ],
        ),
    ]
    return ListPromptsResult(prompts=prompts)


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    """Get a prompt with context."""
    args = arguments or {}

    if name == "capacity_planning":
        capacity = await client.get_capacity()
        context = toon.format(capacity)

        return GetPromptResult(
            description="Analyze capacity for new workload",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Analyze the following infrastructure capacity to determine if it can support a new workload.

Current Capacity:
{context}

Workload Description: {args.get('workload', 'Not specified')}
Resource Requirements: {args.get('requirements', 'Not specified')}

Please provide:
1. Assessment of available resources
2. Recommended placement (which nodes)
3. Any concerns or limitations
4. Suggested optimizations if needed""",
                    ),
                )
            ],
        )

    elif name == "troubleshoot_network":
        networks, _ = await client.list_networks()
        topology = await client.get_topology(mode="network")

        return GetPromptResult(
            description="Diagnose network issues",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Help diagnose the following network issue.

Current Network Configuration:
{toon.format({"networks": networks if isinstance(networks, list) else []})}

Network Topology Summary:
{toon.format(topology)}

Symptoms: {args.get('symptoms', 'Not specified')}
Affected Nodes: {args.get('affected_nodes', 'Not specified')}

Please provide:
1. Likely causes based on the topology
2. Diagnostic steps to confirm
3. Recommended fixes
4. Prevention measures""",
                    ),
                )
            ],
        )

    elif name == "infrastructure_audit":
        nodes, _ = await client.list_nodes()
        services, _ = await client.list_services()

        return GetPromptResult(
            description="Infrastructure audit",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Perform an infrastructure audit with the following scope.

Nodes:
{toon.format({"nodes": nodes if isinstance(nodes, list) else []})}

Services:
{toon.format({"services": services if isinstance(services, list) else []})}

Scope: {args.get('scope', 'all')}
Focus: {args.get('focus', 'general')}

Please analyze:
1. Security considerations
2. Configuration issues
3. Resource utilization
4. Best practice deviations
5. Recommendations for improvement""",
                    ),
                )
            ],
        )

    elif name == "service_dependency_map":
        services, _ = await client.list_services()

        return GetPromptResult(
            description="Map service dependencies",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Map the dependencies between services.

Services:
{toon.format({"services": services if isinstance(services, list) else []})}

Target Service: {args.get('service', 'All services')}
Analysis Depth: {args.get('depth', 'Full')}

Please identify:
1. Service dependencies (upstream/downstream)
2. Potential single points of failure
3. Service communication patterns
4. Dependency chain risks""",
                    ),
                )
            ],
        )

    elif name == "migration_planning":
        source_id = args.get("source", "")
        target_id = args.get("target", "")

        try:
            source_node = await client.get_node(source_id)
            source_info = toon.format(source_node)
        except Exception:
            source_info = f"Source: {source_id} (details unavailable)"

        return GetPromptResult(
            description="Plan infrastructure migration",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Plan a migration between infrastructure components.

Source:
{source_info}

Target: {target_id}

Please provide:
1. Pre-migration checklist
2. Migration steps
3. Service dependencies to consider
4. Rollback plan
5. Verification steps
6. Estimated impact and downtime""",
                    ),
                )
            ],
        )

    elif name == "documentation_generator":
        entity_type = args.get("entity_type", "")
        entity_id = args.get("entity_id", "")

        if entity_type == "node":
            entity = await client.get_node(entity_id)
            entity_info = toon.format(entity)
        elif entity_type == "service":
            entity = await client.get_service(entity_id)
            entity_info = toon.format(entity)
        elif entity_type == "network":
            entity = await client.get_network(entity_id, include_nodes=True)
            entity_info = toon.format(entity)
        else:
            entity_info = f"Entity type '{entity_type}' not supported"

        return GetPromptResult(
            description="Generate documentation",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Generate comprehensive documentation for the following infrastructure entity.

Entity Information:
{entity_info}

Please create documentation including:
1. Overview and purpose
2. Technical specifications
3. Configuration details
4. Dependencies and relationships
5. Operational procedures
6. Troubleshooting guide
7. Maintenance schedule""",
                    ),
                )
            ],
        )

    else:
        raise ValueError(f"Unknown prompt: {name}")


# ==================== HTTP Transport ====================


def create_http_app():
    """Create FastAPI app for HTTP transport."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    http_app = FastAPI(
        title="Hydra MCP Server",
        description="MCP server for Hydra infrastructure management",
        version=settings.server_version,
    )

    # CORS middleware
    http_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class ToolCallRequest(BaseModel):
        name: str
        arguments: dict[str, Any] = {}

    class ToolCallResponse(BaseModel):
        content: str
        is_error: bool = False

    class ResourceReadRequest(BaseModel):
        uri: str

    @http_app.get("/health")
    async def health():
        """Health check endpoint."""
        tools_result = await list_tools()
        resources_result = await list_resources()
        return {
            "status": "healthy",
            "transport": "http",
            "server": settings.server_name,
            "version": settings.server_version,
            "tools": [t.name for t in tools_result.tools],
            "resources": [r.uri for r in resources_result.resources],
        }

    @http_app.get("/tools")
    async def get_tools():
        """List available tools."""
        result = await list_tools()
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                }
                for t in result.tools
            ]
        }

    @http_app.post("/tools/call")
    async def call_tool_http(request: ToolCallRequest):
        """Call a tool."""
        result = await call_tool(request.name, request.arguments)
        content = result.content[0].text if result.content else ""
        return ToolCallResponse(
            content=content,
            is_error=result.isError if hasattr(result, "isError") else False,
        )

    @http_app.get("/resources")
    async def get_resources():
        """List available resources."""
        result = await list_resources()
        return {
            "resources": [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mimeType,
                }
                for r in result.resources
            ]
        }

    @http_app.post("/resources/read")
    async def read_resource_http(request: ResourceReadRequest):
        """Read a resource."""
        result = await read_resource(request.uri)
        content = result.contents[0].text if result.contents else ""
        return {"content": content}

    @http_app.get("/prompts")
    async def get_prompts():
        """List available prompts."""
        result = await list_prompts()
        return {
            "prompts": [
                {
                    "name": p.name,
                    "description": p.description,
                    "arguments": [
                        {
                            "name": a.name,
                            "description": a.description,
                            "required": a.required,
                        }
                        for a in (p.arguments or [])
                    ],
                }
                for p in result.prompts
            ]
        }

    return http_app


# ==================== Server Entry Point ====================


async def run_stdio():
    """Run the MCP server with stdio transport."""
    logger.info(
        "starting_hydra_mcp_server",
        transport="stdio",
        version=settings.server_version,
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def run_http():
    """Run the MCP server with HTTP transport."""
    import uvicorn

    logger.info(
        "starting_hydra_mcp_server",
        transport="http",
        host=settings.http_host,
        port=settings.http_port,
        version=settings.server_version,
    )

    http_app = create_http_app()
    config = uvicorn.Config(
        http_app,
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
    )
    http_server = uvicorn.Server(config)
    await http_server.serve()


async def main(transport: str | None = None):
    """Run the MCP server with the specified transport."""
    transport = transport or settings.transport

    if transport == "http":
        await run_http()
    else:
        await run_stdio()


def run(transport: str | None = None):
    """Synchronous entry point for CLI."""
    import asyncio
    asyncio.run(main(transport))


if __name__ == "__main__":
    run()
