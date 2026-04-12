/**
 * StatGroupWidget -- renders a 2-4 column grid of small stat cards.
 *
 * Data shape: { label: string; value: string | number; icon?: string }[]
 * Config:     (none required)
 *
 * Each card shows the label above a large value. If the data array is
 * empty or null, a placeholder message is rendered.
 */

import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface StatItem {
  label: string;
  value: string | number;
  icon?: string;
}

type StatGroupData = StatItem[];

export function StatGroupWidget({
  data,
  config: _config,
  isLoading,
  error,
}: WidgetComponentProps<StatGroupData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const items = Array.isArray(data) ? data : [];

  if (items.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No statistics configured
      </div>
    );
  }

  // Determine grid columns: 2 for 1-2 items, 3 for 3, 4 for 4+
  const cols =
    items.length <= 2
      ? 'grid-cols-2'
      : items.length === 3
        ? 'grid-cols-3'
        : 'grid-cols-2 sm:grid-cols-4';

  return (
    <div className={`grid h-full gap-3 p-1 ${cols}`}>
      {items.map((item, idx) => (
        <div
          key={`${item.label}-${idx}`}
          className="flex flex-col justify-center rounded-lg border border-border/60 bg-muted/20 p-3"
        >
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {item.label}
          </span>
          <span className="mt-1 text-2xl font-bold leading-tight text-foreground">
            {typeof item.value === 'number'
              ? item.value.toLocaleString()
              : item.value}
          </span>
        </div>
      ))}
    </div>
  );
}
