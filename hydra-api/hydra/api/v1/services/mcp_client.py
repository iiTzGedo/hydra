"""MCP Client wrapper for calling MCP servers."""

from typing import Any

import httpx
import structlog

from hydra.api.v1.core.exceptions import ValidationError
from hydra.core.config import get_settings
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class MCPClientError(ValidationError):
    """MCP client error."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details or {})


class MCPClient:
    """Client for calling MCP servers over HTTP."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb
        self.settings = get_settings()
        # Built-in hydra-mcp server URL (from docker-compose or config)
        self._builtin_mcp_url: str | None = None

    @property
    def builtin_mcp_url(self) -> str:
        """Get the built-in hydra-mcp server URL."""
        if self._builtin_mcp_url is None:
            self._builtin_mcp_url = self.settings.mcp_server_url
        return self._builtin_mcp_url

    async def get_server_config(self, server_id: str, user_id: str) -> dict:
        """Get MCP server configuration."""
        # Check if this is the built-in server
        if server_id == "hydra-mcp" or server_id == "builtin":
            return {
                "server_id": "hydra-mcp",
                "name": "Hydra MCP",
                "url": self.builtin_mcp_url,
                "is_builtin": True,
            }

        # Look up user-configured server
        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "createdBy": user_id,
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
        """Get available tools from an MCP server."""
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

    async def call_tool(
        self,
        server_config: dict,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict:
        """Call a tool on an MCP server.

        Returns:
            {
                "content": str,  # Tool result content
                "is_error": bool,  # Whether the tool returned an error
            }
        """
        url = server_config.get("url")
        if not url:
            raise MCPClientError("Server URL not configured")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{url.rstrip('/')}/tools/call",
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
        """Get available resources from an MCP server."""
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
        """Read a resource from an MCP server."""
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
        """Check the health of an MCP server."""
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

        Returns tools with server_id attached for routing.
        """
        all_tools = []

        for server_id in server_ids:
            try:
                config = await self.get_server_config(server_id, user_id)
                tools = await self.get_tools(config)

                # Attach server info to each tool (copy to avoid mutating original)
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

        Args:
            tool_call: {"id": "...", "name": "...", "input": {...}, "server_id": "..."}
            server_ids: List of enabled server IDs for this session
            user_id: User ID for authorization

        Returns:
            {"content": "...", "is_error": bool}
        """
        tool_name = tool_call.get("name", "")
        tool_input = tool_call.get("input", {})
        server_id = tool_call.get("server_id")

        # If server_id is specified, use that server
        if server_id:
            try:
                config = await self.get_server_config(server_id, user_id)
                return await self.call_tool(config, tool_name, tool_input)
            except MCPClientError as e:
                return {"content": str(e), "is_error": True}

        # Otherwise, search for the tool across enabled servers
        for sid in server_ids:
            try:
                config = await self.get_server_config(sid, user_id)
                tools = await self.get_tools(config)

                # Check if this server has the tool
                if any(t.get("name") == tool_name for t in tools):
                    return await self.call_tool(config, tool_name, tool_input)

            except MCPClientError:
                continue

        return {"content": f"Tool not found: {tool_name}", "is_error": True}
