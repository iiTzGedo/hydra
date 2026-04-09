"""Tests for the Terraform plugin handler."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from hydra.api.v1.services.plugins.terraform import TerraformPlugin


@pytest.fixture
def tf_config() -> dict:
    """Default Terraform plugin configuration."""
    return {
        "workingDir": "/opt/terraform/myproject",
        "backendConfig": {"bucket": "tf-state"},
        "varFiles": ["/opt/terraform/prod.tfvars"],
    }


@pytest.fixture
def tf_plugin(tf_config) -> TerraformPlugin:
    """Instantiate a TerraformPlugin with test config."""
    return TerraformPlugin(config=tf_config)


def _make_mock_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> AsyncMock:
    """Create a mock async subprocess whose communicate() returns the given output."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode()),
    )
    return proc


# ── MANIFEST ────────────────────────────────────────────────────────


class TestManifest:
    """Tests for the static MANIFEST class variable."""

    def test_plugin_id(self) -> None:
        """Manifest declares the correct pluginId."""
        assert TerraformPlugin.MANIFEST["pluginId"] == "plg::terraform"

    def test_name_and_version(self) -> None:
        """Manifest declares name and version."""
        assert TerraformPlugin.MANIFEST["name"] == "Terraform"
        assert TerraformPlugin.MANIFEST["version"] == "1.0.0"

    def test_classification_and_category(self) -> None:
        """Manifest declares core classification and development category."""
        assert TerraformPlugin.MANIFEST["classification"] == "core"
        assert TerraformPlugin.MANIFEST["category"] == "development"

    def test_touchpoints(self) -> None:
        """Manifest declares the correct touchpoints."""
        tp = TerraformPlugin.MANIFEST["touchpoints"]
        assert tp["commandProvider"] is True
        assert tp["executionHandler"] is True
        assert tp["workflowBlockProvider"] is True
        assert tp["profileEnrichment"] is False
        assert tp["discoveryProvider"] is False
        assert tp["topologyProvider"] is False

    def test_supported_tiers(self) -> None:
        """Manifest supports normal and max agent tiers."""
        assert TerraformPlugin.MANIFEST["supportedTiers"] == ["normal", "max"]

    def test_contributed_commands_count(self) -> None:
        """Manifest contributes exactly 5 command registry IDs."""
        assert len(TerraformPlugin.MANIFEST["contributedCommands"]) == 5

    def test_contributed_commands_ids(self) -> None:
        """All 5 expected registry IDs are present."""
        expected = {
            "reg::terraform::plan",
            "reg::terraform::apply",
            "reg::terraform::destroy",
            "reg::terraform::state-list",
            "reg::terraform::output",
        }
        assert set(TerraformPlugin.MANIFEST["contributedCommands"]) == expected


# ── COMMAND_DEFINITIONS ─────────────────────────────────────────────


