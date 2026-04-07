"""Workflow service for managing command chain definitions and executions."""

import ast
import asyncio
import contextlib
import re
from collections import defaultdict
from datetime import UTC, datetime
from itertools import groupby
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
    UpdateWorkflowRequest,
    WorkflowExecutionStatus,
)
from hydra.api.v1.models.notifications import NotificationSource, NotificationType
from hydra.api.v1.services.commands.service import CommandsService
from hydra.api.v1.services.notifications import emit_notification
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


# ── Safe Condition Evaluator ────────────────────────────────────────────


# Whitelisted AST node types for condition expressions
_ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Constant,
    ast.Attribute,
    ast.Name,
    # Context nodes attached to Name/Attribute by the parser
    ast.Load,
)


def _validate_condition_ast(node: ast.AST) -> None:
    """Recursively validate that all AST nodes are whitelisted.

    Raises ValidationError for any disallowed node type (function calls,
    imports, subscripts, assignments, lambdas, etc.).
    """
    if not isinstance(node, _ALLOWED_AST_NODES):
        raise ValidationError(
            f"Unsafe expression node type '{type(node).__name__}' in condition. "
            "Only comparisons, boolean operators, literals, and "
            "steps.<stepId>.status / steps.<stepId>.output.<field> are allowed."
        )
    for child in ast.iter_child_nodes(node):
        _validate_condition_ast(child)


def _resolve_attribute_chain(node: ast.AST) -> list[str]:
    """Resolve a dotted attribute chain like ``steps.step1.status`` into
    ``['steps', 'step1', 'status']``.

    Returns an empty list for non-attribute / non-name nodes so the caller
    can decide whether to reject.
    """
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    parts.reverse()
    return parts


def _resolve_value(parts: list[str], context: dict[str, Any]) -> Any:
    """Resolve a dotted path against the step-results context.

    Supported patterns:
    - ``steps.<stepId>.status``   -> str
    - ``steps.<stepId>.output.<field>`` -> Any
    """
    if len(parts) < 3 or parts[0] != "steps":
        raise ValidationError(
            f"Invalid variable reference '{ '.'.join(parts)}'. "
            "Only 'steps.<stepId>.status' and 'steps.<stepId>.output.<field>' are allowed."
        )
    step_id = parts[1]
    step_data = context.get(step_id)
    if step_data is None:
        # Step has not executed yet – treat as None
        return None
    remainder = parts[2:]
    if remainder == ["status"]:
        return step_data.get("status")
    if len(remainder) >= 2 and remainder[0] == "output":
        output = step_data.get("output", {}) or {}
        cur: Any = output
        for key in remainder[1:]:
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                return None
        return cur
    raise ValidationError(
        f"Invalid variable reference '{ '.'.join(parts)}'. "
        "Only 'steps.<stepId>.status' and 'steps.<stepId>.output.<field>' are allowed."
    )


def _safe_ordered_compare(left: Any, right: Any, operator: str) -> bool:
    """Evaluate ordered comparisons and fail closed on runtime type issues."""
    try:
        if operator == "<":
            return bool(left < right)
        if operator == "<=":
            return bool(left <= right)
        if operator == ">":
            return bool(left > right)
        if operator == ">=":
            return bool(left >= right)
    except TypeError:
        return False
    raise ValidationError(f"Unsupported comparison operator: {operator}")


