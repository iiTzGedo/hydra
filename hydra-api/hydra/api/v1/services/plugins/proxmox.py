"""Proxmox VE plugin handler.

Integrates with the Proxmox Virtual Environment API to provide VM/LXC
lifecycle management, profile enrichment with host resource data, node
discovery from cluster resources, and topology edges between guests and
their host nodes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
import structlog

from hydra.api.v1.services.plugins.base import PluginHandler

logger = structlog.get_logger(__name__)

_NOW = datetime.now(UTC)

# ── Manifest ────────────────────────────────────────────────────────────

_MANIFEST: dict[str, Any] = {
    "pluginId": "plg::proxmox",
    "name": "Proxmox VE",
    "version": "1.0.0",
    "description": "Proxmox Virtual Environment integration for VM/LXC lifecycle, "
    "cluster discovery, and resource monitoring",
    "author": "Hydra Team",
    "classification": "core",
    "category": "infrastructure",
    "touchpoints": {
        "profileEnrichment": True,
        "discoveryProvider": True,
        "commandProvider": True,
        "executionHandler": True,
        "topologyProvider": True,
        "workflowBlockProvider": False,
    },
    "supportedTiers": ["normal", "max"],
    "healthCheckEndpoint": None,
    "contributedCommands": [
        "reg::proxmox::list-vms",
        "reg::proxmox::vm-status",
        "reg::proxmox::start-vm",
        "reg::proxmox::stop-vm",
        "reg::proxmox::snapshot",
        "reg::proxmox::list-storage",
    ],
}

# ── Command definitions ─────────────────────────────────────────────────

_COMMAND_DEFINITIONS: list[dict[str, Any]] = [
    {
        "registryId": "reg::proxmox::list-vms",
        "category": "proxmox",
        "action": "list-vms",
        "displayName": "List VMs and LXCs",
        "description": "List all virtual machines and LXC containers on a Proxmox node or cluster",
        "targetSchema": {"required": ["nodeId"]},
        "parametersSchema": {
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["qemu", "lxc", "all"],
                    "default": "all",
                    "description": "Filter by guest type",
                },
            },
        },
        "execution": {
            "handler": "proxmox_list_vms",
            "timeout": 30,
            "deliveryMode": "plugin_via_api_direct",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "safe",
            "controlPermission": "proxmox:control:list-vms",
        },
        "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::proxmox::vm-status",
        "category": "proxmox",
        "action": "vm-status",
        "displayName": "Get VM/LXC Status",
        "description": "Retrieve the current status and resource usage of a VM or LXC container",
        "targetSchema": {"required": ["nodeId", "vmid"]},
        "parametersSchema": {
            "required": ["vmid"],
            "properties": {
                "vmid": {"type": "integer", "description": "Proxmox VM/LXC ID"},
                "type": {
                    "type": "string",
                    "enum": ["qemu", "lxc"],
                    "default": "qemu",
                    "description": "Guest type",
                },
            },
        },
        "execution": {
            "handler": "proxmox_vm_status",
            "timeout": 15,
            "deliveryMode": "plugin_via_api_direct",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "safe",
            "controlPermission": "proxmox:control:vm-status",
        },
        "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::proxmox::start-vm",
        "category": "proxmox",
        "action": "start-vm",
        "displayName": "Start VM/LXC",
        "description": "Start a stopped virtual machine or LXC container",
        "targetSchema": {"required": ["nodeId", "vmid"]},
        "parametersSchema": {
            "required": ["vmid", "node"],
            "properties": {
                "vmid": {"type": "integer", "description": "Proxmox VM/LXC ID"},
                "node": {"type": "string", "description": "Proxmox node name hosting the guest"},
                "type": {
                    "type": "string",
                    "enum": ["qemu", "lxc"],
                    "default": "qemu",
                    "description": "Guest type",
                },
            },
        },
        "execution": {
            "handler": "proxmox_start_vm",
            "timeout": 60,
            "deliveryMode": "plugin_via_api_direct",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "medium",
            "controlPermission": "proxmox:control:start-vm",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::proxmox::stop-vm",
        "category": "proxmox",
        "action": "stop-vm",
        "displayName": "Stop VM/LXC",
        "description": "Stop a running virtual machine or LXC container",
        "targetSchema": {"required": ["nodeId", "vmid"]},
        "parametersSchema": {
            "required": ["vmid", "node"],
            "properties": {
                "vmid": {"type": "integer", "description": "Proxmox VM/LXC ID"},
                "node": {"type": "string", "description": "Proxmox node name hosting the guest"},
                "type": {
                    "type": "string",
                    "enum": ["qemu", "lxc"],
                    "default": "qemu",
                    "description": "Guest type",
                },
            },
        },
        "execution": {
            "handler": "proxmox_stop_vm",
            "timeout": 60,
            "deliveryMode": "plugin_via_api_direct",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": True,
            "confirmationMessage": "This will stop the VM/LXC. Running workloads will be interrupted.",
            "dangerLevel": "high",
            "controlPermission": "proxmox:control:stop-vm",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::proxmox::snapshot",
        "category": "proxmox",
        "action": "snapshot",
        "displayName": "Create Snapshot",
        "description": "Create a point-in-time snapshot of a VM or LXC container",
        "targetSchema": {"required": ["nodeId", "vmid"]},
        "parametersSchema": {
            "required": ["vmid", "node", "snapName"],
            "properties": {
                "vmid": {"type": "integer", "description": "Proxmox VM/LXC ID"},
                "node": {"type": "string", "description": "Proxmox node name hosting the guest"},
                "snapName": {"type": "string", "description": "Snapshot name"},
                "description": {"type": "string", "description": "Snapshot description"},
                "type": {
                    "type": "string",
                    "enum": ["qemu", "lxc"],
                    "default": "qemu",
                    "description": "Guest type",
                },
                "includeRam": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include RAM state in snapshot (QEMU only)",
                },
            },
        },
        "execution": {
            "handler": "proxmox_snapshot",
            "timeout": 120,
            "deliveryMode": "plugin_via_api_direct",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "low",
            "controlPermission": "proxmox:control:snapshot",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::proxmox::list-storage",
        "category": "proxmox",
        "action": "list-storage",
        "displayName": "List Storage Pools",
        "description": "List available storage pools on a Proxmox node",
        "targetSchema": {"required": ["nodeId"]},
        "parametersSchema": {
            "properties": {
                "node": {"type": "string", "description": "Proxmox node name (optional)"},
            },
        },
        "execution": {
            "handler": "proxmox_list_storage",
            "timeout": 15,
            "deliveryMode": "plugin_via_api_direct",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "safe",
            "controlPermission": "proxmox:control:list-storage",
        },
        "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
]

# ── Config schema documentation ─────────────────────────────────────────
#
# Expected keys in self.config:
#   host        (str)  – PVE hostname or IP
#   port        (int)  – PVE API port, default 8006
#   verifySsl   (bool) – Whether to verify TLS certs, default False
#
# Expected keys in self.credentials:
#   tokenId     (str)  – PVE API token ID, e.g. "user@pam!mytoken"
#   tokenSecret (str)  – PVE API token secret UUID


class ProxmoxHandler(PluginHandler):
    """Proxmox VE plugin handler.

    Connects to the PVE REST API using an API token and provides profile
    enrichment, node discovery, command execution, and topology edges.
    """

    MANIFEST: ClassVar[dict[str, Any]] = _MANIFEST
    COMMAND_DEFINITIONS: ClassVar[list[dict[str, Any]]] = _COMMAND_DEFINITIONS

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
    ) -> None:
        super().__init__(config, credentials)
        self._client: httpx.AsyncClient | None = None

    # ── Internal helpers ────────────────────────────────────────────

    @property
    def _base_url(self) -> str:
        """Build the PVE API base URL from config."""
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 8006)
        return f"https://{host}:{port}"

    @property
    def _auth_header(self) -> dict[str, str]:
        """Build PVE API token authorization header."""
        if not self.credentials:
            return {}
        token_id = self.credentials.get("tokenId", "")
        token_secret = self.credentials.get("tokenSecret", "")
        return {"Authorization": f"PVEAPIToken={token_id}={token_secret}"}

    def _build_client(self) -> httpx.AsyncClient:
        """Create an httpx.AsyncClient configured for the PVE API."""
        verify_ssl = self.config.get("verifySsl", False)
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._auth_header,
            verify=verify_ssl,
            timeout=30.0,
        )

    async def _get(self, path: str) -> dict[str, Any]:
        """Issue a GET request against the PVE API and return the JSON body."""
        client = self._client or self._build_client()
        resp = await client.get(path)
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        return body

    async def _post(self, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Issue a POST request against the PVE API and return the JSON body."""
        client = self._client or self._build_client()
        resp = await client.post(path, data=data)
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        return body

    # ── Lifecycle ───────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Verify connectivity to the PVE API via the version endpoint.

        Returns True on success, False on failure.
        """
        try:
            self._client = self._build_client()
            resp = await self._client.get("/api2/json/version")
            resp.raise_for_status()
            data = resp.json().get("data", {})
            logger.info(
                "proxmox_connected",
                version=data.get("version"),
                release=data.get("release"),
            )
            return True
        except (httpx.HTTPError, httpx.InvalidURL, KeyError) as exc:
            logger.warning("proxmox_connect_failed", error=str(exc))
            return False

    async def health_check(self) -> dict[str, Any]:
        """Check PVE API health by querying the version endpoint.

        Returns a dict matching the PluginHealthStatus schema.
        """
        now = datetime.now(UTC)
        try:
            start = datetime.now(UTC)
            result = await self._get("/api2/json/version")
            elapsed_ms = (datetime.now(UTC) - start).total_seconds() * 1000
            version = result.get("data", {}).get("version", "unknown")
            return {
                "status": "healthy",
                "lastCheck": now,
                "consecutiveFailures": 0,
                "lastError": None,
                "responseTimeMs": round(elapsed_ms, 2),
                "pveVersion": version,
            }
        except (httpx.HTTPError, httpx.InvalidURL, KeyError) as exc:
            return {
                "status": "unhealthy",
                "lastCheck": now,
                "consecutiveFailures": 1,
                "lastError": str(exc),
                "responseTimeMs": None,
            }

    async def disconnect(self) -> None:
        """Close the persistent HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Touchpoints ─────────────────────────────────────────────────

    async def enrich_profile(
        self,
        node_id: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich a node profile with PVE host resource statistics.

        Queries ``/api2/json/nodes/{node}/status`` and returns CPU, memory,
        uptime, and kernel version data to be merged into
        ``profile.pluginData["plg::proxmox"]``.
        """
        pve_node = profile.get("network", {}).get("hostname", node_id)
        try:
            result = await self._get(f"/api2/json/nodes/{pve_node}/status")
            data = result.get("data", {})
            cpu_info = data.get("cpuinfo", {})
            memory = data.get("memory", {})
            return {
                "pveNode": pve_node,
                "uptime": data.get("uptime"),
                "kernelVersion": data.get("kversion"),
                "cpuModel": cpu_info.get("model"),
                "cpuCores": cpu_info.get("cores"),
                "cpuSockets": cpu_info.get("sockets"),
                "cpuUsage": data.get("cpu"),
                "memoryTotal": memory.get("total"),
                "memoryUsed": memory.get("used"),
                "memoryFree": memory.get("free"),
            }
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning(
                "proxmox_enrich_profile_failed",
                node_id=node_id,
                pve_node=pve_node,
                error=str(exc),
            )
            return {}

    async def discover_nodes(self) -> list[dict[str, Any]]:
        """Discover VMs, LXC containers, and physical nodes from the PVE cluster.

        Queries ``/api2/json/cluster/resources`` with type filters for VMs,
        nodes, and storage, returning each as a discovered resource.
        """
        discovered: list[dict[str, Any]] = []
        now = datetime.now(UTC)

        try:
            # Discover VMs and LXC containers
            vm_result = await self._get("/api2/json/cluster/resources?type=vm")
            for vm in vm_result.get("data", []):
                guest_type = vm.get("type", "qemu")
                discovered.append({
                    "sourcePlugin": "plg::proxmox",
                    "resourceType": "vm" if guest_type == "qemu" else "container",
                    "identifier": str(vm.get("vmid", "")),
                    "displayName": vm.get("name", f"VM {vm.get('vmid', '?')}"),
                    "status": vm.get("status", "unknown"),
                    "discoveredAt": now,
                    "metadata": {
                        "vmid": vm.get("vmid"),
                        "type": guest_type,
                        "node": vm.get("node"),
                        "maxcpu": vm.get("maxcpu"),
                        "maxmem": vm.get("maxmem"),
                        "maxdisk": vm.get("maxdisk"),
                        "uptime": vm.get("uptime"),
                    },
                })

            # Discover physical nodes
            node_result = await self._get("/api2/json/cluster/resources?type=node")
            for node in node_result.get("data", []):
                discovered.append({
                    "sourcePlugin": "plg::proxmox",
                    "resourceType": "hypervisor",
                    "identifier": node.get("node", ""),
                    "displayName": node.get("node", "unknown"),
                    "status": node.get("status", "unknown"),
                    "discoveredAt": now,
                    "metadata": {
                        "type": "node",
                        "node": node.get("node"),
                        "maxcpu": node.get("maxcpu"),
                        "maxmem": node.get("maxmem"),
                        "uptime": node.get("uptime"),
                        "level": node.get("level"),
                    },
                })

        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("proxmox_discover_nodes_failed", error=str(exc))

        return discovered

    async def execute_command(
        self,
        command_id: str,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a Proxmox command to the PVE API.

        Each command maps to a specific PVE API endpoint and HTTP method.
        """
        dispatch: dict[str, Any] = {
            "reg::proxmox::list-vms": self._cmd_list_vms,
            "reg::proxmox::vm-status": self._cmd_vm_status,
            "reg::proxmox::start-vm": self._cmd_start_vm,
            "reg::proxmox::stop-vm": self._cmd_stop_vm,
            "reg::proxmox::snapshot": self._cmd_snapshot,
            "reg::proxmox::list-storage": self._cmd_list_storage,
        }

        handler = dispatch.get(command_id)
        if handler is None:
            return {
                "success": False,
                "output": f"Unknown Proxmox command: {command_id}",
            }

        try:
            result: dict[str, Any] = await handler(target, params)
            return result
        except httpx.HTTPStatusError as exc:
            error_body = exc.response.text
            logger.error(
                "proxmox_command_http_error",
                command_id=command_id,
                status_code=exc.response.status_code,
                body=error_body[:500],
            )
            return {
                "success": False,
                "output": f"PVE API error {exc.response.status_code}: {error_body[:200]}",
            }
        except httpx.HTTPError as exc:
            logger.error(
                "proxmox_command_error",
                command_id=command_id,
                error=str(exc),
            )
            return {
                "success": False,
                "output": f"Connection error: {exc}",
            }

    async def get_topology_edges(
        self,
        node_id: str,
    ) -> list[dict[str, Any]]:
        """Return topology edges linking VMs/CTs to their PVE host nodes
        and storage pools to nodes.
        """
        edges: list[dict[str, Any]] = []

        try:
            # VM/CT -> host node edges
            vm_result = await self._get("/api2/json/cluster/resources?type=vm")
            for vm in vm_result.get("data", []):
                host_node = vm.get("node")
                vmid = vm.get("vmid")
                guest_type = vm.get("type", "qemu")
                if host_node and vmid is not None:
                    edges.append({
                        "source": f"proxmox::{guest_type}::{vmid}",
                        "target": f"proxmox::node::{host_node}",
                        "relationship": "runs_on",
                        "sourcePlugin": "plg::proxmox",
                        "metadata": {
                            "vmid": vmid,
                            "type": guest_type,
                            "status": vm.get("status"),
                        },
                    })

            # Storage -> node edges
            storage_result = await self._get("/api2/json/cluster/resources?type=storage")
            for storage in storage_result.get("data", []):
                storage_name = storage.get("storage")
                host_node = storage.get("node")
                if storage_name and host_node:
                    edges.append({
                        "source": f"proxmox::storage::{storage_name}",
                        "target": f"proxmox::node::{host_node}",
                        "relationship": "attached_to",
                        "sourcePlugin": "plg::proxmox",
                        "metadata": {
                            "storage": storage_name,
                            "plugintype": storage.get("plugintype"),
                            "status": storage.get("status"),
                            "maxdisk": storage.get("maxdisk"),
                            "disk": storage.get("disk"),
                        },
                    })

        except (httpx.HTTPError, KeyError) as exc:
            logger.warning(
                "proxmox_topology_edges_failed",
                node_id=node_id,
                error=str(exc),
            )

        return edges

    # ── Command implementations ─────────────────────────────────────

    async def _cmd_list_vms(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """List VMs and/or LXC containers from the cluster."""
        result = await self._get("/api2/json/cluster/resources?type=vm")
        vms = result.get("data", [])
        type_filter = params.get("type", "all")
        if type_filter != "all":
            vms = [v for v in vms if v.get("type") == type_filter]
        return {
            "success": True,
            "output": f"Found {len(vms)} guest(s)",
            "data": vms,
        }

    async def _cmd_vm_status(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Get the status of a specific VM or LXC container."""
        vmid = params["vmid"]
        guest_type = params.get("type", "qemu")
        # Determine the PVE node from params or discover it
        node = params.get("node")
        if not node:
            node = await self._resolve_vm_node(vmid)
        if not node:
            return {"success": False, "output": f"Cannot resolve PVE node for VMID {vmid}"}

        endpoint = f"/api2/json/nodes/{node}/{guest_type}/{vmid}/status/current"
        result = await self._get(endpoint)
        return {
            "success": True,
            "output": f"Status for {guest_type}/{vmid} on {node}",
            "data": result.get("data", {}),
        }

    async def _cmd_start_vm(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Start a VM or LXC container."""
        vmid = params["vmid"]
        node = params["node"]
        guest_type = params.get("type", "qemu")
        endpoint = f"/api2/json/nodes/{node}/{guest_type}/{vmid}/status/start"
        result = await self._post(endpoint)
        task_id = result.get("data", "")
        return {
            "success": True,
            "output": f"Start command issued for {guest_type}/{vmid} on {node} (task: {task_id})",
            "data": {"taskId": task_id},
        }

    async def _cmd_stop_vm(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Stop a VM or LXC container."""
        vmid = params["vmid"]
        node = params["node"]
        guest_type = params.get("type", "qemu")
        endpoint = f"/api2/json/nodes/{node}/{guest_type}/{vmid}/status/stop"
        result = await self._post(endpoint)
        task_id = result.get("data", "")
        return {
            "success": True,
            "output": f"Stop command issued for {guest_type}/{vmid} on {node} (task: {task_id})",
            "data": {"taskId": task_id},
        }

    async def _cmd_snapshot(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a snapshot of a VM or LXC container."""
        vmid = params["vmid"]
        node = params["node"]
        snap_name = params["snapName"]
        guest_type = params.get("type", "qemu")
        endpoint = f"/api2/json/nodes/{node}/{guest_type}/{vmid}/snapshot"
        post_data: dict[str, Any] = {"snapname": snap_name}
        description = params.get("description")
        if description:
            post_data["description"] = description
        if guest_type == "qemu" and params.get("includeRam"):
            post_data["vmstate"] = 1
        result = await self._post(endpoint, data=post_data)
        task_id = result.get("data", "")
        return {
            "success": True,
            "output": f"Snapshot '{snap_name}' created for {guest_type}/{vmid} (task: {task_id})",
            "data": {"taskId": task_id, "snapName": snap_name},
        }

    async def _cmd_list_storage(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """List storage pools, optionally filtered to a specific node."""
        node = params.get("node")
        if node:
            endpoint = f"/api2/json/nodes/{node}/storage"
        else:
            endpoint = "/api2/json/cluster/resources?type=storage"
        result = await self._get(endpoint)
        pools = result.get("data", [])
        return {
            "success": True,
            "output": f"Found {len(pools)} storage pool(s)",
            "data": pools,
        }

    async def _resolve_vm_node(self, vmid: int) -> str | None:
        """Resolve the PVE node hosting a given VMID by querying cluster resources."""
        try:
            result = await self._get("/api2/json/cluster/resources?type=vm")
            for vm in result.get("data", []):
                if vm.get("vmid") == vmid:
                    return vm.get("node")  # type: ignore[no-any-return]
        except (httpx.HTTPError, KeyError):
            pass
        return None
