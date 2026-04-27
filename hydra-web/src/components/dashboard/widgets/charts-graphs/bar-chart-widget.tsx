/**
 * BarChartWidget
 *
 * Multi-series bar chart using recharts. Categories form the x-axis,
 * and each series becomes a grouped bar. Data is transformed from the
 * category/series format into recharts' row-based format.
 *
 * Data binding:
 *   source: hydra::nodes | hydra::services | static::
 *   endpoint: /nodes | /services
 *
 * Accepted data shapes:
 *   1. Native: { categories: string[], series: [{ name, data: number[] }] }
 *   2. Raw entity array — auto-aggregated by a grouping field:
 *      - nodes: counted by class (compute/networking/iot)
 *      - services: counted by runtime or status
 *      - networks: counted by type
 *      - any array with a string field → counted by that field
 *   3. [{ label, value }] tuples — single series
 *
 * Config options:
 *   orientation: "vertical" | "horizontal"
 *   stacking: "none" | "normal" | "percent"
 *   showValues: boolean
 *   showGrid: boolean
 *   showLegend: boolean
 *   groupBy: string field name to count by (used with raw arrays)
 */

import { useMemo } from 'react';
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
  stacking?: string;
  orientation?: string;
  showValues?: boolean;
  groupBy?: string;
}

/**
 * Pick the best field to group-count an entity array by.
 * Priority: config.groupBy → 'class' → 'runtime' → 'status' → 'type' → first string field.
 */
function pickGroupByField(
  items: Record<string, unknown>[],
  configGroupBy?: string,
): string {
  if (configGroupBy && configGroupBy in items[0]) return configGroupBy;
  for (const candidate of ['class', 'runtime', 'status', 'type']) {
    if (candidate in items[0]) return candidate;
  }
  // Fall back to first string-valued field
  for (const key of Object.keys(items[0])) {
    if (typeof items[0][key] === 'string') return key;
  }
  return Object.keys(items[0])[0];
}

/**
 * Aggregate an array of entity objects into BarChartData by counting occurrences
 * of each value in `groupByField`.
 */
function aggregateEntitiesForBarChart(
  items: Record<string, unknown>[],
  groupByField: string,
): BarChartData {
  const counts = new Map<string, number>();
  for (const item of items) {
    const key = String(item[groupByField] ?? 'unknown');
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const sorted = Array.from(counts.entries()).sort(([, a], [, b]) => b - a);
  return {
    categories: sorted.map(([label]) => label),
    series: [
      {
        name: groupByField.charAt(0).toUpperCase() + groupByField.slice(1),
        data: sorted.map(([, count]) => count),
      },
    ],
  };
}

/**
 * Normalize incoming data to BarChartData.
 *
 * Handles:
 *   - Native { categories, series } shape
 *   - [{ label, value }] tuples
 *   - Raw entity array → aggregated by best field
 */
function normalizeBarChartData(
  raw: unknown,
  configGroupBy?: string,
): BarChartData | null {
  if (raw == null) return null;

  // Native shape
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.categories) && Array.isArray(obj.series)) {
      return raw as BarChartData;
    }
  }

  // Array
  if (Array.isArray(raw) && raw.length > 0) {
    const first = raw[0] as Record<string, unknown>;

    // [{ label, value }] tuples
    if ('label' in first && 'value' in first) {
      return {
        categories: (raw as Record<string, unknown>[]).map((d) => String(d.label)),
        series: [
          {
            name: 'Value',
            data: (raw as Record<string, unknown>[]).map((d) => Number(d.value)),
          },
        ],
      };
    }

    // Raw entity array → aggregate
    if (typeof first === 'object') {
      const groupByField = pickGroupByField(
        raw as Record<string, unknown>[],
        configGroupBy,
      );
      return aggregateEntitiesForBarChart(
        raw as Record<string, unknown>[],
        groupByField,
      );
    }
  }

  return null;
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
  data: rawData,
  config,
  isLoading,
  error,
  dimensions,
}: WidgetComponentProps<unknown, BarChartConfig>) {
  const typedConfig = config as BarChartConfig;
  const data = useMemo(
    () => normalizeBarChartData(rawData, typedConfig.groupBy as string | undefined),
    [rawData, typedConfig.groupBy],
  );
  const showGrid = typedConfig.showGrid !== false;
  const showLegend = typedConfig.showLegend !== false;
  const stacked = typedConfig.stacked === true || typedConfig.stacking === 'normal';

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
