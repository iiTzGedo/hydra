/**
 * NodeSummaryWidget -- multi-section card displaying node identity, specs,
 * and service/profile metadata.
 *
 * Data shape:
 *   { nodeId: string; displayName?: string; class: string; status: string;
 *     type?: string; tags?: string[]; specs?: { cores?: number; memory?: string;
 *     storage?: string }; servicesCount?: number; lastProfileAt?: string }
 *
 * Config: { nodeId: string }
 */

import {
  Server,
  Router,
  Cpu,
  MemoryStick,
  HardDrive,
  Layers,
  Clock,
  Radio,
  Tag,
} from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface NodeSummaryData {
  nodeId: string;
  displayName?: string;
  class: string;
  status: string;
  type?: string;
  tags?: string[];
  specs?: {
    cores?: number;
    memory?: string;
    storage?: string;
  };
  servicesCount?: number;
  lastProfileAt?: string;
}

interface NodeSummaryConfig extends Record<string, unknown> {
  nodeId?: string;
}

const CLASS_ICONS: Record<string, typeof Server> = {
  compute: Server,
  networking: Router,
  iot: Radio,
};

const STATUS_COLORS: Record<string, string> = {
  online: 'bg-emerald-500',
  offline: 'bg-red-500',
  degraded: 'bg-amber-500',
  unknown: 'bg-gray-400',
};

function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;

  if (Number.isNaN(diffMs)) return isoString;

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function NodeSummaryWidget({
  data,
  config,
  isLoading,
  error,
}: WidgetComponentProps<NodeSummaryData, NodeSummaryConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Server className="h-5 w-5" />
        <div className="text-sm font-medium">{config.nodeId ?? 'Node'}</div>
        <div className="text-xs">Loading...</div>
      </div>
    );
  }

  const ClassIcon = CLASS_ICONS[data.class] ?? Server;
  const statusColor = STATUS_COLORS[data.status] ?? STATUS_COLORS.unknown;

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-1">
      {/* Identity section */}
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <ClassIcon className="h-5 w-5 text-muted-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold">
              {data.displayName ?? data.nodeId}
            </span>
            <span
              className={`inline-block h-2 w-2 shrink-0 rounded-full ${statusColor}`}
              title={data.status}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="capitalize">{data.class}</span>
            {data.type && (
              <>
                <span className="text-border">/</span>
                <span>{data.type}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Tags */}
      {data.tags && data.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
            >
              <Tag className="h-2.5 w-2.5" />
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Specs section */}
      {data.specs && (data.specs.cores || data.specs.memory || data.specs.storage) && (
        <div className="grid grid-cols-3 gap-2 rounded-lg border border-border/60 bg-muted/20 p-2.5">
          {data.specs.cores != null && (
            <div className="flex flex-col items-center gap-1">
              <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs font-medium">{data.specs.cores}</span>
              <span className="text-[10px] text-muted-foreground">cores</span>
            </div>
          )}
          {data.specs.memory != null && (
            <div className="flex flex-col items-center gap-1">
              <MemoryStick className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs font-medium">{data.specs.memory}</span>
              <span className="text-[10px] text-muted-foreground">RAM</span>
            </div>
          )}
          {data.specs.storage != null && (
            <div className="flex flex-col items-center gap-1">
              <HardDrive className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs font-medium">{data.specs.storage}</span>
              <span className="text-[10px] text-muted-foreground">disk</span>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="mt-auto flex items-center justify-between border-t border-border/40 pt-2 text-xs text-muted-foreground">
        {data.servicesCount != null && (
          <span className="inline-flex items-center gap-1">
            <Layers className="h-3 w-3" />
            {data.servicesCount} service{data.servicesCount !== 1 ? 's' : ''}
          </span>
        )}
        {data.lastProfileAt && (
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatRelativeTime(data.lastProfileAt)}
          </span>
        )}
      </div>
    </div>
  );
}
