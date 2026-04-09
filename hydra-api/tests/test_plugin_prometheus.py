"""Tests for the Prometheus plugin handler."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from hydra.api.v1.services.plugins.prometheus import PrometheusHandler, _extract_ip

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def handler() -> PrometheusHandler:
    """Return a handler wired to a local Prometheus URL with no auth."""
    return PrometheusHandler(
        config={"url": "http://prometheus:9090"},
        credentials=None,
    )


@pytest.fixture
def handler_basic_auth() -> PrometheusHandler:
    """Return a handler configured with basic-auth credentials."""
    return PrometheusHandler(
        config={"url": "http://prometheus:9090"},
        credentials={"username": "admin", "password": "secret"},
    )


@pytest.fixture
def handler_bearer() -> PrometheusHandler:
    """Return a handler configured with a bearer token."""
    return PrometheusHandler(
        config={"url": "http://prometheus:9090"},
        credentials={"bearerToken": "tok_abc123"},
    )


def _ok_response(body: dict[str, Any], status_code: int = 200) -> httpx.Response:
    """Build a synthetic ``httpx.Response``."""
    resp = httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("GET", "http://prometheus:9090"),
    )
    return resp


# ── Manifest & Command Definitions ──────────────────────────────────────


class TestManifest:
    """Verify static MANIFEST constant."""

    def test_plugin_id(self) -> None:
        assert PrometheusHandler.MANIFEST["pluginId"] == "plg::prometheus"

    def test_classification_and_category(self) -> None:
        assert PrometheusHandler.MANIFEST["classification"] == "core"
        assert PrometheusHandler.MANIFEST["category"] == "monitoring"

    def test_touchpoints(self) -> None:
        tp = PrometheusHandler.MANIFEST["touchpoints"]
        assert tp["profileEnrichment"] is True
        assert tp["discoveryProvider"] is True
        assert tp["commandProvider"] is True
        assert tp["executionHandler"] is True
        assert tp["topologyProvider"] is False
        assert tp["workflowBlockProvider"] is False

    def test_contributed_commands(self) -> None:
        cmds = PrometheusHandler.MANIFEST["contributedCommands"]
        assert len(cmds) == 5
        assert "reg::prometheus::query" in cmds
        assert "reg::prometheus::query-range" in cmds
        assert "reg::prometheus::targets" in cmds
        assert "reg::prometheus::alerts" in cmds
        assert "reg::prometheus::rules" in cmds

    def test_supported_tiers(self) -> None:
        assert PrometheusHandler.MANIFEST["supportedTiers"] == ["normal", "max"]


class TestCommandDefinitions:
    """Verify static COMMAND_DEFINITIONS constant."""

    def test_count(self) -> None:
        assert len(PrometheusHandler.COMMAND_DEFINITIONS) == 5

    def test_registry_ids(self) -> None:
        ids = {d["registryId"] for d in PrometheusHandler.COMMAND_DEFINITIONS}
        expected = {
            "reg::prometheus::query",
            "reg::prometheus::query-range",
            "reg::prometheus::targets",
            "reg::prometheus::alerts",
            "reg::prometheus::rules",
        }
        assert ids == expected

    def test_query_rbac(self) -> None:
        defn = next(d for d in PrometheusHandler.COMMAND_DEFINITIONS if d["registryId"] == "reg::prometheus::query")
        assert defn["rbac"]["minimumRole"] == "operator"
        assert defn["rbac"]["dangerLevel"] == "safe"

    def test_targets_rbac(self) -> None:
        defn = next(d for d in PrometheusHandler.COMMAND_DEFINITIONS if d["registryId"] == "reg::prometheus::targets")
        assert defn["rbac"]["minimumRole"] == "viewer"
        assert defn["rbac"]["dangerLevel"] == "safe"

    def test_alerts_rbac(self) -> None:
        defn = next(d for d in PrometheusHandler.COMMAND_DEFINITIONS if d["registryId"] == "reg::prometheus::alerts")
        assert defn["rbac"]["minimumRole"] == "viewer"


# ── connect() ───────────────────────────────────────────────────────────


class TestConnect:
    """Test the ``connect`` lifecycle method."""

    @pytest.mark.asyncio
    async def test_connect_success(self, handler: PrometheusHandler) -> None:
        mock_resp = _ok_response({}, 200)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_unhealthy(self, handler: PrometheusHandler) -> None:
        mock_resp = _ok_response({}, 503)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_network_error(self, handler: PrometheusHandler) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")):
            result = await handler.connect()
        assert result is False


# ── health_check() ──────────────────────────────────────────────────────


class TestHealthCheck:
    """Test the ``health_check`` lifecycle method."""

    @pytest.mark.asyncio
    async def test_healthy(self, handler: PrometheusHandler) -> None:
        mock_resp = _ok_response({}, 200)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.health_check()
        assert result["status"] == "healthy"
        assert result["consecutiveFailures"] == 0
        assert result["lastError"] is None
        assert result["responseTimeMs"] >= 0

    @pytest.mark.asyncio
    async def test_unhealthy_status_code(self, handler: PrometheusHandler) -> None:
        mock_resp = _ok_response({}, 500)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.health_check()
        assert result["status"] == "unhealthy"
        assert result["lastError"] == "HTTP 500"

    @pytest.mark.asyncio
    async def test_unhealthy_exception(self, handler: PrometheusHandler) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("timeout")):
            result = await handler.health_check()
        assert result["status"] == "unhealthy"
        assert "timeout" in (result["lastError"] or "")


# ── enrich_profile() ───────────────────────────────────────────────────


class TestEnrichProfile:
    """Test profile enrichment via PromQL metric queries."""

    @pytest.mark.asyncio
    async def test_enrich_with_metrics(self, handler: PrometheusHandler) -> None:
        prom_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "instance": "testhost:9100", "job": "node"},
                        "value": [1700000000, "1"],
                    }
                ],
            },
        }
        mock_resp = _ok_response(prom_response, 200)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.enrich_profile(
                node_id="test-node",
                profile={"network": {"hostname": "testhost"}},
            )

        assert "collectedAt" in result
        assert "metrics" in result
        # Both metrics use the same mock so both should have results
        assert "up" in result["metrics"]
        assert result["metrics"]["up"][0]["value"] == "1"

    @pytest.mark.asyncio
    async def test_enrich_http_error(self, handler: PrometheusHandler) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("down")):
            result = await handler.enrich_profile(
                node_id="test-node",
                profile={"network": {"hostname": "testhost"}},
            )

        assert "error" in result
        assert result["metrics"] == {}


# ── discover_nodes() ───────────────────────────────────────────────────


class TestDiscoverNodes:
    """Test scrape-target discovery."""

    @pytest.mark.asyncio
    async def test_discover_active_targets(self, handler: PrometheusHandler) -> None:
        targets_response = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {
                        "labels": {"instance": "192.168.1.50:9100", "job": "node-exporter"},
                        "scrapeUrl": "http://192.168.1.50:9100/metrics",
                        "health": "up",
                    },
                    {
                        "labels": {"instance": "10.0.0.1:9090", "job": "prometheus"},
                        "scrapeUrl": "http://10.0.0.1:9090/metrics",
                        "health": "up",
                    },
                ],
                "droppedTargets": [],
            },
        }
        mock_resp = _ok_response(targets_response, 200)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            results = await handler.discover_nodes()

        assert len(results) == 2
        first = results[0]
        assert first["source"] == "plg::prometheus"
        assert first["ip"] == "192.168.1.50"
        assert first["job"] == "node-exporter"
        assert first["health"] == "up"
        assert first["scrapeUrl"] == "http://192.168.1.50:9100/metrics"

    @pytest.mark.asyncio
    async def test_discover_empty(self, handler: PrometheusHandler) -> None:
        targets_response = {"status": "success", "data": {"activeTargets": [], "droppedTargets": []}}
        mock_resp = _ok_response(targets_response, 200)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            results = await handler.discover_nodes()

        assert results == []

    @pytest.mark.asyncio
    async def test_discover_http_error(self, handler: PrometheusHandler) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")):
            results = await handler.discover_nodes()

        assert results == []


# ── execute_command() ───────────────────────────────────────────────────


class TestExecuteCommand:
    """Test command dispatch and execution."""

    @pytest.mark.asyncio
    async def test_exec_query_success(self, handler: PrometheusHandler) -> None:
        prom_body = {
            "status": "success",
            "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1700000000, "42"]}]},
        }
        mock_resp = _ok_response(prom_body, 200)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.execute_command(
                "reg::prometheus::query",
                target={"nodeId": "n1"},
                params={"query": "up"},
            )

        assert result["success"] is True
        assert result["output"]["resultType"] == "vector"

    @pytest.mark.asyncio
    async def test_exec_query_missing_param(self, handler: PrometheusHandler) -> None:
        result = await handler.execute_command(
            "reg::prometheus::query",
            target={"nodeId": "n1"},
            params={},
        )
        assert result["success"] is False
        assert "query" in result["output"]

    @pytest.mark.asyncio
    async def test_exec_targets_success(self, handler: PrometheusHandler) -> None:
        prom_body = {
            "data": {"activeTargets": [{"labels": {"job": "node"}}]},
        }
        mock_resp = _ok_response(prom_body, 200)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.execute_command(
                "reg::prometheus::targets",
                target={"nodeId": "n1"},
                params={"state": "active"},
            )

        assert result["success"] is True
        assert "activeTargets" in result["output"]

    @pytest.mark.asyncio
    async def test_exec_unknown_command(self, handler: PrometheusHandler) -> None:
        result = await handler.execute_command(
            "reg::prometheus::unknown",
            target={"nodeId": "n1"},
            params={},
        )
        assert result["success"] is False
        assert "Unknown" in result["output"]

    @pytest.mark.asyncio
    async def test_exec_query_range_missing_params(self, handler: PrometheusHandler) -> None:
        result = await handler.execute_command(
            "reg::prometheus::query-range",
            target={"nodeId": "n1"},
            params={"query": "up"},
        )
        assert result["success"] is False
        assert "start" in result["output"]

    @pytest.mark.asyncio
    async def test_exec_alerts_success(self, handler: PrometheusHandler) -> None:
        prom_body = {"data": {"alerts": [{"state": "firing", "labels": {"alertname": "HighLoad"}}]}}
        mock_resp = _ok_response(prom_body, 200)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.execute_command(
                "reg::prometheus::alerts",
                target={"nodeId": "n1"},
                params={},
            )

        assert result["success"] is True
        assert "alerts" in result["output"]

    @pytest.mark.asyncio
    async def test_exec_rules_success(self, handler: PrometheusHandler) -> None:
        prom_body = {"data": {"groups": [{"name": "test-group", "rules": []}]}}
        mock_resp = _ok_response(prom_body, 200)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.execute_command(
                "reg::prometheus::rules",
                target={"nodeId": "n1"},
                params={"type": "alert"},
            )

        assert result["success"] is True
        assert "groups" in result["output"]


# ── Auth configuration ──────────────────────────────────────────────────


class TestAuth:
    """Verify that auth kwargs are built correctly."""

    def test_no_auth(self, handler: PrometheusHandler) -> None:
        kwargs = handler._client_kwargs()
        assert "auth" not in kwargs
        assert "headers" not in kwargs or kwargs.get("headers") == {}

    def test_basic_auth(self, handler_basic_auth: PrometheusHandler) -> None:
        kwargs = handler_basic_auth._client_kwargs()
        assert kwargs.get("auth") is not None
        assert isinstance(kwargs["auth"], httpx.BasicAuth)

    def test_bearer_token(self, handler_bearer: PrometheusHandler) -> None:
        kwargs = handler_bearer._client_kwargs()
        assert "auth" not in kwargs
        headers = kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer tok_abc123"


# ── _extract_ip helper ─────────────────────────────────────────────────


class TestExtractIp:
    """Unit tests for the _extract_ip utility."""

    def test_host_port(self) -> None:
        assert _extract_ip("192.168.1.50:9090") == "192.168.1.50"

    def test_full_url(self) -> None:
        assert _extract_ip("http://192.168.1.50:9090/metrics") == "192.168.1.50"

    def test_hostname_port(self) -> None:
        assert _extract_ip("myhost:9090") == "myhost"

    def test_empty(self) -> None:
        assert _extract_ip("") == ""
