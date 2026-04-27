/**
 * HeatmapWidget
 *
 * CSS grid-based heatmap visualization (no recharts dependency).
 * Values are normalized to [0, 1] and color-interpolated from
 * slate-100 (cold) to blue-600 (hot). Row and column labels are
 * displayed along the edges.
 *
 * Data binding:
 *   source: static:: | hydra::nodes
 *   endpoint: /nodes  (for service-count heatmap across nodes)
 *
 * Accepted data shapes:
 *   1. Native: { rows: string[], columns: string[], values: number[][] }
 *   2. [{ x, y, v }] tuples — 2D sparse data → builds rows/columns/values grid
 *   3. Raw entity array (e.g., nodes) → builds a single-row heatmap of
 *      numeric fields (servicesCount, profileCount, etc.)
 *
 * Config options:
 *   colorScale: "blue-red" | "green-red" | "grayscale" | "spectral"
 *   showLegend: boolean
 *   aggregation: "sum" | "avg" | "max"
 *   showValues: boolean
 */

import { useMemo } from 'react';
import { Grid3x3 } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface HeatmapData {
  rows: string[];
  columns: string[];
  values: number[][];
}

interface HeatmapConfig extends Record<string, unknown> {
  showValues?: boolean;
  colorScale?: string;
  showLegend?: boolean;
  aggregation?: string;
}

/**
 * Build a HeatmapData from sparse [{ x, y, v }] tuples.
 */
function buildHeatmapFromTuples(
  tuples: { x: string; y: string; v: number }[],
): HeatmapData {
  const rowSet = new Set<string>();
  const colSet = new Set<string>();
  for (const t of tuples) {
    rowSet.add(t.y);
    colSet.add(t.x);
  }
  const rows = Array.from(rowSet).sort();
  const columns = Array.from(colSet).sort();
  const values = rows.map((row) =>
    columns.map((col) => {
      const t = tuples.find((tt) => tt.y === row && tt.x === col);
      return t ? t.v : 0;
    }),
  );
  return { rows, columns, values };
}

/**
 * Build a HeatmapData from a flat entity array.
 * Rows are entity names, columns are numeric fields found in the first entity.
 */
function buildHeatmapFromEntityArray(
  items: Record<string, unknown>[],
): HeatmapData {
  // Find all numeric fields across the first few items
  const numericFields = new Set<string>();
  for (const item of items.slice(0, 3)) {
    for (const [key, val] of Object.entries(item)) {
      if (typeof val === 'number') numericFields.add(key);
    }
  }
  const columns = Array.from(numericFields);

  // Use displayName / name / nodeId / id as row label
  const rows = items.map((item) =>
    String(
      item.displayName ??
        item.name ??
        item.nodeId ??
        item.serviceId ??
        item.id ??
        'Unknown',
    ),
  );

  const values = items.map((item) =>
    columns.map((col) => Number(item[col] ?? 0)),
  );

  return { rows, columns, values };
}

/**
 * Normalize incoming data to HeatmapData.
 *
 * Handles:
 *   - Native { rows, columns, values } shape
 *   - [{ x, y, v }] sparse tuples
 *   - Raw entity array
 */
function normalizeHeatmapData(raw: unknown): HeatmapData | null {
  if (raw == null) return null;

  // Native shape
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (
      Array.isArray(obj.rows) &&
      Array.isArray(obj.columns) &&
      Array.isArray(obj.values)
    ) {
      return raw as HeatmapData;
    }
  }

  if (Array.isArray(raw) && raw.length > 0) {
    const first = raw[0] as Record<string, unknown>;

    // [{ x, y, v }] tuples
    if ('x' in first && 'y' in first && 'v' in first) {
      return buildHeatmapFromTuples(
        raw as { x: string; y: string; v: number }[],
      );
    }

    // Raw entity array → build from numeric fields
    if (typeof first === 'object') {
      const result = buildHeatmapFromEntityArray(
        raw as Record<string, unknown>[],
      );
      if (result.columns.length > 0 && result.rows.length > 0) return result;
    }
  }

  return null;
}

/**
 * Interpolate between two RGB colors.
 */
