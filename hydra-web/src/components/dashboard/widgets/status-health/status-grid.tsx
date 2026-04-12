/**
 * StatusGridWidget -- responsive grid of status cards, each showing an
 * entity name and coloured left border indicating its status.
 *
 * Data shape:  { items: { id: string; name: string; status: string; type?: string }[] }
 * Config:      { columns?: number }
 *
 * Border colours:
 *   online   -> green
 *   offline  -> red
 *   degraded -> yellow
 *   unknown  -> gray  (default)
 */

import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface StatusItem {
  id: string;
  name: string;
  status: string;
  type?: string;
}

interface StatusGridData {
  items: StatusItem[];
}

interface StatusGridConfig extends Record<string, unknown> {
  columns?: number;
}

const STATUS_BORDER: Record<string, string> = {
  online: 'border-l-emerald-500',
  active: 'border-l-emerald-500',
  running: 'border-l-emerald-500',
  healthy: 'border-l-emerald-500',
  offline: 'border-l-red-500',
  down: 'border-l-red-500',
  stopped: 'border-l-red-500',
  degraded: 'border-l-yellow-500',
  warning: 'border-l-yellow-500',
  unknown: 'border-l-gray-400',
};

const STATUS_DOT: Record<string, string> = {
  online: 'bg-emerald-500',
  active: 'bg-emerald-500',
  running: 'bg-emerald-500',
  healthy: 'bg-emerald-500',
  offline: 'bg-red-500',
  down: 'bg-red-500',
  stopped: 'bg-red-500',
  degraded: 'bg-yellow-500',
  warning: 'bg-yellow-500',
  unknown: 'bg-gray-400',
};

function borderClass(status: string): string {
  return STATUS_BORDER[status.toLowerCase()] ?? 'border-l-gray-400';
}

function dotClass(status: string): string {
  return STATUS_DOT[status.toLowerCase()] ?? 'bg-gray-400';
}

/** Map config.columns to a Tailwind grid class. */
function gridCols(columns?: number): string {
  switch (columns) {
    case 1:
      return 'grid-cols-1';
    case 2:
      return 'grid-cols-1 sm:grid-cols-2';
    case 4:
      return 'grid-cols-2 sm:grid-cols-4';
    default:
      return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3';
  }
}

export function StatusGridWidget({
  data,
  config,
  isLoading,
  error,
}: WidgetComponentProps<StatusGridData, StatusGridConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No status items
      </div>
    );
  }

  return (
    <div className={`grid gap-2 p-1 ${gridCols(config.columns)}`}>
      {items.map((item) => (
        <div
          key={item.id}
          className={`rounded-md border border-border/60 border-l-4 bg-muted/20 px-3 py-2 ${borderClass(item.status)}`}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground truncate">
              {item.name}
            </span>
            <span
              className={`ml-2 inline-flex h-2 w-2 shrink-0 rounded-full ${dotClass(item.status)}`}
            />
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
            {item.type && <span className="capitalize">{item.type}</span>}
            <span className="capitalize">{item.status}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
