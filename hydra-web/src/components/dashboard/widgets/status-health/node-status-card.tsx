/**
 * NodeStatusCardWidget -- single-node information card showing the
 * node name, class, status badge, last profile timestamp, and optional
 * hardware specs (cores, memory, storage).
 *
 * Data shape:
 *   {
 *     nodeId: string;
 *     displayName?: string;
 *     class: string;
 *     status: string;
 *     lastProfileAt?: string;
 *     specs?: { cores?: number; memory?: string; storage?: string };
 *   }
 *
 * Config: { nodeId?: string }  (used by the data binding layer)
 */

import { Server, Cpu, MemoryStick, HardDrive } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface NodeSpecs {
  cores?: number;
  memory?: string;
  storage?: string;
}

interface NodeStatusData {
  nodeId: string;
  displayName?: string;
  class: string;
  status: string;
  lastProfileAt?: string;
  specs?: NodeSpecs;
}

interface NodeStatusConfig extends Record<string, unknown> {
  nodeId?: string;
}

const STATUS_STYLES: Record<string, string> = {
  online: 'bg-emerald-500/15 text-emerald-600',
  active: 'bg-emerald-500/15 text-emerald-600',
  running: 'bg-emerald-500/15 text-emerald-600',
  offline: 'bg-red-500/15 text-red-600',
  down: 'bg-red-500/15 text-red-600',
  degraded: 'bg-yellow-500/15 text-yellow-600',
  warning: 'bg-yellow-500/15 text-yellow-600',
  archived: 'bg-gray-500/15 text-gray-500',
  unknown: 'bg-gray-500/15 text-gray-500',
};

function statusStyle(status: string): string {
  return STATUS_STYLES[status.toLowerCase()] ?? 'bg-gray-500/15 text-gray-500';
}

function formatRelativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return 'just now';
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return iso;
  }
}

export function NodeStatusCardWidget({
  data,
  config: _config,
  isLoading,
  error,
}: WidgetComponentProps<NodeStatusData, NodeStatusConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (!data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Server className="h-5 w-5" />
        <span className="text-sm">No node data</span>
      </div>
    );
  }

  const { nodeId, displayName, status, specs, lastProfileAt } = data;
  const nodeClass = data.class;

  return (
    <div className="flex h-full flex-col gap-3 p-1">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm font-semibold text-foreground">
              {displayName ?? nodeId}
            </span>
          </div>
          {displayName && (
            <span className="ml-6 text-xs text-muted-foreground">{nodeId}</span>
          )}
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusStyle(status)}`}
        >
          {status}
        </span>
      </div>

      {/* Class badge */}
      <div className="flex items-center gap-2">
        <span className="rounded bg-muted px-2 py-0.5 text-xs font-medium capitalize text-muted-foreground">
          {nodeClass}
        </span>
        {lastProfileAt && (
          <span className="text-xs text-muted-foreground">
            Profiled {formatRelativeTime(lastProfileAt)}
          </span>
        )}
      </div>

      {/* Specs grid */}
      {specs && (specs.cores || specs.memory || specs.storage) && (
        <div className="mt-auto grid grid-cols-3 gap-2">
          {specs.cores != null && (
            <div className="flex flex-col items-center rounded-md border border-border/40 bg-muted/20 py-1.5">
              <Cpu className="mb-0.5 h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-sm font-semibold text-foreground">{specs.cores}</span>
              <span className="text-[10px] text-muted-foreground">Cores</span>
            </div>
          )}
          {specs.memory && (
            <div className="flex flex-col items-center rounded-md border border-border/40 bg-muted/20 py-1.5">
              <MemoryStick className="mb-0.5 h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-sm font-semibold text-foreground">{specs.memory}</span>
              <span className="text-[10px] text-muted-foreground">Memory</span>
            </div>
          )}
          {specs.storage && (
            <div className="flex flex-col items-center rounded-md border border-border/40 bg-muted/20 py-1.5">
              <HardDrive className="mb-0.5 h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-sm font-semibold text-foreground">{specs.storage}</span>
              <span className="text-[10px] text-muted-foreground">Storage</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