class TestCommandDefinitions:
    """Tests for the COMMAND_DEFINITIONS class variable."""

    def test_definitions_count(self) -> None:
        """There are exactly 5 command definitions."""
        assert len(TerraformPlugin.COMMAND_DEFINITIONS) == 5

    def test_registry_ids_match_manifest(self) -> None:
        """Every command definition registryId matches the manifest's contributedCommands."""
        manifest_ids = set(TerraformPlugin.MANIFEST["contributedCommands"])
        definition_ids = {d["registryId"] for d in TerraformPlugin.COMMAND_DEFINITIONS}
        assert definition_ids == manifest_ids

    def test_plan_definition_structure(self) -> None:
        """The plan command has correct RBAC and execution settings."""
        plan = next(
            d for d in TerraformPlugin.COMMAND_DEFINITIONS
            if d["registryId"] == "reg::terraform::plan"
        )
        assert plan["rbac"]["minimumRole"] == "admin"
        assert plan["rbac"]["dangerLevel"] == "medium"
        assert plan["rbac"]["requiresConfirmation"] is False
        assert plan["execution"]["handler"] == "terraform_plan"

    def test_apply_requires_confirmation(self) -> None:
        """The apply command requires confirmation and is critical."""
        apply_cmd = next(
            d for d in TerraformPlugin.COMMAND_DEFINITIONS
            if d["registryId"] == "reg::terraform::apply"
        )
        assert apply_cmd["rbac"]["requiresConfirmation"] is True
        assert apply_cmd["rbac"]["dangerLevel"] == "critical"
        assert apply_cmd["rbac"]["minimumRole"] == "admin"

    def test_destroy_requires_confirmation(self) -> None:
        """The destroy command requires confirmation and is critical."""
        destroy_cmd = next(
            d for d in TerraformPlugin.COMMAND_DEFINITIONS
            if d["registryId"] == "reg::terraform::destroy"
        )
        assert destroy_cmd["rbac"]["requiresConfirmation"] is True
        assert destroy_cmd["rbac"]["dangerLevel"] == "critical"

    def test_state_list_is_safe(self) -> None:
        """state-list is safe and accessible to operators."""
        state_list = next(
            d for d in TerraformPlugin.COMMAND_DEFINITIONS
            if d["registryId"] == "reg::terraform::state-list"
        )
        assert state_list["rbac"]["minimumRole"] == "operator"
        assert state_list["rbac"]["dangerLevel"] == "safe"

    def test_output_is_safe(self) -> None:
        """output is safe and accessible to operators."""
        output_cmd = next(
            d for d in TerraformPlugin.COMMAND_DEFINITIONS
            if d["registryId"] == "reg::terraform::output"
        )
        assert output_cmd["rbac"]["minimumRole"] == "operator"
        assert output_cmd["rbac"]["dangerLevel"] == "safe"


# ── connect() ───────────────────────────────────────────────────────


class TestConnect:
    """Tests for the connect() lifecycle method."""

    @pytest.mark.asyncio
    async def test_connect_success(self, tf_plugin: TerraformPlugin) -> None:
        """connect() returns True when terraform version exits 0."""
        proc = _make_mock_process(
            returncode=0,
            stdout=json.dumps({"terraform_version": "1.7.5"}),
        )
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tf_plugin.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_failure(self, tf_plugin: TerraformPlugin) -> None:
        """connect() returns False when terraform is not found."""
        proc = _make_mock_process(returncode=1, stderr="command not found")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tf_plugin.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_file_not_found(self, tf_plugin: TerraformPlugin) -> None:
        """connect() returns False when the terraform binary does not exist."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("terraform"),
        ):
            result = await tf_plugin.connect()
        assert result is False


# ── health_check() ──────────────────────────────────────────────────


class TestHealthCheck:
    """Tests for the health_check() lifecycle method."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, tf_plugin: TerraformPlugin) -> None:
        """health_check() returns healthy when terraform version succeeds."""
        version_json = json.dumps({
            "terraform_version": "1.7.5",
            "platform": "linux_amd64",
        })
        proc = _make_mock_process(returncode=0, stdout=version_json)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tf_plugin.health_check()

        assert result["status"] == "healthy"
        assert result["consecutiveFailures"] == 0
        assert result["lastError"] is None
        assert result["terraformVersion"] == "1.7.5"
        assert result["responseTimeMs"] >= 0

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, tf_plugin: TerraformPlugin) -> None:
        """health_check() returns unhealthy when terraform version fails."""
        proc = _make_mock_process(returncode=1, stderr="terraform not installed")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tf_plugin.health_check()

        assert result["status"] == "unhealthy"
        assert result["consecutiveFailures"] == 1
        assert "terraform not installed" in (result["lastError"] or "")


# ── execute_command() ───────────────────────────────────────────────


