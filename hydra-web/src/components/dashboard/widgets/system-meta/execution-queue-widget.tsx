/**
 * ExecutionQueueWidget -- table of command executions with status badges.
 *
 * Data shape:
 *   { executions: { commandId: string; registryId: string; status: string;
 *     createdAt: string }[] }
 *
 * Status badge colors: pending=gray, running=blue, completed=green, failed=red.
 */

import { ListOrdered } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ExecutionEntry {
  commandId: string;
  registryId: string;
  status: string;
  createdAt: string;
}

interface ExecutionQueueData {
  executions: ExecutionEntry[];
}

const STATUS_BADGE: Record<string, { bg: string; text: string }> = {
  pending: { bg: 'bg-gray-500/10', text: 'text-gray-600' },
  running: { bg: 'bg-blue-500/10', text: 'text-blue-600' },
  completed: { bg: 'bg-emerald-500/10', text: 'text-emerald-600' },
  failed: { bg: 'bg-red-500/10', text: 'text-red-600' },
};

const DEFAULT_BADGE = { bg: 'bg-gray-500/10', text: 'text-gray-600' };

function formatTimestamp(isoString: string): string {
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return isoString;
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function ExecutionQueueWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<ExecutionQueueData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.executions.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <ListOrdered className="h-5 w-5" />
        <div className="text-sm">No pending executions</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-auto p-1">
      {/* Table header */}
      <div className="sticky top-0 grid grid-cols-[1fr_1fr_auto_auto] gap-2 border-b border-border/40 bg-background pb-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        <span>Command</span>
        <span>Registry</span>
        <span>Status</span>
        <span>Created</span>
      </div>

      {/* Table rows */}
      <div className="space-y-0.5 pt-1">
        {data.executions.map((execution, index) => {
          const badge =
            STATUS_BADGE[execution.status.toLowerCase()] ?? DEFAULT_BADGE;

          return (
            <div
              key={`${execution.commandId}-${index}`}
              className="grid grid-cols-[1fr_1fr_auto_auto] items-center gap-2 rounded-md px-1 py-1.5 transition-colors hover:bg-muted/20"
            >
              <span className="truncate font-mono text-xs">
                {execution.commandId}
              </span>
              <span className="truncate text-xs text-muted-foreground">
                {execution.registryId}
              </span>
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-semibold capitalize ${badge.bg} ${badge.text}`}
              >
                {execution.status}
              </span>
              <span className="text-[10px] tabular-nums text-muted-foreground/60">
                {formatTimestamp(execution.createdAt)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
