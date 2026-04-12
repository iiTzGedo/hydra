/**
 * SparklineWidget -- minimal recharts LineChart with no axes, grid, or
 * tooltip. Renders a smooth line from a series of numeric data points.
 *
 * Data shape: number[] | { value: number }[]
 * Config:     { color?: string; strokeWidth?: number }
 */

import { LineChart, Line, ResponsiveContainer } from 'recharts';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

type SparklineData = number[] | { value: number }[];

interface SparklineConfig extends Record<string, unknown> {
  color?: string;
  strokeWidth?: number;
}

/** Normalise raw data into { value } objects for recharts. */
function normaliseData(raw: SparklineData): { value: number }[] {
  if (raw.length === 0) return [];
  if (typeof raw[0] === 'number') {
    return (raw as number[]).map((v) => ({ value: v }));
  }
  return raw as { value: number }[];
}

export function SparklineWidget({
  data,
  config,
  isLoading,
  error,
}: WidgetComponentProps<SparklineData, SparklineConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const color = config.color ?? 'hsl(var(--primary))';
  const strokeWidth = config.strokeWidth ?? 2;

  if (!data || (Array.isArray(data) && data.length === 0)) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No data points
      </div>
    );
  }

  const points = normaliseData(data);

  return (
    <div className="h-full w-full p-1">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={strokeWidth}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