class TestExecuteCommand:
    """Tests for command execution via execute_command()."""

    @pytest.mark.asyncio
    async def test_exec_plan(self, tf_plugin: TerraformPlugin) -> None:
        """Plan command invokes terraform plan with correct arguments."""
        plan_output = '{"format_version":"1.0","changes":{}}'
        proc = _make_mock_process(returncode=0, stdout=plan_output)

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            result = await tf_plugin.execute_command(
                "reg::terraform::plan",
                {"nodeId": "node-01"},
                {"workingDir": "/opt/tf/prod", "varFile": "vars.tfvars", "target": "aws_instance.web"},
            )

        assert result["success"] is True
        assert result["exitCode"] == 0
        assert plan_output in result["output"]

        # Verify the subprocess was called with the right arguments
        call_args = mock_exec.call_args
        cmd_parts = call_args[0]
        assert cmd_parts[0] == "terraform"
        assert "-chdir=/opt/tf/prod" in cmd_parts
        assert "plan" in cmd_parts
        assert "-json" in cmd_parts
        assert "-input=false" in cmd_parts
        assert "-var-file=vars.tfvars" in cmd_parts
        assert "-target=aws_instance.web" in cmd_parts

    @pytest.mark.asyncio
    async def test_exec_apply(self, tf_plugin: TerraformPlugin) -> None:
        """Apply command includes -auto-approve."""
        proc = _make_mock_process(returncode=0, stdout="Apply complete!")
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            result = await tf_plugin.execute_command(
                "reg::terraform::apply",
                {"nodeId": "node-01"},
                {"workingDir": "/opt/tf/prod"},
            )

        assert result["success"] is True
        call_args = mock_exec.call_args[0]
        assert "-auto-approve" in call_args
        assert "apply" in call_args

    @pytest.mark.asyncio
    async def test_exec_destroy(self, tf_plugin: TerraformPlugin) -> None:
        """Destroy command includes -auto-approve and optional target."""
        proc = _make_mock_process(returncode=0, stdout="Destroy complete!")
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            result = await tf_plugin.execute_command(
                "reg::terraform::destroy",
                {"nodeId": "node-01"},
                {"target": "aws_instance.web"},
            )

        assert result["success"] is True
        call_args = mock_exec.call_args[0]
        assert "-auto-approve" in call_args
        assert "destroy" in call_args
        assert "-target=aws_instance.web" in call_args

    @pytest.mark.asyncio
    async def test_exec_state_list(self, tf_plugin: TerraformPlugin) -> None:
        """state-list command returns the resource list."""
        state_output = "aws_instance.web\naws_vpc.main\naws_subnet.public"
        proc = _make_mock_process(returncode=0, stdout=state_output)

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            result = await tf_plugin.execute_command(
                "reg::terraform::state-list",
                {"nodeId": "node-01"},
                {"workingDir": "/opt/tf/prod"},
            )

        assert result["success"] is True
        assert "aws_instance.web" in result["output"]
        assert "aws_vpc.main" in result["output"]

        call_args = mock_exec.call_args[0]
        assert "state" in call_args
        assert "list" in call_args
        assert "-chdir=/opt/tf/prod" in call_args

    @pytest.mark.asyncio
    async def test_exec_output(self, tf_plugin: TerraformPlugin) -> None:
        """output command parses JSON results."""
        output_data = {"vpc_id": {"value": "vpc-12345", "type": "string"}}
        proc = _make_mock_process(returncode=0, stdout=json.dumps(output_data))

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            result = await tf_plugin.execute_command(
                "reg::terraform::output",
                {"nodeId": "node-01"},
                {},
            )

        assert result["success"] is True
        assert result["parsed"] == output_data

        call_args = mock_exec.call_args[0]
        assert "output" in call_args
        assert "-json" in call_args

    @pytest.mark.asyncio
    async def test_exec_plan_failure(self, tf_plugin: TerraformPlugin) -> None:
        """Plan command failure is reported correctly."""
        proc = _make_mock_process(
            returncode=1,
            stderr="Error: No configuration files",
        )
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tf_plugin.execute_command(
                "reg::terraform::plan",
                {"nodeId": "node-01"},
                {"workingDir": "/nonexistent"},
            )

        assert result["success"] is False
        assert result["exitCode"] == 1
        assert "No configuration files" in result["stderr"]

    @pytest.mark.asyncio
    async def test_exec_unknown_action(self, tf_plugin: TerraformPlugin) -> None:
        """Unknown action returns a failure result."""
        result = await tf_plugin.execute_command(
            "reg::terraform::foobar",
            {"nodeId": "node-01"},
            {},
        )
        assert result["success"] is False
        assert "Unknown Terraform action" in result["output"]

    @pytest.mark.asyncio
    async def test_working_dir_falls_back_to_config(self, tf_plugin: TerraformPlugin) -> None:
        """When no workingDir in params, config value is used."""
        proc = _make_mock_process(returncode=0, stdout="")
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await tf_plugin.execute_command(
                "reg::terraform::state-list",
                {"nodeId": "node-01"},
                {},
            )

        call_args = mock_exec.call_args[0]
        assert f"-chdir={tf_plugin.config['workingDir']}" in call_args

    @pytest.mark.asyncio
    async def test_apply_uses_config_var_file(self, tf_plugin: TerraformPlugin) -> None:
        """When no varFile in params, first config varFiles entry is used."""
        proc = _make_mock_process(returncode=0, stdout="")
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await tf_plugin.execute_command(
                "reg::terraform::apply",
                {"nodeId": "node-01"},
                {},
            )

        call_args = mock_exec.call_args[0]
        assert "-var-file=/opt/terraform/prod.tfvars" in call_args

    @pytest.mark.asyncio
    async def test_timeout_handling(self, tf_plugin: TerraformPlugin) -> None:
        """Command that times out returns an appropriate error."""
        async def _slow_communicate():
            await asyncio.sleep(10)
            return (b"", b"")

        proc = AsyncMock()
        proc.returncode = None
        proc.communicate = _slow_communicate

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            # Override config timeout to something tiny for the test
            tf_plugin.config["timeoutSeconds"] = 0.01
            result = await tf_plugin.execute_command(
                "reg::terraform::plan",
                {"nodeId": "node-01"},
                {},
            )

        assert result["success"] is False
        assert "timed out" in result["stderr"]


