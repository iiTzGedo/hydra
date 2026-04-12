/**
 * BarChartWidget
 *
 * Multi-series bar chart using recharts. Categories form the x-axis,
 * and each series becomes a grouped bar. Data is transformed from the
 * category/series format into recharts' row-based format.
 */

import { BarChart3 } from 'lucide-react';
import {
  BarChart,
  Bar,
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

interface BarChartSeries {
  name: string;
  data: number[];
}

interface BarChartData {
  categories: string[];
  series: BarChartSeries[];
}

interface BarChartConfig extends Record<string, unknown> {
  showGrid?: boolean;
  showLegend?: boolean;
  stacked?: boolean;
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
 * Transform category/series data into recharts row format.
 *
 * Input: categories=["Jan","Feb"], series=[{name:"CPU", data:[40,60]}]
 * Output: [{name:"Jan", CPU:40}, {name:"Feb", CPU:60}]
 */
function transformData(
  categories: string[],
  series: BarChartSeries[],
): Record<string, unknown>[] {
  return categories.map((cat, i) => {
    const row: Record<string, unknown> = { name: cat };
    for (const s of series) {
      row[s.name] = s.data[i] ?? 0;
    }
    return row;
  });
}

export function BarChartWidget({
  data,
  config,
  isLoading,
  error,
  dimensions,
}: WidgetComponentProps<BarChartData, BarChartConfig>) {
  const typedConfig = config as BarChartConfig;
  const showGrid = typedConfig.showGrid !== false;
  const showLegend = typedConfig.showLegend !== false;
  const stacked = typedConfig.stacked === true;

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <BarChart3 className="h-5 w-5" />
        <div className="text-sm">Configure a data source</div>
      </div>
    );
  }

  if (
    !data.categories ||
    data.categories.length === 0 ||
    !data.series ||
    data.series.length === 0
  ) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <BarChart3 className="h-5 w-5" />
        <div className="text-sm">No chart data</div>
      </div>
    );
  }

  const chartData = transformData(data.categories, data.series);
  const isCompact = dimensions.height < 200;
  const stackId = stacked ? 'stack' : undefined;

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
          {showGrid && (
            <CartesianGrid
              strokeDasharray="3 3"
              className="stroke-border/30"
            />
          )}
          <XAxis
            dataKey="name"
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
            <Bar
              key={s.name}
              dataKey={s.name}
              fill={SERIES_COLORS[idx % SERIES_COLORS.length]}
              stackId={stackId}
              radius={stacked ? undefined : [4, 4, 0, 0]}
              maxBarSize={48}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
