"""Tests for HydraClient methods and error handling."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hydra_mcp.auth import AuthContext, set_auth_context
from hydra_mcp.client import HydraAPIError, HydraClient
from hydra_mcp.config import Settings


def _make_settings(**overrides):
    """Create a Settings instance for testing."""
    defaults = {
        "api_url": "http://test-api:8080/api/v1",
        "api_key": "test-key",
        "api_timeout": 5,
        "transport": "stdio",
        "internal_secret": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _mock_response(status_code=200, json_data=None):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


class TestClientInit:
    """Tests for HydraClient initialization."""

    def test_default_settings(self):
        client = HydraClient()
        assert client.settings is not None
        assert client._client is None

    def test_custom_settings(self):
        s = _make_settings(api_url="http://custom:9090/api/v1")
        client = HydraClient(s)
        assert client.settings.api_url == "http://custom:9090/api/v1"


class TestGetClient:
    """Tests for _get_client connection management."""

    async def test_creates_new_client(self):
        s = _make_settings()
        client = HydraClient(s)
        http_client = await client._get_client()
        assert http_client is not None
        assert not http_client.is_closed
        await client.close()

    async def test_reuses_existing_client(self):
        s = _make_settings()
        client = HydraClient(s)
        c1 = await client._get_client()
        c2 = await client._get_client()
        assert c1 is c2
        await client.close()

    async def test_recreates_if_closed(self):
        s = _make_settings()
        client = HydraClient(s)
        c1 = await client._get_client()
        await c1.aclose()
        c2 = await client._get_client()
        assert c1 is not c2
        await client.close()

    async def test_api_key_in_headers(self):
        s = _make_settings(api_key="my-secret-key")
        client = HydraClient(s)
        http_client = await client._get_client()
        assert http_client.headers.get("X-API-Key") == "my-secret-key"
        await client.close()

    async def test_no_api_key(self):
        s = _make_settings(api_key=None)
        client = HydraClient(s)
        http_client = await client._get_client()
        assert "X-API-Key" not in http_client.headers
        await client.close()


class TestRequestWithMeta:
    """Tests for _request_with_meta retry and error handling."""

    async def test_success_returns_data_and_meta(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": [{"nodeId": "n1"}], "meta": {"total": 1}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            payload, meta = await client._request_with_meta("GET", "/nodes")
            assert payload == [{"nodeId": "n1"}]
            assert meta == {"total": 1}

    async def test_400_error_raises_api_error(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(
            400,
            {"error": {"code": "VALIDATION_ERROR", "message": "Bad request"}},
        )

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            with pytest.raises(HydraAPIError) as exc_info:
                await client._request_with_meta("GET", "/bad")
            assert exc_info.value.code == "VALIDATION_ERROR"

    async def test_404_error_raises_not_found(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(
            404,
            {"error": {"code": "NOT_FOUND", "message": "Not found"}},
        )

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            with pytest.raises(HydraAPIError) as exc_info:
                await client._request_with_meta("GET", "/nodes/missing")
            assert exc_info.value.code == "NOT_FOUND"

    async def test_502_retries_and_eventually_fails(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(
            502,
            {"error": {"code": "BAD_GATEWAY", "message": "Bad gateway"}},
        )

        with patch.object(client, "_get_client") as mock_gc, \
             patch("hydra_mcp.client.asyncio.sleep", new_callable=AsyncMock):
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            with pytest.raises(HydraAPIError):
                await client._request_with_meta("GET", "/nodes")
            # Should have been called 3 times (initial + 2 retries)
            assert mock_http.request.call_count == 3

    async def test_connection_error_retries(self):
        s = _make_settings()
        client = HydraClient(s)

        with patch.object(client, "_get_client") as mock_gc, \
             patch("hydra_mcp.client.asyncio.sleep", new_callable=AsyncMock):
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_gc.return_value = mock_http
            set_auth_context(None)

            with pytest.raises(HydraAPIError) as exc_info:
                await client._request_with_meta("GET", "/nodes")
            assert exc_info.value.code == "CONNECTION_ERROR"
            assert mock_http.request.call_count == 3

    async def test_invalid_json_response(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Not JSON")

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            with pytest.raises(HydraAPIError) as exc_info:
                await client._request_with_meta("GET", "/bad-json")
            assert exc_info.value.code == "INVALID_RESPONSE"

    async def test_auth_context_forwarded(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"ok": True}})

        ctx = AuthContext(
            user_id="user1",
            permissions=["*:*"],
            metadata={"forward_auth": {"Authorization": "Bearer tok123"}},
        )
        set_auth_context(ctx)

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http

            await client._request_with_meta("GET", "/nodes")
            call_kwargs = mock_http.request.call_args
            assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer tok123"

        set_auth_context(None)

    async def test_missing_forward_auth_on_network_raises(self):
        """Non-stdio transport with auth context but no forward_auth headers should raise."""
        s = _make_settings(transport="http")
        client = HydraClient(s)

        ctx = AuthContext(user_id="user1", permissions=["*:*"], metadata={})
        set_auth_context(ctx)

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_gc.return_value = mock_http

            with pytest.raises(HydraAPIError) as exc_info:
                await client._request_with_meta("GET", "/nodes")
            assert exc_info.value.code == "UNAUTHORIZED"

        set_auth_context(None)


class TestExtractListTotal:
    """Tests for _extract_list_total."""

    def test_with_meta_total(self):
        assert HydraClient._extract_list_total({"total": 42}, [1, 2, 3]) == 42

    def test_without_meta(self):
        assert HydraClient._extract_list_total(None, [1, 2]) == 2

    def test_with_non_int_total(self):
        assert HydraClient._extract_list_total({"total": "not-int"}, [1]) == 1


class TestExpectObjectResult:
    """Tests for _expect_object_result."""

    def test_valid_dict_passes(self):
        result = HydraClient._expect_object_result({"key": "val"}, "/test")
        assert result == {"key": "val"}

    def test_list_raises(self):
        with pytest.raises(HydraAPIError) as exc_info:
            HydraClient._expect_object_result([1, 2, 3], "/test")
        assert exc_info.value.code == "INVALID_RESPONSE"

    def test_none_raises(self):
        with pytest.raises(HydraAPIError):
            HydraClient._expect_object_result(None, "/test")


class TestExpectListResult:
    """Tests for _expect_list_result."""

    def test_valid_list_passes(self):
        result = HydraClient._expect_list_result([1, 2], "/test")
        assert result == [1, 2]

    def test_dict_raises(self):
        with pytest.raises(HydraAPIError) as exc_info:
            HydraClient._expect_list_result({"key": "val"}, "/test")
        assert exc_info.value.code == "INVALID_RESPONSE"


class TestEntityMethods:
    """Tests for individual entity methods."""

    async def _setup_client_with_response(self, response_data, meta=None):
        s = _make_settings()
        client = HydraClient(s)
        full_response = {"data": response_data}
        if meta:
            full_response["meta"] = meta
        mock_resp = _mock_response(200, full_response)

        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)
        with patch.object(client, "_get_client", return_value=mock_http):
            set_auth_context(None)
            yield client
        set_auth_context(None)

    async def test_list_nodes(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": [{"nodeId": "n1"}], "meta": {"total": 1}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            items, total = await client.list_nodes(node_class="compute", tags=["prod"])
            assert items == [{"nodeId": "n1"}]
            assert total == 1

    async def test_get_node(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"nodeId": "n1", "class": "compute"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            node = await client.get_node("n1")
            assert node["nodeId"] == "n1"

    async def test_get_node_profile(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"profileId": "p1"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            profile = await client.get_node_profile("n1", sections=["hardware"])
            assert profile["profileId"] == "p1"

    async def test_list_services(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": [{"serviceId": "svc-1"}], "meta": {"total": 1}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            items, total = await client.list_services(node_id="n1", runtime="docker")
            assert len(items) == 1

    async def test_get_service(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"serviceId": "svc-1"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            svc = await client.get_service("svc-1")
            assert svc["serviceId"] == "svc-1"

    async def test_list_groups(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": [{"groupId": "g1"}], "meta": {"total": 1}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            items, total = await client.list_groups(types=["node"], tags=["prod"])
            assert len(items) == 1

    async def test_get_group(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"groupId": "g1"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            group = await client.get_group("g1", resolve_members=True)
            assert group["groupId"] == "g1"

    async def test_list_networks(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": [{"networkId": "net1"}], "meta": {"total": 1}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            items, total = await client.list_networks(network_type="physical")
            assert len(items) == 1

    async def test_get_network(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"networkId": "net1"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            net = await client.get_network("net1", include_nodes=True)
            assert net["networkId"] == "net1"

    async def test_get_topology(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"nodes": [], "edges": []}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            topo = await client.get_topology(mode="infrastructure")
            assert "nodes" in topo

    async def test_get_topology_at_time(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"nodes": []}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            ts = datetime(2025, 1, 1, tzinfo=UTC)
            topo = await client.get_topology_at_time("network", ts)
            assert "nodes" in topo

    async def test_get_node_at_time(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"nodeId": "n1", "state": "active"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            ts = datetime(2025, 1, 1, tzinfo=UTC)
            state = await client.get_node_at_time("n1", ts, sections=["hardware"])
            assert state["nodeId"] == "n1"

    async def test_compare_profiles(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"diff": {}}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            diff = await client.compare_profiles("n1", from_version="v1", to_version="v2")
            assert "diff" in diff

    async def test_get_capacity(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"totalCpu": 16}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            cap = await client.get_capacity(group_by="class", include_logical=True)
            assert cap["totalCpu"] == 16

    async def test_query(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"results": []}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.query("nodes", filter_query={"status": "active"})
            assert "results" in result

    async def test_search(self):
        s = _make_settings()
        client = HydraClient(s)
        # list_nodes returns data+meta, list_services returns data+meta
        nodes_resp = _mock_response(200, {"data": [{"nodeId": "web-01", "displayName": "Web 01"}], "meta": {"total": 1}})
        services_resp = _mock_response(200, {"data": [{"serviceId": "svc-nginx-a1", "name": "nginx"}], "meta": {"total": 1}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(side_effect=[nodes_resp, services_resp])
            mock_gc.return_value = mock_http
            set_auth_context(None)

            results = await client.search("web")
            assert any(r["type"] == "node" for r in results)

    async def test_control_service(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"commandId": "cmd1", "status": "queued"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.control_service("n1", "svc-1", "restart")
            assert result["commandId"] == "cmd1"

    async def test_control_node(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"commandId": "cmd2", "status": "queued"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.control_node("n1", "reboot")
            assert result["commandId"] == "cmd2"

    async def test_control_agent(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"commandId": "cmd3", "status": "queued"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.control_agent("n1", "status")
            assert result["commandId"] == "cmd3"

    async def test_get_command_status(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"commandId": "cmd1", "status": "completed"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.get_command_status("cmd1")
            assert result["status"] == "completed"

    async def test_list_command_catalog(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": [{"registryId": "reg::service::restart"}]})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.list_command_catalog(category="service")
            assert len(result) == 1

    async def test_list_commands(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": [{"commandId": "cmd1"}]})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.list_commands(node_id="n1", status="completed")
            assert len(result) == 1

    async def test_get_queue_status(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"pending": 3, "executing": 1}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.get_queue_status(node_id="n1")
            assert result["pending"] == 3

    async def test_control_device(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"status": "ok"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.control_device("light.living_room", "turn_on", {"brightness": 100})
            assert result["status"] == "ok"

    async def test_get_ha_status(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"connected": True}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.get_ha_status()
            assert result["connected"] is True

    async def test_list_notifications(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {
            "data": [{"notificationId": "n1"}],
            "meta": {"total": 1},
        })

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            items, total = await client.list_notifications(
                tier=3, tier_min=2, status="active", source="hydra-api",
                node_id="n1", notification_type="node_offline",
            )
            assert total == 1

    async def test_get_notification_stats(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"total": 10, "unread": 3}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.get_notification_stats()
            assert result["total"] == 10

    async def test_get_notification(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"notificationId": "n1"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.get_notification("n1")
            assert result["notificationId"] == "n1"

    async def test_list_audit_entries(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": [{"action": "create"}]})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.list_audit_entries(
                action="create", resource_type="node", resource_id="n1",
                actor_id="u1", since="2025-01-01T00:00:00Z", until="2025-12-31T23:59:59Z",
            )
            assert len(result) == 1

    async def test_delete_audit_entries(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"deleted": 5}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.delete_audit_entries("2025-01-01T00:00:00Z", "2025-06-01T00:00:00Z")
            assert result["deleted"] == 5

    async def test_health_check(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"status": "healthy"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.health_check()
            assert result["status"] == "healthy"

    async def test_get_info(self):
        s = _make_settings()
        client = HydraClient(s)
        mock_resp = _mock_response(200, {"data": {"version": "0.5.0"}})

        with patch.object(client, "_get_client") as mock_gc:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_resp)
            mock_gc.return_value = mock_http
            set_auth_context(None)

            result = await client.get_info()
            assert result["version"] == "0.5.0"


class TestClientClose:
    """Tests for client close lifecycle."""

    async def test_close_open_client(self):
        s = _make_settings()
        client = HydraClient(s)
        await client._get_client()
        assert client._client is not None
        await client.close()

    async def test_close_already_closed(self):
        s = _make_settings()
        client = HydraClient(s)
        http_client = await client._get_client()
        await http_client.aclose()
        await client.close()  # Should not raise

    async def test_close_no_client(self):
        s = _make_settings()
        client = HydraClient(s)
        await client.close()  # Should not raise


class TestHydraAPIError:
    """Tests for HydraAPIError exception."""

    def test_error_attributes(self):
        err = HydraAPIError("NOT_FOUND", "Node not found", {"nodeId": "n1"})
        assert err.code == "NOT_FOUND"
        assert err.message == "Node not found"
        assert err.details == {"nodeId": "n1"}
        assert str(err) == "Node not found"

    def test_default_details(self):
        err = HydraAPIError("ERROR", "Something failed")
        assert err.details == {}
