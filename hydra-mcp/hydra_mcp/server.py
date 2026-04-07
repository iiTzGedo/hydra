"""Hydra MCP Server implementation.

This module implements the Model Context Protocol server for Hydra,
exposing infrastructure data through tools, resources, and prompts.
"""

import json
from typing import Any, cast

import httpx
import structlog
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http import StreamableHTTPServerTransport
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
    TextResourceContents,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Import tool handlers to register them with the registry
import hydra_mcp.tool_handlers  # noqa: F401
from hydra_mcp.auth import (
    INTERNAL_CLIENT_ID_HEADER,
    INTERNAL_PERMISSIONS_HEADER,
    INTERNAL_REQUEST_HEADER,
    INTERNAL_ROLE_HEADER,
    INTERNAL_SECRET_HEADER,
    INTERNAL_USER_ID_HEADER,
    AuthorizationError,
    SourceRestrictionError,
    create_context_from_user_info,
    push_auth_context,
    reset_auth_context,
)
from hydra_mcp.client import HydraAPIError
from hydra_mcp.config import get_settings
from hydra_mcp.shared import client, format_list_response, safe_list, settings, toon
from hydra_mcp.tools import ToolValidationError, get_all_tools
from hydra_mcp.tools import execute_tool as registry_execute_tool

logger = structlog.get_logger(__name__)

# Aliases for backward compatibility within this module
_safe_list = safe_list
_format_list_response = format_list_response

server = Server("hydra-mcp")

# Write tools that should emit notifications on failure
_WRITE_TOOLS = {"control_service", "control_device", "control_node", "control_agent"}
_SAFE_API_ERROR_CODES = {"NOT_FOUND", "VALIDATION_ERROR"}
_GENERIC_AUTH_ERROR_MESSAGE = "Authentication failed for this MCP request"
_GENERIC_TOOL_ERROR_MESSAGE = "An internal error occurred while executing the tool"
_GENERIC_RESOURCE_ERROR_MESSAGE = "An internal error occurred while reading the resource"


def _parse_internal_permissions(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, str)]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_internal_context(headers: Any) -> Any | None:
    if headers.get(INTERNAL_REQUEST_HEADER, "").lower() not in {"1", "true", "yes"}:
        return None

    import hmac

    runtime_settings = get_settings()
    if not runtime_settings.internal_secret:
        raise PermissionError("Internal MCP request support is not configured")

    provided_secret = headers.get(INTERNAL_SECRET_HEADER, "")
    if not hmac.compare_digest(provided_secret, runtime_settings.internal_secret):
        raise PermissionError("Invalid internal request secret")

    user_id = headers.get(INTERNAL_USER_ID_HEADER)
    role = headers.get(INTERNAL_ROLE_HEADER)
    if not user_id or not role:
        raise PermissionError("Internal MCP requests must include user and role headers")

    permissions = _parse_internal_permissions(headers.get(INTERNAL_PERMISSIONS_HEADER))
    return create_context_from_user_info(
        {
            "userId": user_id,
            "role": role,
            "permissions": permissions,
            "type": "internal",
        },
        source_type="internal",
        client_id=headers.get(INTERNAL_CLIENT_ID_HEADER) or "hydra-api",
        metadata={
            "source": "hydra_internal",
            "forward_auth": {
                INTERNAL_REQUEST_HEADER: "true",
                INTERNAL_USER_ID_HEADER: user_id,
                INTERNAL_ROLE_HEADER: role,
                INTERNAL_PERMISSIONS_HEADER: json.dumps(permissions),
                INTERNAL_CLIENT_ID_HEADER: headers.get(INTERNAL_CLIENT_ID_HEADER) or "hydra-api",
                INTERNAL_SECRET_HEADER: runtime_settings.internal_secret,
            },
        },
    )


