"""Tests for the Ansible plugin handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.api.v1.services.plugins.ansible import AnsibleHandler

# ── Helpers ──────────────────────────────────────────────────────────


def _make_process(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    """Create a mock asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def _handler(config: dict | None = None) -> AnsibleHandler:
    """Instantiate AnsibleHandler with default or supplied config."""
    return AnsibleHandler(config=config or {})


# ── MANIFEST ─────────────────────────────────────────────────────────


class TestManifest:
    """Verify MANIFEST class constant."""

    def test_plugin_id(self) -> None:
        assert AnsibleHandler.MANIFEST["pluginId"] == "plg::ansible"

    def test_classification_and_category(self) -> None:
        assert AnsibleHandler.MANIFEST["classification"] == "core"
        assert AnsibleHandler.MANIFEST["category"] == "development"

    def test_touchpoints(self) -> None:
        tp = AnsibleHandler.MANIFEST["touchpoints"]
        assert tp["commandProvider"] is True
        assert tp["executionHandler"] is True
        assert tp["workflowBlockProvider"] is True
        assert tp["profileEnrichment"] is False
        assert tp["discoveryProvider"] is False

    def test_contributed_commands(self) -> None:
        expected = {
            "reg::ansible::run-playbook",
            "reg::ansible::run-module",
            "reg::ansible::list-inventory",
            "reg::ansible::galaxy-install",
        }
        assert set(AnsibleHandler.MANIFEST["contributedCommands"]) == expected

    def test_supported_tiers(self) -> None:
        assert AnsibleHandler.MANIFEST["supportedTiers"] == ["normal", "max"]


# ── COMMAND_DEFINITIONS ──────────────────────────────────────────────


class TestCommandDefinitions:
    """Verify COMMAND_DEFINITIONS class constant."""

    def test_count(self) -> None:
        assert len(AnsibleHandler.COMMAND_DEFINITIONS) == 4

    def test_registry_ids(self) -> None:
        ids = {c["registryId"] for c in AnsibleHandler.COMMAND_DEFINITIONS}
        assert ids == {
            "reg::ansible::run-playbook",
            "reg::ansible::run-module",
            "reg::ansible::list-inventory",
            "reg::ansible::galaxy-install",
        }

    def test_run_playbook_rbac(self) -> None:
        cmd = next(
            c for c in AnsibleHandler.COMMAND_DEFINITIONS
            if c["registryId"] == "reg::ansible::run-playbook"
        )
        assert cmd["rbac"]["minimumRole"] == "admin"
        assert cmd["rbac"]["dangerLevel"] == "high"
        assert cmd["rbac"]["requiresConfirmation"] is True

    def test_list_inventory_rbac(self) -> None:
        cmd = next(
            c for c in AnsibleHandler.COMMAND_DEFINITIONS
            if c["registryId"] == "reg::ansible::list-inventory"
        )
        assert cmd["rbac"]["minimumRole"] == "operator"
        assert cmd["rbac"]["dangerLevel"] == "safe"

    def test_galaxy_install_rbac(self) -> None:
        cmd = next(
            c for c in AnsibleHandler.COMMAND_DEFINITIONS
            if c["registryId"] == "reg::ansible::galaxy-install"
        )
        assert cmd["rbac"]["minimumRole"] == "admin"
        assert cmd["rbac"]["dangerLevel"] == "medium"


# ── connect() ────────────────────────────────────────────────────────


class TestConnect:
    """Tests for the connect() lifecycle method."""

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        handler = _handler()
        proc = _make_process(returncode=0, stdout=b"ansible [core 2.16.0]")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            result = await handler.connect()

        assert result is True

    @pytest.mark.asyncio
    async def test_connect_failure_nonzero_exit(self) -> None:
        handler = _handler()
        proc = _make_process(returncode=1, stderr=b"command not found")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            result = await handler.connect()

        assert result is False

    @pytest.mark.asyncio
    async def test_connect_failure_file_not_found(self) -> None:
        handler = _handler()

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("ansible"),
        ):
            result = await handler.connect()

        assert result is False


# ── health_check() ───────────────────────────────────────────────────


