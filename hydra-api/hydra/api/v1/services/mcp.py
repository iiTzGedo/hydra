"""MCP server configuration management service."""

import secrets
from datetime import datetime, timezone

import httpx
import structlog

from hydra.api.v1.core.crypto import decrypt_value, encrypt_value
from hydra.api.v1.core.exceptions import NotFoundError
from hydra.api.v1.models.mcp import (
    MCPAuthType,
    MCPServerCreate,
    MCPServerStatus,
    MCPServerUpdate,
)
from hydra.core.config import get_settings
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class MCPServerNotFoundError(NotFoundError):
    """MCP server configuration not found."""

    def __init__(self, server_id: str):
        super().__init__("mcp_server", server_id)


class MCPService:
    """MCP server configuration management service.

    Manages user-configured MCP server connections including CRUD operations,
    health checks, and capability discovery (tools and resources).
    """

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def list_servers(
        self,
        user_id: str,
        category: str | None = None,
        enabled_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List MCP server configurations for a user.

        Args:
            user_id: User identifier.
            category: Optional category filter.
            enabled_only: If True, return only enabled servers.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            Dict with "servers" list and "total" count.
        """
        query: dict = {"ownerId": user_id}
        if category:
            query["category"] = category
        if enabled_only:
            query["enabled"] = True

        cursor = (
            self.db.mcp_servers.find(query)
            .sort("createdAt", -1)
            .skip(offset)
            .limit(limit)
        )

        servers = []
        async for doc in cursor:
            servers.append(self._doc_to_response(doc))

        total = await self.db.mcp_servers.count_documents(query)

        return {"servers": servers, "total": total}

    async def get_server(self, server_id: str, user_id: str) -> dict:
        """Get a specific MCP server configuration.

        Args:
            server_id: Server identifier.
            user_id: User identifier.

        Returns:
            Server configuration dict.

        Raises:
            MCPServerNotFoundError: If the server does not exist.
        """
        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "ownerId": user_id,
        })

        if not doc:
            raise MCPServerNotFoundError(server_id)

        return self._doc_to_response(doc)

    async def create_server(
        self,
        request: MCPServerCreate,
        user_id: str,
    ) -> dict:
        """Create a new MCP server configuration.

        Args:
            request: Server creation payload.
            user_id: User identifier.

        Returns:
            The created server configuration.
        """
        now = datetime.now(timezone.utc)
        server_id = f"mcp_{secrets.token_urlsafe(8)}"

        encrypted_auth = None
        if request.auth_value:
            encrypted_auth = encrypt_value(request.auth_value)

        doc = {
            "serverId": server_id,
            "name": request.name,
            "endpoint": request.endpoint,
            "description": request.description,
            "category": request.category.value,
            "authType": request.auth_type.value,
            "authValueEncrypted": encrypted_auth,
            "enabled": request.enabled,
            "status": MCPServerStatus.UNKNOWN.value,
            "lastHealthCheck": None,
            "docsUrl": request.docs_url,
            "ownerId": user_id,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.mcp_servers.insert_one(doc)

        logger.info(
            "mcp_server_created",
            server_id=server_id,
            name=request.name,
            user_id=user_id,
        )

        return self._doc_to_response(doc)

    async def update_server(
        self,
        server_id: str,
        request: MCPServerUpdate,
        user_id: str,
    ) -> dict:
        """Update an MCP server configuration.

        Endpoint changes reset the server status to unknown and clear the
        last health check timestamp.

        Args:
            server_id: Server identifier.
            request: Fields to update.
            user_id: User identifier.

        Returns:
            The updated server configuration.

        Raises:
            MCPServerNotFoundError: If the server does not exist.
        """
        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "ownerId": user_id,
        })

        if not doc:
            raise MCPServerNotFoundError(server_id)

        now = datetime.now(timezone.utc)
        update_fields: dict = {"updatedAt": now}

        if request.name is not None:
            update_fields["name"] = request.name
        if request.endpoint is not None:
            update_fields["endpoint"] = request.endpoint
            update_fields["status"] = MCPServerStatus.UNKNOWN.value
            update_fields["lastHealthCheck"] = None
        if request.description is not None:
            update_fields["description"] = request.description
        if request.category is not None:
            update_fields["category"] = request.category.value
        if request.auth_type is not None:
            update_fields["authType"] = request.auth_type.value
        if request.auth_value is not None:
            update_fields["authValueEncrypted"] = encrypt_value(request.auth_value)
        if request.enabled is not None:
            update_fields["enabled"] = request.enabled
        if request.docs_url is not None:
            update_fields["docsUrl"] = request.docs_url

        await self.db.mcp_servers.update_one(
            {"serverId": server_id},
            {"$set": update_fields},
        )

        updated_doc = await self.db.mcp_servers.find_one({"serverId": server_id})

        logger.info("mcp_server_updated", server_id=server_id, user_id=user_id)

        return self._doc_to_response(updated_doc)

    async def delete_server(self, server_id: str, user_id: str) -> dict:
        """Delete an MCP server configuration.

        Args:
            server_id: Server identifier.
            user_id: User identifier.

        Returns:
            Dict with "deleted" status and "serverId".

        Raises:
            MCPServerNotFoundError: If the server does not exist.
        """
        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "ownerId": user_id,
        })

        if not doc:
            raise MCPServerNotFoundError(server_id)

        await self.db.mcp_servers.delete_one({"serverId": server_id})

        logger.info("mcp_server_deleted", server_id=server_id, user_id=user_id)

        return {"deleted": True, "serverId": server_id}

    async def check_health(self, server_id: str, user_id: str) -> dict:
        """Check the health of an MCP server.

        Attempts to reach the server's /health endpoint and updates the stored
        status accordingly.

        Args:
            server_id: Server identifier.
            user_id: User identifier.

        Returns:
            Health check result with status, message, tools, and resources.

        Raises:
            MCPServerNotFoundError: If the server does not exist.
        """
        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "ownerId": user_id,
        })

        if not doc:
            raise MCPServerNotFoundError(server_id)

        now = datetime.now(timezone.utc)
        endpoint = doc["endpoint"]
        auth_type = MCPAuthType(doc.get("authType", "none"))

        # SSRF protection: validate the endpoint URL
        from hydra.api.v1.core.url_validator import validate_external_url
        from hydra.core.config import get_settings

        settings = get_settings()
        try:
            validate_external_url(endpoint, allow_private=settings.is_development)
        except ValueError as exc:
            return {
                "serverId": server_id,
                "status": MCPServerStatus.UNHEALTHY.value,
                "message": f"Endpoint URL rejected: {exc}",
                "checkedAt": now.isoformat(),
            }

        headers = {}
        if doc.get("authValueEncrypted"):
            auth_value = decrypt_value(doc["authValueEncrypted"])
            if auth_type == MCPAuthType.API_KEY:
                headers["X-API-Key"] = auth_value
            elif auth_type == MCPAuthType.BEARER:
                headers["Authorization"] = f"Bearer {auth_value}"

        status = MCPServerStatus.UNHEALTHY
        message = ""
        tools = None
        resources = None

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                health_url = f"{endpoint.rstrip('/')}/health"
                response = await client.get(health_url, headers=headers)

                if response.status_code == 200:
                    status = MCPServerStatus.HEALTHY
                    message = "Server is reachable"
                    data = response.json()
                    tools = data.get("tools", [])
                    resources = data.get("resources", [])
                else:
                    message = f"Health check returned status {response.status_code}"
            except httpx.TimeoutException:
                message = "Connection timed out"
            except httpx.ConnectError:
                message = "Cannot connect to server"
            except Exception as e:
                message = f"Health check failed: {str(e)}"

        await self.db.mcp_servers.update_one(
            {"serverId": server_id},
            {
                "$set": {
                    "status": status.value,
                    "lastHealthCheck": now,
                    "updatedAt": now,
                }
            },
        )

        logger.info(
            "mcp_server_health_checked",
            server_id=server_id,
            status=status.value,
        )

        return {
            "server_id": server_id,
            "status": status,
            "message": message,
            "checked_at": now,
            "tools": tools,
            "resources": resources,
        }

    async def list_tools(self, server_id: str, user_id: str) -> dict:
        """List tools available on an MCP server.

        Args:
            server_id: Server identifier.
            user_id: User identifier.

        Returns:
            Dict with "server_id" and "tools" list.

        Raises:
            MCPServerNotFoundError: If the server does not exist.
        """
        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "ownerId": user_id,
        })

        if not doc:
            raise MCPServerNotFoundError(server_id)

        endpoint = doc["endpoint"]
        auth_type = MCPAuthType(doc.get("authType", "none"))

        headers = {}
        if doc.get("authValueEncrypted"):
            auth_value = decrypt_value(doc["authValueEncrypted"])
            if auth_type == MCPAuthType.API_KEY:
                headers["X-API-Key"] = auth_value
            elif auth_type == MCPAuthType.BEARER:
                headers["Authorization"] = f"Bearer {auth_value}"

        tools = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                tools_url = f"{endpoint.rstrip('/')}/tools"
                response = await client.get(tools_url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        tools = data
                    elif isinstance(data, dict) and "tools" in data:
                        tools = data["tools"]
            except httpx.TimeoutException:
                logger.warning("mcp_tools_fetch_failed", server_id=server_id, error="Connection timed out", error_type="timeout")
            except httpx.ConnectError:
                logger.warning("mcp_tools_fetch_failed", server_id=server_id, error="Cannot connect to server", error_type="connection")
            except httpx.HTTPStatusError as e:
                logger.warning("mcp_tools_fetch_failed", server_id=server_id, error=str(e), error_type="http_status")
            except Exception as e:
                logger.error("mcp_tools_fetch_unexpected_error", server_id=server_id, error=str(e), error_type=type(e).__name__)

        return {
            "server_id": server_id,
            "tools": [
                {"name": t.get("name", t) if isinstance(t, dict) else t, "description": t.get("description") if isinstance(t, dict) else None}
                for t in tools
            ],
        }

    async def list_resources(self, server_id: str, user_id: str) -> dict:
        """List resources available on an MCP server.

        Args:
            server_id: Server identifier.
            user_id: User identifier.

        Returns:
            Dict with "server_id" and "resources" list.

        Raises:
            MCPServerNotFoundError: If the server does not exist.
        """
        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "ownerId": user_id,
        })

        if not doc:
            raise MCPServerNotFoundError(server_id)

        endpoint = doc["endpoint"]
        auth_type = MCPAuthType(doc.get("authType", "none"))

        headers = {}
        if doc.get("authValueEncrypted"):
            auth_value = decrypt_value(doc["authValueEncrypted"])
            if auth_type == MCPAuthType.API_KEY:
                headers["X-API-Key"] = auth_value
            elif auth_type == MCPAuthType.BEARER:
                headers["Authorization"] = f"Bearer {auth_value}"

        resources = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resources_url = f"{endpoint.rstrip('/')}/resources"
                response = await client.get(resources_url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        resources = data
                    elif isinstance(data, dict) and "resources" in data:
                        resources = data["resources"]
            except httpx.TimeoutException:
                logger.warning("mcp_resources_fetch_failed", server_id=server_id, error="Connection timed out", error_type="timeout")
            except httpx.ConnectError:
                logger.warning("mcp_resources_fetch_failed", server_id=server_id, error="Cannot connect to server", error_type="connection")
            except httpx.HTTPStatusError as e:
                logger.warning("mcp_resources_fetch_failed", server_id=server_id, error=str(e), error_type="http_status")
            except Exception as e:
                logger.error("mcp_resources_fetch_unexpected_error", server_id=server_id, error=str(e), error_type=type(e).__name__)

        return {
            "server_id": server_id,
            "resources": [
                {
                    "uri": r.get("uri", r) if isinstance(r, dict) else r,
                    "name": r.get("name") if isinstance(r, dict) else None,
                    "description": r.get("description") if isinstance(r, dict) else None,
                    "mime_type": (
                        r.get("mimeType") or r.get("mime_type") if isinstance(r, dict) else None
                    ),
                }
                for r in resources
            ],
        }

    def _doc_to_response(self, doc: dict) -> dict:
        """Convert a database document to a response dictionary."""
        return {
            "server_id": doc["serverId"],
            "name": doc["name"],
            "endpoint": doc["endpoint"],
            "description": doc.get("description"),
            "category": doc["category"],
            "auth_type": doc.get("authType", "none"),
            "auth_configured": doc.get("authValueEncrypted") is not None,
            "enabled": doc.get("enabled", True),
            "status": doc.get("status", "unknown"),
            "last_health_check": doc.get("lastHealthCheck"),
            "docs_url": doc.get("docsUrl"),
            "owner_id": doc["ownerId"],
            "created_at": doc["createdAt"],
            "updated_at": doc["updatedAt"],
        }

    async def check_hydra_health(self) -> dict:
        """Check health of the built-in Hydra MCP server.

        This doesn't require DB lookup - uses the configured MCP server URL directly.

        Returns:
            Health check result with status, tools count, prompts count, etc.
        """
        settings = get_settings()
        endpoint = settings.mcp_server_url
        now = datetime.now(timezone.utc)

        status = MCPServerStatus.UNHEALTHY
        message = ""
        server_name = None
        version = None
        tools_count = 0
        prompts_count = 0
        resources_count = 0

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                health_url = f"{endpoint.rstrip('/')}/health"
                response = await client.get(health_url)

                if response.status_code == 200:
                    status = MCPServerStatus.HEALTHY
                    message = "Hydra MCP is reachable"
                    data = response.json()
                    server_name = data.get("server")
                    version = data.get("version")
                    tools_count = len(data.get("tools", []))
                    resources_count = len(data.get("resources", []))

                    # Fetch prompts count separately
                    try:
                        prompts_url = f"{endpoint.rstrip('/')}/prompts"
                        prompts_response = await client.get(prompts_url)
                        if prompts_response.status_code == 200:
                            prompts_data = prompts_response.json()
                            if isinstance(prompts_data, list):
                                prompts_count = len(prompts_data)
                            elif isinstance(prompts_data, dict) and "prompts" in prompts_data:
                                prompts_count = len(prompts_data["prompts"])
                    except Exception:
                        pass  # Prompts endpoint may not exist
                else:
                    message = f"Health check returned status {response.status_code}"
            except httpx.TimeoutException:
                message = "Connection timed out - is hydra-mcp service running?"
            except httpx.ConnectError:
                message = "Cannot connect to Hydra MCP - check if the service is running"
            except Exception as e:
                message = f"Health check failed: {str(e)}"

        logger.info(
            "hydra_mcp_health_checked",
            status=status.value,
            tools_count=tools_count,
            prompts_count=prompts_count,
        )

        return {
            "status": status,
            "message": message,
            "checked_at": now,
            "server_name": server_name,
            "version": version,
            "tools_count": tools_count,
            "prompts_count": prompts_count,
            "resources_count": resources_count,
            "endpoint": endpoint,
        }

    async def list_prompts(self, server_id: str, user_id: str) -> dict:
        """List prompts available on an MCP server.

        Args:
            server_id: Server identifier.
            user_id: User identifier.

        Returns:
            Dict with "server_id" and "prompts" list.

        Raises:
            MCPServerNotFoundError: If the server does not exist.
        """
        doc = await self.db.mcp_servers.find_one({
            "serverId": server_id,
            "ownerId": user_id,
        })

        if not doc:
            raise MCPServerNotFoundError(server_id)

        endpoint = doc["endpoint"]
        auth_type = MCPAuthType(doc.get("authType", "none"))

        headers = {}
        if doc.get("authValueEncrypted"):
            auth_value = decrypt_value(doc["authValueEncrypted"])
            if auth_type == MCPAuthType.API_KEY:
                headers["X-API-Key"] = auth_value
            elif auth_type == MCPAuthType.BEARER:
                headers["Authorization"] = f"Bearer {auth_value}"

        prompts = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                prompts_url = f"{endpoint.rstrip('/')}/prompts"
                response = await client.get(prompts_url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        prompts = data
                    elif isinstance(data, dict) and "prompts" in data:
                        prompts = data["prompts"]
            except httpx.TimeoutException:
                logger.warning("mcp_prompts_fetch_failed", server_id=server_id, error="Connection timed out", error_type="timeout")
            except httpx.ConnectError:
                logger.warning("mcp_prompts_fetch_failed", server_id=server_id, error="Cannot connect to server", error_type="connection")
            except httpx.HTTPStatusError as e:
                logger.warning("mcp_prompts_fetch_failed", server_id=server_id, error=str(e), error_type="http_status")
            except Exception as e:
                logger.error("mcp_prompts_fetch_unexpected_error", server_id=server_id, error=str(e), error_type=type(e).__name__)

        return {
            "server_id": server_id,
            "prompts": [
                {
                    "name": p.get("name", p) if isinstance(p, dict) else p,
                    "description": p.get("description") if isinstance(p, dict) else None,
                    "arguments": [
                        {
                            "name": arg.get("name", ""),
                            "description": arg.get("description"),
                            "required": arg.get("required", False),
                        }
                        for arg in (p.get("arguments", []) if isinstance(p, dict) else [])
                    ],
                }
                for p in prompts
            ],
        }

    async def list_hydra_prompts(self) -> dict:
        """List prompts available on the built-in Hydra MCP server.

        Returns:
            Dict with "server_id" as "hydra-mcp" and "prompts" list.
        """
        settings = get_settings()
        endpoint = settings.mcp_server_url

        prompts = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                prompts_url = f"{endpoint.rstrip('/')}/prompts"
                response = await client.get(prompts_url)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        prompts = data
                    elif isinstance(data, dict) and "prompts" in data:
                        prompts = data["prompts"]
            except httpx.TimeoutException:
                logger.warning("hydra_mcp_prompts_fetch_failed", error="Connection timed out", error_type="timeout")
            except httpx.ConnectError:
                logger.warning("hydra_mcp_prompts_fetch_failed", error="Cannot connect to Hydra MCP", error_type="connection")
            except httpx.HTTPStatusError as e:
                logger.warning("hydra_mcp_prompts_fetch_failed", error=str(e), error_type="http_status")
            except Exception as e:
                logger.error("hydra_mcp_prompts_fetch_unexpected_error", error=str(e), error_type=type(e).__name__)

        return {
            "server_id": "hydra-mcp",
            "prompts": [
                {
                    "name": p.get("name", p) if isinstance(p, dict) else p,
                    "description": p.get("description") if isinstance(p, dict) else None,
                    "arguments": [
                        {
                            "name": arg.get("name", ""),
                            "description": arg.get("description"),
                            "required": arg.get("required", False),
                        }
                        for arg in (p.get("arguments", []) if isinstance(p, dict) else [])
                    ],
                }
                for p in prompts
            ],
        }

    async def list_hydra_tools(self) -> dict:
        """List tools available on the built-in Hydra MCP server.

        Returns:
            Dict with "server_id" as "hydra-mcp" and "tools" list.
        """
        settings = get_settings()
        endpoint = settings.mcp_server_url

        tools = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                tools_url = f"{endpoint.rstrip('/')}/tools"
                response = await client.get(tools_url)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        tools = data
                    elif isinstance(data, dict) and "tools" in data:
                        tools = data["tools"]
            except httpx.TimeoutException:
                logger.warning("hydra_mcp_tools_fetch_failed", error="Connection timed out", error_type="timeout")
            except httpx.ConnectError:
                logger.warning("hydra_mcp_tools_fetch_failed", error="Cannot connect to Hydra MCP", error_type="connection")
            except httpx.HTTPStatusError as e:
                logger.warning("hydra_mcp_tools_fetch_failed", error=str(e), error_type="http_status")
            except Exception as e:
                logger.error("hydra_mcp_tools_fetch_unexpected_error", error=str(e), error_type=type(e).__name__)

        return {
            "server_id": "hydra-mcp",
            "tools": [
                {
                    "name": t.get("name", t) if isinstance(t, dict) else t,
                    "description": t.get("description") if isinstance(t, dict) else None,
                }
                for t in tools
            ],
        }
