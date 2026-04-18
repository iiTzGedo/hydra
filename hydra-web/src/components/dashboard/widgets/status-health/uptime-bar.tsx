/**
 * UptimeBarWidget -- horizontal row of thin rectangles, each
 * representing a single day. Green = up, red = down, gray = no data.
 *
 * Data shape: { days: { date: string; up: boolean }[] }
 * Config:     (none required)
 *
 * When data is null or empty, renders 30 gray placeholder bars.
 * Shows an uptime percentage below the bar.
 */

import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface UptimeDay {
  date: string;
  up: boolean;
}

interface UptimeBarData {
  days: UptimeDay[];
}

const PLACEHOLDER_COUNT = 30;

export function UptimeBarWidget({
  data,
  config: _config,
  isLoading,
  error,
}: WidgetComponentProps<UptimeBarData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const days = data?.days ?? [];
  const hasData = days.length > 0;

  // Compute uptime percentage
  const upCount = days.filter((d) => d.up).length;
  const uptimePct = hasData ? (upCount / days.length) * 100 : 0;

  // Either real days or placeholder bars
  const barCount = hasData ? days.length : PLACEHOLDER_COUNT;

  return (
    <div className="flex h-full flex-col justify-center gap-2 p-1">
      {/* Bar strip */}
      <div className="flex w-full items-center gap-[2px]">
        {Array.from({ length: barCount }).map((_, idx) => {
          let colorClass: string;
          let title: string;

          if (!hasData) {
            colorClass = 'bg-muted';
            title = 'No data';
          } else {
            const day = days[idx];
            colorClass = day.up ? 'bg-success' : 'bg-destructive';
            title = `${day.date}: ${day.up ? 'up' : 'down'}`;
          }

          return (
            <div
              key={hasData ? days[idx].date : idx}
              className={`h-6 flex-1 rounded-sm ${colorClass}`}
              title={title}
            />
          );
        })}
      </div>

      {/* Summary */}
      <div className="flex items-baseline justify-between">
        {hasData ? (
          <>
            <span className="text-xs text-muted-foreground">
              {days.length} day{days.length !== 1 ? 's' : ''}
            </span>
            <span
              className={`text-sm font-semibold ${
                uptimePct >= 99.5
                  ? 'text-success'
                  : uptimePct >= 95
                    ? 'text-warning'
                    : 'text-destructive'
              }`}
            >
              {uptimePct.toFixed(1)}% uptime
            </span>
          </>
        ) : (
          <span className="text-xs text-muted-foreground">
            No uptime data available
          </span>
        )}
      </div>
    </div>
  );
}