async def _build_external_context(headers: Any) -> Any | None:
    auth_headers: dict[str, str] = {}
    auth_source = "request_headers"

    authorization = headers.get("authorization")
    api_key = headers.get("x-api-key")
    if authorization:
        auth_headers["Authorization"] = authorization
    if api_key:
        auth_headers["X-API-Key"] = api_key

    if not auth_headers:
        if not settings.api_key:
            return None
        auth_headers["X-API-Key"] = settings.api_key
        auth_source = "server_api_key"

    async with httpx.AsyncClient(timeout=settings.api_timeout) as http_client:
        response = await http_client.get(
            f"{settings.api_url.rstrip('/')}/auth/me",
            headers=auth_headers,
        )

    if response.status_code in {401, 403}:
        raise PermissionError("Invalid MCP credentials")
    response.raise_for_status()
    user_info = response.json()
    return create_context_from_user_info(
        user_info,
        source_type="external",
        client_id=headers.get("x-client-id") or headers.get("user-agent") or settings.server_name,
        metadata={
            "source": auth_source,
            "forward_auth": auth_headers,
        },
    )


async def _build_request_auth_context(headers: Any) -> Any | None:
    internal_context = _build_internal_context(headers)
    if internal_context is not None:
        return internal_context
    return await _build_external_context(headers)


def _build_auth_error_response() -> JSONResponse:
    """Build a sanitized auth failure response for HTTP transports."""
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "UNAUTHORIZED",
                "message": _GENERIC_AUTH_ERROR_MESSAGE,
            }
        },
    )


def _map_hydra_api_error(
    error: HydraAPIError,
    *,
    fallback_code: str,
    fallback_message: str,
) -> tuple[str, str, dict[str, Any] | None]:
    """Map API errors to safe client-facing MCP responses."""
    if error.code in _SAFE_API_ERROR_CODES:
        return error.code, error.message, error.details

    if error.code in {"FORBIDDEN", "UNAUTHORIZED"}:
        return error.code, "The Hydra API rejected the request", None

    if error.code in {"CONNECTION_ERROR", "INVALID_RESPONSE"}:
        return fallback_code, fallback_message, None

    return fallback_code, fallback_message, None


def _build_text_resource_result(uri: str, text: str) -> ReadResourceResult:
    """Build a text resource response with a validated MCP resource payload."""
    return ReadResourceResult(
        contents=[
            TextResourceContents(
                uri=cast(Any, uri),
                mimeType="text/plain",
                text=text,
            )
        ]
    )


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Populate request-scoped auth context for HTTP-based MCP transports."""

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        try:
            context = await _build_request_auth_context(request.headers)
        except PermissionError:
            return _build_auth_error_response()
        except Exception as exc:
            logger.exception("auth_context_build_failed", error=str(exc))
            return _build_auth_error_response()

        token = push_auth_context(context)
        try:
            return await call_next(request)
        finally:
            reset_auth_context(token)


async def _emit_mcp_notification(
    event_type: str,
    title: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Fire-and-forget notification emission from MCP context.

    Attempts to use the Hydra API /agent/report endpoint. If the MCP
    client doesn't have agent-level auth, this will silently fail
    and log a warning instead.
    """
    try:
        await client._request(
            "POST",
            "/agent/report",
            json_data={
                "eventType": event_type,
                "title": title,
                "message": message,
                "details": details,
            },
        )
    except Exception:
        # MCP may not have agent auth — log instead
        logger.warning(
            "mcp_notification_emit_skipped",
            event_type=event_type,
            title=title,
            reason="MCP client may not have agent auth for /agent/report",
        )


