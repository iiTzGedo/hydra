"""Tests for the Home Assistant plugin handler."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hydra.api.v1.services.plugins.homeassistant import HomeAssistantHandler

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def ha_config() -> dict[str, Any]:
    """Standard HA plugin configuration."""
    return {
        "url": "http://homeassistant.local:8123",
        "token": "test-long-lived-token",
        "verifySsl": False,
    }


@pytest.fixture
def handler(ha_config: dict[str, Any]) -> HomeAssistantHandler:
    """Instantiate a HomeAssistantHandler with test config."""
    return HomeAssistantHandler(config=ha_config)


@pytest.fixture
def sample_states() -> list[dict[str, Any]]:
    """Sample HA entity states used in multiple tests."""
    return [
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"friendly_name": "Living Room", "brightness": 255},
            "last_changed": "2026-04-09T10:00:00+00:00",
        },
        {
            "entity_id": "light.bedroom",
            "state": "off",
            "attributes": {"friendly_name": "Bedroom"},
            "last_changed": "2026-04-09T09:00:00+00:00",
        },
        {
            "entity_id": "switch.desk_lamp",
            "state": "on",
            "attributes": {"friendly_name": "Desk Lamp"},
            "last_changed": "2026-04-09T08:00:00+00:00",
        },
        {
            "entity_id": "sensor.temperature",
            "state": "21.5",
            "attributes": {"friendly_name": "Temperature", "unit_of_measurement": "°C"},
            "last_changed": "2026-04-09T10:05:00+00:00",
        },
    ]


def _build_response(
    status_code: int = 200,
    json_data: Any = None,
) -> httpx.Response:
    """Build a mock httpx.Response with the given status and JSON body."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.elapsed = MagicMock()
    resp.elapsed.total_seconds.return_value = 0.042
    return resp


# ── MANIFEST tests ──────────────────────────────────────────────────────


class TestManifest:
    """Validate the static MANIFEST constant."""

    def test_manifest_plugin_id(self) -> None:
        assert HomeAssistantHandler.MANIFEST["pluginId"] == "plg::homeassistant"

    def test_manifest_classification(self) -> None:
        manifest = HomeAssistantHandler.MANIFEST
        assert manifest["classification"] == "core"
        assert manifest["category"] == "infrastructure"

    def test_manifest_touchpoints(self) -> None:
        tp = HomeAssistantHandler.MANIFEST["touchpoints"]
        assert tp["discoveryProvider"] is True
        assert tp["commandProvider"] is True
        assert tp["executionHandler"] is True
        assert tp["profileEnrichment"] is False

    def test_manifest_supported_tiers(self) -> None:
        assert set(HomeAssistantHandler.MANIFEST["supportedTiers"]) == {"normal", "max"}

    def test_manifest_contributed_commands(self) -> None:
        contributed = HomeAssistantHandler.MANIFEST["contributedCommands"]
        assert len(contributed) == 6
        assert "reg::ha::list-entities" in contributed
        assert "reg::ha::toggle" in contributed


# ── COMMAND_DEFINITIONS tests ───────────────────────────────────────────


class TestCommandDefinitions:
    """Validate the static COMMAND_DEFINITIONS constant."""

    def test_command_count(self) -> None:
        assert len(HomeAssistantHandler.COMMAND_DEFINITIONS) == 6

    def test_all_commands_have_required_keys(self) -> None:
        required_keys = {"registryId", "category", "action", "displayName", "description",
                         "execution", "rbac", "audit", "metadata"}
        for cmd in HomeAssistantHandler.COMMAND_DEFINITIONS:
            missing = required_keys - set(cmd.keys())
            assert not missing, f"Command {cmd['registryId']} missing keys: {missing}"

    def test_registry_id_prefix(self) -> None:
        for cmd in HomeAssistantHandler.COMMAND_DEFINITIONS:
            assert cmd["registryId"].startswith("reg::ha::")

    def test_family_role_commands(self) -> None:
        """turn-on, turn-off, toggle should require family role."""
        family_ids = {"reg::ha::turn-on", "reg::ha::turn-off", "reg::ha::toggle"}
        for cmd in HomeAssistantHandler.COMMAND_DEFINITIONS:
            if cmd["registryId"] in family_ids:
                assert cmd["rbac"]["minimumRole"] == "family"
                assert cmd["rbac"]["dangerLevel"] == "safe"


# ── connect() tests ─────────────────────────────────────────────────────


