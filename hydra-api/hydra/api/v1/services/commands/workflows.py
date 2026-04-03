"""Workflow service for managing command chain definitions and executions."""

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from hydra.api.v1.core.exceptions import (
    ValidationError,
    WorkflowCycleError,
    WorkflowExecutionNotFoundError,
    WorkflowNotCancellableError,
    WorkflowNotFoundError,
)
from hydra.api.v1.core.tasks import safe_create_task
from hydra.api.v1.models.commands import CommandSource, CommandStatus, CreateCommandRequest
from hydra.api.v1.models.commands.schemas import CommandTarget
from hydra.api.v1.models.commands.workflows import (
    CreateWorkflowRequest,
    ExecuteWorkflowRequest,
    StepFailurePolicy,
    UpdateWorkflowRequest,
    WorkflowExecutionStatus,
)
from hydra.api.v1.services.commands.service import CommandsService
from hydra.api.v1.services.notifications import emit_notification
from hydra.api.v1.models.notifications import NotificationType, NotificationSource
from hydra.api.v1.services.query import log_audit
from hydra.api.v1.models.query import AuditAction
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class WorkflowService:
    """Service for managing workflow definitions and executions."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb
        self.workflows = mongodb.workflows
        self.workflow_executions = mongodb.workflow_executions
        self.commands_service = CommandsService(mongodb)

    def _validate_unsupported_step_features(self, steps: list[Any]) -> None:
        """Reject workflow features that are still explicitly out of scope."""
        for step in steps:
            condition = step.condition if hasattr(step, "condition") else step.get("condition")
            step_id = step.step_id if hasattr(step, "step_id") else step.get("stepId")
            if condition is not None:
                raise ValidationError(
                    (
                        f"Workflow step '{step_id}' uses unsupported 'condition' logic. "
                        "Conditional workflow execution is not implemented in this phase."
                    )
                )

    # ── Workflow CRUD ────────────────────────────────────────────────────

    async def create_workflow(
        self,
        request: CreateWorkflowRequest,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new workflow definition."""
        chain_id = f"chain_{uuid4().hex[:12]}"
        now = datetime.now(UTC)

        # Validate no duplicate step IDs
        step_ids = [s.step_id for s in request.steps]
        if len(step_ids) != len(set(step_ids)):
            raise WorkflowCycleError("Duplicate step IDs found")

        self._validate_unsupported_step_features(request.steps)

        # Validate step dependency graph (no cycles, all refs valid)
        self._validate_step_graph(request.steps)

        # Validate all registryIds exist in the catalog
        for step in request.steps:
            definition = await self.mongodb.command_definitions.find_one(
                {"registryId": step.registry_id}
            )
            if not definition:
                raise WorkflowCycleError(
                    f"Step '{step.step_id}' references unknown registry ID: {step.registry_id}"
                )

        workflow_doc = {
            "chainId": chain_id,
            "name": request.name,
            "description": request.description,
            "steps": [
                {
                    "stepId": s.step_id,
                    "registryId": s.registry_id,
                    "target": {
                        "nodeId": s.target.node_id,
                        "serviceId": s.target.service_id,
                    },
                    "parameters": s.parameters,
                    "dependsOn": s.depends_on,
                    "onFailure": s.on_failure.value,
                    "maxRetries": s.max_retries,
                    "condition": s.condition,
                }
                for s in request.steps
            ],
            "inputs": (
                {
                    k: {
                        "type": v.type,
                        "required": v.required,
                        "default": v.default,
                        "description": v.description,
                    }
                    for k, v in request.inputs.items()
                }
                if request.inputs
                else None
            ),
            "createdBy": user_id,
            "createdAt": now,
            "updatedAt": None,
        }

        await self.workflows.insert_one(workflow_doc)

        logger.info(
            "workflow_created",
            chain_id=chain_id,
            name=request.name,
            step_count=len(request.steps),
        )

        return workflow_doc

    async def get_workflow(self, chain_id: str) -> dict[str, Any]:
        """Get a workflow by chain ID."""
        workflow = await self.workflows.find_one({"chainId": chain_id})
        if not workflow:
            raise WorkflowNotFoundError(chain_id)
        return workflow

    async def list_workflows(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """List workflows with pagination."""
        total = await self.workflows.count_documents({})

        cursor = self.workflows.find({})
        cursor = cursor.sort("createdAt", -1)
        cursor = cursor.skip(offset).limit(limit)

        workflows = await cursor.to_list(length=limit)
        return workflows, total

    async def update_workflow(
        self,
        chain_id: str,
        request: UpdateWorkflowRequest,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a workflow definition."""
        workflow = await self.get_workflow(chain_id)
        now = datetime.now(UTC)

        update_set: dict[str, Any] = {"updatedAt": now}

        if request.name is not None:
            update_set["name"] = request.name
        if request.description is not None:
            update_set["description"] = request.description
        if request.steps is not None:
            self._validate_unsupported_step_features(request.steps)
            self._validate_step_graph(request.steps)
            update_set["steps"] = [
                {
                    "stepId": s.step_id,
                    "registryId": s.registry_id,
                    "target": {
                        "nodeId": s.target.node_id,
                        "serviceId": s.target.service_id,
                    },
                    "parameters": s.parameters,
                    "dependsOn": s.depends_on,
                    "onFailure": s.on_failure.value,
                    "maxRetries": s.max_retries,
                    "condition": s.condition,
                }
                for s in request.steps
            ]
        if request.inputs is not None:
            update_set["inputs"] = {
                k: {
                    "type": v.type,
                    "required": v.required,
                    "default": v.default,
                    "description": v.description,
                }
                for k, v in request.inputs.items()
            }

        await self.workflows.update_one(
            {"chainId": chain_id},
            {"$set": update_set},
        )

        return await self.get_workflow(chain_id)

    async def delete_workflow(self, chain_id: str) -> None:
        """Delete a workflow definition."""
        workflow = await self.get_workflow(chain_id)

        # Check for active executions
        active_count = await self.workflow_executions.count_documents({
            "chainId": chain_id,
            "status": {"$in": [
                WorkflowExecutionStatus.PENDING.value,
                WorkflowExecutionStatus.RUNNING.value,
            ]},
        })
        if active_count > 0:
            raise WorkflowCycleError(
                f"Cannot delete workflow '{chain_id}' with {active_count} active execution(s)"
            )

        await self.workflows.delete_one({"chainId": chain_id})
        logger.info("workflow_deleted", chain_id=chain_id)

    # ── Workflow Execution ───────────────────────────────────────────────

    async def execute_workflow(
        self,
        chain_id: str,
        request: ExecuteWorkflowRequest | None = None,
        user_id: str | None = None,
        user_role: str | None = None,
        user_permissions: list[str] | None = None,
        source: CommandSource = CommandSource.API,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a workflow, returning immediately with an execution ID."""
        workflow = await self.get_workflow(chain_id)
        self._validate_unsupported_step_features(workflow["steps"])

        execution_id = f"exec_{uuid4().hex[:12]}"
        now = datetime.now(UTC)

        steps_execution = [
            {
                "stepId": step["stepId"],
                "registryId": step["registryId"],
                "commandId": None,
                "status": "pending",
                "retryCount": 0,
                "startedAt": None,
                "completedAt": None,
                "result": None,
                "error": None,
            }
            for step in workflow["steps"]
        ]

        execution_doc = {
            "executionId": execution_id,
            "chainId": chain_id,
            "name": workflow["name"],
            "status": WorkflowExecutionStatus.RUNNING.value,
            "steps": steps_execution,
            "inputs": request.inputs if request else None,
            "startedBy": user_id,
            "startedAt": now,
            "completedAt": None,
        }

        await self.workflow_executions.insert_one(execution_doc)

        logger.info(
            "workflow_execution_started",
            execution_id=execution_id,
            chain_id=chain_id,
            step_count=len(workflow["steps"]),
        )

        # Spawn background orchestration task
        safe_create_task(
            self._run_workflow_execution(
                execution_id,
                workflow,
                user_id,
                user_role,
                user_permissions,
                source,
                client_id,
                request,
            )
        )

        return execution_doc

    async def get_execution(self, execution_id: str) -> dict[str, Any]:
        """Get a workflow execution by ID."""
        execution = await self.workflow_executions.find_one(
            {"executionId": execution_id}
        )
        if not execution:
            raise WorkflowExecutionNotFoundError(execution_id)
        return execution

    async def list_executions(
        self,
        chain_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List workflow executions with optional chain ID filter."""
        query: dict[str, Any] = {}
        if chain_id:
            query["chainId"] = chain_id

        total = await self.workflow_executions.count_documents(query)

        cursor = self.workflow_executions.find(query)
        cursor = cursor.sort("startedAt", -1)
        cursor = cursor.skip(offset).limit(limit)

        executions = await cursor.to_list(length=limit)
        return executions, total

    async def cancel_execution(
        self, execution_id: str, user_id: str | None = None
    ) -> dict[str, Any]:
        """Cancel a running workflow execution."""
        execution = await self.get_execution(execution_id)

        if execution["status"] not in [
            WorkflowExecutionStatus.PENDING.value,
            WorkflowExecutionStatus.RUNNING.value,
        ]:
            raise WorkflowNotCancellableError(execution_id, execution["status"])

        now = datetime.now(UTC)

        # Cancel all pending steps
        steps = execution["steps"]
        for step in steps:
            if step["status"] in ["pending", "executing"]:
                step["status"] = "cancelled"
                step["completedAt"] = now
                # Cancel the underlying command if it exists
                if step["commandId"]:
                    try:
                        await self.commands_service.cancel_command(
                            step["commandId"], cancelled_by=user_id
                        )
                    except Exception:
                        pass  # Best-effort cancel

        await self.workflow_executions.update_one(
            {"executionId": execution_id},
            {
                "$set": {
                    "status": WorkflowExecutionStatus.CANCELLED.value,
                    "steps": steps,
                    "completedAt": now,
                }
            },
        )

        logger.info("workflow_execution_cancelled", execution_id=execution_id)

        safe_create_task(
            emit_notification(
                notification_type=NotificationType.COMMAND_EXECUTION_FAILED,
                source=NotificationSource(
                    component="hydra-api", service="workflows"
                ),
                title="Workflow cancelled",
                message=f"Workflow execution '{execution_id}' was cancelled",
                details={
                    "executionId": execution_id,
                    "cancelledBy": user_id,
                },
            )
        )

        return await self.get_execution(execution_id)

    # ── Internal Orchestration ───────────────────────────────────────────

    async def _run_workflow_execution(
        self,
        execution_id: str,
        workflow: dict[str, Any],
        user_id: str | None,
        user_role: str | None,
        user_permissions: list[str] | None,
        source: CommandSource,
        client_id: str | None,
        request: ExecuteWorkflowRequest | None,
    ) -> None:
        """Orchestrate workflow step execution in topological order."""
        chain_id = workflow["chainId"]
        steps = workflow["steps"]
        execution_order = self._topological_sort(steps)
        step_index_map = {sid: i for i, sid in enumerate(execution_order)}
        completed_steps: dict[str, bool] = {}  # step_id -> success
        has_failure = False

        for step_id in execution_order:
            # Re-check execution status (may have been cancelled)
            execution = await self.workflow_executions.find_one(
                {"executionId": execution_id}
            )
            if not execution or execution["status"] == WorkflowExecutionStatus.CANCELLED.value:
                return

            step = next(s for s in steps if s["stepId"] == step_id)

            # Check if dependencies are met
            deps_ok = all(
                completed_steps.get(dep, False) for dep in step.get("dependsOn", [])
            )

            on_failure = step.get("onFailure", "abort")

            if not deps_ok and on_failure == "abort":
                # Skip this step and mark as failed
                await self._update_step_status(
                    execution_id, step_id, "failed",
                    error="Dependency step failed",
                )
                completed_steps[step_id] = False
                has_failure = True
                continue
            elif not deps_ok and on_failure == "continue":
                await self._update_step_status(
                    execution_id, step_id, "skipped",
                    error="Dependency step failed (continue policy)",
                )
                completed_steps[step_id] = False
                continue

            # Execute the step
            outcome = await self._execute_step(
                execution_id,
                chain_id,
                step,
                step_index_map[step_id],
                user_id,
                user_role,
                user_permissions,
                source,
                client_id,
            )
            if outcome == "cancelled":
                return

            success = outcome == "completed"
            completed_steps[step_id] = success

            if not success:
                has_failure = True
                max_retries = step.get("maxRetries", 0)
                retry_count = 0

                # Retry logic
                if on_failure == "retry" and max_retries > 0:
                    while retry_count < max_retries and not success:
                        retry_count += 1
                        logger.info(
                            "workflow_step_retry",
                            execution_id=execution_id,
                            step_id=step_id,
                            attempt=retry_count,
                        )
                        await self._update_step_retry(
                            execution_id, step_id, retry_count
                        )
                        outcome = await self._execute_step(
                            execution_id,
                            chain_id,
                            step,
                            step_index_map[step_id],
                            user_id,
                            user_role,
                            user_permissions,
                            source,
                            client_id,
                        )
                        if outcome == "cancelled":
                            return
                        success = outcome == "completed"
                        completed_steps[step_id] = success

                if not success and on_failure == "abort":
                    # Mark remaining steps as cancelled and fail the workflow
                    remaining = [
                        s["stepId"]
                        for s in steps
                        if s["stepId"] not in completed_steps
                    ]
                    for rem_id in remaining:
                        await self._update_step_status(
                            execution_id, rem_id, "cancelled"
                        )

                    await self._finish_execution(
                        execution_id,
                        WorkflowExecutionStatus.FAILED,
                    )
                    return

        # Determine final status
        if has_failure:
            final_status = WorkflowExecutionStatus.PARTIALLY_COMPLETED
        else:
            final_status = WorkflowExecutionStatus.COMPLETED

        execution = await self.workflow_executions.find_one(
            {"executionId": execution_id}
        )
        if execution and execution["status"] == WorkflowExecutionStatus.CANCELLED.value:
            return

        await self._finish_execution(execution_id, final_status)

    async def _execute_step(
        self,
        execution_id: str,
        chain_id: str,
        step: dict[str, Any],
        step_index: int,
        user_id: str | None,
        user_role: str | None,
        user_permissions: list[str] | None,
        source: CommandSource,
        client_id: str | None,
    ) -> str:
        """Execute a single workflow step by creating a command."""
        step_id = step["stepId"]
        registry_id = step["registryId"]
        target = step["target"]
        parameters = step.get("parameters")

        await self._update_step_status(execution_id, step_id, "executing")

        try:
            cmd_request = CreateCommandRequest(
                registry_id=registry_id,
                target=CommandTarget(
                    node_id=target["nodeId"],
                    service_id=target.get("serviceId"),
                ),
                parameters=parameters,
            )

            # Build chain reference linking this command to the workflow
            chain_ref = {
                "chainId": chain_id,
                "sequence": step_index,
                "dependsOn": step.get("dependsOn", []),
            }

            command = await self.commands_service.create_command(
                cmd_request,
                user_id=user_id,
                user_role=user_role,
                user_permissions=user_permissions,
                source=source,
                client_id=client_id,
                chain=chain_ref,
            )

            command_id = command["commandId"]

            # Record the command ID
            await self._update_step_command_id(execution_id, step_id, command_id)

            # Wait for command completion (poll every 2 seconds, max 10 min)
            max_wait = 600  # 10 minutes
            waited = 0
            while waited < max_wait:
                await asyncio.sleep(2)
                waited += 2

                execution = await self.workflow_executions.find_one(
                    {"executionId": execution_id}
                )
                if execution and execution["status"] == WorkflowExecutionStatus.CANCELLED.value:
                    return "cancelled"

                cmd = await self.commands_service.get_command(command_id)
                status = cmd.get("status")

                if status in [
                    CommandStatus.COMPLETED.value,
                    CommandStatus.FAILED.value,
                    CommandStatus.TIMEOUT.value,
                    CommandStatus.CANCELLED.value,
                ]:
                    success = status == CommandStatus.COMPLETED.value
                    result = cmd.get("result")
                    error = cmd.get("error", {}).get("message") if cmd.get("error") else None

                    final_status = (
                        "cancelled"
                        if status == CommandStatus.CANCELLED.value
                        else "completed" if success else "failed"
                    )
                    await self._update_step_status(
                        execution_id, step_id, final_status,
                        result=result, error=error,
                    )
                    if status == CommandStatus.CANCELLED.value:
                        execution = await self.workflow_executions.find_one(
                            {"executionId": execution_id}
                        )
                        if execution and execution["status"] != WorkflowExecutionStatus.CANCELLED.value:
                            await self._finish_execution(
                                execution_id,
                                WorkflowExecutionStatus.CANCELLED,
                            )
                        return "cancelled"
                    return "completed" if success else "failed"

            # Timed out waiting
            await self._update_step_status(
                execution_id, step_id, "failed",
                error="Timed out waiting for command completion",
            )
            return "failed"

        except Exception as e:
            logger.error(
                "workflow_step_failed",
                execution_id=execution_id,
                step_id=step_id,
                error=str(e),
            )
            await self._update_step_status(
                execution_id, step_id, "failed",
                error=str(e),
            )
            return "failed"

    async def _update_step_status(
        self,
        execution_id: str,
        step_id: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        """Update the status of a specific step in an execution."""
        now = datetime.now(UTC)

        update: dict[str, Any] = {
            "steps.$[elem].status": status,
        }

        if status == "executing":
            update["steps.$[elem].startedAt"] = now
        elif status in ["completed", "failed", "cancelled", "skipped"]:
            update["steps.$[elem].completedAt"] = now

        if result is not None:
            update["steps.$[elem].result"] = result
        if error is not None:
            update["steps.$[elem].error"] = error

        await self.workflow_executions.update_one(
            {"executionId": execution_id},
            {"$set": update},
            array_filters=[{"elem.stepId": step_id}],
        )

    async def _update_step_command_id(
        self, execution_id: str, step_id: str, command_id: str
    ) -> None:
        """Set the command ID for a step."""
        await self.workflow_executions.update_one(
            {"executionId": execution_id},
            {"$set": {"steps.$[elem].commandId": command_id}},
            array_filters=[{"elem.stepId": step_id}],
        )

    async def _update_step_retry(
        self, execution_id: str, step_id: str, retry_count: int
    ) -> None:
        """Update the retry count for a step."""
        await self.workflow_executions.update_one(
            {"executionId": execution_id},
            {"$set": {"steps.$[elem].retryCount": retry_count}},
            array_filters=[{"elem.stepId": step_id}],
        )

    async def _finish_execution(
        self,
        execution_id: str,
        status: WorkflowExecutionStatus,
    ) -> None:
        """Mark a workflow execution as finished."""
        now = datetime.now(UTC)

        current = await self.workflow_executions.find_one({"executionId": execution_id})
        if not current:
            return
        if (
            current["status"] == WorkflowExecutionStatus.CANCELLED.value
            and status != WorkflowExecutionStatus.CANCELLED
        ):
            logger.info(
                "workflow_finish_skipped",
                execution_id=execution_id,
                current_status=current["status"],
                attempted_status=status.value,
            )
            return

        await self.workflow_executions.update_one(
            {"executionId": execution_id},
            {
                "$set": {
                    "status": status.value,
                    "completedAt": now,
                }
            },
        )

        logger.info(
            "workflow_execution_finished",
            execution_id=execution_id,
            status=status.value,
        )

        # Emit notification
        notification_type = (
            NotificationType.COMMAND_EXECUTION_SUCCEEDED
            if status == WorkflowExecutionStatus.COMPLETED
            else NotificationType.COMMAND_EXECUTION_FAILED
        )
        safe_create_task(
            emit_notification(
                notification_type=notification_type,
                source=NotificationSource(
                    component="hydra-api", service="workflows"
                ),
                title=f"Workflow {status.value}",
                message=f"Workflow execution '{execution_id}' {status.value}",
                details={
                    "executionId": execution_id,
                    "status": status.value,
                },
            )
        )

    # ── Validation Helpers ───────────────────────────────────────────────

    def _validate_step_graph(self, steps: list) -> None:
        """Validate that the step dependency graph is a DAG (no cycles)."""
        step_ids = {s.step_id for s in steps}

        # Check all dependsOn references are valid
        for step in steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise WorkflowCycleError(
                        f"Step '{step.step_id}' depends on unknown step '{dep}'"
                    )

        # Topological sort to detect cycles
        visited: set[str] = set()
        in_stack: set[str] = set()
        step_map = {s.step_id: s for s in steps}

        def dfs(node_id: str) -> None:
            if node_id in in_stack:
                raise WorkflowCycleError(
                    f"Cycle detected involving step '{node_id}'"
                )
            if node_id in visited:
                return
            in_stack.add(node_id)
            for dep in step_map[node_id].depends_on:
                dfs(dep)
            in_stack.remove(node_id)
            visited.add(node_id)

        for step in steps:
            dfs(step.step_id)

    def _topological_sort(self, steps: list[dict[str, Any]]) -> list[str]:
        """Return step IDs in topological execution order."""
        # Build adjacency list
        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {}

        for step in steps:
            sid = step["stepId"]
            in_degree.setdefault(sid, 0)
            for dep in step.get("dependsOn", []):
                graph[dep].append(sid)
                in_degree[sid] = in_degree.get(sid, 0) + 1

        # Kahn's algorithm
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order