@server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_tools() -> ListToolsResult:
    """List all available MCP tools for infrastructure management.

    Tools are registered via the tool registry pattern in tool_handlers.py.

    Returns:
        ListToolsResult containing tool definitions with schemas.
    """
    return ListToolsResult(tools=get_all_tools())


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Execute a tool call and return TOON-formatted results.

    Tool implementations are registered via the tool registry pattern
    in tool_handlers.py. Emits notifications on authorization denials
    and write tool failures.

    Args:
        name: The tool name to execute.
        arguments: Tool arguments as a dictionary.

    Returns:
        CallToolResult with TOON-formatted content or error details.
    """
    try:
        result = await registry_execute_tool(name, arguments)

        # Emit GREEN-tier notification for successful write tool execution (best-effort)
        if name in _WRITE_TOOLS:
            try:
                import asyncio
                asyncio.create_task(_emit_mcp_notification(
                    event_type="mcp_write_succeeded",
                    title=f"MCP write tool succeeded: {name}",
                    message=f"Tool '{name}' executed successfully",
                    details={"tool": name, "arguments": arguments},
                ))
            except Exception:
                pass

        return CallToolResult(content=[TextContent(type="text", text=result)])
    except ToolValidationError as e:
        logger.warning("tool_validation_failed", tool=name, errors=e.errors)
        error_text = toon.format_error(
            "VALIDATION_ERROR",
            str(e),
            {"tool": e.tool_name, "errors": e.errors},
        )
        return CallToolResult(content=[TextContent(type="text", text=error_text)], isError=True)
    except AuthorizationError as e:
        logger.warning("tool_authorization_denied", tool=name, permission=e.required_permission)

        # Emit ORANGE-tier notification for auth denial (best-effort)
        try:
            import asyncio
            asyncio.create_task(_emit_mcp_notification(
                event_type="mcp_auth_denied",
                title=f"MCP authorization denied: {name}",
                message=f"Tool '{name}' was denied due to missing permission '{e.required_permission}'",
                details={"tool": name, "requiredPermission": e.required_permission},
            ))
        except Exception:
            pass

        error_text = toon.format_error(
            "AUTHORIZATION_DENIED",
            e.message,
            {"tool": e.tool, "requiredPermission": e.required_permission},
        )
        return CallToolResult(content=[TextContent(type="text", text=error_text)], isError=True)
    except SourceRestrictionError as e:
        logger.warning("tool_source_restricted", tool=name, source="external")
        error_text = toon.format_error(
            "CLIENT_NOT_AUTHORIZED",
            e.message,
            {
                "tool": e.tool,
                "requestedAction": e.action,
                "guidance": e.context.get("guidance", ""),
                "alternativeActions": e.context.get("alternativeActions", []),
            },
        )
        return CallToolResult(content=[TextContent(type="text", text=error_text)], isError=True)
    except HydraAPIError as e:
        code, message, details = _map_hydra_api_error(
            e,
            fallback_code="TOOL_ERROR",
            fallback_message=_GENERIC_TOOL_ERROR_MESSAGE,
        )

        # Emit RED-tier notification for write tool failures (best-effort)
        if name in _WRITE_TOOLS:
            try:
                import asyncio
                asyncio.create_task(_emit_mcp_notification(
                    event_type="mcp_tool_write_failed",
                    title=f"MCP write tool failed: {name}",
                    message=f"Tool '{name}' failed: {message}",
                    details={"tool": name, "errorCode": code, "arguments": arguments},
                ))
            except Exception:
                pass

        error_text = toon.format_error(code, message, details)
        return CallToolResult(content=[TextContent(type="text", text=error_text)], isError=True)
    except Exception as e:
        logger.exception("tool_execution_error", tool=name, error=str(e))

        # Emit RED-tier notification for unexpected write tool errors (best-effort)
        if name in _WRITE_TOOLS:
            try:
                import asyncio
                asyncio.create_task(_emit_mcp_notification(
                    event_type="mcp_tool_write_failed",
                    title=f"MCP write tool error: {name}",
                    message=f"Tool '{name}' encountered an internal error",
                    details={"tool": name, "errorType": type(e).__name__},
                ))
            except Exception:
                pass

        error_text = toon.format_error("TOOL_ERROR", _GENERIC_TOOL_ERROR_MESSAGE)
        return CallToolResult(content=[TextContent(type="text", text=error_text)], isError=True)


@server.list_resources()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_resources() -> ListResourcesResult:
    """List available MCP resources for infrastructure data.

    Returns:
        ListResourcesResult containing resource definitions with URIs.
    """
    resources = [
        Resource(
            uri="infrastructure://overview",  # type: ignore[arg-type]
            name="Infrastructure Overview",
            description="High-level summary of infrastructure status",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://nodes",  # type: ignore[arg-type]
            name="All Nodes",
            description="List of all infrastructure nodes",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://services",  # type: ignore[arg-type]
            name="All Services",
            description="List of all services",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://networks",  # type: ignore[arg-type]
            name="All Networks",
            description="List of all networks",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://topology/network",  # type: ignore[arg-type]
            name="Network Topology",
            description="Current network topology graph",
            mimeType="text/plain",
        ),
        Resource(
            uri="infrastructure://topology/infrastructure",  # type: ignore[arg-type]
            name="Infrastructure Topology",
            description="Current infrastructure topology graph",
            mimeType="text/plain",
        ),
    ]
    return ListResourcesResult(resources=resources)


@server.read_resource()  # type: ignore[no-untyped-call,untyped-decorator]
async def read_resource(uri: str) -> ReadResourceResult:
    """Read a resource and return its TOON-formatted content.

    Args:
        uri: The resource URI to read (e.g., infrastructure://nodes).

    Returns:
        ReadResourceResult with TOON-formatted content or error message.
    """
    try:
        content = await _read_resource(uri)
        return _build_text_resource_result(uri, content)
    except ValueError as e:
        logger.warning("resource_read_invalid_uri", uri=uri, error=str(e))
        error_text = toon.format_error("INVALID_RESOURCE", str(e))
        return _build_text_resource_result(uri, error_text)
    except HydraAPIError as e:
        logger.exception("resource_read_api_error", uri=uri, error=str(e), code=e.code)
        code, message, details = _map_hydra_api_error(
            e,
            fallback_code="RESOURCE_ERROR",
            fallback_message=_GENERIC_RESOURCE_ERROR_MESSAGE,
        )
        error_text = toon.format_error(code, message, details)
        return _build_text_resource_result(uri, error_text)
    except Exception as e:
        logger.exception("resource_read_error", uri=uri, error=str(e))
        error_text = toon.format_error("RESOURCE_ERROR", _GENERIC_RESOURCE_ERROR_MESSAGE)
        return _build_text_resource_result(uri, error_text)


async def _read_resource(uri: str) -> str:
    if uri == "infrastructure://overview":
        info = await client.get_info()
        return toon.format(info)

    elif uri == "infrastructure://nodes":
        nodes, _ = await client.list_nodes(limit=200)
        return _format_list_response("nodes", nodes)

    elif uri == "infrastructure://services":
        services, _ = await client.list_services(limit=200)
        return _format_list_response("services", services)

    elif uri == "infrastructure://networks":
        networks, _ = await client.list_networks(limit=50)
        return _format_list_response("networks", networks)

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


@server.list_prompts()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_prompts() -> ListPromptsResult:
    """List available MCP prompts for infrastructure analysis.

    Returns:
        ListPromptsResult containing prompt definitions with arguments.
    """
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


@server.get_prompt()  # type: ignore[no-untyped-call,untyped-decorator]
async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    """Get a prompt populated with infrastructure context.

    Args:
        name: The prompt name to retrieve.
        arguments: Optional prompt arguments as key-value pairs.

    Returns:
        GetPromptResult with context-aware prompt messages.
    """
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
{_format_list_response("networks", networks)}

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
{_format_list_response("nodes", nodes)}

Services:
{_format_list_response("services", services)}

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
{_format_list_response("services", services)}

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
        except HydraAPIError as exc:
            if exc.code == "NOT_FOUND":
                source_info = f"Source: {source_id} (node not found)"
            else:
                logger.warning("migration_prompt_source_fetch_failed", node=source_id, error=str(exc))
                source_info = f"Source: {source_id} (details unavailable — API error)"

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


def create_http_app() -> Any:
    """Create a FastAPI application for HTTP transport.

    Returns:
        FastAPI application with MCP endpoints for tools, resources, and prompts.
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    http_app = FastAPI(
        title="Hydra MCP Server",
        description="MCP server for Hydra infrastructure management",
        version=settings.server_version,
    )

    http_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @http_app.middleware("http")
    async def auth_context_middleware(request: Any, call_next: Any) -> Any:
        try:
            context = await _build_request_auth_context(request.headers)
        except PermissionError:
            return _build_auth_error_response()
        except Exception as exc:
            logger.exception("auth_context_build_failed", error=str(exc))
            return _build_auth_error_response()

        token = push_auth_context(context)
        try:
            return await call_next(request)
        finally:
            reset_auth_context(token)

    class ToolCallRequest(BaseModel):
        name: str
        arguments: dict[str, Any] = {}

    class ToolCallResponse(BaseModel):
        content: str
        is_error: bool = False

    class ResourceReadRequest(BaseModel):
        uri: str

    @http_app.get("/health")
    async def health() -> dict[str, Any]:
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
    async def get_tools() -> dict[str, Any]:
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
    async def call_tool_http(request: ToolCallRequest) -> ToolCallResponse:
        """Call a tool."""
        result = await call_tool(request.name, request.arguments)
        content = result.content[0].text if result.content else ""
        return ToolCallResponse(
            content=content,
            is_error=result.isError if hasattr(result, "isError") else False,
        )

    @http_app.get("/resources")
    async def get_resources() -> dict[str, Any]:
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
    async def read_resource_http(request: ResourceReadRequest) -> dict[str, Any]:
        """Read a resource."""
        result = await read_resource(request.uri)
        content = result.contents[0].text if result.contents else ""
        return {"content": content}

    @http_app.get("/prompts")
    async def get_prompts() -> dict[str, Any]:
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


async def run_stdio() -> None:
    """Run the MCP server with stdio transport for CLI and desktop apps."""
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


async def run_http() -> None:
    """Run the MCP server with custom HTTP REST API transport."""
    import uvicorn

    logger.info(
        "starting_hydra_mcp_server",
        transport="http",
        host=settings.http_host,
        port=settings.http_port,
        version=settings.server_version,
    )

    http_app: Any = create_http_app()
    config = uvicorn.Config(
        http_app,
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
    )
    http_server = uvicorn.Server(config)
    await http_server.serve()


async def run_sse() -> None:
    """Run the MCP server with Server-Sent Events transport."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route

    logger.info(
        "starting_hydra_mcp_server",
        transport="sse",
        host=settings.http_host,
        port=settings.http_port,
        version=settings.server_version,
    )

    sse_transport = SseServerTransport("/messages")

    sse_app = Starlette(
        routes=[
            Route("/sse", endpoint=sse_transport.connect_sse),
            Route("/messages", endpoint=sse_transport.handle_post_message, methods=["POST"]),
        ]
    )
    sse_app.add_middleware(AuthContextMiddleware)

    async with sse_transport.connect_sse() as streams:  # type: ignore[call-arg]
        async def run_server() -> None:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

        import anyio
        async with anyio.create_task_group() as tg:
            tg.start_soon(run_server)
            config = uvicorn.Config(
                sse_app,
                host=settings.http_host,
                port=settings.http_port,
                log_level=settings.log_level.lower(),
            )
            http_server = uvicorn.Server(config)
            tg.start_soon(http_server.serve)


async def run_streamable_http() -> None:
    """Run the MCP server with Streamable HTTP transport for Claude Desktop."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Mount

    logger.info(
        "starting_hydra_mcp_server",
        transport="streamable-http",
        host=settings.http_host,
        port=settings.http_port,
        version=settings.server_version,
    )

    streamable_transport = StreamableHTTPServerTransport(
        mcp_session_id=None,
        is_json_response_enabled=False,
    )

    mcp_app = Starlette(
        routes=[
            Mount("/mcp", app=streamable_transport.handle_request),
        ]
    )
    mcp_app.add_middleware(AuthContextMiddleware)

    mcp_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def run_mcp() -> None:
        async with streamable_transport.connect() as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

    import anyio
    async with anyio.create_task_group() as tg:
        tg.start_soon(run_mcp)
        config = uvicorn.Config(
            mcp_app,
            host=settings.http_host,
            port=settings.http_port,
            log_level=settings.log_level.lower(),
        )
        http_server = uvicorn.Server(config)
        await http_server.serve()


async def main(transport: str | None = None) -> None:
    """Run the MCP server with the specified transport.

    Args:
        transport: Transport mode override. If None, uses settings.transport.
            Valid values: 'stdio', 'http', 'sse', 'streamable-http'.
    """
    transport = transport or settings.transport

    if transport == "http":
        await run_http()
    elif transport == "sse":
        await run_sse()
    elif transport == "streamable-http":
        await run_streamable_http()
    else:
        await run_stdio()


def run(transport: str | None = None) -> None:
    """Synchronous entry point for running the MCP server.

    Args:
        transport: Transport mode override. If None, uses settings.transport.
    """
    import asyncio
    asyncio.run(main(transport))


if __name__ == "__main__":
    run()
