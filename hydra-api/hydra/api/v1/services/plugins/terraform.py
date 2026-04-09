"""Terraform plugin handler.

Provides infrastructure-as-code management through the Terraform CLI.
All commands execute via ``asyncio.create_subprocess_exec`` since
Terraform is a local CLI tool, not a REST API.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from datetime import UTC, datetime
from typing import Any, ClassVar

import structlog

from hydra.api.v1.services.plugins.base import PluginHandler

logger = structlog.get_logger(__name__)

_NOW = datetime.now(UTC)

# ── Default config values ───────────────────────────────────────────
_DEFAULT_WORKING_DIR = "/opt/terraform"
_DEFAULT_TIMEOUT_SECONDS = 300


class TerraformPlugin(PluginHandler):
    """Terraform CLI plugin handler.

    Config schema::

        workingDir   – Base working directory for Terraform projects (default: /opt/terraform)
        backendConfig – dict of backend configuration key/value pairs
        varFiles     – list of .tfvars file paths to include in plan/apply
    """

    MANIFEST: ClassVar[dict[str, Any]] = {
        "pluginId": "plg::terraform",
        "name": "Terraform",
        "version": "1.0.0",
        "description": "Infrastructure-as-code management via Terraform CLI",
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
            "reg::terraform::plan",
            "reg::terraform::apply",
            "reg::terraform::destroy",
            "reg::terraform::state-list",
            "reg::terraform::output",
        ],
    }

    COMMAND_DEFINITIONS: ClassVar[list[dict[str, Any]]] = [
        {
            "registryId": "reg::terraform::plan",
            "category": "terraform",
            "action": "plan",
            "displayName": "Terraform Plan",
            "description": "Generate a Terraform execution plan",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "workingDir": {
                        "type": "string",
                        "description": "Terraform project directory",
                    },
                    "varFile": {
                        "type": "string",
                        "description": "Path to a .tfvars variable file",
                    },
                    "target": {
                        "type": "string",
                        "description": "Resource address to target",
                    },
                },
            },
            "execution": {
                "handler": "terraform_plan",
                "timeout": 300,
                "deliveryMode": "poll_only",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "admin",
                "requiresConfirmation": False,
                "confirmationMessage": None,
                "dangerLevel": "medium",
                "controlPermission": "commands:execute",
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
        {
            "registryId": "reg::terraform::apply",
            "category": "terraform",
            "action": "apply",
            "displayName": "Terraform Apply",
            "description": "Apply a Terraform execution plan",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "workingDir": {
                        "type": "string",
                        "description": "Terraform project directory",
                    },
                    "varFile": {
                        "type": "string",
                        "description": "Path to a .tfvars variable file",
                    },
                },
            },
            "execution": {
                "handler": "terraform_apply",
                "timeout": 600,
                "deliveryMode": "poll_only",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "admin",
                "requiresConfirmation": True,
                "confirmationMessage": "This will apply Terraform changes to your infrastructure. Review the plan before confirming.",
                "dangerLevel": "critical",
                "controlPermission": "commands:execute",
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
        {
            "registryId": "reg::terraform::destroy",
            "category": "terraform",
            "action": "destroy",
            "displayName": "Terraform Destroy",
            "description": "Destroy Terraform-managed infrastructure",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "workingDir": {
                        "type": "string",
                        "description": "Terraform project directory",
                    },
                    "target": {
                        "type": "string",
                        "description": "Resource address to target for destruction",
                    },
                },
            },
            "execution": {
                "handler": "terraform_destroy",
                "timeout": 600,
                "deliveryMode": "poll_only",
                "retryable": False,
                "maxRetries": 0,
            },
            "rbac": {
                "minimumRole": "admin",
                "requiresConfirmation": True,
                "confirmationMessage": "This will DESTROY Terraform-managed resources. This action cannot be undone.",
                "dangerLevel": "critical",
                "controlPermission": "commands:execute",
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
        {
            "registryId": "reg::terraform::state-list",
            "category": "terraform",
            "action": "state-list",
            "displayName": "Terraform State List",
            "description": "List resources tracked in Terraform state",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "workingDir": {
                        "type": "string",
                        "description": "Terraform project directory",
                    },
                },
            },
            "execution": {
                "handler": "terraform_state_list",
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
                "controlPermission": "commands:execute",
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
        {
            "registryId": "reg::terraform::output",
            "category": "terraform",
            "action": "output",
            "displayName": "Terraform Output",
            "description": "Retrieve Terraform output values",
            "targetSchema": {"required": ["nodeId"]},
            "parametersSchema": {
                "properties": {
                    "workingDir": {
                        "type": "string",
                        "description": "Terraform project directory",
                    },
                },
            },
            "execution": {
                "handler": "terraform_output",
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
                "controlPermission": "commands:execute",
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
    ]

    # ── Helpers ──────────────────────────────────────────────────────

    def _working_dir(self, params: dict[str, Any] | None = None) -> str:
        """Resolve the effective working directory.

        Priority: params.workingDir > config.workingDir > default.
        """
        if params and params.get("workingDir"):
            return str(params["workingDir"])
        return str(self.config.get("workingDir", _DEFAULT_WORKING_DIR))

    async def _run_terraform(
        self,
        args: list[str],
        *,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Execute a Terraform CLI command via subprocess.

        Args:
            args: Command arguments (without the leading ``terraform``).
            timeout: Optional timeout in seconds.

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        effective_timeout = timeout or float(
            self.config.get("timeoutSeconds", _DEFAULT_TIMEOUT_SECONDS)
        )

        cmd = ["terraform", *args]
        logger.info("terraform_exec", cmd=cmd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=effective_timeout,
            )
            return (
                proc.returncode or 0,
                stdout_bytes.decode("utf-8", errors="replace"),
                stderr_bytes.decode("utf-8", errors="replace"),
            )
        except TimeoutError:
            logger.error("terraform_timeout", cmd=cmd, timeout=effective_timeout)
            return (1, "", f"Command timed out after {effective_timeout}s")
        except FileNotFoundError:
            logger.error("terraform_not_found")
            return (1, "", "terraform binary not found on PATH")
        except OSError as exc:
            logger.error("terraform_os_error", error=str(exc))
            return (1, "", f"OS error running terraform: {exc}")

    # ── Lifecycle ────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Verify the Terraform CLI is available by running ``terraform version``."""
        returncode, _stdout, stderr = await self._run_terraform(
            ["version", "-json"],
            timeout=15,
        )
        if returncode != 0:
            logger.warning("terraform_connect_failed", stderr=stderr)
            return False
        return True

    async def health_check(self) -> dict[str, Any]:
        """Run ``terraform version -json`` and return a health status dict."""
        start = time.monotonic()
        returncode, stdout, stderr = await self._run_terraform(
            ["version", "-json"],
            timeout=15,
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        now = datetime.now(UTC)

        if returncode != 0:
            return {
                "status": "unhealthy",
                "lastCheck": now,
                "consecutiveFailures": 1,
                "lastError": stderr.strip() or "terraform version failed",
                "responseTimeMs": round(elapsed_ms, 2),
            }

        # Parse version from JSON output
        version = "unknown"
        try:
            version_data = json.loads(stdout)
            version = version_data.get("terraform_version", "unknown")
        except (json.JSONDecodeError, KeyError):
            pass

        return {
            "status": "healthy",
            "lastCheck": now,
            "consecutiveFailures": 0,
            "lastError": None,
            "responseTimeMs": round(elapsed_ms, 2),
            "terraformVersion": version,
        }

    # ── Command Execution ────────────────────────────────────────────

    async def execute_command(
        self,
        command_id: str,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Terraform CLI command.

        Args:
            command_id: Registry ID (e.g. ``reg::terraform::plan``).
            target: Target dict containing at least ``nodeId``.
            params: Command parameters (workingDir, varFile, target, etc.).

        Returns:
            Result dict with ``success``, ``output``, ``exitCode``, and
            optional ``stderr`` keys.
        """
        action = command_id.rsplit("::", 1)[-1] if "::" in command_id else command_id
        working_dir = self._working_dir(params)

        logger.info(
            "terraform_execute",
            command_id=command_id,
            action=action,
            working_dir=working_dir,
            node_id=target.get("nodeId"),
        )

        if action == "plan":
            return await self._exec_plan(working_dir, params)
        if action == "apply":
            return await self._exec_apply(working_dir, params)
        if action == "destroy":
            return await self._exec_destroy(working_dir, params)
        if action == "state-list":
            return await self._exec_state_list(working_dir)
        if action == "output":
            return await self._exec_output(working_dir)

        return {
            "success": False,
            "output": f"Unknown Terraform action: {action}",
            "exitCode": 1,
        }

    async def _exec_plan(
        self,
        working_dir: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Run ``terraform plan``."""
        args = [f"-chdir={working_dir}", "plan", "-json", "-input=false"]

        var_file = params.get("varFile") or self._first_var_file()
        if var_file:
            args.append(f"-var-file={var_file}")

        target_resource = params.get("target")
        if target_resource:
            args.append(f"-target={target_resource}")

        returncode, stdout, stderr = await self._run_terraform(args)
        return {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "exitCode": returncode,
        }

    async def _exec_apply(
        self,
        working_dir: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Run ``terraform apply -auto-approve``."""
        args = [
            f"-chdir={working_dir}",
            "apply",
            "-json",
            "-input=false",
            "-auto-approve",
        ]

        var_file = params.get("varFile") or self._first_var_file()
        if var_file:
            args.append(f"-var-file={var_file}")

        returncode, stdout, stderr = await self._run_terraform(args)
        return {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "exitCode": returncode,
        }

    async def _exec_destroy(
        self,
        working_dir: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Run ``terraform destroy -auto-approve``."""
        args = [
            f"-chdir={working_dir}",
            "destroy",
            "-json",
            "-input=false",
            "-auto-approve",
        ]

        target_resource = params.get("target")
        if target_resource:
            args.append(f"-target={target_resource}")

        returncode, stdout, stderr = await self._run_terraform(args)
        return {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "exitCode": returncode,
        }

    async def _exec_state_list(self, working_dir: str) -> dict[str, Any]:
        """Run ``terraform state list``."""
        args = [f"-chdir={working_dir}", "state", "list"]

        returncode, stdout, stderr = await self._run_terraform(args)
        return {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "exitCode": returncode,
        }

    async def _exec_output(self, working_dir: str) -> dict[str, Any]:
        """Run ``terraform output -json``."""
        args = [f"-chdir={working_dir}", "output", "-json"]

        returncode, stdout, stderr = await self._run_terraform(args)

        # Attempt to parse JSON output for structured result
        parsed: dict[str, Any] | None = None
        if returncode == 0 and stdout.strip():
            with contextlib.suppress(json.JSONDecodeError):
                parsed = json.loads(stdout)

        result: dict[str, Any] = {
            "success": returncode == 0,
            "output": stdout,
            "stderr": stderr,
            "exitCode": returncode,
        }
        if parsed is not None:
            result["parsed"] = parsed
        return result

    # ── Workflow Blocks ──────────────────────────────────────────────

    def get_workflow_blocks(self) -> list[dict[str, Any]]:
        """Return the ``terraform-plan-apply`` workflow block definition."""
        return [
            {
                "blockId": "terraform-plan-apply",
                "name": "Terraform Plan & Apply",
                "description": (
                    "Run terraform plan then apply in sequence. "
                    "The workflow aborts if the plan step fails."
                ),
                "pluginId": "plg::terraform",
                "steps": [
                    {
                        "stepId": "plan",
                        "commandId": "reg::terraform::plan",
                        "name": "Plan",
                        "description": "Generate execution plan",
                        "onFailure": "abort",
                    },
                    {
                        "stepId": "apply",
                        "commandId": "reg::terraform::apply",
                        "name": "Apply",
                        "description": "Apply the execution plan",
                        "onFailure": "abort",
                    },
                ],
                "parameters": {
                    "workingDir": {
                        "type": "string",
                        "description": "Terraform project directory",
                        "required": True,
                    },
                    "varFile": {
                        "type": "string",
                        "description": "Optional .tfvars file path",
                        "required": False,
                    },
                },
            },
        ]

    # ── Private helpers ──────────────────────────────────────────────

    def _first_var_file(self) -> str | None:
        """Return the first var file from the config, if any."""
        var_files = self.config.get("varFiles")
        if var_files and isinstance(var_files, list) and len(var_files) > 0:
            return str(var_files[0])
        return None
