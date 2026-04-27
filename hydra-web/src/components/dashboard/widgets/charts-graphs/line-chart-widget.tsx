/**
 * LineChartWidget
 *
 * Multi-series line chart using recharts. Each series is rendered
 * as a distinct colored line with tooltips and an optional legend.
 * Responsive to container dimensions.
 *
 * Data binding:
 *   source: hydra::timeline | static::
 *   endpoint: /timemachine/timeline  (for time-series views)
 *
 * Accepted data shapes:
 *   1. Native: { series: [{ name, data: [{ x, y }] }] }
 *   2. TimelineResponse from /timemachine/timeline — aggregates event count
 *      per hour as a single "Events" series
 *   3. Raw array (any) — treated as a single unnamed series if it has
 *      { x, y } or { t, v } tuples; otherwise falls back to event-count
 *      aggregation if entries have { timestamp } fields
 *
 * Config options:
 *   showLegend: boolean
 *   showGrid: boolean
 *   smoothing: boolean
 *   stacking: "none" | "normal" | "percent"
 */

import { useMemo } from 'react';
import { TrendingUp } from 'lucide-react';
import {
  LineChart,
  Line,
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

interface LineChartData {
  series: Series[];
}

interface LineChartConfig extends Record<string, unknown> {
  showGrid?: boolean;
  showLegend?: boolean;
  smoothing?: boolean;
  stacking?: string;
}

/**
 * Aggregate timeline events into hourly buckets for a line chart.
 * Returns a single "Events" series keyed by hour label.
 */
function aggregateTimelineToSeries(
  events: Record<string, unknown>[],
): LineChartData {
  const buckets = new Map<string, number>();

  for (const e of events) {
    const ts = new Date(String(e.timestamp ?? ''));
    if (Number.isNaN(ts.getTime())) continue;
    // Hour bucket: "HH:00"
    const label = `${String(ts.getHours()).padStart(2, '0')}:00`;
    buckets.set(label, (buckets.get(label) ?? 0) + 1);
  }

  const sorted = Array.from(buckets.entries()).sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return {
    series: [
      {
        name: 'Events',
        data: sorted.map(([label, count]) => ({ x: label, y: count })),
      },
    ],
  };
}

/**
 * Normalize raw data to LineChartData.
 *
 * Handles:
 *   - Native LineChartData with series
 *   - TimelineResponse { events: [...], since, until, total }
 *   - Raw array with { x, y } or { t, v } tuples
 *   - Raw array with { timestamp } → aggregate by hour
 */
function normalizeLineChartData(raw: unknown): LineChartData | null {
  if (raw == null) return null;

  // Native shape
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;

    if (Array.isArray(obj.series)) {
      return { series: obj.series as Series[] };
    }

    // TimelineResponse
    if (Array.isArray(obj.events)) {
      return aggregateTimelineToSeries(
        obj.events as Record<string, unknown>[],
      );
    }
  }

  // Raw array
  if (Array.isArray(raw) && raw.length > 0) {
    const first = raw[0] as Record<string, unknown>;

    // { x, y } tuples
    if ('x' in first && 'y' in first) {
      return {
        series: [
          {
            name: 'Value',
            data: (raw as Record<string, unknown>[]).map((d) => ({
              x: d.x as string | number,
              y: Number(d.y),
            })),
          },
        ],
      };
    }

    // { t, v } tuples
    if ('t' in first && 'v' in first) {
      return {
        series: [
          {
            name: 'Value',
            data: (raw as Record<string, unknown>[]).map((d) => ({
              x: String(d.t),
              y: Number(d.v),
            })),
          },
        ],
      };
    }

    // { timestamp } → aggregate
    if ('timestamp' in first) {
      return aggregateTimelineToSeries(raw as Record<string, unknown>[]);
    }
  }

  return null;
}

/**
 * Preset color palette for chart series. Chosen for visual distinction
 * and reasonable accessibility on both light and dark backgrounds.
 */
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
 * Each row has shape: { x: <value>, series1Name: y1, series2Name: y2, ... }
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

export function LineChartWidget({
  data: rawData,
  config,
  isLoading,
  error,
  dimensions,
}: WidgetComponentProps<unknown, LineChartConfig>) {
  const data = useMemo(() => normalizeLineChartData(rawData), [rawData]);
  const typedConfig = config as LineChartConfig;
  const showGrid = typedConfig.showGrid !== false;
  const showLegend = typedConfig.showLegend !== false;

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <TrendingUp className="h-5 w-5" />
        <div className="text-sm">Configure a data source</div>
      </div>
    );
  }

  if (!data.series || data.series.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <TrendingUp className="h-5 w-5" />
        <div className="text-sm">No chart data</div>
      </div>
    );
  }

  const merged = mergeSeriesData(data.series);
  const isCompact = dimensions.height < 200;

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={merged} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
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
              iconType="line"
            />
          )}
          {data.series.map((s, idx) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
