"""Workflow definition and execution models for command chains."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .schemas import CommandTarget

# ── Enums ────────────────────────────────────────────────────────────────


class WorkflowExecutionStatus(StrEnum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"


class StepFailurePolicy(StrEnum):
    """Policy for handling step failures."""

    ABORT = "abort"
    CONTINUE = "continue"
    RETRY = "retry"


# ── Step Models ──────────────────────────────────────────────────────────


class WorkflowStep(BaseModel):
    """Definition of a single step within a workflow."""

    model_config = ConfigDict(populate_by_name=True)

    step_id: Annotated[str, Field(alias="stepId", description="Unique step identifier")]
    registry_id: Annotated[
        str, Field(alias="registryId", description="Command registry ID to execute")
    ]
    target: CommandTarget = Field(description="Target node/service for this step")
    parameters: dict[str, Any] | None = Field(
        default=None, description="Command parameters"
    )
    depends_on: list[str] = Field(
        default_factory=list,
        alias="dependsOn",
        description="Step IDs this step depends on",
    )
    on_failure: StepFailurePolicy = Field(
        default=StepFailurePolicy.ABORT,
        alias="onFailure",
        description="Policy when this step fails",
    )
    max_retries: int = Field(
        default=0, alias="maxRetries", ge=0, le=5, description="Max retry attempts"
    )
    condition: str | None = Field(
        default=None, description="Optional condition expression"
    )

    @field_validator("step_id")
    @classmethod
    def validate_step_id(cls, v: str) -> str:
        if not v or len(v) > 64:
            raise ValueError("stepId must be 1-64 characters")
        return v


class WorkflowInput(BaseModel):
    """Input parameter definition for a workflow."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(description="Input type (string, number, boolean)")
    required: bool = Field(default=True, description="Whether this input is required")
    default: Any | None = Field(default=None, description="Default value")
    description: str | None = Field(default=None, description="Input description")


# ── Request Models ───────────────────────────────────────────────────────


class CreateWorkflowRequest(BaseModel):
    """Request to create a new workflow definition."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=128, description="Workflow name")
    description: str | None = Field(
        default=None, max_length=512, description="Workflow description"
    )
    steps: list[WorkflowStep] = Field(
        min_length=1, max_length=50, description="Ordered workflow steps"
    )
    inputs: dict[str, WorkflowInput] | None = Field(
        default=None, description="Workflow input definitions"
    )


class UpdateWorkflowRequest(BaseModel):
    """Request to update an existing workflow definition."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(
        default=None, min_length=1, max_length=128, description="Workflow name"
    )
    description: str | None = Field(
        default=None, max_length=512, description="Workflow description"
    )
    steps: list[WorkflowStep] | None = Field(
        default=None, min_length=1, max_length=50, description="Workflow steps"
    )
    inputs: dict[str, WorkflowInput] | None = Field(
        default=None, description="Workflow input definitions"
    )


class ExecuteWorkflowRequest(BaseModel):
    """Request to execute a workflow."""

    model_config = ConfigDict(populate_by_name=True)

    inputs: dict[str, Any] | None = Field(
        default=None, description="Input values for the workflow"
    )


# ── Response Models ──────────────────────────────────────────────────────


class WorkflowSummary(BaseModel):
    """Summary view of a workflow for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    chain_id: Annotated[str, Field(alias="chainId")]
    name: str
    description: str | None = None
    step_count: Annotated[int, Field(alias="stepCount")]
    created_by: Annotated[str | None, Field(default=None, alias="createdBy")]
    created_at: Annotated[datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime | None, Field(default=None, alias="updatedAt")]


class WorkflowResponse(BaseModel):
    """Full workflow definition response."""

    model_config = ConfigDict(populate_by_name=True)

    chain_id: Annotated[str, Field(alias="chainId")]
    name: str
    description: str | None = None
    steps: list[WorkflowStep]
    inputs: dict[str, WorkflowInput] | None = None
    created_by: Annotated[str | None, Field(default=None, alias="createdBy")]
    created_at: Annotated[datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime | None, Field(default=None, alias="updatedAt")]


class WorkflowStepExecution(BaseModel):
    """Execution state of a single workflow step."""

    model_config = ConfigDict(populate_by_name=True)

    step_id: Annotated[str, Field(alias="stepId")]
    registry_id: Annotated[str, Field(alias="registryId")]
    command_id: Annotated[str | None, Field(default=None, alias="commandId")]
    status: str = Field(default="pending")
    retry_count: Annotated[int, Field(default=0, alias="retryCount")]
    started_at: Annotated[datetime | None, Field(default=None, alias="startedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]
    result: dict[str, Any] | None = None
    error: str | None = None


class WorkflowExecutionResponse(BaseModel):
    """Response for a workflow execution."""

    model_config = ConfigDict(populate_by_name=True)

    execution_id: Annotated[str, Field(alias="executionId")]
    chain_id: Annotated[str, Field(alias="chainId")]
    name: str
    status: WorkflowExecutionStatus
    steps: list[WorkflowStepExecution]
    inputs: dict[str, Any] | None = None
    started_by: Annotated[str | None, Field(default=None, alias="startedBy")]
    started_at: Annotated[datetime, Field(alias="startedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]


class WorkflowExecutionSummary(BaseModel):
    """Summary view of a workflow execution for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    execution_id: Annotated[str, Field(alias="executionId")]
    chain_id: Annotated[str, Field(alias="chainId")]
    name: str
    status: WorkflowExecutionStatus
    step_count: Annotated[int, Field(alias="stepCount")]
    completed_steps: Annotated[int, Field(default=0, alias="completedSteps")]
    started_by: Annotated[str | None, Field(default=None, alias="startedBy")]
    started_at: Annotated[datetime, Field(alias="startedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]