# ── get_workflow_blocks() ───────────────────────────────────────────


class TestWorkflowBlocks:
    """Tests for the get_workflow_blocks() touchpoint."""

    def test_returns_one_block(self, tf_plugin: TerraformPlugin) -> None:
        """get_workflow_blocks() returns exactly one block definition."""
        blocks = tf_plugin.get_workflow_blocks()
        assert len(blocks) == 1

    def test_block_id(self, tf_plugin: TerraformPlugin) -> None:
        """The block has the correct ID."""
        block = tf_plugin.get_workflow_blocks()[0]
        assert block["blockId"] == "terraform-plan-apply"

    def test_block_has_two_steps(self, tf_plugin: TerraformPlugin) -> None:
        """The plan-apply block has exactly 2 steps in order."""
        block = tf_plugin.get_workflow_blocks()[0]
        steps = block["steps"]
        assert len(steps) == 2
        assert steps[0]["commandId"] == "reg::terraform::plan"
        assert steps[1]["commandId"] == "reg::terraform::apply"

    def test_block_abort_on_plan_failure(self, tf_plugin: TerraformPlugin) -> None:
        """Plan step has onFailure=abort so the workflow stops on failure."""
        block = tf_plugin.get_workflow_blocks()[0]
        plan_step = block["steps"][0]
        assert plan_step["onFailure"] == "abort"

    def test_block_plugin_id(self, tf_plugin: TerraformPlugin) -> None:
        """The block references the correct pluginId."""
        block = tf_plugin.get_workflow_blocks()[0]
        assert block["pluginId"] == "plg::terraform"

    def test_block_parameters(self, tf_plugin: TerraformPlugin) -> None:
        """The block declares workingDir and varFile parameters."""
        block = tf_plugin.get_workflow_blocks()[0]
        params = block["parameters"]
        assert "workingDir" in params
        assert params["workingDir"]["required"] is True
        assert "varFile" in params
        assert params["varFile"]["required"] is False
