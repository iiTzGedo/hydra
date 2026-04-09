"""Docker Engine plugin handler.

Communicates with the Docker Engine API over TCP or Unix socket to
provide profile enrichment, container discovery, and command execution.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
import structlog

from hydra.api.v1.services.plugins.base import PluginHandler

logger = structlog.get_logger(__name__)

_NOW = datetime.now(UTC)

# ── Registry IDs ─────────────────────────────────────────────────────

_CMD_LIST_CONTAINERS = "reg::docker::list-containers"
_CMD_CONTAINER_STATS = "reg::docker::container-stats"
_CMD_PULL_IMAGE = "reg::docker::pull-image"
_CMD_COMPOSE_UP = "reg::docker::compose-up"
_CMD_COMPOSE_DOWN = "reg::docker::compose-down"
_CMD_PRUNE = "reg::docker::prune"


class DockerPluginHandler(PluginHandler):
    """Docker Engine plugin handler.

    Talks to the Docker Engine API to enrich profiles, discover containers,
    and execute Docker-related commands on target nodes.
    """

    MANIFEST: ClassVar[dict[str, Any]] = {
        "pluginId": "plg::docker",
        "name": "Docker Engine",
        "version": "1.0.0",
        "description": "Manages Docker Engine containers, images, and compose projects",
        "author": "Hydra",
        "classification": "core",
        "category": "infrastructure",
        "touchpoints": {
            "profileEnrichment": True,
            "discoveryProvider": True,
            "commandProvider": True,
            "executionHandler": True,
            "topologyProvider": False,
            "workflowBlockProvider": False,
        },
        "supportedTiers": ["normal", "max"],
        "healthCheckEndpoint": None,
        "contributedCommands": [
            _CMD_LIST_CONTAINERS,
            _CMD_CONTAINER_STATS,
            _CMD_PULL_IMAGE,
            _CMD_COMPOSE_UP,
            _CMD_COMPOSE_DOWN,
            _CMD_PRUNE,
        ],
    }

    COMMAND_DEFINITIONS: ClassVar[list[dict[str, Any]]] = [
        # ── List containers ─────────────────────────────────────────
        {
            "registryId": _CMD_LIST_CONTAINERS,
            "category": "docker",
            "action": "list-containers",
            "displayName": "List Docker Containers",
            "description": "List all containers on the target node",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "all": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include stopped containers",
                    },
                },
            },
            "execution": {
                "runtimes": {},
                "handler": "docker_list_containers",
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
                "controlPermission": "docker:control:list-containers",
            },
            "audit": {
                "logLevel": "minimal",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "0.5.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
        # ── Container stats ─────────────────────────────────────────
        {
            "registryId": _CMD_CONTAINER_STATS,
            "category": "docker",
            "action": "container-stats",
            "displayName": "Container Resource Usage",
            "description": "Get real-time resource usage statistics for a container",
            "targetSchema": {"required": ["nodeId", "containerId"]},
            "parametersSchema": {
                "properties": {
                    "stream": {
                        "type": "boolean",
                        "default": False,
                        "description": "Stream stats continuously (single snapshot if false)",
                    },
                },
            },
            "execution": {
                "runtimes": {},
                "handler": "docker_container_stats",
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
                "controlPermission": "docker:control:container-stats",
            },
            "audit": {
                "logLevel": "minimal",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "0.5.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
        # ── Pull image ──────────────────────────────────────────────
        {
            "registryId": _CMD_PULL_IMAGE,
            "category": "docker",
            "action": "pull-image",
            "displayName": "Pull Docker Image",
            "description": "Pull an image from a registry",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "required": ["image"],
                "properties": {
                    "image": {
                        "type": "string",
                        "description": "Image reference (e.g. nginx:latest)",
                    },
                    "tag": {
                        "type": "string",
                        "default": "latest",
                        "description": "Tag to pull (overrides tag in image ref)",
                    },
                },
            },
            "execution": {
                "runtimes": {},
                "handler": "docker_pull_image",
                "timeout": 300,
                "deliveryMode": "poll_only",
                "retryable": True,
                "maxRetries": 2,
            },
            "rbac": {
                "minimumRole": "operator",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "low",
                "controlPermission": "docker:control:pull-image",
            },
            "audit": {
                "logLevel": "standard",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "0.5.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
        # ── Compose up ──────────────────────────────────────────────
        {
            "registryId": _CMD_COMPOSE_UP,
            "category": "docker",
            "action": "compose-up",
            "displayName": "Start Compose Project",
            "description": "Start a Docker Compose project",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "required": ["project"],
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Compose project name or file path",
                    },
                    "services": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific services to start (all if empty)",
                    },
                    "detach": {
                        "type": "boolean",
                        "default": True,
                        "description": "Run in detached mode",
                    },
                },
            },
            "execution": {
                "runtimes": {},
                "handler": "docker_compose_up",
                "timeout": 300,
                "deliveryMode": "poll_only",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "operator",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "medium",
                "controlPermission": "docker:control:compose-up",
            },
            "audit": {
                "logLevel": "standard",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "0.5.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
        # ── Compose down ────────────────────────────────────────────
        {
            "registryId": _CMD_COMPOSE_DOWN,
            "category": "docker",
            "action": "compose-down",
            "displayName": "Stop Compose Project",
            "description": "Stop and remove a Docker Compose project",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "required": ["project"],
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Compose project name or file path",
                    },
                    "removeVolumes": {
                        "type": "boolean",
                        "default": False,
                        "description": "Remove named volumes declared in the project",
                    },
                },
            },
            "execution": {
                "runtimes": {},
                "handler": "docker_compose_down",
                "timeout": 120,
                "deliveryMode": "poll_only",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "operator",
                "requiresConfirmation": True,
                "confirmationMessage": (
                    "This will stop and remove all containers in the compose project."
                ),
                "dangerLevel": "high",
                "controlPermission": "docker:control:compose-down",
            },
            "audit": {
                "logLevel": "verbose",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "0.5.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
        # ── Prune ───────────────────────────────────────────────────
        {
            "registryId": _CMD_PRUNE,
            "category": "docker",
            "action": "prune",
            "displayName": "Prune Unused Resources",
            "description": "Remove all unused containers, images, networks, and optionally volumes",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "volumes": {
                        "type": "boolean",
                        "default": False,
                        "description": "Also prune unused volumes",
                    },
                },
            },
            "execution": {
                "runtimes": {},
                "handler": "docker_prune",
                "timeout": 300,
                "deliveryMode": "poll_only",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "admin",
                "requiresConfirmation": True,
                "confirmationMessage": (
                    "This will permanently remove unused Docker resources. "
                    "This action cannot be undone."
                ),
                "dangerLevel": "critical",
                "controlPermission": "docker:control:prune",
            },
            "audit": {
                "logLevel": "verbose",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "0.5.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
    ]

    # ── Lifecycle ────────────────────────────────────────────────────

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
    ) -> None:
        super().__init__(config, credentials)
        self._client: httpx.AsyncClient | None = None

    def _build_base_url(self) -> str:
        """Construct the Docker API base URL from config."""
        host: str = self.config.get("host", "localhost")
        port: int = int(self.config.get("port", 2375))
        return f"http://{host}:{port}"

    def _get_client(self) -> httpx.AsyncClient:
        """Return or lazily create the httpx client.

        If ``socketPath`` is present in config, a Unix-domain transport is
        used.  Otherwise plain TCP.
        """
        if self._client is not None:
            return self._client

        socket_path: str | None = self.config.get("socketPath")
        if socket_path:
            transport = httpx.AsyncHTTPTransport(uds=socket_path)
            self._client = httpx.AsyncClient(
                transport=transport,
                base_url="http://docker",  # required by httpx; unused with UDS
                timeout=30.0,
            )
        else:
            self._client = httpx.AsyncClient(
                base_url=self._build_base_url(),
                timeout=30.0,
            )
        return self._client

    async def connect(self) -> bool:
        """Ping the Docker daemon to verify connectivity."""
        try:
            client = self._get_client()
            resp = await client.get("/_ping")
            ok = resp.status_code == 200
            if ok:
                logger.info("docker_plugin_connected", base_url=self._build_base_url())
            else:
                logger.warning(
                    "docker_plugin_ping_failed",
                    status_code=resp.status_code,
                )
            return ok
        except httpx.HTTPError as exc:
            logger.warning("docker_plugin_connect_error", error=str(exc))
            return False

    async def health_check(self) -> dict[str, Any]:
        """Run a health check against the Docker daemon ``/_ping`` endpoint."""
        now = datetime.now(UTC)
        start = time.monotonic()
        try:
            client = self._get_client()
            resp = await client.get("/_ping")
            elapsed_ms = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                return {
                    "status": "healthy",
                    "lastCheck": now.isoformat(),
                    "consecutiveFailures": 0,
                    "lastError": None,
                    "responseTimeMs": round(elapsed_ms, 2),
                }
            return {
                "status": "unhealthy",
                "lastCheck": now.isoformat(),
                "consecutiveFailures": 1,
                "lastError": f"HTTP {resp.status_code}",
                "responseTimeMs": round(elapsed_ms, 2),
            }
        except httpx.HTTPError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            return {
                "status": "unhealthy",
                "lastCheck": now.isoformat(),
                "consecutiveFailures": 1,
                "lastError": str(exc),
                "responseTimeMs": round(elapsed_ms, 2),
            }

    async def disconnect(self) -> None:
        """Close the underlying httpx client if open."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("docker_plugin_disconnected")

    # ── Touchpoint: Profile Enrichment ───────────────────────────────

    async def enrich_profile(
        self,
        node_id: str,
        profile: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Enrich a node profile with Docker Engine metadata.

        Calls ``/info`` and ``/version`` on the Docker API and returns
        a summary dict suitable for ``profile.pluginData["plg::docker"]``.
        """
        client = self._get_client()
        result: dict[str, Any] = {}

        try:
            info_resp = await client.get("/info")
            if info_resp.status_code == 200:
                info: dict[str, Any] = info_resp.json()
                result["containerCount"] = info.get("Containers", 0)
                result["containerRunning"] = info.get("ContainersRunning", 0)
                result["containerStopped"] = info.get("ContainersStopped", 0)
                result["imageCount"] = info.get("Images", 0)
                result["storageDriver"] = info.get("Driver", "")
        except httpx.HTTPError as exc:
            logger.warning("docker_enrich_info_error", node_id=node_id, error=str(exc))

        try:
            version_resp = await client.get("/version")
            if version_resp.status_code == 200:
                version: dict[str, Any] = version_resp.json()
                result["dockerVersion"] = version.get("Version", "")
                result["apiVersion"] = version.get("ApiVersion", "")
                result["serverVersion"] = version.get("Version", "")
        except httpx.HTTPError as exc:
            logger.warning("docker_enrich_version_error", node_id=node_id, error=str(exc))

        return result

    # ── Touchpoint: Discovery ────────────────────────────────────────

    async def discover_nodes(self) -> list[dict[str, Any]]:
        """Discover containers as infrastructure resources.

        Returns a list of discovered-resource dicts, one per container.
        """
        client = self._get_client()
        try:
            resp = await client.get("/containers/json", params={"all": "true"})
            if resp.status_code != 200:
                logger.warning(
                    "docker_discover_failed",
                    status_code=resp.status_code,
                )
                return []

            containers: list[dict[str, Any]] = resp.json()
            discovered: list[dict[str, Any]] = []

            for container in containers:
                # Extract first name (Docker prefixes with /)
                names: list[str] = container.get("Names", [])
                display_name = names[0].lstrip("/") if names else container.get("Id", "")[:12]

                # Extract first IP from the networks map
                networks: dict[str, Any] = container.get("NetworkSettings", {}).get(
                    "Networks", {}
                )
                ip_address: str | None = None
                for net_info in networks.values():
                    addr = net_info.get("IPAddress")
                    if addr:
                        ip_address = addr
                        break

                discovered.append({
                    "resourceId": container.get("Id", "")[:12],
                    "displayName": display_name,
                    "resourceType": "docker-container",
                    "ip": ip_address,
                    "confidence": 1.0,
                    "metadata": {
                        "image": container.get("Image", ""),
                        "state": container.get("State", ""),
                        "status": container.get("Status", ""),
                        "created": container.get("Created"),
                    },
                })

            return discovered

        except httpx.HTTPError as exc:
            logger.warning("docker_discover_error", error=str(exc))
            return []

    # ── Touchpoint: Command Execution ────────────────────────────────

    async def execute_command(
        self,
        command_id: str,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a command to the appropriate Docker API endpoint."""
        dispatch: dict[str, Any] = {
            _CMD_LIST_CONTAINERS: self._exec_list_containers,
            _CMD_CONTAINER_STATS: self._exec_container_stats,
            _CMD_PULL_IMAGE: self._exec_pull_image,
            _CMD_COMPOSE_UP: self._exec_compose_up,
            _CMD_COMPOSE_DOWN: self._exec_compose_down,
            _CMD_PRUNE: self._exec_prune,
        }

        handler = dispatch.get(command_id)
        if handler is None:
            return {
                "success": False,
                "output": f"Unknown command '{command_id}' for Docker plugin",
            }

        try:
            result: dict[str, Any] = await handler(target, params)
            return result
        except httpx.HTTPError as exc:
            logger.warning(
                "docker_command_error",
                command_id=command_id,
                error=str(exc),
            )
            return {
                "success": False,
                "output": f"Docker API error: {exc}",
            }

    # ── Command implementations ──────────────────────────────────────

    async def _exec_list_containers(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """List containers via GET /containers/json."""
        client = self._get_client()
        include_all = params.get("all", True)
        resp = await client.get("/containers/json", params={"all": str(include_all).lower()})

        if resp.status_code != 200:
            return {"success": False, "output": f"HTTP {resp.status_code}: {resp.text}"}

        containers: list[dict[str, Any]] = resp.json()
        return {
            "success": True,
            "output": f"Found {len(containers)} container(s)",
            "data": containers,
        }

    async def _exec_container_stats(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Get container stats via GET /containers/{id}/stats."""
        container_id: str = target.get("containerId", "")
        if not container_id:
            return {"success": False, "output": "Missing containerId in target"}

        client = self._get_client()
        # stream=false returns a single stats snapshot
        stream = params.get("stream", False)
        resp = await client.get(
            f"/containers/{container_id}/stats",
            params={"stream": str(stream).lower()},
        )

        if resp.status_code != 200:
            return {"success": False, "output": f"HTTP {resp.status_code}: {resp.text}"}

        stats: dict[str, Any] = resp.json()
        return {
            "success": True,
            "output": f"Stats for container {container_id}",
            "data": stats,
        }

    async def _exec_pull_image(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Pull an image via POST /images/create."""
        image: str = params.get("image", "")
        if not image:
            return {"success": False, "output": "Missing 'image' parameter"}

        tag: str = params.get("tag", "latest")
        client = self._get_client()
        resp = await client.post(
            "/images/create",
            params={"fromImage": image, "tag": tag},
        )

        if resp.status_code not in (200, 201):
            return {"success": False, "output": f"HTTP {resp.status_code}: {resp.text}"}

        return {
            "success": True,
            "output": f"Successfully pulled {image}:{tag}",
        }

    async def _exec_compose_up(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Start a compose project.

        Uses the Docker Compose v2 API (``POST /compose/{project}/up``)
        available on Docker Engine >=25.  Falls back to a descriptive
        error if the endpoint is not available.
        """
        project: str = params.get("project", "")
        if not project:
            return {"success": False, "output": "Missing 'project' parameter"}

        client = self._get_client()
        body: dict[str, Any] = {}
        services: list[str] = params.get("services", [])
        if services:
            body["services"] = services

        resp = await client.post(f"/compose/{project}/up", json=body)

        if resp.status_code not in (200, 201, 204):
            return {"success": False, "output": f"HTTP {resp.status_code}: {resp.text}"}

        return {
            "success": True,
            "output": f"Compose project '{project}' started",
        }

    async def _exec_compose_down(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Stop a compose project via ``POST /compose/{project}/down``."""
        project: str = params.get("project", "")
        if not project:
            return {"success": False, "output": "Missing 'project' parameter"}

        client = self._get_client()
        body: dict[str, Any] = {}
        if params.get("removeVolumes", False):
            body["removeVolumes"] = True

        resp = await client.post(f"/compose/{project}/down", json=body)

        if resp.status_code not in (200, 204):
            return {"success": False, "output": f"HTTP {resp.status_code}: {resp.text}"}

        return {
            "success": True,
            "output": f"Compose project '{project}' stopped",
        }

    async def _exec_prune(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Prune unused Docker resources.

        Calls the container, image, and network prune endpoints, and
        optionally the volume prune endpoint.
        """
        client = self._get_client()
        results: dict[str, Any] = {}

        # Prune containers
        resp = await client.post("/containers/prune")
        if resp.status_code == 200:
            results["containers"] = resp.json()

        # Prune images
        resp = await client.post("/images/prune")
        if resp.status_code == 200:
            results["images"] = resp.json()

        # Prune networks
        resp = await client.post("/networks/prune")
        if resp.status_code == 200:
            results["networks"] = resp.json()

        # Optionally prune volumes
        if params.get("volumes", False):
            resp = await client.post("/volumes/prune")
            if resp.status_code == 200:
                results["volumes"] = resp.json()

        return {
            "success": True,
            "output": "Prune completed",
            "data": results,
        }
