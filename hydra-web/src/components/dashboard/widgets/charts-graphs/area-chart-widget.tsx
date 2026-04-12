/**
 * AreaChartWidget
 *
 * Multi-series area chart using recharts with gradient fills.
 * Supports stacked mode via `config.stacked`. Each series gets
 * a unique color from the preset palette and a matching gradient fill.
 */

import { AreaChart as AreaChartIcon } from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface DataPoint {
  x: string | number;
  y: number;
}

interface Series {
  name: string;
  data: DataPoint[];
}

interface AreaChartData {
  series: Series[];
}

interface AreaChartConfig extends Record<string, unknown> {
  stacked?: boolean;
  showGrid?: boolean;
  showLegend?: boolean;
}

const SERIES_COLORS = [
  '#3b82f6', // blue-500
  '#10b981', // emerald-500
  '#f59e0b', // amber-500
  '#ef4444', // red-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#06b6d4', // cyan-500
  '#f97316', // orange-500
];

/**
 * Merge multiple series into a unified dataset keyed by x-value.
 */
function mergeSeriesData(series: Series[]): Record<string, unknown>[] {
  const map = new Map<string | number, Record<string, unknown>>();

  for (const s of series) {
    for (const point of s.data) {
      const existing = map.get(point.x) ?? { x: point.x };
      existing[s.name] = point.y;
      map.set(point.x, existing);
    }
  }

  return Array.from(map.values());
}

export function AreaChartWidget({
  data,
  config,
  isLoading,
  error,
  dimensions,
}: WidgetComponentProps<AreaChartData, AreaChartConfig>) {
  const typedConfig = config as AreaChartConfig;
  const stacked = typedConfig.stacked === true;
  const showGrid = typedConfig.showGrid !== false;
  const showLegend = typedConfig.showLegend !== false;

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <AreaChartIcon className="h-5 w-5" />
        <div className="text-sm">Configure a data source</div>
      </div>
    );
  }

  if (!data.series || data.series.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <AreaChartIcon className="h-5 w-5" />
        <div className="text-sm">No chart data</div>
      </div>
    );
  }

  const merged = mergeSeriesData(data.series);
  const isCompact = dimensions.height < 200;
  const stackId = stacked ? 'stack' : undefined;

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={merged} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
          <defs>
            {data.series.map((s, idx) => {
              const color = SERIES_COLORS[idx % SERIES_COLORS.length];
              return (
                <linearGradient
                  key={s.name}
                  id={`gradient-${idx}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="5%" stopColor={color} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={color} stopOpacity={0.05} />
                </linearGradient>
              );
            })}
          </defs>

          {showGrid && (
            <CartesianGrid
              strokeDasharray="3 3"
              className="stroke-border/30"
            />
          )}
          <XAxis
            dataKey="x"
            tick={{ fontSize: 11 }}
            className="text-muted-foreground"
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            className="text-muted-foreground"
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              borderColor: 'hsl(var(--border))',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelStyle={{ fontWeight: 600 }}
          />
          {showLegend && !isCompact && (
            <Legend
              wrapperStyle={{ fontSize: '12px' }}
              iconType="square"
            />
          )}
          {data.series.map((s, idx) => (
            <Area
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
              strokeWidth={2}
              fill={`url(#gradient-${idx})`}
              stackId={stackId}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