class TestHealthCheck:
    """Tests for the health_check() method."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self) -> None:
        handler = _handler()
        proc = _make_process(
            returncode=0,
            stdout=b"ansible [core 2.16.0]\n  config file = /etc/ansible/ansible.cfg\n",
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            result = await handler.health_check()

        assert result["status"] == "healthy"
        assert result["consecutiveFailures"] == 0
        assert result["lastError"] is None
        assert "2.16.0" in result["version"]

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self) -> None:
        handler = _handler()
        proc = _make_process(returncode=127, stderr=b"ansible: command not found")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            result = await handler.health_check()

        assert result["status"] == "unhealthy"
        assert result["consecutiveFailures"] == 1
        assert result["lastError"] is not None

    @pytest.mark.asyncio
    async def test_health_check_os_error(self) -> None:
        handler = _handler()

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            side_effect=OSError("permission denied"),
        ):
            result = await handler.health_check()

        assert result["status"] == "unhealthy"
        assert "permission denied" in (result["lastError"] or "")


# ── execute_command() — run-playbook ─────────────────────────────────


class TestExecRunPlaybook:
    """Tests for the run-playbook command execution."""

    @pytest.mark.asyncio
    async def test_run_playbook_basic(self) -> None:
        handler = _handler({"inventoryPath": "/my/inventory"})
        proc = _make_process(
            returncode=0,
            stdout=b"PLAY [all] ***\nok: [host1]\n",
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            result = await handler.execute_command(
                "reg::ansible::run-playbook",
                {"nodeId": "node-01"},
                {"playbook": "/opt/site.yml"},
            )

        assert result["success"] is True
        assert "PLAY [all]" in result["output"]

        # Verify the assembled command
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "ansible-playbook"
        assert "/opt/site.yml" in call_args
        assert "-i" in call_args
        assert "/my/inventory" in call_args

    @pytest.mark.asyncio
    async def test_run_playbook_with_all_options(self) -> None:
        handler = _handler()
        proc = _make_process(returncode=0, stdout=b"ok")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            result = await handler.execute_command(
                "reg::ansible::run-playbook",
                {"nodeId": "node-01"},
                {
                    "playbook": "/opt/deploy.yml",
                    "inventory": "/tmp/hosts",
                    "limit": "webservers",
                    "tags": "deploy,restart",
                    "check": True,
                },
            )

        assert result["success"] is True
        call_args = mock_exec.call_args[0]
        assert "--limit" in call_args
        assert "webservers" in call_args
        assert "--tags" in call_args
        assert "deploy,restart" in call_args
        assert "--check" in call_args
        assert "/tmp/hosts" in call_args

    @pytest.mark.asyncio
    async def test_run_playbook_missing_param(self) -> None:
        handler = _handler()

        result = await handler.execute_command(
            "reg::ansible::run-playbook",
            {"nodeId": "node-01"},
            {},
        )

        assert result["success"] is False
        assert "playbook" in result["output"].lower()


# ── execute_command() — list-inventory ───────────────────────────────


class TestExecListInventory:
    """Tests for the list-inventory command execution."""

    @pytest.mark.asyncio
    async def test_list_inventory(self) -> None:
        handler = _handler()
        inventory_json = b'{"all": {"hosts": ["host1", "host2"]}}'
        proc = _make_process(returncode=0, stdout=inventory_json)

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            result = await handler.execute_command(
                "reg::ansible::list-inventory",
                {"nodeId": "node-01"},
                {},
            )

        assert result["success"] is True
        assert "host1" in result["output"]
        call_args = mock_exec.call_args[0]
        assert "ansible-inventory" in call_args
        assert "--list" in call_args


# ── execute_command() — run-module ───────────────────────────────────


class TestExecRunModule:
    """Tests for the run-module command execution."""

    @pytest.mark.asyncio
    async def test_run_module(self) -> None:
        handler = _handler()
        proc = _make_process(returncode=0, stdout=b"host1 | SUCCESS => {}")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            result = await handler.execute_command(
                "reg::ansible::run-module",
                {"nodeId": "node-01"},
                {"pattern": "all", "module": "ping"},
            )

        assert result["success"] is True
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "ansible"
        assert "all" in call_args
        assert "-m" in call_args
        assert "ping" in call_args

    @pytest.mark.asyncio
    async def test_run_module_with_args(self) -> None:
        handler = _handler()
        proc = _make_process(returncode=0, stdout=b"ok")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            result = await handler.execute_command(
                "reg::ansible::run-module",
                {"nodeId": "node-01"},
                {"pattern": "webservers", "module": "shell", "args": "uptime"},
            )

        assert result["success"] is True
        call_args = mock_exec.call_args[0]
        assert "-a" in call_args
        assert "uptime" in call_args

    @pytest.mark.asyncio
    async def test_run_module_missing_params(self) -> None:
        handler = _handler()

        result = await handler.execute_command(
            "reg::ansible::run-module",
            {"nodeId": "node-01"},
            {"pattern": "all"},
        )

        assert result["success"] is False
        assert "module" in result["output"].lower()


# ── execute_command() — galaxy-install ───────────────────────────────


class TestExecGalaxyInstall:
    """Tests for the galaxy-install command execution."""

    @pytest.mark.asyncio
    async def test_galaxy_install_role(self) -> None:
        handler = _handler()
        proc = _make_process(returncode=0, stdout=b"- downloading role 'docker'")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            result = await handler.execute_command(
                "reg::ansible::galaxy-install",
                {"nodeId": "node-01"},
                {"name": "geerlingguy.docker", "type": "role"},
            )

        assert result["success"] is True
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "ansible-galaxy"
        assert "role" in call_args
        assert "install" in call_args
        assert "geerlingguy.docker" in call_args

    @pytest.mark.asyncio
    async def test_galaxy_install_collection(self) -> None:
        handler = _handler()
        proc = _make_process(returncode=0, stdout=b"Installing 'community.general:9.0.0'")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            result = await handler.execute_command(
                "reg::ansible::galaxy-install",
                {"nodeId": "node-01"},
                {"name": "community.general", "type": "collection"},
            )

        assert result["success"] is True
        call_args = mock_exec.call_args[0]
        assert "collection" in call_args

    @pytest.mark.asyncio
    async def test_galaxy_install_invalid_type(self) -> None:
        handler = _handler()

        result = await handler.execute_command(
            "reg::ansible::galaxy-install",
            {"nodeId": "node-01"},
            {"name": "something", "type": "invalid"},
        )

        assert result["success"] is False
        assert "invalid" in result["output"].lower()


# ── execute_command() — unknown command ──────────────────────────────


class TestExecUnknown:
    """Test unknown command_id returns failure."""

    @pytest.mark.asyncio
    async def test_unknown_command(self) -> None:
        handler = _handler()

        result = await handler.execute_command(
            "reg::ansible::nonexistent",
            {"nodeId": "node-01"},
            {},
        )

        assert result["success"] is False
        assert "Unknown" in result["output"]


# ── get_workflow_blocks() ────────────────────────────────────────────


class TestWorkflowBlocks:
    """Tests for get_workflow_blocks()."""

    def test_returns_ansible_playbook_block(self) -> None:
        handler = _handler()
        blocks = handler.get_workflow_blocks()

        assert len(blocks) == 1
        block = blocks[0]
        assert block["blockId"] == "ansible-playbook"
        assert block["pluginId"] == "plg::ansible"

    def test_block_inputs(self) -> None:
        handler = _handler()
        block = handler.get_workflow_blocks()[0]
        inputs = block["inputs"]

        assert "playbook" in inputs
        assert inputs["playbook"]["required"] is True
        assert "inventory" in inputs
        assert "limit" in inputs
        assert "tags" in inputs
        assert "check" in inputs
        assert inputs["check"]["required"] is False

    def test_block_outputs(self) -> None:
        handler = _handler()
        block = handler.get_workflow_blocks()[0]
        outputs = block["outputs"]

        assert "stdout" in outputs
        assert "stderr" in outputs
        assert "returnCode" in outputs


# ── Config / environment ─────────────────────────────────────────────


class TestConfigEnv:
    """Test that config options propagate to subprocess env."""

    @pytest.mark.asyncio
    async def test_env_from_config(self) -> None:
        handler = _handler({
            "configPath": "/custom/ansible.cfg",
            "vaultPasswordFile": "/secret/vault_pass",
        })
        proc = _make_process(returncode=0, stdout=b"ok")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            await handler.connect()

        call_kwargs = mock_exec.call_args[1]
        env = call_kwargs.get("env")
        assert env is not None
        assert env["ANSIBLE_CONFIG"] == "/custom/ansible.cfg"
        assert env["ANSIBLE_VAULT_PASSWORD_FILE"] == "/secret/vault_pass"

    @pytest.mark.asyncio
    async def test_no_env_when_config_empty(self) -> None:
        handler = _handler({})
        proc = _make_process(returncode=0, stdout=b"ok")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            await handler.connect()

        call_kwargs = mock_exec.call_args[1]
        assert call_kwargs.get("env") is None