def _eval_node(node: ast.AST, context: dict[str, Any]) -> Any:
    """Evaluate a single AST node against the step-results context."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, context)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        # Bare name – must be part of an attribute chain, but if we get
        # here it's a standalone reference like ``True`` / ``False`` /
        # ``None`` which Python parses as Constant in 3.12+.  For safety,
        # treat unknown bare names as references.
        parts = [node.id]
        return _resolve_value(parts, context)

    if isinstance(node, ast.Attribute):
        parts = _resolve_attribute_chain(node)
        return _resolve_value(parts, context)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, context)

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, context) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v, context) for v in node.values)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            right = _eval_node(comparator, context)
            if isinstance(op, ast.Eq):
                if left != right:
                    return False
            elif isinstance(op, ast.NotEq):
                if left == right:
                    return False
            elif isinstance(op, ast.Lt):
                if not _safe_ordered_compare(left, right, "<"):
                    return False
            elif isinstance(op, ast.LtE):
                if not _safe_ordered_compare(left, right, "<="):
                    return False
            elif isinstance(op, ast.Gt):
                if not _safe_ordered_compare(left, right, ">"):
                    return False
            elif isinstance(op, ast.GtE):
                if not _safe_ordered_compare(left, right, ">="):
                    return False
            else:
                raise ValidationError(f"Unsupported comparison operator: {type(op).__name__}")
            left = right
        return True

    raise ValidationError(f"Unsupported AST node: {type(node).__name__}")


# Regex to find step ID references like ``steps.<stepId>.`` where stepId may
# contain hyphens, dots, or other characters that are invalid in Python identifiers.
_STEP_REF_RE = re.compile(r"steps\.([a-zA-Z0-9_\-]+)\.")


def _normalize_expression(
    expression: str, context: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Rewrite step IDs that contain non-identifier characters so the
    expression is valid Python syntax.

    Returns the rewritten expression and a new context dict keyed by the
    normalized step IDs.
    """
    mapping: dict[str, str] = {}  # original -> normalized

    def _replacer(m: re.Match[str]) -> str:
        original_id = m.group(1)
        if original_id.isidentifier():
            return m.group(0)
        safe_id = original_id.replace("-", "_h_").replace(".", "_d_")
        if not safe_id.isidentifier():
            safe_id = f"_s_{safe_id}"
        mapping[original_id] = safe_id
        return f"steps.{safe_id}."

    normalized_expr = _STEP_REF_RE.sub(_replacer, expression)

    # Build a normalized context
    normalized_ctx: dict[str, Any] = {}
    for key, value in context.items():
        normalized_key = mapping.get(key, key)
        normalized_ctx[normalized_key] = value

    return normalized_expr, normalized_ctx


def evaluate_condition(expression: str, context: dict[str, Any]) -> bool:
    """Parse and safely evaluate a workflow condition expression.

    Args:
        expression: A condition string, e.g.
            ``steps.step1.status == 'completed'`` or
            ``steps.step-1.status == 'completed'``
        context: A dict mapping step IDs to their result dicts,
            each containing at minimum ``{"status": ..., "output": ...}``.

    Returns:
        True if the condition is met, False otherwise.

    Raises:
        ValidationError: If the expression contains disallowed constructs.
    """
    normalized_expr, normalized_ctx = _normalize_expression(expression, context)

    try:
        tree = ast.parse(normalized_expr, mode="eval")
    except SyntaxError as exc:
        raise ValidationError(f"Invalid condition syntax: {exc}") from exc

    _validate_condition_ast(tree)
    result = _eval_node(tree, normalized_ctx)
    return bool(result)


