"""Tests for the Docker Engine plugin handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hydra.api.v1.services.plugins.docker import DockerPluginHandler

# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def docker_config() -> dict[str, str | int]:
    """Default TCP config for the Docker plugin."""
    return {"host": "localhost", "port": 2375}


@pytest.fixture
def docker_handler(docker_config: dict[str, str | int]) -> DockerPluginHandler:
    """Create a DockerPluginHandler with default TCP config."""
    return DockerPluginHandler(config=docker_config)


@pytest.fixture
def docker_handler_socket() -> DockerPluginHandler:
    """Create a DockerPluginHandler with Unix socket config."""
    return DockerPluginHandler(config={"socketPath": "/var/run/docker.sock"})


def _mock_response(
    status_code: int = 200,
    json_data: object = None,
    text: str = "",
) -> httpx.Response:
    """Build a fake ``httpx.Response``."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    return resp


# ── Manifest & Command Definitions ───────────────────────────────────


class TestManifest:
    """Tests for MANIFEST class constant."""

    def test_manifest_plugin_id(self) -> None:
        assert DockerPluginHandler.MANIFEST["pluginId"] == "plg::docker"

    def test_manifest_name(self) -> None:
        assert DockerPluginHandler.MANIFEST["name"] == "Docker Engine"

    def test_manifest_classification(self) -> None:
        assert DockerPluginHandler.MANIFEST["classification"] == "core"

    def test_manifest_touchpoints(self) -> None:
        tp = DockerPluginHandler.MANIFEST["touchpoints"]
        assert tp["profileEnrichment"] is True
        assert tp["discoveryProvider"] is True
        assert tp["commandProvider"] is True
        assert tp["executionHandler"] is True
        assert tp["topologyProvider"] is False
        assert tp["workflowBlockProvider"] is False

    def test_manifest_contributed_commands_count(self) -> None:
        assert len(DockerPluginHandler.MANIFEST["contributedCommands"]) == 6


class TestCommandDefinitions:
    """Tests for COMMAND_DEFINITIONS class constant."""

    def test_command_definitions_count(self) -> None:
        assert len(DockerPluginHandler.COMMAND_DEFINITIONS) == 6

    def test_command_definitions_registry_ids(self) -> None:
        ids = {cmd["registryId"] for cmd in DockerPluginHandler.COMMAND_DEFINITIONS}
        expected = {
            "reg::docker::list-containers",
            "reg::docker::container-stats",
            "reg::docker::pull-image",
            "reg::docker::compose-up",
            "reg::docker::compose-down",
            "reg::docker::prune",
        }
        assert ids == expected

    def test_prune_requires_admin(self) -> None:
        prune = next(
            cmd for cmd in DockerPluginHandler.COMMAND_DEFINITIONS
            if cmd["registryId"] == "reg::docker::prune"
        )
        assert prune["rbac"]["minimumRole"] == "admin"
        assert prune["rbac"]["requiresConfirmation"] is True
        assert prune["rbac"]["dangerLevel"] == "critical"

    def test_list_containers_is_safe(self) -> None:
        cmd = next(
            c for c in DockerPluginHandler.COMMAND_DEFINITIONS
            if c["registryId"] == "reg::docker::list-containers"
        )
        assert cmd["rbac"]["dangerLevel"] == "safe"
        assert cmd["rbac"]["requiresConfirmation"] is False


# ── connect() ────────────────────────────────────────────────────────


class TestConnect:
    """Tests for connect()."""

    @pytest.mark.asyncio
    async def test_connect_success(self, docker_handler: DockerPluginHandler) -> None:
        mock_resp = _mock_response(status_code=200)
        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            result = await docker_handler.connect()

        assert result is True
        mock_client.get.assert_awaited_once_with("/_ping")

    @pytest.mark.asyncio
    async def test_connect_failure_http_error(self, docker_handler: DockerPluginHandler) -> None:
        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_get.return_value = mock_client

            result = await docker_handler.connect()

        assert result is False

    @pytest.mark.asyncio
    async def test_connect_failure_non_200(self, docker_handler: DockerPluginHandler) -> None:
        mock_resp = _mock_response(status_code=500)
        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            result = await docker_handler.connect()

        assert result is False


# ── health_check() ───────────────────────────────────────────────────