function interpolateColor(
  r1: number, g1: number, b1: number,
  r2: number, g2: number, b2: number,
  t: number,
): string {
  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Map a normalized value [0, 1] to a color from slate-100 to blue-600.
 * Uses a three-stop gradient: slate-100 -> blue-300 -> blue-600.
 */
function valueToColor(normalized: number): string {
  const clamped = Math.max(0, Math.min(1, normalized));

  if (clamped < 0.5) {
    // slate-100 (241,245,249) -> blue-300 (147,197,253)
    const t = clamped / 0.5;
    return interpolateColor(241, 245, 249, 147, 197, 253, t);
  }

  // blue-300 (147,197,253) -> blue-600 (37,99,235)
  const t = (clamped - 0.5) / 0.5;
  return interpolateColor(147, 197, 253, 37, 99, 235, t);
}

/**
 * Choose black or white text based on the background luminance.
 */
function contrastText(normalized: number): string {
  return normalized > 0.6 ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.7)';
}

export function HeatmapWidget({
  data: rawData,
  config,
  isLoading,
  error,
}: WidgetComponentProps<unknown, HeatmapConfig>) {
  const data = useMemo(() => normalizeHeatmapData(rawData), [rawData]);
  const typedConfig = config as HeatmapConfig;
  const showValues = typedConfig.showValues !== false;

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Grid3x3 className="h-5 w-5" />
        <div className="text-sm">No heatmap data</div>
      </div>
    );
  }

  if (
    !data.rows ||
    data.rows.length === 0 ||
    !data.columns ||
    data.columns.length === 0 ||
    !data.values ||
    data.values.length === 0
  ) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Grid3x3 className="h-5 w-5" />
        <div className="text-sm">No heatmap data</div>
      </div>
    );
  }

  // Compute min/max across all values for normalization
  let minVal = Infinity;
  let maxVal = -Infinity;

  for (const row of data.values) {
    for (const val of row) {
      if (val < minVal) minVal = val;
      if (val > maxVal) maxVal = val;
    }
  }

  const range = maxVal - minVal;

  const normalize = (val: number): number => {
    if (range === 0) return 0.5;
    return (val - minVal) / range;
  };

  const colCount = data.columns.length;

  return (
    <div className="flex h-full flex-col gap-2 overflow-auto">
      {/* Column headers */}
      <div
        className="grid gap-px"
        style={{
          gridTemplateColumns: `minmax(60px, auto) repeat(${colCount}, minmax(32px, 1fr))`,
        }}
      >
        {/* Empty corner cell */}
        <div />
        {data.columns.map((col) => (
          <div
            key={col}
            className="truncate px-1 text-center text-[10px] font-medium text-muted-foreground"
            title={col}
          >
            {col}
          </div>
        ))}
      </div>

      {/* Rows */}
      <div className="flex min-h-0 flex-1 flex-col gap-px overflow-y-auto">
        {data.rows.map((rowLabel, rowIdx) => {
          const rowValues = data.values[rowIdx] ?? [];

          return (
            <div
              key={rowLabel}
              className="grid gap-px"
              style={{
                gridTemplateColumns: `minmax(60px, auto) repeat(${colCount}, minmax(32px, 1fr))`,
              }}
            >
              {/* Row label */}
              <div
                className="flex items-center truncate pr-2 text-[10px] font-medium text-muted-foreground"
                title={rowLabel}
              >
                {rowLabel}
              </div>

              {/* Cells */}
              {data.columns.map((col, colIdx) => {
                const raw = rowValues[colIdx] ?? 0;
                const norm = normalize(raw);
                const bgColor = valueToColor(norm);
                const textColor = contrastText(norm);

                return (
                  <div
                    key={`${rowLabel}-${col}`}
                    className="flex items-center justify-center rounded-sm transition-transform hover:scale-105"
                    style={{
                      backgroundColor: bgColor,
                      minHeight: '28px',
                    }}
                    title={`${rowLabel} / ${col}: ${raw}`}
                  >
                    {showValues && (
                      <span
                        className="text-[10px] font-medium tabular-nums"
                        style={{ color: textColor }}
                      >
                        {Number.isInteger(raw) ? raw : raw.toFixed(1)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Legend bar */}
      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] text-muted-foreground tabular-nums">{minVal}</span>
        <div
          className="h-2 flex-1 rounded-full"
          style={{
            background: `linear-gradient(to right, ${valueToColor(0)}, ${valueToColor(0.5)}, ${valueToColor(1)})`,
          }}
        />
        <span className="text-[10px] text-muted-foreground tabular-nums">{maxVal}</span>
      </div>
    </div>
  );
}
