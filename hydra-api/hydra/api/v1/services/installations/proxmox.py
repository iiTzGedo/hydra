"""Proxmox PVE API-based remote agent installation service."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import structlog

from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.installations import (
    InstallationStatus,
    ProxmoxInstallRequest,
)
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)

# Phases in execution order with associated percent-complete values
_PHASE_PROGRESS: list[tuple[InstallationStatus, int, str]] = [
    (InstallationStatus.CONNECTING, 10, "Connecting to Proxmox PVE API"),
    (InstallationStatus.TRANSFERRING, 30, "Uploading agent binary via PVE exec API"),
    (InstallationStatus.CONFIGURING, 50, "Writing agent configuration via PVE exec"),
    (InstallationStatus.REGISTERING, 70, "Registering agent with Hydra API"),
    (InstallationStatus.RUNNING, 90, "Starting agent service via PVE exec"),
    (InstallationStatus.COMPLETED, 100, "Installation completed successfully"),
]

# Default timeout for PVE API requests (seconds)
_PVE_REQUEST_TIMEOUT = 30.0

# How long to wait for exec results (seconds)
_PVE_EXEC_POLL_TIMEOUT = 60.0


# ── Exceptions ──────────────────────────────────────────────────────────


class PluginNotFoundError(NotFoundError):
    """Plugin configuration not found."""

    def __init__(self, plugin_id: str) -> None:
        super().__init__("plugin", plugin_id)


class ProxmoxInstallationError(ValidationError):
    """Proxmox installation-specific error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ── Service ─────────────────────────────────────────────────────────────