class TestConnect:
    """Tests for the connect() lifecycle method."""

    @pytest.mark.asyncio
    async def test_connect_success(self, handler: HomeAssistantHandler) -> None:
        resp = _build_response(200, {"message": "API running."})
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            result = await handler.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_failure_status(self, handler: HomeAssistantHandler) -> None:
        resp = _build_response(401, {"message": "Unauthorized"})
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            result = await handler.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_network_error(self, handler: HomeAssistantHandler) -> None:
        with patch.object(
            handler,
            "_request",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await handler.connect()
        assert result is False


# ── health_check() tests ────────────────────────────────────────────────


class TestHealthCheck:
    """Tests for the health_check() lifecycle method."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, handler: HomeAssistantHandler) -> None:
        resp = _build_response(200, {"message": "API running."})
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            result = await handler.health_check()

        assert result["status"] == "healthy"
        assert result["consecutiveFailures"] == 0
        assert result["lastError"] is None
        assert result["responseTimeMs"] is not None

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, handler: HomeAssistantHandler) -> None:
        resp = _build_response(500)
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            result = await handler.health_check()

        assert result["status"] == "unhealthy"
        assert result["consecutiveFailures"] == 1
        assert result["lastError"] == "HTTP 500"


# ── discover_nodes() tests ──────────────────────────────────────────────


class TestDiscoverNodes:
    """Tests for entity discovery via GET /api/states."""

    @pytest.mark.asyncio
    async def test_discover_groups_by_domain(
        self,
        handler: HomeAssistantHandler,
        sample_states: list[dict[str, Any]],
    ) -> None:
        resp = _build_response(200, sample_states)
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            discovered = await handler.discover_nodes()

        # 3 domains: light (2), switch (1), sensor (1)
        assert len(discovered) == 3
        domains = {d["domain"] for d in discovered}
        assert domains == {"light", "switch", "sensor"}

        # Verify entity counts
        light_group = next(d for d in discovered if d["domain"] == "light")
        assert light_group["entityCount"] == 2
        assert light_group["source"] == "homeassistant"
        assert len(light_group["entities"]) == 2

    @pytest.mark.asyncio
    async def test_discover_failure_returns_empty(
        self,
        handler: HomeAssistantHandler,
    ) -> None:
        resp = _build_response(500)
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            discovered = await handler.discover_nodes()
        assert discovered == []


# ── execute_command() tests ─────────────────────────────────────────────


class TestExecuteCommand:
    """Tests for command execution dispatch."""

    @pytest.mark.asyncio
    async def test_list_entities(
        self,
        handler: HomeAssistantHandler,
        sample_states: list[dict[str, Any]],
    ) -> None:
        resp = _build_response(200, sample_states)
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            result = await handler.execute_command(
                "reg::ha::list-entities", {}, {},
            )

        assert result["success"] is True
        assert result["data"]["count"] == 4

    @pytest.mark.asyncio
    async def test_list_entities_domain_filter(
        self,
        handler: HomeAssistantHandler,
        sample_states: list[dict[str, Any]],
    ) -> None:
        resp = _build_response(200, sample_states)
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            result = await handler.execute_command(
                "reg::ha::list-entities", {}, {"domain": "light"},
            )

        assert result["success"] is True
        assert result["data"]["count"] == 2

    @pytest.mark.asyncio
    async def test_get_state(self, handler: HomeAssistantHandler) -> None:
        entity_data = {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"brightness": 255},
        }
        resp = _build_response(200, entity_data)
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            result = await handler.execute_command(
                "reg::ha::get-state",
                {"entityId": "light.living_room"},
                {},
            )

        assert result["success"] is True
        assert "on" in result["output"]
        assert result["data"]["entity_id"] == "light.living_room"

    @pytest.mark.asyncio
    async def test_get_state_missing_entity_id(
        self,
        handler: HomeAssistantHandler,
    ) -> None:
        result = await handler.execute_command("reg::ha::get-state", {}, {})
        assert result["success"] is False
        assert "entityId" in result["output"]

    @pytest.mark.asyncio
    async def test_turn_on(self, handler: HomeAssistantHandler) -> None:
        resp = _build_response(200, [])
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp) as mock_req:
            result = await handler.execute_command(
                "reg::ha::turn-on",
                {"entityId": "light.living_room"},
                {},
            )

        assert result["success"] is True
        assert "turn_on" in result["output"]
        # Verify the correct HA API path was called
        mock_req.assert_awaited_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/services/light/turn_on"

    @pytest.mark.asyncio
    async def test_turn_off(self, handler: HomeAssistantHandler) -> None:
        resp = _build_response(200, [])
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp) as mock_req:
            result = await handler.execute_command(
                "reg::ha::turn-off",
                {"entityId": "switch.desk_lamp"},
                {},
            )

        assert result["success"] is True
        assert "turn_off" in result["output"]
        call_args = mock_req.call_args
        assert call_args[0][1] == "/api/services/switch/turn_off"

    @pytest.mark.asyncio
    async def test_toggle(self, handler: HomeAssistantHandler) -> None:
        resp = _build_response(200, [])
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp):
            result = await handler.execute_command(
                "reg::ha::toggle",
                {"entityId": "switch.desk_lamp"},
                {},
            )

        assert result["success"] is True
        assert "toggle" in result["output"]

    @pytest.mark.asyncio
    async def test_call_service(self, handler: HomeAssistantHandler) -> None:
        resp = _build_response(200, [{"entity_id": "light.living_room", "state": "on"}])
        with patch.object(handler, "_request", new_callable=AsyncMock, return_value=resp) as mock_req:
            result = await handler.execute_command(
                "reg::ha::call-service",
                {"domain": "light", "service": "turn_on"},
                {"entityId": "light.living_room", "serviceData": {"brightness": 128}},
            )

        assert result["success"] is True
        assert "light.turn_on" in result["output"]
        call_args = mock_req.call_args
        assert call_args[0][1] == "/api/services/light/turn_on"
        body = call_args[1]["json_body"]
        assert body["entity_id"] == "light.living_room"
        assert body["brightness"] == 128

    @pytest.mark.asyncio
    async def test_unknown_command(self, handler: HomeAssistantHandler) -> None:
        result = await handler.execute_command("reg::ha::nonexistent", {}, {})
        assert result["success"] is False
        assert "Unknown command" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_http_error(self, handler: HomeAssistantHandler) -> None:
        with patch.object(
            handler,
            "_request",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await handler.execute_command(
                "reg::ha::list-entities", {}, {},
            )

        assert result["success"] is False
        assert "HTTP error" in result["output"]
