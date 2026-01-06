"""Hydra API client wrapper for MCP service."""

from datetime import datetime
from typing import Any

import httpx
import structlog

from hydra.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class HydraAPIError(Exception):
    """Exception for Hydra API errors."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class HydraClient:
    """Async client for Hydra API."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}

            if self.settings.api_key:
                headers["X-API-Key"] = self.settings.api_key

            self._client = httpx.AsyncClient(
                base_url=self.settings.api_url,
                headers=headers,
                timeout=self.settings.api_timeout,
            )
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict[str, Any]:
        """Make an API request."""
        client = await self._get_client()

        try:
            response = await client.request(
                method,
                endpoint,
                params=params,
                json=json_data,
            )

            data = response.json()

            if response.status_code >= 400:
                error = data.get("error", {})
                raise HydraAPIError(
                    code=error.get("code", "UNKNOWN_ERROR"),
                    message=error.get("message", "Unknown error"),
                    details=error.get("details"),
                )

            return data.get("data", data)

        except httpx.RequestError as e:
            logger.error("api_request_error", error=str(e), endpoint=endpoint)
            raise HydraAPIError("CONNECTION_ERROR", f"Failed to connect to API: {e}")

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ==================== Nodes ====================

    async def list_nodes(
        self,
        node_class: str | None = None,
        node_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List infrastructure nodes."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if node_class:
            params["class"] = node_class
        if node_type:
            params["type"] = node_type
        if status:
            params["status"] = status
        if tags:
            params["tags"] = ",".join(tags)

        result = await self._request("GET", "/nodes", params=params)
        return result if isinstance(result, list) else result, 0

    async def get_node(
        self,
        node_id: str,
        include_children: bool = True,
        include_services: bool = True,
    ) -> dict:
        """Get node details."""
        params = {
            "includeChildren": include_children,
            "includeServices": include_services,
        }
        return await self._request("GET", f"/nodes/{node_id}", params=params)

    async def get_node_profile(
        self,
        node_id: str,
        sections: list[str] | None = None,
    ) -> dict:
        """Get latest profile for a node."""
        params = {}
        if sections:
            params["sections"] = ",".join(sections)
        return await self._request("GET", f"/nodes/{node_id}/profiles/latest", params=params)

    # ==================== Services ====================

    async def list_services(
        self,
        node_id: str | None = None,
        runtime: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List services."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if node_id:
            params["nodeId"] = node_id
        if runtime:
            params["runtime"] = runtime
        if status:
            params["status"] = status

        result = await self._request("GET", "/services", params=params)
        return result if isinstance(result, list) else result, 0

    async def get_service(self, service_id: str) -> dict:
        """Get service details."""
        return await self._request("GET", f"/services/{service_id}")

    # ==================== Groups ====================

    async def list_groups(
        self,
        types: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List groups."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if types:
            params["types"] = ",".join(types)
        if tags:
            params["tags"] = ",".join(tags)

        result = await self._request("GET", "/groups", params=params)
        return result if isinstance(result, list) else result, 0

    async def get_group(self, group_id: str, resolve_members: bool = False) -> dict:
        """Get group details."""
        params = {"resolveMembers": resolve_members}
        return await self._request("GET", f"/groups/{group_id}", params=params)

    # ==================== Networks ====================

    async def list_networks(
        self,
        network_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List networks."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if network_type:
            params["type"] = network_type

        result = await self._request("GET", "/networks", params=params)
        return result if isinstance(result, list) else result, 0

    async def get_network(
        self,
        network_id: str,
        include_nodes: bool = False,
    ) -> dict:
        """Get network details."""
        params = {"includeNodes": include_nodes}
        return await self._request("GET", f"/networks/{network_id}", params=params)

    # ==================== Topologies ====================

    async def get_topology(
        self,
        mode: str = "network",
        scope: dict | None = None,
    ) -> dict:
        """Get latest topology."""
        params = {"mode": mode}
        return await self._request("GET", "/topologies/latest", params=params)

    async def get_topology_at_time(
        self,
        mode: str,
        timestamp: datetime,
    ) -> dict:
        """Get topology at a specific time."""
        params = {
            "mode": mode,
            "timestamp": timestamp.isoformat(),
        }
        return await self._request("GET", "/timemachine/topology", params=params)

    # ==================== Time Machine ====================

    async def get_node_at_time(
        self,
        node_id: str,
        timestamp: datetime,
        sections: list[str] | None = None,
    ) -> dict:
        """Get node state at a specific time."""
        params: dict[str, Any] = {"timestamp": timestamp.isoformat()}
        if sections:
            params["sections"] = ",".join(sections)
        return await self._request("GET", f"/timemachine/node/{node_id}", params=params)

    # ==================== Profiles ====================

    async def compare_profiles(
        self,
        node_id: str,
        from_version: str | None = None,
        to_version: str | None = None,
    ) -> dict:
        """Compare two profiles."""
        params: dict[str, Any] = {}
        if from_version:
            params["from"] = from_version
        if to_version:
            params["to"] = to_version
        return await self._request("GET", f"/nodes/{node_id}/profiles/diff", params=params)

    # ==================== Query & Analytics ====================

    async def get_capacity(
        self,
        group_by: str | None = None,
        include_logical: bool = False,
    ) -> dict:
        """Get capacity summary."""
        params: dict[str, Any] = {"includeLogical": include_logical}
        if group_by:
            params["groupBy"] = group_by
        return await self._request("GET", "/capacity", params=params)

    async def query(
        self,
        collection: str,
        filter_query: dict | None = None,
        projection: dict | None = None,
        sort: dict | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict:
        """Execute a raw query."""
        body = {
            "collection": collection,
            "filter": filter_query,
            "projection": projection,
            "sort": sort,
            "limit": limit,
            "skip": skip,
        }
        return await self._request("POST", "/query", json_data=body)

    async def search(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search across infrastructure entities."""
        # Search nodes
        nodes, _ = await self.list_nodes(limit=limit)
        results = []

        query_lower = query.lower()
        for node in nodes if isinstance(nodes, list) else []:
            if (
                query_lower in node.get("nodeId", "").lower()
                or query_lower in node.get("displayName", "").lower()
            ):
                results.append({"type": "node", **node})

        if not types or "service" in types:
            services, _ = await self.list_services(limit=limit)
            for svc in services if isinstance(services, list) else []:
                if (
                    query_lower in svc.get("serviceId", "").lower()
                    or query_lower in svc.get("name", "").lower()
                ):
                    results.append({"type": "service", **svc})

        return results[:limit]

    # ==================== Commands ====================

    async def control_service(
        self,
        node_id: str,
        service_id: str,
        action: str,
        parameters: dict | None = None,
    ) -> dict:
        """Control a service."""
        body = {
            "type": "service",
            "target": {"nodeId": node_id, "serviceId": service_id},
            "action": action,
            "parameters": parameters or {},
        }
        return await self._request("POST", "/commands", json_data=body)

    # ==================== Home Assistant ====================

    async def control_device(
        self,
        entity_id: str,
        service: str,
        data: dict | None = None,
    ) -> dict:
        """Control a Home Assistant device."""
        body = {
            "entityId": entity_id,
            "service": service,
            "data": data,
        }
        return await self._request("POST", "/ha/control", json_data=body)

    async def get_ha_status(self) -> dict:
        """Get Home Assistant integration status."""
        return await self._request("GET", "/ha/status")

    # ==================== Health ====================

    async def health_check(self) -> dict:
        """Check API health."""
        return await self._request("GET", "/health")

    async def get_info(self) -> dict:
        """Get API info and stats."""
        return await self._request("GET", "/info")
