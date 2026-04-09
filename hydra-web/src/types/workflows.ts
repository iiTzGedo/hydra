import type { ListParams } from './api';

// ── Enums ──────────────────────────────────────────────────────────────

export type WorkflowExecutionStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'partially_completed';

export type StepFailurePolicy = 'abort' | 'continue' | 'retry';

// ── Step Models ────────────────────────────────────────────────────────

export interface CommandTarget {
  nodeId: string;
  serviceId?: string | null;
}

export interface WorkflowStepConfig {
  stepId: string;
  registryId: string;
  target: CommandTarget;
  parameters?: Record<string, unknown> | null;
  dependsOn?: string[];
  onFailure?: StepFailurePolicy;
  maxRetries?: number;
  condition?: string | null;
  parallelGroup?: string | null;
  compensation?: Record<string, unknown> | null;
}

export interface WorkflowInput {
  type: string;
  required: boolean;
  default?: unknown;
  description?: string | null;
}

// ── Response Models ────────────────────────────────────────────────────

export interface WorkflowSummary {
  chainId: string;
  name: string;
  description?: string | null;
  stepCount: number;
  createdBy?: string | null;
  createdAt: string;
  updatedAt?: string | null;
}

export interface WorkflowResponse extends WorkflowSummary {
  steps: WorkflowStepConfig[];
  inputs?: Record<string, WorkflowInput> | null;
}

export interface WorkflowStepExecution {
  stepId: string;
  registryId: string;
  commandId?: string | null;
  status: string;
  retryCount: number;
  startedAt?: string | null;
  completedAt?: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
}

export interface WorkflowExecutionSummary {
  executionId: string;
  chainId: string;
  name: string;
  status: WorkflowExecutionStatus;
  stepCount: number;
  completedSteps: number;
  startedBy?: string | null;
  startedAt: string;
  completedAt?: string | null;
}

export interface WorkflowExecutionResponse extends WorkflowExecutionSummary {
  steps: WorkflowStepExecution[];
  inputs?: Record<string, unknown> | null;
}

// ── Request Models ─────────────────────────────────────────────────────

export interface CreateWorkflowRequest {
  name: string;
  description?: string;
  steps: WorkflowStepConfig[];
  inputs?: Record<string, WorkflowInput>;
}

export interface ExecuteWorkflowRequest {
  inputs?: Record<string, unknown>;
}

// ── Query Params ───────────────────────────────────────────────────────

export interface WorkflowListParams extends Omit<ListParams, 'search'> {
  limit?: number;
  offset?: number;
}

export interface WorkflowExecutionListParams {
  chainId?: string;
  limit?: number;
  offset?: number;
}
