/**
 * WorkflowTriggerWidget -- single button to trigger a workflow execution.
 * Placeholder for Wave 3 workflow integration.
 *
 * Config: { workflowId: string; label?: string }
 *
 * Displays a disabled button with a GitBranch icon indicating workflow
 * triggers will be available in Wave 3.
 */

import { GitBranch } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface WorkflowTriggerConfig extends Record<string, unknown> {
  workflowId?: string;
  label?: string;
}

export function WorkflowTriggerWidget({
  config,
  isLoading,
  error,
}: WidgetComponentProps<unknown, WorkflowTriggerConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const label = config.label ?? 'Run Workflow';

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-2">
      <button
        type="button"
        disabled
        title="Workflow triggers — Wave 3"
        className="flex items-center gap-2.5 rounded-xl border border-border/60 bg-muted/20 px-5 py-3 text-sm font-medium shadow-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50"
      >
        <GitBranch className="h-4 w-4 text-muted-foreground" />
        <span>{label}</span>
      </button>

      {config.workflowId && (
        <span className="rounded bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
          {config.workflowId}
        </span>
      )}

      <div className="text-center text-[10px] text-muted-foreground/60">
        Workflow triggers — Wave 3
      </div>
    </div>
  );
}
