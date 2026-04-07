"""Hydra API client wrapper for MCP service."""

import asyncio
from datetime import datetime
from typing import Any, TypeVar, cast

import httpx
import structlog

from hydra_mcp.auth import get_auth_context, get_forward_auth_headers
from hydra_mcp.config import Settings, get_settings

logger = structlog.get_logger(__name__)
ListItemT = TypeVar("ListItemT")


class HydraAPIError(Exception):
    """Exception raised when the Hydra API returns an error.

    Attributes:
        code: Error code from the API (e.g., 'NOT_FOUND', 'UNAUTHORIZED').
        message: Human-readable error message.
        details: Optional dictionary with additional error context.
    """

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class HydraClient:
    """Async HTTP client for interacting with the Hydra API.

    Provides methods for querying infrastructure entities (nodes, services,
    networks, groups), accessing historical data via Time Machine, and
    executing control commands.

    The client automatically manages connection pooling and handles API
    authentication via API key or JWT token.

    Args:
        settings: Optional Settings instance. If not provided, uses the
            default settings from get_settings().

    Example::

        client = HydraClient()
        nodes, _ = await client.list_nodes(node_class="compute")
        await client.close()
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
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

    # Retry configuration for transient failures
    _MAX_RETRIES = 3
    _RETRY_BACKOFF_BASE = 0.5  # seconds; delays: 0.5, 1.0, 2.0
    _RETRYABLE_STATUS_CODES = {502, 503, 504}

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        auth_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make an API request, optionally with per-request auth headers.

        When auth_headers are provided they are merged on top of the
        client's default headers for this single request, allowing
        user credentials to be forwarded from the MCP auth context.

        Retries up to 3 times on transient failures (502, 503, 504,
        connection errors) with exponential backoff.
        """
        client = await self._get_client()
        merged_auth_headers = dict(auth_headers or {})
        context_headers = get_forward_auth_headers()
        if context_headers:
            merged_auth_headers.update(context_headers)
        elif get_auth_context() is not None and self.settings.transport != "stdio":
            raise HydraAPIError(
                "UNAUTHORIZED",
                "MCP request context is missing forward auth headers",
            )

        last_exception: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            try:
                response = await client.request(
                    method,
                    endpoint,
                    params=params,
                    json=json_data,
                    headers=merged_auth_headers or None,
                )
                data = response.json()
                if response.status_code >= 400:
                    if response.status_code in self._RETRYABLE_STATUS_CODES:
                        last_exception = HydraAPIError(
                            code="TRANSIENT_ERROR",
                            message=f"Server returned {response.status_code}",
                        )
                        if attempt < self._MAX_RETRIES - 1:
                            delay = self._RETRY_BACKOFF_BASE * (2 ** attempt)
                            logger.warning(
                                "api_request_retrying",
                                endpoint=endpoint,
                                status=response.status_code,
                                attempt=attempt + 1,
                                delay=delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                    error = data.get("error", {})
                    raise HydraAPIError(
                        code=error.get("code", "UNKNOWN_ERROR"),
                        message=error.get("message", "Unknown error"),
                        details=error.get("details"),
                    )
                result: dict[str, Any] = data.get("data", data)
                return result
            except httpx.RequestError as e:
                last_exception = e
                if attempt < self._MAX_RETRIES - 1:
                    delay = self._RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "api_request_retrying",
                        endpoint=endpoint,
                        error=str(e),
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error("api_request_error", error=str(e), endpoint=endpoint)
                raise HydraAPIError(
                    "CONNECTION_ERROR", f"Failed to connect to API: {e}"
                ) from e

        # Should only reach here after exhausting retries on transient HTTP errors
        raise HydraAPIError(
            "CONNECTION_ERROR",
            f"API request failed after {self._MAX_RETRIES} attempts",
        ) from last_exception

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def _expect_list_result(result: Any, endpoint: str) -> list[ListItemT]:
        """Validate list endpoints so schema drift fails loudly."""
        if isinstance(result, list):
            return cast(list[ListItemT], result)

        raise HydraAPIError(
            "INVALID_RESPONSE",
            f"Expected a list response from {endpoint}, got {type(result).__name__}",
            details={
                "endpoint": endpoint,
                "expected": "list",
                "received_type": type(result).__name__,
            },
        )

    async def list_nodes(
        self,
        node_class: str | None = None,
        node_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        agent_tier: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List infrastructure nodes with optional filtering.

        Args:
            node_class: Filter by node class (compute, networking, iot).
            node_type: Filter by node type (physical, logical).
            status: Filter by status (active, inactive, archived).
            tags: Filter by tags using AND logic.
            agent_tier: Filter by agent tier (lite, normal, max).
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Tuple of (list of node dictionaries, total count).
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if node_class:
            params["class"] = node_class
        if node_type:
            params["type"] = node_type
        if status:
            params["status"] = status
        if tags:
            params["tags"] = tags  # httpx sends as tags=tag1&tags=tag2
        if agent_tier:
            params["agentTier"] = agent_tier
        result = await self._request("GET", "/nodes", params=params)
        return self._expect_list_result(result, "/nodes"), 0

    async def get_node(
        self,
        node_id: str,
        include_children: bool = True,
        include_services: bool = True,
    ) -> dict[str, Any]:
        """Get detailed information about a specific node.

        Args:
            node_id: The unique node identifier.
            include_children: Include child nodes in the response.
            include_services: Include services running on the node.

        Returns:
            Node details including metadata, status, and optional children/services.
        """
        params = {
            "includeChildren": include_children,
            "includeServices": include_services,
        }
        return await self._request("GET", f"/nodes/{node_id}", params=params)

    async def get_node_profile(
        self,
        node_id: str,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get the latest profile snapshot for a node.

        Args:
            node_id: The unique node identifier.
            sections: Specific profile sections to include
                (hardware, network, storage, software, configs).

        Returns:
            Profile data with hardware, network, storage, and software details.
        """
        params = {}
        if sections:
            params["sections"] = sections  # httpx sends as sections=s1&sections=s2
        return await self._request("GET", f"/nodes/{node_id}/profiles/latest", params=params)

    async def list_services(
        self,
        node_id: str | None = None,
        runtime: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List services across the infrastructure.

        Args:
            node_id: Filter services by node.
            runtime: Filter by runtime (systemd, docker, podman, kubernetes).
            status: Filter by status (running, stopped, failed).
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Tuple of (list of service dictionaries, total count).
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if node_id:
            params["nodeId"] = node_id
        if runtime:
            params["runtime"] = runtime
        if status:
            params["status"] = status
        result = await self._request("GET", "/services", params=params)
        return self._expect_list_result(result, "/services"), 0

    async def get_service(self, service_id: str) -> dict[str, Any]:
        """Get detailed information about a specific service.

        Args:
            service_id: The unique service identifier (e.g., svc-nginx-a1b2).

        Returns:
            Service details including runtime, status, and metadata.
        """
        return await self._request("GET", f"/services/{service_id}")

    async def list_groups(
        self,
        types: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List logical groups.

        Args:
            types: Filter by group types (node, service).
            tags: Filter by tags.
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Tuple of (list of group dictionaries, total count).
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if types:
            params["types"] = types  # httpx sends as types=node&types=service
        if tags:
            params["tags"] = tags  # httpx sends as tags=tag1&tags=tag2
        result = await self._request("GET", "/groups", params=params)
        return self._expect_list_result(result, "/groups"), 0

    async def get_group(self, group_id: str, resolve_members: bool = False) -> dict[str, Any]:
        """Get detailed information about a specific group.

        Args:
            group_id: The unique group identifier.
            resolve_members: Include resolved member entities in the response.

        Returns:
            Group details including selectors and optionally resolved members.
        """
        params = {"resolveMembers": resolve_members}
        return await self._request("GET", f"/groups/{group_id}", params=params)

    async def list_networks(
        self,
        network_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List networks in the infrastructure.

        Args:
            network_type: Filter by network type (physical, vlan, overlay, virtual).
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Tuple of (list of network dictionaries, total count).
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if network_type:
            params["type"] = network_type
        result = await self._request("GET", "/networks", params=params)
        return self._expect_list_result(result, "/networks"), 0

    async def get_network(
        self,
        network_id: str,
        include_nodes: bool = False,
    ) -> dict[str, Any]:
        """Get detailed information about a specific network.

        Args:
            network_id: The unique network identifier.
            include_nodes: Include nodes connected to this network.

        Returns:
            Network details including CIDR, gateway, and optionally nodes.
        """
        params = {"includeNodes": include_nodes}
        return await self._request("GET", f"/networks/{network_id}", params=params)

    async def get_topology(
        self,
        mode: str = "network",
        _scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get the current infrastructure or network topology graph.

        Args:
            mode: Topology mode ('network' or 'infrastructure').
            scope: Optional scope filter for the topology.

        Returns:
            Topology graph with nodes, edges, and metadata.
        """
        params = {"mode": mode}
        return await self._request("GET", "/topologies/latest", params=params)

    async def get_topology_at_time(
        self,
        mode: str,
        timestamp: datetime,
    ) -> dict[str, Any]:
        """Get the topology at a specific historical point in time.

        Args:
            mode: Topology mode ('network' or 'infrastructure').
            timestamp: The point in time to query.

        Returns:
            Historical topology graph as it existed at the specified time.
        """
        params = {
            "mode": mode,
            "timestamp": timestamp.isoformat(),
        }
        return await self._request("GET", "/timemachine/topology", params=params)

    async def get_node_at_time(
        self,
        node_id: str,
        timestamp: datetime,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get a node's state at a specific historical point in time.

        Args:
            node_id: The unique node identifier.
            timestamp: The point in time to query.
            sections: Specific profile sections to include.

        Returns:
            Reconstructed node state as it existed at the specified time.
        """
        params: dict[str, Any] = {"timestamp": timestamp.isoformat()}
        if sections:
            params["sections"] = sections  # httpx sends as sections=s1&sections=s2
        return await self._request("GET", f"/timemachine/node/{node_id}", params=params)

    async def compare_profiles(
        self,
        node_id: str,
        from_version: str | None = None,
        to_version: str | None = None,
    ) -> dict[str, Any]:
        """Compare two profile versions to see what changed.

        Args:
            node_id: The unique node identifier.
            from_version: Starting version for comparison (default: previous).
            to_version: Ending version for comparison (default: latest).

        Returns:
            Diff showing added, removed, and modified sections between versions.
        """
        params: dict[str, Any] = {}
        if from_version:
            params["from"] = from_version
        if to_version:
            params["to"] = to_version
        return await self._request("GET", f"/nodes/{node_id}/profiles/diff", params=params)

    async def get_capacity(
        self,
        group_by: str | None = None,
        include_logical: bool = False,
    ) -> dict[str, Any]:
        """Get infrastructure capacity summary.

        Args:
            group_by: Group results by dimension (node, class, location, network, group).
            include_logical: Include logical nodes (may double-count resources).

        Returns:
            Capacity summary with CPU, memory, and storage totals.
        """
        params: dict[str, Any] = {"includeLogical": include_logical}
        if group_by:
            params["groupBy"] = group_by
        return await self._request("GET", "/capacity", params=params)

    async def query(
        self,
        collection: str,
        filter_query: dict[str, Any] | None = None,
        projection: dict[str, Any] | None = None,
        sort: dict[str, Any] | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Execute a raw query against infrastructure data.

        Args:
            collection: Collection to query (nodes, profiles, services, groups, networks).
            filter_query: MongoDB-style filter document.
            projection: Fields to include or exclude.
            sort: Sort specification.
            limit: Maximum number of results.
            skip: Number of results to skip.

        Returns:
            Query results matching the filter criteria.
        """
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
    ) -> list[dict[str, Any]]:
        """Search across nodes and services by name or ID.

        Args:
            query: Search query string.
            types: Entity types to search (node, service).
            limit: Maximum number of results.

        Returns:
            List of matching entities with their type annotation.
        """
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

    async def control_service(
        self,
        node_id: str,
        service_id: str,
        action: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a control action on a service.

        Args:
            node_id: The node hosting the service.
            service_id: The unique service identifier.
            action: Action to perform (start, stop, restart, reload, logs, inspect).
            parameters: Optional parameters for the action.

        Returns:
            Command execution result with status and output.
        """
        body = {
            "registryId": f"reg::service::{action}",
            "target": {"nodeId": node_id, "serviceId": service_id},
            "parameters": parameters or {},
        }
        return await self._request("POST", "/commands", json_data=body)

    async def control_node(
        self,
        node_id: str,
        action: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a control action on a node.

        Args:
            node_id: The target node identifier.
            action: Action to perform (reboot, shutdown, update-system, set-hostname).
            parameters: Optional parameters for the action.

        Returns:
            Command execution result with status and output.
        """
        body = {
            "registryId": f"reg::node::{action}",
            "target": {"nodeId": node_id},
            "parameters": parameters or {},
        }
        return await self._request("POST", "/commands", json_data=body)

    async def control_agent(
        self,
        node_id: str,
        action: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a control action on the Hydra agent.

        Args:
            node_id: The target node identifier.
            action: Action to perform (restart, update, config-reload, collect-now, probe-network, status).
            parameters: Optional parameters for the action.

        Returns:
            Command execution result with status and output.
        """
        body = {
            "registryId": f"reg::agent::{action}",
            "target": {"nodeId": node_id},
            "parameters": parameters or {},
        }
        return await self._request("POST", "/commands", json_data=body)

    async def get_command_status(self, command_id: str) -> dict[str, Any]:
        """Get the status and result of a command.

        Args:
            command_id: The command identifier.

        Returns:
            Command details including status and result.
        """
        return await self._request("GET", f"/commands/{command_id}")

    async def list_command_catalog(
        self,
        category: str | None = None,
    ) -> list[Any]:
        """List available commands from the command registry/catalog.

        Args:
            category: Filter by command category (service, node, agent).

        Returns:
            List of command definitions from the catalog.
        """
        params: dict[str, Any] = {}
        if category:
            params["category"] = category
        result = await self._request("GET", "/command-catalog", params=params)
        return self._expect_list_result(result, "/command-catalog")

    async def list_commands(
        self,
        node_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[Any]:
        """List command execution history with optional filters.

        Args:
            node_id: Filter by target node.
            status: Filter by command status.
            limit: Maximum number of results to return.

        Returns:
            List of command summary dictionaries.
        """
        params: dict[str, Any] = {"limit": limit}
        if node_id:
            params["nodeId"] = node_id
        if status:
            params["status"] = status
        result = await self._request("GET", "/commands", params=params)
        return self._expect_list_result(result, "/commands")

    async def get_queue_status(
        self,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        """Get the current command queue state and statistics.

        Args:
            node_id: Filter queue status by target node.

        Returns:
            Queue status with counts and statistics.
        """
        params: dict[str, Any] = {}
        if node_id:
            params["nodeId"] = node_id
        return await self._request("GET", "/commands/queue", params=params)

    async def control_device(
        self,
        entity_id: str,
        service: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Control an IoT device via Home Assistant integration.

        Args:
            entity_id: Home Assistant entity ID (e.g., light.living_room).
            service: Service to call (e.g., turn_on, set_temperature).
            data: Optional service parameters.

        Returns:
            Command execution result.
        """
        body = {
            "entityId": entity_id,
            "service": service,
            "data": data,
        }
        return await self._request("POST", "/ha/control", json_data=body)

    async def get_ha_status(self) -> dict[str, Any]:
        """Get Home Assistant integration status.

        Returns:
            Integration status including connection state and entity counts.
        """
        return await self._request("GET", "/ha/status")

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    async def list_notifications(
        self,
        tier: int | None = None,
        tier_min: int | None = None,
        status: str | None = None,
        source: str | None = None,
        node_id: str | None = None,
        notification_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List notifications visible to the current user.

        Args:
            tier: Filter by exact tier (1-5).
            tier_min: Filter by minimum tier.
            status: Filter by status (active, resolved, expired).
            source: Filter by source component.
            node_id: Filter by originating node.
            notification_type: Filter by notification type.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            Tuple of (list of notification dictionaries, total count).
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if tier is not None:
            params["tier"] = tier
        if tier_min is not None:
            params["tierMin"] = tier_min
        if status:
            params["status"] = status
        if source:
            params["source"] = source
        if node_id:
            params["nodeId"] = node_id
        if notification_type:
            params["type"] = notification_type
        result = await self._request("GET", "/notifications", params=params)
        return self._expect_list_result(result, "/notifications"), 0

    async def get_notification_stats(self) -> dict[str, Any]:
        """Get aggregated notification statistics.

        Returns:
            Stats with total, unread, byTier, byStatus, bySource.
        """
        return await self._request("GET", "/notifications/stats")

    async def get_notification(self, notification_id: str) -> dict[str, Any]:
        """Get a single notification by ID.

        Args:
            notification_id: The notification identifier.

        Returns:
            Notification details with read state.
        """
        return await self._request("GET", f"/notifications/{notification_id}")

    # ------------------------------------------------------------------
    # Audit Log
    # ------------------------------------------------------------------

    async def list_audit_entries(
        self,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List audit log entries with optional filtering.

        Args:
            action: Filter by action (e.g., create, update, delete).
            resource_type: Filter by resource type (e.g., node, service).
            resource_id: Filter by specific resource ID.
            actor_id: Filter by actor (user) ID.
            since: ISO timestamp for start of time range.
            until: ISO timestamp for end of time range.
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            List of audit log entry dictionaries.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if action:
            params["action"] = action
        if resource_type:
            params["resourceType"] = resource_type
        if resource_id:
            params["resourceId"] = resource_id
        if actor_id:
            params["actorId"] = actor_id
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        result = await self._request("GET", "/audit", params=params)
        return self._expect_list_result(result, "/audit")

    async def delete_audit_entries(
        self,
        since: str,
        until: str,
    ) -> dict[str, Any]:
        """Delete audit log entries within a time range.

        Args:
            since: ISO timestamp for start of deletion range (required).
            until: ISO timestamp for end of deletion range (required).

        Returns:
            Deletion result with count of removed entries.
        """
        params = {"since": since, "until": until}
        return await self._request("DELETE", "/audit", params=params)

    async def health_check(self) -> dict[str, Any]:
        """Check API health status.

        Returns:
            Health check result with service status and uptime.
        """
        return await self._request("GET", "/health")

    async def get_info(self) -> dict[str, Any]:
        """Get API information and statistics.

        Returns:
            API version, build info, and usage statistics.
        """
        return await self._request("GET", "/info")
