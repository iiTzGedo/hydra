"""Ansible plugin handler.

Executes Ansible CLI commands (playbooks, ad-hoc modules, inventory,
Galaxy) via ``asyncio.create_subprocess_exec``.  Ansible is a local CLI
tool, not a REST API, so all operations shell out to the ``ansible*``
binaries available on ``$PATH``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any, ClassVar

import structlog

from hydra.api.v1.services.plugins.base import PluginHandler

logger = structlog.get_logger(__name__)

_NOW = datetime.now(UTC)

# ── Default paths ────────────────────────────────────────────────────

_DEFAULT_INVENTORY = "/etc/ansible/hosts"
_DEFAULT_CONFIG = "/etc/ansible/ansible.cfg"


class AnsibleHandler(PluginHandler):
    """Plugin handler for Ansible CLI operations.

    Config schema:
        inventoryPath  – default inventory file   (default: /etc/ansible/hosts)
        configPath     – ansible.cfg location      (default: /etc/ansible/ansible.cfg)
        vaultPasswordFile – path to vault password file (optional)
    """

    # ── Class-level constants ────────────────────────────────────────

    MANIFEST: ClassVar[dict[str, Any]] = {
        "pluginId": "plg::ansible",
        "name": "Ansible",
        "version": "1.0.0",
        "description": "Ansible automation — playbooks, ad-hoc modules, inventory, and Galaxy",
        "author": "Hydra Team",
        "classification": "core",
        "category": "development",
        "touchpoints": {
            "profileEnrichment": False,
            "discoveryProvider": False,
            "commandProvider": True,
            "executionHandler": True,
            "topologyProvider": False,
            "workflowBlockProvider": True,
        },
        "supportedTiers": ["normal", "max"],
        "healthCheckEndpoint": None,
        "contributedCommands": [
            "reg::ansible::run-playbook",
            "reg::ansible::run-module",
            "reg::ansible::list-inventory",
            "reg::ansible::galaxy-install",
        ],
    }

    COMMAND_DEFINITIONS: ClassVar[list[dict[str, Any]]] = [
        # ── run-playbook ────────────────────────────────────────────
        {
            "registryId": "reg::ansible::run-playbook",
            "category": "ansible",
            "action": "run-playbook",
            "displayName": "Run Ansible Playbook",
            "description": "Execute an Ansible playbook against target hosts",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "required": ["playbook"],
                "properties": {
                    "playbook": {
                        "type": "string",
                        "description": "Path to the playbook YAML file",
                    },
                    "inventory": {
                        "type": "string",
                        "description": "Inventory file or host list (overrides default)",
                    },
                    "limit": {
                        "type": "string",
                        "description": "Limit execution to matching hosts/groups",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags to run",
                    },
                    "check": {
                        "type": "boolean",
                        "default": False,
                        "description": "Run in check (dry-run) mode",
                    },
                },
            },
            "execution": {
                "handler": "ansible_run_playbook",
                "timeout": 600,
                "deliveryMode": "poll_only",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "admin",
                "requiresConfirmation": True,
                "confirmationMessage": "This will execute an Ansible playbook which may modify remote hosts.",
                "dangerLevel": "high",
                "controlPermission": "plugins:control:ansible:run-playbook",
            },
            "audit": {
                "logLevel": "verbose",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "1.0.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
        # ── run-module ──────────────────────────────────────────────
        {
            "registryId": "reg::ansible::run-module",
            "category": "ansible",
            "action": "run-module",
            "displayName": "Run Ansible Module",
            "description": "Execute an ad-hoc Ansible module against target hosts",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "required": ["pattern", "module"],
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Host pattern (e.g. 'all', 'webservers')",
                    },
                    "module": {
                        "type": "string",
                        "description": "Module name (e.g. 'ping', 'shell', 'copy')",
                    },
                    "args": {
                        "type": "string",
                        "description": "Module arguments",
                    },
                    "inventory": {
                        "type": "string",
                        "description": "Inventory file or host list (overrides default)",
                    },
                },
            },
            "execution": {
                "handler": "ansible_run_module",
                "timeout": 300,
                "deliveryMode": "poll_only",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "admin",
                "requiresConfirmation": True,
                "confirmationMessage": "This will execute an ad-hoc Ansible module which may modify remote hosts.",
                "dangerLevel": "high",
                "controlPermission": "plugins:control:ansible:run-module",
            },
            "audit": {
                "logLevel": "verbose",
                "captureOutput": True,
                "sensitiveParameters": ["args"],
            },
            "metadata": {
                "version": "1.0.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
        # ── list-inventory ──────────────────────────────────────────
        {
            "registryId": "reg::ansible::list-inventory",
            "category": "ansible",
            "action": "list-inventory",
            "displayName": "List Ansible Inventory",
            "description": "List hosts and groups from the Ansible inventory",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "inventory": {
                        "type": "string",
                        "description": "Inventory file or host list (overrides default)",
                    },
                },
            },
            "execution": {
                "handler": "ansible_list_inventory",
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
                "controlPermission": "plugins:control:ansible:list-inventory",
            },
            "audit": {
                "logLevel": "minimal",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "1.0.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
        # ── galaxy-install ──────────────────────────────────────────
        {
            "registryId": "reg::ansible::galaxy-install",
            "category": "ansible",
            "action": "galaxy-install",
            "displayName": "Install Galaxy Role/Collection",
            "description": "Install an Ansible Galaxy role or collection",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Galaxy role or collection name (e.g. 'geerlingguy.docker')",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["role", "collection"],
                        "default": "role",
                        "description": "Install a role or collection",
                    },
                },
            },
            "execution": {
                "handler": "ansible_galaxy_install",
                "timeout": 120,
                "deliveryMode": "poll_only",
                "retryable": True,
                "maxRetries": 2,
            },
            "rbac": {
                "minimumRole": "admin",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "medium",
                "controlPermission": "plugins:control:ansible:galaxy-install",
            },
            "audit": {
                "logLevel": "standard",
                "captureOutput": True,
                "sensitiveParameters": [],
            },
            "metadata": {
                "version": "1.0.0",
                "addedAt": _NOW,
                "builtIn": False,
                "deprecated": False,
            },
        },
    ]

    # ── Helpers ──────────────────────────────────────────────────────

    def _inventory_path(self, params: dict[str, Any] | None = None) -> str:
        """Return the effective inventory path from params or config."""
        if params and params.get("inventory"):
            return str(params["inventory"])
        return str(self.config.get("inventoryPath", _DEFAULT_INVENTORY))

    def _build_env(self) -> dict[str, str] | None:
        """Build environment overrides for Ansible subprocesses."""
        env: dict[str, str] = {}
        config_path = self.config.get("configPath")
        if config_path:
            env["ANSIBLE_CONFIG"] = str(config_path)
        vault_file = self.config.get("vaultPasswordFile")
        if vault_file:
            env["ANSIBLE_VAULT_PASSWORD_FILE"] = str(vault_file)
        return env or None

    async def _run_subprocess(
        self,
        *args: str,
    ) -> tuple[int, str, str]:
        """Run a subprocess and capture stdout/stderr.

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        env = self._build_env()
        logger.debug("ansible_subprocess", cmd=args, env=env)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
        )

    # ── Lifecycle ────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Verify the ``ansible`` binary is reachable."""
        try:
            returncode, _stdout, _stderr = await self._run_subprocess("ansible", "--version")
            return returncode == 0
        except FileNotFoundError:
            logger.warning("ansible_not_found")
            return False
        except OSError as exc:
            logger.warning("ansible_connect_error", error=str(exc))
            return False

    async def health_check(self) -> dict[str, Any]:
        """Return health status by running ``ansible --version``."""
        check_time = datetime.now(UTC)
        try:
            returncode, stdout, stderr = await self._run_subprocess("ansible", "--version")
            if returncode == 0:
                # First line is typically "ansible [core X.Y.Z]"
                version_line = stdout.strip().splitlines()[0] if stdout.strip() else "unknown"
                return {
                    "status": "healthy",
                    "lastCheck": check_time.isoformat(),
                    "consecutiveFailures": 0,
                    "lastError": None,
                    "version": version_line,
                }
            return {
                "status": "unhealthy",
                "lastCheck": check_time.isoformat(),
                "consecutiveFailures": 1,
                "lastError": stderr.strip() or f"ansible exited with code {returncode}",
                "version": None,
            }
        except (FileNotFoundError, OSError) as exc:
            return {
                "status": "unhealthy",
                "lastCheck": check_time.isoformat(),
                "consecutiveFailures": 1,
                "lastError": str(exc),
                "version": None,
            }

    # ── Command execution ────────────────────────────────────────────

    async def execute_command(
        self,
        command_id: str,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a plugin command to the appropriate Ansible CLI."""
        _CommandHandler = Callable[
            [dict[str, Any], dict[str, Any]],
            Coroutine[Any, Any, dict[str, Any]],
        ]
        handlers: dict[str, _CommandHandler] = {
            "reg::ansible::run-playbook": self._exec_run_playbook,
            "reg::ansible::run-module": self._exec_run_module,
            "reg::ansible::list-inventory": self._exec_list_inventory,
            "reg::ansible::galaxy-install": self._exec_galaxy_install,
        }

        handler = handlers.get(command_id)
        if handler is None:
            return {
                "success": False,
                "output": f"Unknown Ansible command: {command_id}",
            }

        try:
            return await handler(target, params)
        except Exception as exc:
            logger.exception("ansible_command_error", command_id=command_id, error=str(exc))
            return {
                "success": False,
                "output": f"Ansible command failed: {exc}",
            }

    async def _exec_run_playbook(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute ``ansible-playbook``."""
        playbook = params.get("playbook")
        if not playbook:
            return {"success": False, "output": "Missing required parameter: playbook"}

        cmd: list[str] = ["ansible-playbook", str(playbook)]

        inventory = self._inventory_path(params)
        cmd.extend(["-i", inventory])

        limit = params.get("limit")
        if limit:
            cmd.extend(["--limit", str(limit)])

        tags = params.get("tags")
        if tags:
            cmd.extend(["--tags", str(tags)])

        if params.get("check"):
            cmd.append("--check")

        returncode, stdout, stderr = await self._run_subprocess(*cmd)
        return {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "returnCode": returncode,
        }

    async def _exec_run_module(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute ad-hoc ``ansible`` module."""
        pattern = params.get("pattern")
        module = params.get("module")
        if not pattern or not module:
            return {
                "success": False,
                "output": "Missing required parameters: pattern, module",
            }

        cmd: list[str] = ["ansible", str(pattern), "-m", str(module)]

        args = params.get("args")
        if args:
            cmd.extend(["-a", str(args)])

        inventory = self._inventory_path(params)
        cmd.extend(["-i", inventory])

        returncode, stdout, stderr = await self._run_subprocess(*cmd)
        return {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "returnCode": returncode,
        }

    async def _exec_list_inventory(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute ``ansible-inventory --list``."""
        cmd: list[str] = ["ansible-inventory", "--list"]

        inventory = self._inventory_path(params)
        cmd.extend(["-i", inventory])

        returncode, stdout, stderr = await self._run_subprocess(*cmd)
        return {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "returnCode": returncode,
        }

    async def _exec_galaxy_install(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute ``ansible-galaxy {type} install {name}``."""
        name = params.get("name")
        if not name:
            return {"success": False, "output": "Missing required parameter: name"}

        install_type = params.get("type", "role")
        if install_type not in ("role", "collection"):
            return {
                "success": False,
                "output": f"Invalid type '{install_type}'; must be 'role' or 'collection'",
            }

        cmd: list[str] = ["ansible-galaxy", str(install_type), "install", str(name)]

        returncode, stdout, stderr = await self._run_subprocess(*cmd)
        return {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "returnCode": returncode,
        }

    # ── Workflow blocks ──────────────────────────────────────────────

    def get_workflow_blocks(self) -> list[dict[str, Any]]:
        """Return the ``ansible-playbook`` workflow block definition."""
        return [
            {
                "blockId": "ansible-playbook",
                "name": "Ansible Playbook",
                "description": "Execute an Ansible playbook as a workflow step",
                "pluginId": "plg::ansible",
                "inputs": {
                    "playbook": {
                        "type": "string",
                        "required": True,
                        "description": "Path to the playbook YAML file",
                    },
                    "inventory": {
                        "type": "string",
                        "required": False,
                        "description": "Inventory file or host list",
                    },
                    "limit": {
                        "type": "string",
                        "required": False,
                        "description": "Limit execution to matching hosts/groups",
                    },
                    "tags": {
                        "type": "string",
                        "required": False,
                        "description": "Comma-separated tags to run",
                    },
                    "check": {
                        "type": "boolean",
                        "required": False,
                        "default": False,
                        "description": "Run in check (dry-run) mode",
                    },
                },
                "outputs": {
                    "stdout": {"type": "string", "description": "Standard output"},
                    "stderr": {"type": "string", "description": "Standard error"},
                    "returnCode": {"type": "integer", "description": "Process exit code"},
                },
            },
        ]