class TestHealthCheck:
    """Tests for health_check()."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, docker_handler: DockerPluginHandler) -> None:
        mock_resp = _mock_response(status_code=200)
        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            result = await docker_handler.health_check()

        assert result["status"] == "healthy"
        assert result["consecutiveFailures"] == 0
        assert result["lastError"] is None
        assert isinstance(result["responseTimeMs"], float)

    @pytest.mark.asyncio
    async def test_health_check_failure_non_200(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        mock_resp = _mock_response(status_code=503)
        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            result = await docker_handler.health_check()

        assert result["status"] == "unhealthy"
        assert result["consecutiveFailures"] == 1
        assert result["lastError"] == "HTTP 503"

    @pytest.mark.asyncio
    async def test_health_check_failure_exception(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_get.return_value = mock_client

            result = await docker_handler.health_check()

        assert result["status"] == "unhealthy"
        assert result["consecutiveFailures"] == 1
        assert "refused" in (result["lastError"] or "")


# ── enrich_profile() ─────────────────────────────────────────────────


class TestEnrichProfile:
    """Tests for enrich_profile()."""

    @pytest.mark.asyncio
    async def test_enrich_profile_returns_docker_info(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        info_resp = _mock_response(
            status_code=200,
            json_data={
                "Containers": 12,
                "ContainersRunning": 8,
                "ContainersStopped": 4,
                "Images": 25,
                "Driver": "overlay2",
            },
        )
        version_resp = _mock_response(
            status_code=200,
            json_data={
                "Version": "25.0.3",
                "ApiVersion": "1.44",
            },
        )

        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(side_effect=[info_resp, version_resp])
            mock_get.return_value = mock_client

            result = await docker_handler.enrich_profile("test-node-01", {})

        assert result["containerCount"] == 12
        assert result["containerRunning"] == 8
        assert result["imageCount"] == 25
        assert result["storageDriver"] == "overlay2"
        assert result["dockerVersion"] == "25.0.3"
        assert result["serverVersion"] == "25.0.3"
        assert result["apiVersion"] == "1.44"


# ── discover_nodes() ─────────────────────────────────────────────────


class TestDiscoverNodes:
    """Tests for discover_nodes()."""

    @pytest.mark.asyncio
    async def test_discover_nodes_returns_containers(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        containers_payload = [
            {
                "Id": "abc123def456789012345678",
                "Names": ["/my-nginx"],
                "Image": "nginx:latest",
                "State": "running",
                "Status": "Up 2 hours",
                "Created": 1700000000,
                "NetworkSettings": {
                    "Networks": {
                        "bridge": {"IPAddress": "172.17.0.2"},
                    },
                },
            },
            {
                "Id": "def789abc012345678901234",
                "Names": ["/redis"],
                "Image": "redis:7",
                "State": "exited",
                "Status": "Exited (0) 1 hour ago",
                "Created": 1700000100,
                "NetworkSettings": {"Networks": {}},
            },
        ]
        mock_resp = _mock_response(status_code=200, json_data=containers_payload)

        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            result = await docker_handler.discover_nodes()

        assert len(result) == 2

        # First container
        assert result[0]["displayName"] == "my-nginx"
        assert result[0]["resourceType"] == "docker-container"
        assert result[0]["ip"] == "172.17.0.2"
        assert result[0]["confidence"] == 1.0
        assert result[0]["metadata"]["image"] == "nginx:latest"

        # Second container (no IP)
        assert result[1]["displayName"] == "redis"
        assert result[1]["ip"] is None

    @pytest.mark.asyncio
    async def test_discover_nodes_empty_on_error(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_get.return_value = mock_client

            result = await docker_handler.discover_nodes()

        assert result == []


# ── execute_command() ────────────────────────────────────────────────


class TestExecuteCommand:
    """Tests for execute_command()."""

    @pytest.mark.asyncio
    async def test_execute_list_containers(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        containers_payload = [
            {"Id": "abc123", "Names": ["/nginx"], "State": "running"},
        ]
        mock_resp = _mock_response(status_code=200, json_data=containers_payload)

        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            result = await docker_handler.execute_command(
                "reg::docker::list-containers",
                {"nodeId": "test-node-01"},
                {"all": True},
            )

        assert result["success"] is True
        assert "1 container(s)" in result["output"]
        assert len(result["data"]) == 1

    @pytest.mark.asyncio
    async def test_execute_unknown_command(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        result = await docker_handler.execute_command(
            "reg::docker::nonexistent",
            {"nodeId": "test-node-01"},
            {},
        )

        assert result["success"] is False
        assert "Unknown command" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_pull_image(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        mock_resp = _mock_response(status_code=200)

        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            result = await docker_handler.execute_command(
                "reg::docker::pull-image",
                {"nodeId": "test-node-01"},
                {"image": "nginx", "tag": "alpine"},
            )

        assert result["success"] is True
        assert "nginx:alpine" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_prune(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        mock_resp = _mock_response(
            status_code=200,
            json_data={"SpaceReclaimed": 1024},
        )

        with patch.object(
            DockerPluginHandler, "_get_client"
        ) as mock_get:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            result = await docker_handler.execute_command(
                "reg::docker::prune",
                {"nodeId": "test-node-01"},
                {"volumes": True},
            )

        assert result["success"] is True
        assert "Prune completed" in result["output"]
        # 4 prune calls: containers, images, networks, volumes
        assert mock_client.post.await_count == 4


# ── disconnect() ─────────────────────────────────────────────────────


class TestDisconnect:
    """Tests for disconnect()."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_client(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        docker_handler._client = mock_client  # type: ignore[assignment]

        await docker_handler.disconnect()

        mock_client.aclose.assert_awaited_once()
        assert docker_handler._client is None

    @pytest.mark.asyncio
    async def test_disconnect_noop_when_no_client(
        self, docker_handler: DockerPluginHandler
    ) -> None:
        assert docker_handler._client is None
        await docker_handler.disconnect()
        # Should not raise


# ── Client construction ──────────────────────────────────────────────


class TestClientConstruction:
    """Tests for _get_client and _build_base_url."""

    def test_build_base_url_defaults(self) -> None:
        handler = DockerPluginHandler(config={})
        assert handler._build_base_url() == "http://localhost:2375"

    def test_build_base_url_custom(self) -> None:
        handler = DockerPluginHandler(config={"host": "docker-host", "port": 2376})
        assert handler._build_base_url() == "http://docker-host:2376"

    def test_get_client_tcp(self, docker_handler: DockerPluginHandler) -> None:
        client = docker_handler._get_client()
        assert isinstance(client, httpx.AsyncClient)
        # Second call returns same instance
        assert docker_handler._get_client() is client

    def test_get_client_socket(self, docker_handler_socket: DockerPluginHandler) -> None:
        client = docker_handler_socket._get_client()
        assert isinstance(client, httpx.AsyncClient)
        assert docker_handler_socket._get_client() is client
