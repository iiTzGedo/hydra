/**
 * MetricCardWidget -- displays a single prominent metric value with an
 * optional trend indicator (direction + percentage).
 *
 * Data shape: { value: number; label?: string; trend?: { direction: 'up' | 'down'; percent: number } }
 * Config:     { label?: string; icon?: string; color?: string }
 */

import { TrendingUp, TrendingDown } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface MetricCardData {
  value: number;
  label?: string;
  trend?: {
    direction: 'up' | 'down';
    percent: number;
  };
}

interface MetricCardConfig extends Record<string, unknown> {
  label?: string;
  icon?: string;
  color?: string;
}

export function MetricCardWidget({
  data,
  config,
  isLoading,
  error,
}: WidgetComponentProps<MetricCardData, MetricCardConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const metric = data ?? null;
  const label = metric?.label ?? config.label ?? 'Metric';
  const color = config.color ?? 'hsl(var(--primary))';

  return (
    <div className="flex h-full flex-col justify-center gap-1 p-1">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <div className="flex items-end gap-3">
        <span
          className="text-4xl font-bold leading-none tracking-tight"
          style={{ color }}
        >
          {metric !== null ? formatValue(metric.value) : '\u2014'}
        </span>
        {metric?.trend && (
          <span
            className={`mb-0.5 inline-flex items-center gap-1 text-sm font-medium ${
              metric.trend.direction === 'up'
                ? 'text-emerald-500'
                : 'text-red-500'
            }`}
          >
            {metric.trend.direction === 'up' ? (
              <TrendingUp className="h-4 w-4" />
            ) : (
              <TrendingDown className="h-4 w-4" />
            )}
            {metric.trend.percent.toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

/** Format large numbers with locale separators for readability. */
function formatValue(value: number): string {
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
