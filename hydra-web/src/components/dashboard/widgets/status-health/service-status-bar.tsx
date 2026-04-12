/**
 * ServiceStatusBarWidget -- horizontal segmented bar where each
 * segment is proportional to the count of services in that state.
 *
 * Data shape: { running: number; stopped: number; failed: number; unknown: number }
 * Config:     (none required)
 *
 * Segment colours:
 *   running -> emerald
 *   stopped -> gray
 *   failed  -> red
 *   unknown -> amber
 */

import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ServiceStatusData {
  running: number;
  stopped: number;
  failed: number;
  unknown: number;
}

interface Segment {
  key: string;
  count: number;
  pct: number;
  bg: string;
  text: string;
  dot: string;
}

const SEGMENT_META: {
  key: keyof ServiceStatusData;
  label: string;
  bg: string;
  text: string;
  dot: string;
}[] = [
  { key: 'running', label: 'Running', bg: 'bg-emerald-500', text: 'text-emerald-600', dot: 'bg-emerald-500' },
  { key: 'stopped', label: 'Stopped', bg: 'bg-gray-400', text: 'text-gray-500', dot: 'bg-gray-400' },
  { key: 'failed', label: 'Failed', bg: 'bg-red-500', text: 'text-red-600', dot: 'bg-red-500' },
  { key: 'unknown', label: 'Unknown', bg: 'bg-amber-500', text: 'text-amber-600', dot: 'bg-amber-500' },
];

export function ServiceStatusBarWidget({
  data,
  config: _config,
  isLoading,
  error,
}: WidgetComponentProps<ServiceStatusData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No service data
      </div>
    );
  }

  const total = data.running + data.stopped + data.failed + data.unknown;

  if (total === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No services
      </div>
    );
  }

  const segments: Segment[] = SEGMENT_META.map((meta) => ({
    key: meta.key,
    count: data[meta.key],
    pct: (data[meta.key] / total) * 100,
    bg: meta.bg,
    text: meta.text,
    dot: meta.dot,
  })).filter((s) => s.count > 0);

  return (
    <div className="flex h-full flex-col justify-center gap-3 p-1">
      {/* Total */}
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-foreground">Services</span>
        <span className="text-xs text-muted-foreground">{total} total</span>
      </div>

      {/* Segmented bar */}
      <div className="flex h-4 w-full overflow-hidden rounded-full">
        {segments.map((seg, idx) => (
          <div
            key={seg.key}
            className={`h-full ${seg.bg} ${idx === 0 ? 'rounded-l-full' : ''} ${idx === segments.length - 1 ? 'rounded-r-full' : ''}`}
            style={{ width: `${seg.pct}%` }}
            title={`${seg.key}: ${seg.count}`}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {SEGMENT_META.map((meta) => (
          <div key={meta.key} className="flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 rounded-full ${meta.dot}`} />
            <span className="text-xs text-muted-foreground">
              {meta.label}
            </span>
            <span className={`text-xs font-medium ${meta.text}`}>
              {data[meta.key]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
