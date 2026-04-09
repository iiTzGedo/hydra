"""Prometheus plugin handler.

Provides PromQL querying, scrape-target discovery, alert/rule listing,
and profile enrichment with key node metrics via the Prometheus HTTP API.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpx
import structlog

from hydra.api.v1.services.plugins.base import PluginHandler

logger = structlog.get_logger(__name__)

_NOW = datetime.now(UTC)

# ── Helpers ────────────────────────────────────────────────────────────


def _build_auth(
    config: dict[str, Any],
    credentials: dict[str, str] | None,
) -> tuple[httpx.BasicAuth | None, dict[str, str]]:
    """Return (auth, extra_headers) derived from config + credentials.

    Priority: bearerToken > username/password > no auth.
    """
    creds = credentials or {}
    bearer = creds.get("bearerToken") or config.get("bearerToken")
    if bearer:
        return None, {"Authorization": f"Bearer {bearer}"}

    username = creds.get("username") or config.get("username")
    password = creds.get("password") or config.get("password")
    if username and password:
        return httpx.BasicAuth(username, password), {}

    return None, {}


class PrometheusHandler(PluginHandler):
    """Plugin handler for Prometheus monitoring integration."""

    # ── Manifest ────────────────────────────────────────────────────

    MANIFEST: ClassVar[dict[str, Any]] = {
        "pluginId": "plg::prometheus",
        "name": "Prometheus",
        "version": "1.0.0",
        "description": "Prometheus monitoring integration — PromQL queries, target discovery, alerts, and profile enrichment",
        "author": "Hydra Team",
        "classification": "core",
        "category": "monitoring",
        "touchpoints": {
            "profileEnrichment": True,
            "discoveryProvider": True,
            "commandProvider": True,
            "executionHandler": True,
            "topologyProvider": False,
            "workflowBlockProvider": False,
        },
        "supportedTiers": ["normal", "max"],
        "healthCheckEndpoint": None,  # connect() uses /-/healthy directly
        "contributedCommands": [
            "reg::prometheus::query",
            "reg::prometheus::query-range",
            "reg::prometheus::targets",
            "reg::prometheus::alerts",
            "reg::prometheus::rules",
        ],
    }

    # ── Command Definitions ─────────────────────────────────────────

    COMMAND_DEFINITIONS: ClassVar[list[dict[str, Any]]] = [
        {
            "registryId": "reg::prometheus::query",
            "category": "prometheus",
            "action": "query",
            "displayName": "PromQL Instant Query",
            "description": "Execute a PromQL instant query against Prometheus",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "PromQL expression"},
                    "time": {"type": "string", "description": "Evaluation timestamp (RFC3339 or Unix)"},
                },
            },
            "execution": {
                "handler": "prometheus_query",
                "timeout": 30,
                "deliveryMode": "direct_or_poll",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "operator",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "safe",
                "controlPermission": "plugins:control:prometheus:query",
            },
            "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
            "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
        },
        {
            "registryId": "reg::prometheus::query-range",
            "category": "prometheus",
            "action": "query-range",
            "displayName": "PromQL Range Query",
            "description": "Execute a PromQL range query over a time window",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "required": ["query", "start", "end", "step"],
                "properties": {
                    "query": {"type": "string", "description": "PromQL expression"},
                    "start": {"type": "string", "description": "Start timestamp (RFC3339 or Unix)"},
                    "end": {"type": "string", "description": "End timestamp (RFC3339 or Unix)"},
                    "step": {"type": "string", "description": "Query resolution step (e.g. '15s', '1m')"},
                },
            },
            "execution": {
                "handler": "prometheus_query_range",
                "timeout": 60,
                "deliveryMode": "direct_or_poll",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "operator",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "safe",
                "controlPermission": "plugins:control:prometheus:query-range",
            },
            "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
            "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
        },
        {
            "registryId": "reg::prometheus::targets",
            "category": "prometheus",
            "action": "targets",
            "displayName": "List Scrape Targets",
            "description": "List all configured Prometheus scrape targets and their health",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "Filter by target state (active, dropped, any)",
                    },
                },
            },
            "execution": {
                "handler": "prometheus_targets",
                "timeout": 15,
                "deliveryMode": "direct_or_poll",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "viewer",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "safe",
                "controlPermission": "plugins:control:prometheus:targets",
            },
            "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
            "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
        },
        {
            "registryId": "reg::prometheus::alerts",
            "category": "prometheus",
            "action": "alerts",
            "displayName": "List Active Alerts",
            "description": "List currently active Prometheus alerts",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": None,
            "execution": {
                "handler": "prometheus_alerts",
                "timeout": 15,
                "deliveryMode": "direct_or_poll",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "viewer",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "safe",
                "controlPermission": "plugins:control:prometheus:alerts",
            },
            "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
            "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
        },
        {
            "registryId": "reg::prometheus::rules",
            "category": "prometheus",
            "action": "rules",
            "displayName": "List Rules",
            "description": "List alerting and recording rules from Prometheus",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "Filter by rule type (alert, record)",
                    },
                },
            },
            "execution": {
                "handler": "prometheus_rules",
                "timeout": 15,
                "deliveryMode": "direct_or_poll",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "viewer",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "safe",
                "controlPermission": "plugins:control:prometheus:rules",
            },
            "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
            "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
        },
    ]

    # ── Config schema defaults ──────────────────────────────────────

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "url": {"type": "string", "default": "http://prometheus:9090", "description": "Prometheus base URL"},
        "username": {"type": "string", "default": None, "description": "Basic auth username (optional)"},
        "password": {"type": "string", "default": None, "description": "Basic auth password (optional)"},
        "bearerToken": {"type": "string", "default": None, "description": "Bearer token (optional)"},
    }

    # ── Internal helpers ────────────────────────────────────────────

    @property
    def _base_url(self) -> str:
        """Return the Prometheus base URL (no trailing slash)."""
        url: str = self.config.get("url", "http://prometheus:9090")
        return url.rstrip("/")

    def _client_kwargs(self) -> dict[str, Any]:
        """Build kwargs for ``httpx.AsyncClient``."""
        auth, headers = _build_auth(self.config, self.credentials)
        kwargs: dict[str, Any] = {"timeout": 10.0}
        if auth:
            kwargs["auth"] = auth
        if headers:
            kwargs["headers"] = headers
        return kwargs

    # ── Lifecycle ───────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Verify Prometheus is reachable via ``/-/healthy``."""
        url = f"{self._base_url}/-/healthy"
        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                resp = await client.get(url)
                healthy = resp.status_code == 200
                logger.info("prometheus_connect", url=url, healthy=healthy)
                return healthy
        except httpx.HTTPError as exc:
            logger.warning("prometheus_connect_failed", url=url, error=str(exc))
            return False

    async def health_check(self) -> dict[str, Any]:
        """Return a health-status dict for the Prometheus connection."""
        url = f"{self._base_url}/-/healthy"
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                resp = await client.get(url)
                elapsed_ms = (time.monotonic() - start) * 1000
                if resp.status_code == 200:
                    return {
                        "status": "healthy",
                        "lastCheck": datetime.now(UTC).isoformat(),
                        "consecutiveFailures": 0,
                        "lastError": None,
                        "responseTimeMs": round(elapsed_ms, 2),
                    }
                return {
                    "status": "unhealthy",
                    "lastCheck": datetime.now(UTC).isoformat(),
                    "consecutiveFailures": 1,
                    "lastError": f"HTTP {resp.status_code}",
                    "responseTimeMs": round(elapsed_ms, 2),
                }
        except httpx.HTTPError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            return {
                "status": "unhealthy",
                "lastCheck": datetime.now(UTC).isoformat(),
                "consecutiveFailures": 1,
                "lastError": str(exc),
                "responseTimeMs": round(elapsed_ms, 2),
            }

    # ── Touchpoints ─────────────────────────────────────────────────

    async def enrich_profile(
        self,
        node_id: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Query key node metrics and return a snapshot for profile enrichment.

        Queries ``up`` and ``node_load1`` filtered by the node's hostname
        extracted from the profile.
        """
        hostname = profile.get("network", {}).get("hostname", node_id)
        url = f"{self._base_url}/api/v1/query"
        enrichment: dict[str, Any] = {
            "collectedAt": datetime.now(UTC).isoformat(),
            "metrics": {},
        }

        queries = {
            "up": f'up{{instance=~".*{hostname}.*"}}',
            "node_load1": f'node_load1{{instance=~".*{hostname}.*"}}',
        }

        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                for metric_name, promql in queries.items():
                    resp = await client.get(url, params={"query": promql})
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("data", {}).get("result", [])
                        if results:
                            enrichment["metrics"][metric_name] = [
                                {
                                    "labels": r.get("metric", {}),
                                    "value": r.get("value", [None, None])[1],
                                    "timestamp": r.get("value", [None, None])[0],
                                }
                                for r in results
                            ]
        except httpx.HTTPError as exc:
            logger.warning(
                "prometheus_enrich_profile_failed",
                node_id=node_id,
                error=str(exc),
            )
            enrichment["error"] = str(exc)

        return enrichment

    async def discover_nodes(self) -> list[dict[str, Any]]:
        """Extract active scrape targets as discovered resources."""
        url = f"{self._base_url}/api/v1/targets"
        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(
                        "prometheus_discover_targets_failed",
                        status=resp.status_code,
                    )
                    return []

                data = resp.json()
                active_targets = data.get("data", {}).get("activeTargets", [])
                discovered: list[dict[str, Any]] = []

                for target in active_targets:
                    labels = target.get("labels", {})
                    scrape_url = target.get("scrapeUrl", "")
                    instance = labels.get("instance", "")

                    # Extract IP/host from instance label or scrapeUrl
                    ip = _extract_ip(instance or scrape_url)

                    discovered.append({
                        "source": "plg::prometheus",
                        "discoveredAt": datetime.now(UTC).isoformat(),
                        "ip": ip,
                        "hostname": labels.get("instance", ""),
                        "job": labels.get("job", ""),
                        "scrapeUrl": scrape_url,
                        "health": target.get("health", "unknown"),
                        "labels": labels,
                    })

                return discovered

        except httpx.HTTPError as exc:
            logger.warning("prometheus_discover_nodes_failed", error=str(exc))
            return []

    async def execute_command(
        self,
        command_id: str,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a command to the appropriate Prometheus API endpoint."""
        _CommandFn = Callable[  # noqa: N806
            [dict[str, Any], dict[str, Any]],
            Coroutine[Any, Any, dict[str, Any]],
        ]
        dispatch: dict[str, _CommandFn] = {
            "reg::prometheus::query": self._exec_query,
            "reg::prometheus::query-range": self._exec_query_range,
            "reg::prometheus::targets": self._exec_targets,
            "reg::prometheus::alerts": self._exec_alerts,
            "reg::prometheus::rules": self._exec_rules,
        }

        cmd_handler = dispatch.get(command_id)
        if cmd_handler is None:
            return {
                "success": False,
                "output": f"Unknown Prometheus command: {command_id}",
            }

        return await cmd_handler(target, params)

    # ── Command implementations ─────────────────────────────────────

    async def _exec_query(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a PromQL instant query."""
        query = params.get("query")
        if not query:
            return {"success": False, "output": "Missing required parameter: query"}

        url = f"{self._base_url}/api/v1/query"
        query_params: dict[str, str] = {"query": query}
        if params.get("time"):
            query_params["time"] = params["time"]

        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                resp = await client.get(url, params=query_params)
                body = resp.json()
                if resp.status_code == 200 and body.get("status") == "success":
                    return {"success": True, "output": body["data"]}
                return {"success": False, "output": body.get("error", f"HTTP {resp.status_code}")}
        except httpx.HTTPError as exc:
            return {"success": False, "output": str(exc)}

    async def _exec_query_range(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a PromQL range query."""
        required = ("query", "start", "end", "step")
        missing = [k for k in required if not params.get(k)]
        if missing:
            return {"success": False, "output": f"Missing required parameters: {', '.join(missing)}"}

        url = f"{self._base_url}/api/v1/query_range"
        query_params = {k: params[k] for k in required}

        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                resp = await client.get(url, params=query_params)
                body = resp.json()
                if resp.status_code == 200 and body.get("status") == "success":
                    return {"success": True, "output": body["data"]}
                return {"success": False, "output": body.get("error", f"HTTP {resp.status_code}")}
        except httpx.HTTPError as exc:
            return {"success": False, "output": str(exc)}

    async def _exec_targets(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """List scrape targets, optionally filtered by state."""
        url = f"{self._base_url}/api/v1/targets"
        query_params: dict[str, str] = {}
        if params.get("state"):
            query_params["state"] = params["state"]

        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                resp = await client.get(url, params=query_params)
                body = resp.json()
                if resp.status_code == 200:
                    return {"success": True, "output": body.get("data", {})}
                return {"success": False, "output": body.get("error", f"HTTP {resp.status_code}")}
        except httpx.HTTPError as exc:
            return {"success": False, "output": str(exc)}

    async def _exec_alerts(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """List active alerts."""
        url = f"{self._base_url}/api/v1/alerts"
        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                resp = await client.get(url)
                body = resp.json()
                if resp.status_code == 200:
                    return {"success": True, "output": body.get("data", {})}
                return {"success": False, "output": body.get("error", f"HTTP {resp.status_code}")}
        except httpx.HTTPError as exc:
            return {"success": False, "output": str(exc)}

    async def _exec_rules(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """List alerting and recording rules."""
        url = f"{self._base_url}/api/v1/rules"
        query_params: dict[str, str] = {}
        if params.get("type"):
            query_params["type"] = params["type"]

        try:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                resp = await client.get(url, params=query_params)
                body = resp.json()
                if resp.status_code == 200:
                    return {"success": True, "output": body.get("data", {})}
                return {"success": False, "output": body.get("error", f"HTTP {resp.status_code}")}
        except httpx.HTTPError as exc:
            return {"success": False, "output": str(exc)}


# ── Module-level utilities ─────────────────────────────────────────────


def _extract_ip(instance_or_url: str) -> str:
    """Best-effort IP extraction from an instance label or scrape URL.

    Examples:
        "192.168.1.50:9090" -> "192.168.1.50"
        "http://192.168.1.50:9090/metrics" -> "192.168.1.50"
        "myhost:9090" -> "myhost"
    """
    if not instance_or_url:
        return ""

    # If it looks like a full URL, parse properly
    if "://" in instance_or_url:
        parsed = urlparse(instance_or_url)
        return parsed.hostname or ""

    # Otherwise it's likely "host:port"
    host = instance_or_url.rsplit(":", 1)[0]
    return host
