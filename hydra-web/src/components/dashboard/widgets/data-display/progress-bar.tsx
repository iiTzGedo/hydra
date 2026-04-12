/**
 * ProgressBarWidget -- horizontal progress bar with color thresholds.
 *
 * Data shape: { value: number; max?: number }
 * Config:     { max?: number; label?: string }
 *
 * Color thresholds (percentage):
 *   green  < 70%
 *   yellow < 90%
 *   red   >= 90%
 */

import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ProgressBarData {
  value: number;
  max?: number;
}

interface ProgressBarConfig extends Record<string, unknown> {
  max?: number;
  label?: string;
}

function barColor(pct: number): string {
  if (pct >= 90) return 'bg-red-500';
  if (pct >= 70) return 'bg-yellow-500';
  return 'bg-emerald-500';
}

export function ProgressBarWidget({
  data,
  config,
  isLoading,
  error,
}: WidgetComponentProps<ProgressBarData, ProgressBarConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const value = data?.value ?? 0;
  const max = data?.max ?? config.max ?? 100;
  const label = config.label ?? 'Progress';
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;

  const hasData = data !== null && data !== undefined;

  return (
    <div className="flex h-full flex-col justify-center gap-2 p-1">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className="text-sm tabular-nums text-muted-foreground">
          {hasData ? `${pct.toFixed(1)}%` : '\u2014'}
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
        {hasData && (
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor(pct)}`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      {hasData && (
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{formatNum(value)}</span>
          <span>{formatNum(max)}</span>
        </div>
      )}
    </div>
  );
}

function formatNum(n: number): string {
  return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(1);
}