class WorkflowService:
    """Service for managing workflow definitions and executions."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb
        self.workflows = mongodb.workflows
        self.workflow_executions = mongodb.workflow_executions
        self.commands_service = CommandsService(mongodb)

    def _validate_unsupported_step_features(self, steps: list[Any]) -> None:
        """Validate advanced step features (conditions, compensation).

        Conditions are parsed through the safe AST evaluator at definition
        time so that obviously invalid expressions are rejected early.
        """
        for step in steps:
            condition = step.condition if hasattr(step, "condition") else step.get("condition")
            if condition is not None:
                # Validate the expression is parseable and safe at definition time
                normalized_expr, _ = _normalize_expression(condition, {})
                try:
                    tree = ast.parse(normalized_expr, mode="eval")
                except SyntaxError as exc:
                    step_id = step.step_id if hasattr(step, "step_id") else step.get("stepId")
                    raise ValidationError(
                        f"Workflow step '{step_id}' has invalid condition syntax: {exc}"
                    ) from exc
                _validate_condition_ast(tree)

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
                    "parallelGroup": s.parallel_group,
                    "compensation": s.compensation,
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
        return workflow  # type: ignore[no-any-return]

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
        user_id: str | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Update a workflow definition."""
        await self.get_workflow(chain_id)
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
                    "parallelGroup": s.parallel_group,
                    "compensation": s.compensation,
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
        await self.get_workflow(chain_id)

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
        return execution  # type: ignore[no-any-return]

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
                    with contextlib.suppress(Exception):
                        await self.commands_service.cancel_command(
                            step["commandId"], cancelled_by=user_id
                        )

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
                    component="hydra-api", service="workflows"  # type: ignore[arg-type]
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
        request: ExecuteWorkflowRequest | None,  # noqa: ARG002
    ) -> None:
        """Orchestrate workflow step execution in topological order.

        Supports:
        - Conditional branching via ``condition`` expressions
        - Parallel execution of steps sharing the same ``parallelGroup``
        - Compensation handlers executed on abort in reverse completion order
        """
        chain_id = workflow["chainId"]
        steps = workflow["steps"]
        execution_order = self._topological_sort(steps)
        step_map = {s["stepId"]: s for s in steps}
        step_index_map = {sid: i for i, sid in enumerate(execution_order)}
        completed_steps: dict[str, bool] = {}  # step_id -> success
        # Track successful step IDs in completion order for compensation
        successful_step_ids: list[str] = []
        # Track step results for condition evaluation context
        step_results: dict[str, dict[str, Any]] = {}
        has_failure = False

        # Group topological order into batches: consecutive steps with the
        # same parallelGroup are grouped together; steps with None group
        # form single-step batches.
        batches = self._build_execution_batches(execution_order, step_map)

        for batch in batches:
            # Re-check execution status (may have been cancelled)
            execution = await self.workflow_executions.find_one(
                {"executionId": execution_id}
            )
            if not execution or execution["status"] == WorkflowExecutionStatus.CANCELLED.value:
                return

            if len(batch) == 1:
                # Single step – execute sequentially
                step_id = batch[0]
                abort = await self._execute_single_step(
                    execution_id=execution_id,
                    chain_id=chain_id,
                    step_id=step_id,
                    step_map=step_map,
                    step_index_map=step_index_map,
                    completed_steps=completed_steps,
                    successful_step_ids=successful_step_ids,
                    step_results=step_results,
                    has_failure_ref=[has_failure],
                    user_id=user_id,
                    user_role=user_role,
                    user_permissions=user_permissions,
                    source=source,
                    client_id=client_id,
                    steps=steps,
                )
                has_failure = abort.get("has_failure", has_failure)
                if abort.get("cancelled"):
                    return
                if abort.get("abort"):
                    await self._run_compensation(
                        execution_id, chain_id, successful_step_ids,
                        step_map, step_index_map, user_id, user_role,
                        user_permissions, source, client_id,
                    )
                    await self._finish_execution(
                        execution_id, WorkflowExecutionStatus.FAILED,
                    )
                    return
            else:
                # Parallel group – execute concurrently
                abort_result = await self._execute_parallel_batch(
                    execution_id=execution_id,
                    chain_id=chain_id,
                    batch=batch,
                    step_map=step_map,
                    step_index_map=step_index_map,
                    completed_steps=completed_steps,
                    successful_step_ids=successful_step_ids,
                    step_results=step_results,
                    has_failure_ref=[has_failure],
                    user_id=user_id,
                    user_role=user_role,
                    user_permissions=user_permissions,
                    source=source,
                    client_id=client_id,
                    steps=steps,
                )
                has_failure = abort_result.get("has_failure", has_failure)
                if abort_result.get("cancelled"):
                    return
                if abort_result.get("abort"):
                    await self._run_compensation(
                        execution_id, chain_id, successful_step_ids,
                        step_map, step_index_map, user_id, user_role,
                        user_permissions, source, client_id,
                    )
                    await self._finish_execution(
                        execution_id, WorkflowExecutionStatus.FAILED,
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

    async def _execute_single_step(
        self,
        *,
        execution_id: str,
        chain_id: str,
        step_id: str,
        step_map: dict[str, dict[str, Any]],
        step_index_map: dict[str, int],
        completed_steps: dict[str, bool],
        successful_step_ids: list[str],
        step_results: dict[str, dict[str, Any]],
        has_failure_ref: list[bool],
        user_id: str | None,
        user_role: str | None,
        user_permissions: list[str] | None,
        source: CommandSource,
        client_id: str | None,
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute a single step with condition evaluation, dependency checks,
        retry logic, and abort handling.

        Returns a dict with keys: ``cancelled``, ``abort``, ``has_failure``.
        """
        step = step_map[step_id]
        has_failure = has_failure_ref[0]

        # Check dependencies
        deps_ok = all(
            completed_steps.get(dep, False) for dep in step.get("dependsOn", [])
        )
        on_failure = step.get("onFailure", "abort")

        if not deps_ok and on_failure == "abort":
            await self._update_step_status(
                execution_id, step_id, "failed",
                error="Dependency step failed",
            )
            completed_steps[step_id] = False
            return {"cancelled": False, "abort": False, "has_failure": True}
        elif not deps_ok and on_failure == "continue":
            await self._update_step_status(
                execution_id, step_id, "skipped",
                error="Dependency step failed (continue policy)",
            )
            completed_steps[step_id] = False
            return {"cancelled": False, "abort": False, "has_failure": True}

        # Evaluate condition (if present)
        condition = step.get("condition")
        if condition is not None:
            try:
                condition_met = evaluate_condition(condition, step_results)
            except Exception:
                logger.warning(
                    "workflow_condition_failed_closed",
                    execution_id=execution_id,
                    step_id=step_id,
                    condition=condition,
                    exc_info=True,
                )
                condition_met = False
            if not condition_met:
                await self._update_step_status(
                    execution_id, step_id, "skipped",
                    error="Condition not met",
                )
                step_results[step_id] = {"status": "skipped", "output": None}
                completed_steps[step_id] = True  # Skipped is not a failure
                return {"cancelled": False, "abort": False, "has_failure": has_failure}

        # Execute
        outcome = await self._execute_step(
            execution_id, chain_id, step, step_index_map[step_id],
            user_id, user_role, user_permissions, source, client_id,
        )
        if outcome == "cancelled":
            return {"cancelled": True, "abort": False, "has_failure": has_failure}

        success = outcome == "completed"
        completed_steps[step_id] = success

        # Build result context for conditions
        exec_doc = await self.workflow_executions.find_one({"executionId": execution_id})
        step_exec = next(
            (s for s in (exec_doc or {}).get("steps", []) if s["stepId"] == step_id),
            None,
        )
        step_results[step_id] = {
            "status": step_exec["status"] if step_exec else outcome,
            "output": step_exec.get("result") if step_exec else None,
        }

        if success:
            successful_step_ids.append(step_id)

        if not success:
            has_failure = True
            max_retries = step.get("maxRetries", 0)
            retry_count = 0

            if on_failure == "retry" and max_retries > 0:
                while retry_count < max_retries and not success:
                    retry_count += 1
                    logger.info(
                        "workflow_step_retry",
                        execution_id=execution_id,
                        step_id=step_id,
                        attempt=retry_count,
                    )
                    await self._update_step_retry(execution_id, step_id, retry_count)
                    outcome = await self._execute_step(
                        execution_id, chain_id, step, step_index_map[step_id],
                        user_id, user_role, user_permissions, source, client_id,
                    )
                    if outcome == "cancelled":
                        return {"cancelled": True, "abort": False, "has_failure": has_failure}
                    success = outcome == "completed"
                    completed_steps[step_id] = success
                    if success:
                        successful_step_ids.append(step_id)

            if not success and on_failure == "abort":
                remaining = [
                    s["stepId"] for s in steps if s["stepId"] not in completed_steps
                ]
                for rem_id in remaining:
                    await self._update_step_status(execution_id, rem_id, "cancelled")
                return {"cancelled": False, "abort": True, "has_failure": True}

        return {"cancelled": False, "abort": False, "has_failure": has_failure}

    async def _execute_parallel_batch(
        self,
        *,
        execution_id: str,
        chain_id: str,
        batch: list[str],
        step_map: dict[str, dict[str, Any]],
        step_index_map: dict[str, int],
        completed_steps: dict[str, bool],
        successful_step_ids: list[str],
        step_results: dict[str, dict[str, Any]],
        has_failure_ref: list[bool],
        user_id: str | None,
        user_role: str | None,
        user_permissions: list[str] | None,
        source: CommandSource,
        client_id: str | None,
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute a batch of parallel steps concurrently via asyncio.gather.

        Returns a dict with keys: ``cancelled``, ``abort``, ``has_failure``.
        """
        has_failure = has_failure_ref[0]

        async def _run_one(sid: str) -> dict[str, Any]:
            return await self._execute_single_step(
                execution_id=execution_id,
                chain_id=chain_id,
                step_id=sid,
                step_map=step_map,
                step_index_map=step_index_map,
                completed_steps=completed_steps,
                successful_step_ids=successful_step_ids,
                step_results=step_results,
                has_failure_ref=has_failure_ref,
                user_id=user_id,
                user_role=user_role,
                user_permissions=user_permissions,
                source=source,
                client_id=client_id,
                steps=steps,
            )

        results = await asyncio.gather(*[_run_one(sid) for sid in batch])

        any_cancelled = any(r.get("cancelled") for r in results)
        any_abort = any(r.get("abort") for r in results)
        any_failure = any(r.get("has_failure") for r in results)

        return {
            "cancelled": any_cancelled,
            "abort": any_abort,
            "has_failure": has_failure or any_failure,
        }

    def _build_execution_batches(
        self,
        execution_order: list[str],
        step_map: dict[str, dict[str, Any]],
    ) -> list[list[str]]:
        """Group the topological execution order into batches.

        Consecutive steps with the same non-None ``parallelGroup`` are
        grouped together.  Steps without a ``parallelGroup`` (or with a
        unique group) form single-element batches.
        """
        batches: list[list[str]] = []
        for key, group_iter in groupby(
            execution_order,
            key=lambda sid: step_map[sid].get("parallelGroup"),
        ):
            group_list = list(group_iter)
            if key is None:
                # No parallel group – each step is its own batch
                for sid in group_list:
                    batches.append([sid])
            else:
                # All steps in this run share a parallelGroup
                batches.append(group_list)
        return batches

    async def _run_compensation(
        self,
        execution_id: str,
        chain_id: str,
        successful_step_ids: list[str],
        step_map: dict[str, dict[str, Any]],
        step_index_map: dict[str, int],
        user_id: str | None,
        user_role: str | None,
        user_permissions: list[str] | None,
        source: CommandSource,
        client_id: str | None,
    ) -> None:
        """Run compensation handlers in reverse completion order.

        Only steps that completed successfully AND have a ``compensation``
        field are compensated.  Compensation failures are logged but do
        not block the compensation chain.
        """
        # Reverse order – most recently completed first
        for step_id in reversed(successful_step_ids):
            step = step_map.get(step_id, {})
            compensation = step.get("compensation")
            if not compensation:
                continue

            registry_id = compensation.get("registryId")
            if not registry_id:
                continue

            logger.info(
                "workflow_compensation_start",
                execution_id=execution_id,
                step_id=step_id,
                registry_id=registry_id,
            )

            try:
                comp_target = step.get("target", {})
                comp_step = {
                    "stepId": f"comp_{step_id}",
                    "registryId": registry_id,
                    "target": comp_target,
                    "parameters": compensation.get("parameters"),
                }
                await self._execute_step(
                    execution_id=execution_id,
                    chain_id=chain_id,
                    step=comp_step,
                    step_index=step_index_map.get(step_id, 0),
                    user_id=user_id,
                    user_role=user_role,
                    user_permissions=user_permissions,
                    source=source,
                    client_id=client_id,
                )
                logger.info(
                    "workflow_compensation_completed",
                    execution_id=execution_id,
                    step_id=step_id,
                )
            except Exception:
                logger.warning(
                    "workflow_compensation_failed",
                    execution_id=execution_id,
                    step_id=step_id,
                    exc_info=True,
                )

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
            cmd_request = CreateCommandRequest(  # type: ignore[call-arg]
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
        result: dict[str, Any] | None = None,
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
                    component="hydra-api", service="workflows"  # type: ignore[arg-type]
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

    def _validate_step_graph(self, steps: list) -> None:  # type: ignore[type-arg]
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

        # Validate that no step depends on another step within the same
        # parallelGroup.  Steps sharing a parallel group execute concurrently
        # via asyncio.gather, so intra-group dependencies would be violated.
        parallel_groups: dict[str, set[str]] = defaultdict(set)
        for step in steps:
            pg = step.parallel_group if hasattr(step, "parallel_group") else step.get("parallelGroup")
            if pg is not None:
                sid = step.step_id if hasattr(step, "step_id") else step.get("stepId")
                parallel_groups[pg].add(sid)

        for step in steps:
            pg = step.parallel_group if hasattr(step, "parallel_group") else step.get("parallelGroup")
            if pg is None:
                continue
            sid = step.step_id if hasattr(step, "step_id") else step.get("stepId")
            deps = step.depends_on if hasattr(step, "depends_on") else step.get("dependsOn", [])
            group_members = parallel_groups[pg]
            conflicting = set(deps) & group_members
            if conflicting:
                raise ValidationError(
                    f"Step '{sid}' depends on {sorted(conflicting)} which are in "
                    f"the same parallelGroup '{pg}'. Steps in the same parallel "
                    f"group execute concurrently, so intra-group dependencies "
                    f"are not allowed."
                )

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
