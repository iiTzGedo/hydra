/**
 * DonutChartWidget -- recharts PieChart with a 60% inner radius
 * (donut style) and a legend rendered below.
 *
 * Data shape: { name: string; value: number; color?: string }[]
 * Config:     (none required)
 *
 * A preset palette is used when entries omit a `color` field.
 */

import { PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer } from 'recharts';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface DonutSlice {
  name: string;
  value: number;
  color?: string;
}

type DonutChartData = DonutSlice[];

const PRESET_PALETTE = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5, 280 60% 55%))',
  '#06b6d4', // cyan-500
  '#f97316', // orange-500
  '#8b5cf6', // violet-500
];

const tooltipStyle = {
  backgroundColor: 'hsl(var(--popover))',
  border: '1px solid hsl(var(--border))',
  borderRadius: '8px',
  color: 'hsl(var(--popover-foreground))',
  fontSize: '12px',
};

export function DonutChartWidget({
  data,
  config: _config,
  isLoading,
  error,
}: WidgetComponentProps<DonutChartData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const slices = Array.isArray(data) ? data : [];

  if (slices.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No chart data
      </div>
    );
  }

  return (
    <div className="h-full w-full p-1">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={slices}
            cx="50%"
            cy="45%"
            innerRadius="60%"
            outerRadius="85%"
            paddingAngle={2}
            dataKey="value"
            nameKey="name"
            stroke="none"
          >
            {slices.map((entry, index) => (
              <Cell
                key={`${entry.name}-${index}`}
                fill={entry.color ?? PRESET_PALETTE[index % PRESET_PALETTE.length]}
              />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend
            verticalAlign="bottom"
            height={32}
            formatter={(value: string) => (
              <span style={{ color: 'hsl(var(--foreground))', fontSize: '12px' }}>
                {value}
              </span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
