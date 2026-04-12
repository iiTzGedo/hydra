/**
 * TimeMachineScrubberWidget -- horizontal timeline with event markers
 * positioned proportionally along a time range.
 *
 * Data shape:
 *   { events: { timestamp: string; label: string }[];
 *     rangeStart?: string; rangeEnd?: string }
 *
 * Markers are rendered as circles on a horizontal bar, positioned based on
 * their timestamp relative to the range boundaries. Labels appear on hover
 * via the title attribute.
 */

import { Clock } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface TimelineEvent {
  timestamp: string;
  label: string;
}

interface TimeMachineScrubberData {
  events: TimelineEvent[];
  rangeStart?: string;
  rangeEnd?: string;
}

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

export function TimeMachineScrubberWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<TimeMachineScrubberData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.events.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Clock className="h-5 w-5" />
        <div className="text-sm">No timeline data</div>
      </div>
    );
  }

  // Determine the time range
  const timestamps = data.events.map((e) => new Date(e.timestamp).getTime());
  const rangeStartMs = data.rangeStart
    ? new Date(data.rangeStart).getTime()
    : Math.min(...timestamps);
  const rangeEndMs = data.rangeEnd
    ? new Date(data.rangeEnd).getTime()
    : Math.max(...timestamps);
  const rangeDuration = rangeEndMs - rangeStartMs;

  return (
    <div className="flex h-full flex-col justify-center gap-3 overflow-hidden p-1">
      {/* Range labels */}
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>{formatTimestamp(data.rangeStart ?? new Date(rangeStartMs).toISOString())}</span>
        <span>{formatTimestamp(data.rangeEnd ?? new Date(rangeEndMs).toISOString())}</span>
      </div>

      {/* Timeline bar */}
      <div className="relative">
        {/* Track */}
        <div className="h-1.5 w-full rounded-full bg-muted" />

        {/* Event markers */}
        {data.events.map((event, index) => {
          const eventMs = new Date(event.timestamp).getTime();
          const percent =
            rangeDuration > 0
              ? Math.min(Math.max(((eventMs - rangeStartMs) / rangeDuration) * 100, 0), 100)
              : 50;

          return (
            <div
              key={`${event.timestamp}-${index}`}
              className="absolute -top-1 h-3.5 w-3.5 -translate-x-1/2 cursor-default"
              style={{ left: `${percent}%` }}
              title={`${event.label}\n${formatTimestamp(event.timestamp)}`}
            >
              <div className="h-3.5 w-3.5 rounded-full border-2 border-primary bg-background shadow-sm transition-transform hover:scale-125" />
            </div>
          );
        })}
      </div>

      {/* Event count */}
      <div className="text-center text-[10px] text-muted-foreground">
        {data.events.length} event{data.events.length !== 1 ? 's' : ''} in range
      </div>
    </div>
  );
}
