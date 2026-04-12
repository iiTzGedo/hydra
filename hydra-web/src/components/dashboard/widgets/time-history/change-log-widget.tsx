/**
 * ChangeLogWidget -- chronological list of infrastructure change events,
 * each with a type badge, timestamp, entity name, and description.
 *
 * Data shape:
 *   { changes: { timestamp: string; type: string; entity: string;
 *     description: string }[] }
 *
 * Type badge colors: create=green, update=blue, delete=red, default=gray.
 */

import { History } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ChangeEntry {
  timestamp: string;
  type: string;
  entity: string;
  description: string;
}

interface ChangeLogData {
  changes: ChangeEntry[];
}

const TYPE_STYLES: Record<string, { bg: string; text: string }> = {
  create: { bg: 'bg-emerald-500/10', text: 'text-emerald-600' },
  update: { bg: 'bg-blue-500/10', text: 'text-blue-600' },
  delete: { bg: 'bg-red-500/10', text: 'text-red-600' },
};

const DEFAULT_TYPE_STYLE = { bg: 'bg-gray-500/10', text: 'text-gray-600' };

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

export function ChangeLogWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<ChangeLogData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.changes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <History className="h-5 w-5" />
        <div className="text-sm">No changes recorded</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-1 overflow-auto p-1">
      {data.changes.map((change, index) => {
        const style =
          TYPE_STYLES[change.type.toLowerCase()] ?? DEFAULT_TYPE_STYLE;

        return (
          <div
            key={`${change.timestamp}-${index}`}
            className="flex items-start gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted/30"
          >
            {/* Type badge */}
            <span
              className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${style.bg} ${style.text}`}
            >
              {change.type}
            </span>

            {/* Content */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-xs font-semibold">
                  {change.entity}
                </span>
                <span className="shrink-0 text-[10px] text-muted-foreground tabular-nums">
                  {formatTimestamp(change.timestamp)}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                {change.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
