/**
 * WorkflowTriggerWidget -- single button to trigger a workflow execution.
 * Executes workflows via the onExecuteCommand callback using the workflow's
 * registry ID.
 *
 * Config: { workflowId: string; nodeId: string; label?: string }
 */

import { useState } from 'react';
import { GitBranch, Loader2 } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface WorkflowTriggerConfig extends Record<string, unknown> {
  workflowId?: string;
  nodeId?: string;
  label?: string;
}

export function WorkflowTriggerWidget({
  config,
  isLoading,
  isEditing,
  error,
  onExecuteCommand,
}: WidgetComponentProps<unknown, WorkflowTriggerConfig>) {
  const [executing, setExecuting] = useState(false);

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const label = config.label ?? 'Run Workflow';
  const canExecute = !!config.workflowId && !!config.nodeId && !!onExecuteCommand && !isEditing;

  async function handleTrigger() {
    if (!canExecute) return;
    setExecuting(true);
    try {
      await onExecuteCommand!(
        config.workflowId!,
        { nodeId: config.nodeId! },
        {},
      );
    } finally {
      setExecuting(false);
    }
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-2">
      <button
        type="button"
        disabled={!canExecute || executing}
        onClick={() => void handleTrigger()}
        className="flex items-center gap-2.5 rounded-xl border border-border/60 bg-muted/20 px-5 py-3 text-sm font-medium shadow-sm transition-colors hover:bg-muted/40 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {executing ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : (
          <GitBranch className="h-4 w-4 text-muted-foreground" />
        )}
        <span>{executing ? 'Starting...' : label}</span>
      </button>

      {config.workflowId && (
        <span className="rounded bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
          {config.workflowId}
        </span>
      )}

      {!config.workflowId && (
        <span className="text-center text-[10px] text-amber-600">
          Configure a workflowId in widget settings
        </span>
      )}
    </div>
  );
}
