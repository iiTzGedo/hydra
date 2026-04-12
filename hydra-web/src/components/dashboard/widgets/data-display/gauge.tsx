/**
 * GaugeWidget -- semicircular gauge rendered via a recharts PieChart
 * with a 270-degree arc. Value shown as centered text.
 *
 * Data shape: { value: number }
 * Config:     { min?: number; max?: number; units?: string }
 *
 * Color thresholds (percentage of range):
 *   green  < 60%
 *   yellow < 85%
 *   red   >= 85%
 */

import { PieChart, Pie, Cell } from 'recharts';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface GaugeData {
  value: number;
}

interface GaugeConfig extends Record<string, unknown> {
  min?: number;
  max?: number;
  units?: string;
}

/** Map a percentage to a threshold color. */
function gaugeColor(pct: number): string {
  if (pct >= 85) return '#ef4444'; // red-500
  if (pct >= 60) return '#eab308'; // yellow-500
  return '#22c55e'; // green-500
}

const TRACK_COLOR = 'hsl(var(--muted))';

export function GaugeWidget({
  data,
  config,
  isLoading,
  error,
  dimensions,
}: WidgetComponentProps<GaugeData, GaugeConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const min = config.min ?? 0;
  const max = config.max ?? 100;
  const units = config.units ?? '%';
  const rawValue = data?.value ?? null;
  const clamped = rawValue !== null ? Math.max(min, Math.min(max, rawValue)) : 0;
  const range = max - min || 1;
  const pct = ((clamped - min) / range) * 100;

  // We use a 270-degree arc: filled portion + remaining track
  const filledAngle = (pct / 100) * 270;
  const trackAngle = 270 - filledAngle;

  const pieData = [
    { name: 'value', value: filledAngle },
    { name: 'track', value: trackAngle },
  ];

  // Compute responsive sizing from available dimensions
  const size = Math.min(dimensions.width, dimensions.height, 240);
  const outerRadius = size * 0.4;
  const innerRadius = outerRadius * 0.75;

  const fill = rawValue !== null ? gaugeColor(pct) : TRACK_COLOR;

  return (
    <div className="flex h-full flex-col items-center justify-center">
      <div className="relative" style={{ width: size, height: size * 0.65 }}>
        <PieChart width={size} height={size * 0.65}>
          <Pie
            data={pieData}
            cx={size / 2}
            cy={size * 0.55}
            startAngle={225}
            endAngle={-45}
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            dataKey="value"
            stroke="none"
            isAnimationActive={false}
          >
            <Cell fill={fill} />
            <Cell fill={TRACK_COLOR} />
          </Pie>
        </PieChart>
        {/* Centered value text */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-end pb-1"
          style={{ pointerEvents: 'none' }}
        >
          <span className="text-2xl font-bold leading-none" style={{ color: fill }}>
            {rawValue !== null ? formatGaugeValue(rawValue) : '\u2014'}
          </span>
          <span className="text-xs text-muted-foreground">{units}</span>
        </div>
      </div>
    </div>
  );
}

function formatGaugeValue(value: number): string {
  if (Number.isInteger(value)) return value.toString();
  return value.toFixed(1);
}
