"""MCP Client wrapper for calling MCP servers."""

import json
from typing import Any

import httpx
import structlog

from hydra.api.v1.core.exceptions import ValidationError
from hydra.core.config import get_settings
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)

INTERNAL_REQUEST_HEADER = "X-Hydra-Internal-Request"
INTERNAL_USER_ID_HEADER = "X-Hydra-User-Id"
INTERNAL_ROLE_HEADER = "X-Hydra-Role"
INTERNAL_PERMISSIONS_HEADER = "X-Hydra-Permissions"
INTERNAL_CLIENT_ID_HEADER = "X-Hydra-Client-Id"


class MCPClientError(ValidationError):
    """MCP client error."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details or {})


class MCPClient:
    """Client for calling MCP servers over HTTP.

    Provides methods to interact with MCP servers including the built-in
    hydra-mcp server and user-configured external servers. Handles tool
    discovery, tool execution, resource access, and health checks.
    """

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb
        self.settings = get_settings()
        self._builtin_mcp_url: str | None = None

    @property
    def builtin_mcp_url(self) -> str:
        """Get the built-in hydra-mcp server URL."""
        if self._builtin_mcp_url is None:
            self._builtin_mcp_url = self.settings.mcp_server_url
        return self._builtin_mcp_url

    async def get_server_config(self, server_id: str, user_id: str) -> dict:
        """Get MCP server configuration.

        Args:
            server_id: Server identifier or "hydra-mcp"/"builtin" for built-in.
            user_id: User identifier for authorization.

        Returns:
            Server config dict with server_id, name, url, is_builtin, and transport.

        Raises:
            MCPClientError: If the server is not found.
        """
        if server_id == "hydra-mcp" or server_id == "builtin":
            return {
                "server_id": "hydra-mcp",
                "name": "Hydra MCP",
                "url": self.builtin_mcp_url,
                "is_builtin": True,
            }

        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "ownerId": user_id,
        })

        if not doc:
            raise MCPClientError(f"MCP server not found: {server_id}")

        return {
            "server_id": doc["serverId"],
            "name": doc["name"],
            "url": doc.get("url"),
            "is_builtin": False,
            "transport": doc.get("transport", "http"),
        }

    async def get_tools(self, server_config: dict) -> list[dict]:
        """Get available tools from an MCP server.

        Args:
            server_config: Server configuration from get_server_config.

        Returns:
            List of tool definitions with name, description, and inputSchema.

        Raises:
            MCPClientError: If the server URL is not configured or request fails.
        """
        url = server_config.get("url")
        if not url:
            raise MCPClientError("Server URL not configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{url.rstrip('/')}/tools")
                response.raise_for_status()
                data = response.json()
                return data.get("tools", [])
            except httpx.HTTPStatusError as e:
                raise MCPClientError(f"Failed to get tools: {e.response.status_code}")
            except httpx.RequestError as e:
                raise MCPClientError(f"Failed to connect to MCP server: {str(e)}")

    async def _build_internal_headers(self, user_id: str) -> dict[str, str]:
        """Build explicit internal-auth headers for built-in hydra-mcp calls."""
        user = await self.db.users.find_one({"userId": user_id})
        if not user:
            raise MCPClientError(f"User not found for MCP tool execution: {user_id}")

        headers = {
            INTERNAL_REQUEST_HEADER: "true",
            INTERNAL_USER_ID_HEADER: user_id,
            INTERNAL_ROLE_HEADER: user.get("role", "viewer"),
            INTERNAL_PERMISSIONS_HEADER: json.dumps(user.get("permissions", [])),
            INTERNAL_CLIENT_ID_HEADER: "hydra-api",
            "X-Hydra-Internal-Secret": self.settings.mcp_internal_secret,
        }
        return headers

    async def call_tool(
        self,
        server_config: dict,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: str | None = None,
    ) -> dict:
        """Call a tool on an MCP server.

        Args:
            server_config: Server configuration from get_server_config.
            tool_name: Name of the tool to call.
            arguments: Tool arguments as a dictionary.

        Returns:
            Dict with "content" (str) and "is_error" (bool) keys.
        """
        url = server_config.get("url")
        if not url:
            raise MCPClientError("Server URL not configured")

        headers: dict[str, str] = {}
        if server_config.get("is_builtin"):
            if not user_id:
                raise MCPClientError("Built-in MCP tool calls require user context")
            headers.update(await self._build_internal_headers(user_id))

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{url.rstrip('/')}/tools/call",
                    headers=headers or None,
                    json={
                        "name": tool_name,
                        "arguments": arguments,
                    },
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "content": data.get("content", ""),
                    "is_error": data.get("is_error", False),
                }
            except httpx.HTTPStatusError as e:
                logger.error(
                    "mcp_tool_call_error",
                    server_id=server_config.get("server_id"),
                    tool=tool_name,
                    status_code=e.response.status_code,
                )
                return {
                    "content": f"Error calling tool: HTTP {e.response.status_code}",
                    "is_error": True,
                }
            except httpx.RequestError as e:
                logger.error(
                    "mcp_tool_call_connection_error",
                    server_id=server_config.get("server_id"),
                    tool=tool_name,
                    error=str(e),
                )
                return {
                    "content": f"Connection error: {str(e)}",
                    "is_error": True,
                }

    async def get_resources(self, server_config: dict) -> list[dict]:
        """Get available resources from an MCP server.

        Args:
            server_config: Server configuration from get_server_config.

        Returns:
            List of resource definitions with uri, name, and description.

        Raises:
            MCPClientError: If the server URL is not configured or request fails.
        """
        url = server_config.get("url")
        if not url:
            raise MCPClientError("Server URL not configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{url.rstrip('/')}/resources")
                response.raise_for_status()
                data = response.json()
                return data.get("resources", [])
            except httpx.HTTPStatusError as e:
                raise MCPClientError(f"Failed to get resources: {e.response.status_code}")
            except httpx.RequestError as e:
                raise MCPClientError(f"Failed to connect to MCP server: {str(e)}")

    async def read_resource(self, server_config: dict, uri: str) -> str:
        """Read a resource from an MCP server.

        Args:
            server_config: Server configuration from get_server_config.
            uri: Resource URI to read.

        Returns:
            Resource content as a string.

        Raises:
            MCPClientError: If the server URL is not configured or request fails.
        """
        url = server_config.get("url")
        if not url:
            raise MCPClientError("Server URL not configured")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{url.rstrip('/')}/resources/read",
                    json={"uri": uri},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("content", "")
            except httpx.HTTPStatusError as e:
                raise MCPClientError(f"Failed to read resource: {e.response.status_code}")
            except httpx.RequestError as e:
                raise MCPClientError(f"Failed to connect to MCP server: {str(e)}")

    async def check_health(self, server_config: dict) -> dict:
        """Check the health of an MCP server.

        Args:
            server_config: Server configuration from get_server_config.

        Returns:
            Health status dict with healthy, server_name, version, tools_count,
            resources_count, and optionally error.
        """
        url = server_config.get("url")
        if not url:
            return {"healthy": False, "error": "Server URL not configured"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{url.rstrip('/')}/health")
                response.raise_for_status()
                data = response.json()
                return {
                    "healthy": data.get("status") == "healthy",
                    "server_name": data.get("server"),
                    "version": data.get("version"),
                    "tools_count": len(data.get("tools", [])),
                    "resources_count": len(data.get("resources", [])),
                }
            except httpx.HTTPStatusError as e:
                return {"healthy": False, "error": f"HTTP {e.response.status_code}"}
            except httpx.RequestError as e:
                return {"healthy": False, "error": str(e)}

    async def get_all_tools_for_session(
        self,
        server_ids: list[str],
        user_id: str,
    ) -> list[dict]:
        """Get all tools from multiple MCP servers for a chat session.

        Fetches tools from each enabled server and attaches server metadata
        for routing tool calls back to the correct server.

        Args:
            server_ids: List of MCP server identifiers to query.
            user_id: User identifier for authorization.

        Returns:
            List of tools with server_id and server_name attached to each.
        """
        all_tools = []

        for server_id in server_ids:
            try:
                config = await self.get_server_config(server_id, user_id)
                tools = await self.get_tools(config)

                for tool in tools:
                    tool_with_server = {
                        **tool,
                        "server_id": server_id,
                        "server_name": config.get("name", server_id),
                    }
                    all_tools.append(tool_with_server)

            except MCPClientError as e:
                logger.warning(
                    "failed_to_get_tools_from_server",
                    server_id=server_id,
                    error=str(e),
                )
                continue

        return all_tools

    async def execute_tool_call(
        self,
        tool_call: dict,
        server_ids: list[str],
        user_id: str,
    ) -> dict:
        """Execute a tool call, routing to the correct server.

        If server_id is specified in the tool_call, routes directly to that server.
        Otherwise, searches enabled servers for one that provides the tool.

        Args:
            tool_call: Dict with id, name, input, and optionally server_id.
            server_ids: List of enabled server IDs for this session.
            user_id: User identifier for authorization.

        Returns:
            Dict with "content" (str) and "is_error" (bool) keys.
        """
        tool_name = tool_call.get("name", "")
        tool_input = tool_call.get("input", {})
        server_id = tool_call.get("server_id")

        if server_id:
            try:
                config = await self.get_server_config(server_id, user_id)
                return await self.call_tool(config, tool_name, tool_input, user_id)
            except MCPClientError as e:
                return {"content": str(e), "is_error": True}

        for sid in server_ids:
            try:
                config = await self.get_server_config(sid, user_id)
                tools = await self.get_tools(config)

                if any(t.get("name") == tool_name for t in tools):
                    return await self.call_tool(config, tool_name, tool_input, user_id)

            except MCPClientError:
                continue

        return {"content": f"Tool not found: {tool_name}", "is_error": True}