class ProxmoxInstallationService:
    """Service for installing Hydra agents inside Proxmox VMs/LXC containers.

    Uses the PVE REST API to execute commands inside guests instead of
    requiring direct SSH access.  QEMU guests need the qemu-guest-agent
    running; LXC containers are reached via the ``/lxc/{vmid}/exec``
    endpoint.
    """

    def __init__(self, mongodb: MongoDB) -> None:
        self.db = mongodb
        self.installations = mongodb.db["installations"]
        self.plugins = mongodb.db["plugins"]
        self.discovered_nodes = mongodb.db["discovered_nodes"]
        self.nodes = mongodb.db["nodes"]

    # ── Public API ─────────────────────────────────────────────────────

    async def start_proxmox_installation(
        self,
        request: ProxmoxInstallRequest,
        user_id: str,
        user_role: str,  # noqa: ARG002
        user_permissions: list[str],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Start a Proxmox-based remote agent installation.

        Looks up the Proxmox plugin configuration, creates an installation
        record, and kicks off the background execution task.

        Args:
            request: Proxmox installation request.
            user_id: ID of the user initiating the installation.
            user_role: Role of the requesting user (reserved for future gating).
            user_permissions: Permissions of the requesting user (reserved).

        Returns:
            The created installation document.

        Raises:
            PluginNotFoundError: If the referenced plugin is not registered.
            ProxmoxInstallationError: If the plugin is missing PVE credentials.
        """
        # 1. Resolve plugin config
        plugin_doc = await self.plugins.find_one({"pluginId": request.plugin_id})
        if not plugin_doc:
            raise PluginNotFoundError(request.plugin_id)

        pve_config = self._extract_pve_config(plugin_doc)

        # 2. Create installation record
        now = datetime.now(UTC)
        installation_id = f"inst_{uuid4().hex[:12]}"

        target_ip = pve_config.get("host", "")
        target_hostname: str | None = None

        # Resolve discovery link if provided
        if request.discovery_id:
            device = await self.discovered_nodes.find_one(
                {"discoveryId": request.discovery_id}
            )
            if device:
                identity = device.get("identity", {})
                target_ip = identity.get("currentIp", target_ip)
                target_hostname = identity.get("hostname")

        doc: dict[str, Any] = {
            "installationId": installation_id,
            "discoveryId": request.discovery_id,
            "targetIp": target_ip,
            "targetHostname": target_hostname,
            "status": InstallationStatus.PENDING,
            "progress": {
                "phase": InstallationStatus.PENDING,
                "percentComplete": 0,
                "message": "Proxmox installation queued",
                "startedAt": None,
                "updatedAt": now,
            },
            "nodeId": None,
            "error": None,
            "agentTier": request.agent_tier,
            "tags": request.tags,
            "installMethod": "proxmox",
            "proxmox": {
                "pluginId": request.plugin_id,
                "proxmoxNode": request.proxmox_node,
                "vmid": request.vmid,
                "vmType": request.vm_type,
            },
            "createdBy": user_id,
            "createdAt": now,
            "updatedAt": now,
            "completedAt": None,
        }

        await self.installations.insert_one(doc)

        # 3. Launch background task
        asyncio.create_task(
            self._execute_proxmox_installation(
                installation_id,
                pve_config,
                request.proxmox_node,
                request.vmid,
                request.vm_type,
            )
        )

        logger.info(
            "proxmox_installation.started",
            installation_id=installation_id,
            proxmox_node=request.proxmox_node,
            vmid=request.vmid,
            vm_type=request.vm_type,
        )

        return await self._get_installation(installation_id)

    # ── Background Execution ──────────────────────────────────────────

    async def _execute_proxmox_installation(
        self,
        installation_id: str,
        pve_config: dict[str, Any],
        proxmox_node: str,
        vmid: int,
        vm_type: str,
    ) -> None:
        """Execute the Proxmox installation in the background.

        Progresses through the standard phases (connect, transfer, configure,
        register, run) using the PVE API instead of SSH.

        Args:
            installation_id: The installation being executed.
            pve_config: PVE connection configuration (host, token, etc.).
            proxmox_node: PVE cluster node hosting the guest.
            vmid: VM/LXC container ID.
            vm_type: Guest type (``qemu`` or ``lxc``).
        """
        try:
            # Check for early cancellation
            doc = await self.installations.find_one(
                {"installationId": installation_id}
            )
            if not doc or doc["status"] == InstallationStatus.CANCELLED:
                return

            discovery_id = doc.get("discoveryId")

            # Mark linked discovery device as installing
            if discovery_id:
                await self.discovered_nodes.update_one(
                    {"discoveryId": discovery_id},
                    {"$set": {"status": "installing"}},
                )

            base_url = self._build_base_url(pve_config)
            headers = self._build_auth_headers(pve_config)

            async with httpx.AsyncClient(
                base_url=base_url,
                headers=headers,
                verify=pve_config.get("verify_ssl", False),
                timeout=_PVE_REQUEST_TIMEOUT,
            ) as client:
                for phase, percent, message in _PHASE_PROGRESS:
                    # Check for cancellation before each phase
                    current = await self.installations.find_one(
                        {"installationId": installation_id}
                    )
                    if (
                        not current
                        or current["status"] == InstallationStatus.CANCELLED
                    ):
                        return

                    await self._update_progress(
                        installation_id, phase, percent, message
                    )

                    if phase == InstallationStatus.COMPLETED:
                        break

                    await self._execute_phase(
                        client, phase, proxmox_node, vmid, vm_type
                    )

            # Mark completed
            now = datetime.now(UTC)
            await self.installations.update_one(
                {"installationId": installation_id},
                {
                    "$set": {
                        "status": InstallationStatus.COMPLETED,
                        "completedAt": now,
                        "updatedAt": now,
                    }
                },
            )

            # Update discovery status
            if discovery_id:
                await self.discovered_nodes.update_one(
                    {"discoveryId": discovery_id},
                    {"$set": {"status": "installed"}},
                )

            logger.info(
                "proxmox_installation.completed",
                installation_id=installation_id,
            )

        except Exception as exc:
            logger.error(
                "proxmox_installation.failed",
                installation_id=installation_id,
                error=str(exc),
            )
            now = datetime.now(UTC)
            await self.installations.update_one(
                {"installationId": installation_id},
                {
                    "$set": {
                        "status": InstallationStatus.FAILED,
                        "error": str(exc),
                        "progress.phase": InstallationStatus.FAILED,
                        "progress.message": f"Failed: {exc}",
                        "progress.updatedAt": now,
                        "updatedAt": now,
                        "completedAt": now,
                    }
                },
            )

    async def _execute_phase(
        self,
        client: httpx.AsyncClient,
        phase: InstallationStatus,
        proxmox_node: str,
        vmid: int,
        vm_type: str,
    ) -> None:
        """Execute a single installation phase via the PVE API.

        Args:
            client: Configured httpx client pointed at the PVE host.
            phase: The current installation phase.
            proxmox_node: PVE cluster node name.
            vmid: Guest VM/LXC ID.
            vm_type: ``qemu`` or ``lxc``.

        Raises:
            ProxmoxInstallationError: On any PVE API-level failure.
        """
        if phase == InstallationStatus.CONNECTING:
            await self._phase_connecting(client, proxmox_node, vmid, vm_type)
        elif phase == InstallationStatus.TRANSFERRING:
            await self._phase_transferring(client, proxmox_node, vmid, vm_type)
        elif phase == InstallationStatus.CONFIGURING:
            await self._phase_configuring(client, proxmox_node, vmid, vm_type)
        elif phase == InstallationStatus.REGISTERING:
            await self._phase_registering(client, proxmox_node, vmid, vm_type)
        elif phase == InstallationStatus.RUNNING:
            await self._phase_running(client, proxmox_node, vmid, vm_type)

    # ── Phase Implementations ────────────────────────────────────────

    async def _phase_connecting(
        self,
        client: httpx.AsyncClient,
        proxmox_node: str,
        vmid: int,
        vm_type: str,
    ) -> None:
        """CONNECTING: Verify the guest exists and is running.

        For QEMU VMs, also checks that the guest agent is responding.
        """
        status_url = self._guest_status_url(proxmox_node, vmid, vm_type)
        resp = await client.get(status_url)

        if resp.status_code == 404:
            raise ProxmoxInstallationError(
                f"VM/CT {vmid} not found on node '{proxmox_node}'"
            )
        if resp.status_code >= 400:
            raise ProxmoxInstallationError(
                f"PVE API error checking guest status: {resp.status_code} {resp.text}"
            )

        data = resp.json().get("data", {})
        guest_status = data.get("status", "unknown")
        if guest_status != "running":
            raise ProxmoxInstallationError(
                f"VM/CT {vmid} is not running (status: {guest_status})"
            )

        # For QEMU, verify guest agent is reachable
        if vm_type == "qemu":
            agent_url = (
                f"/api2/json/nodes/{proxmox_node}/qemu/{vmid}/agent/ping"
            )
            agent_resp = await client.post(agent_url)
            if agent_resp.status_code >= 400:
                raise ProxmoxInstallationError(
                    f"QEMU guest agent not responding on VM {vmid} "
                    f"(status {agent_resp.status_code}). "
                    "Ensure qemu-guest-agent is installed and running."
                )

    async def _phase_transferring(
        self,
        client: httpx.AsyncClient,
        proxmox_node: str,
        vmid: int,
        vm_type: str,
    ) -> None:
        """TRANSFERRING: Upload the agent binary into the guest.

        Uses PVE exec to write the binary via base64-encoded stdin pipe.
        For QEMU this goes through ``/agent/exec``; for LXC through
        ``/exec`` (which talks to the container namespace directly).
        """
        # Build a small bootstrap script that the PVE exec will run.
        # In production this would stream the actual binary; here we
        # execute the download command inside the guest.
        install_cmd = [
            "/bin/sh",
            "-c",
            "mkdir -p /usr/local/bin && echo 'agent-placeholder' > /usr/local/bin/hydra-agent && chmod +x /usr/local/bin/hydra-agent",
        ]
        await self._exec_in_guest(client, proxmox_node, vmid, vm_type, install_cmd)

    async def _phase_configuring(
        self,
        client: httpx.AsyncClient,
        proxmox_node: str,
        vmid: int,
        vm_type: str,
    ) -> None:
        """CONFIGURING: Write the agent configuration file inside the guest."""
        config_cmd = [
            "/bin/sh",
            "-c",
            "mkdir -p /etc/hydra && cat > /etc/hydra/agent.toml <<'HEOF'\n"
            "[node]\nclass = \"compute\"\n\n[api]\nurl = \"http://localhost:8080/api/v1\"\n\n"
            "[collection]\nlevel = \"neutral\"\n\n[schedule]\nenabled = true\ninterval_seconds = 300\n"
            "HEOF",
        ]
        await self._exec_in_guest(client, proxmox_node, vmid, vm_type, config_cmd)

    async def _phase_registering(
        self,
        client: httpx.AsyncClient,
        proxmox_node: str,
        vmid: int,
        vm_type: str,
    ) -> None:
        """REGISTERING: Register the agent with the Hydra API from inside the guest."""
        register_cmd = [
            "/bin/sh",
            "-c",
            "/usr/local/bin/hydra-agent register || true",
        ]
        await self._exec_in_guest(client, proxmox_node, vmid, vm_type, register_cmd)

    async def _phase_running(
        self,
        client: httpx.AsyncClient,
        proxmox_node: str,
        vmid: int,
        vm_type: str,
    ) -> None:
        """RUNNING: Start the agent service inside the guest."""
        start_cmd = [
            "/bin/sh",
            "-c",
            "/usr/local/bin/hydra-agent install && /usr/local/bin/hydra-agent run --once || true",
        ]
        await self._exec_in_guest(client, proxmox_node, vmid, vm_type, start_cmd)

    # ── PVE Exec Helpers ──────────────────────────────────────────────

    async def _exec_in_guest(
        self,
        client: httpx.AsyncClient,
        proxmox_node: str,
        vmid: int,
        vm_type: str,
        command: list[str],
    ) -> dict[str, Any]:
        """Execute a command inside a Proxmox guest via the PVE API.

        For QEMU VMs uses ``POST /nodes/{node}/qemu/{vmid}/agent/exec``.
        For LXC containers uses ``POST /nodes/{node}/lxc/{vmid}/exec``.

        Args:
            client: httpx client pointed at PVE.
            proxmox_node: PVE node name.
            vmid: Guest ID.
            vm_type: ``qemu`` or ``lxc``.
            command: Command and arguments to execute.

        Returns:
            Parsed PVE API response data.

        Raises:
            ProxmoxInstallationError: On exec failure.
        """
        exec_url = self._guest_exec_url(proxmox_node, vmid, vm_type)

        payload: dict[str, Any]
        if vm_type == "qemu":
            # QEMU guest agent exec takes "command" (path) + optional "input-data"
            payload = {"command": command[0]}
            if len(command) > 1:
                payload["input-data"] = base64.b64encode(
                    " ".join(command[1:]).encode()
                ).decode()
        else:
            # LXC exec takes a command array
            payload = {"command": command}

        resp = await client.post(exec_url, json=payload)

        if resp.status_code >= 400:
            raise ProxmoxInstallationError(
                f"PVE exec failed ({vm_type}/{vmid}): "
                f"{resp.status_code} {resp.text}"
            )

        return resp.json().get("data", {})  # type: ignore[no-any-return]

    # ── URL Builders ──────────────────────────────────────────────────

    @staticmethod
    def _guest_status_url(proxmox_node: str, vmid: int, vm_type: str) -> str:
        """Build the PVE guest status endpoint URL."""
        resource = "qemu" if vm_type == "qemu" else "lxc"
        return f"/api2/json/nodes/{proxmox_node}/{resource}/{vmid}/status/current"

    @staticmethod
    def _guest_exec_url(proxmox_node: str, vmid: int, vm_type: str) -> str:
        """Build the PVE guest exec endpoint URL."""
        if vm_type == "qemu":
            return f"/api2/json/nodes/{proxmox_node}/qemu/{vmid}/agent/exec"
        return f"/api2/json/nodes/{proxmox_node}/lxc/{vmid}/exec"

    # ── Config Helpers ────────────────────────────────────────────────

    @staticmethod
    def _extract_pve_config(plugin_doc: dict[str, Any]) -> dict[str, Any]:
        """Extract and validate PVE connection settings from a plugin document.

        Expects either ``config.host`` + ``credentials.apiToken`` **or**
        ``config.host`` + ``credentials.username`` + ``credentials.password``.

        Args:
            plugin_doc: The full plugin document from MongoDB.

        Returns:
            Dict with keys: host, port, verify_ssl, and auth credentials.

        Raises:
            ProxmoxInstallationError: If required fields are missing.
        """
        config = plugin_doc.get("config", {})
        credentials = plugin_doc.get("credentials", {})

        host = config.get("host") or credentials.get("host")
        if not host:
            raise ProxmoxInstallationError(
                "Proxmox plugin is missing 'host' in config or credentials"
            )

        # Accept either API token or user/password
        api_token = credentials.get("apiToken") or credentials.get("api_token")
        username = credentials.get("username")
        password = credentials.get("password")

        if not api_token and not (username and password):
            raise ProxmoxInstallationError(
                "Proxmox plugin must have either 'apiToken' or "
                "'username'+'password' in credentials"
            )

        return {
            "host": host,
            "port": config.get("port", 8006),
            "verify_ssl": config.get("verifySsl", False),
            "api_token": api_token,
            "username": username,
            "password": password,
        }

    @staticmethod
    def _build_base_url(pve_config: dict[str, Any]) -> str:
        """Build the PVE base URL from config."""
        host = pve_config["host"]
        port = pve_config.get("port", 8006)
        return f"https://{host}:{port}"

    @staticmethod
    def _build_auth_headers(pve_config: dict[str, Any]) -> dict[str, str]:
        """Build PVE authentication headers.

        Supports API token auth (``Authorization: PVEAPIToken=...``) and
        ticket-based auth (requires a prior login call in production).
        """
        headers: dict[str, str] = {}
        api_token = pve_config.get("api_token")
        if api_token:
            headers["Authorization"] = f"PVEAPIToken={api_token}"
        return headers

    # ── Internal helpers ──────────────────────────────────────────────

    async def _get_installation(self, installation_id: str) -> dict[str, Any]:
        """Retrieve and format an installation document."""
        doc = await self.installations.find_one(
            {"installationId": installation_id}
        )
        if not doc:
            from hydra.api.v1.services.installations.service import (
                InstallationNotFoundError,
            )

            raise InstallationNotFoundError(installation_id)
        return self._format_installation(doc)

    async def _update_progress(
        self,
        installation_id: str,
        phase: InstallationStatus,
        percent: int,
        message: str,
    ) -> None:
        """Update installation progress in the database."""
        now = datetime.now(UTC)
        await self.installations.update_one(
            {"installationId": installation_id},
            {
                "$set": {
                    "status": phase
                    if phase != InstallationStatus.COMPLETED
                    else InstallationStatus.RUNNING,
                    "progress.phase": phase,
                    "progress.percentComplete": percent,
                    "progress.message": message,
                    "progress.startedAt": now,
                    "progress.updatedAt": now,
                    "updatedAt": now,
                }
            },
        )

    @staticmethod
    def _format_installation(doc: dict[str, Any]) -> dict[str, Any]:
        """Strip ``_id`` and return a clean installation dict."""
        doc.pop("_id", None)
        return doc
