/**
 * CapacityPanelWidget -- grouped horizontal bars showing resource utilization
 * across infrastructure groups.
 *
 * Data shape:
 *   { groups: { name: string; resources: { label: string; used: number;
 *     total: number }[] }[] }
 *
 * Bar coloring: green < 70%, yellow < 90%, red >= 90% utilization.
 */

import { BarChart3 } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface CapacityResource {
  label: string;
  used: number;
  total: number;
}

interface CapacityGroup {
  name: string;
  resources: CapacityResource[];
}

interface CapacityPanelData {
  groups: CapacityGroup[];
}

function getUtilizationColor(percent: number): string {
  if (percent >= 90) return 'bg-red-500';
  if (percent >= 70) return 'bg-amber-500';
  return 'bg-emerald-500';
}

function getUtilizationTextColor(percent: number): string {
  if (percent >= 90) return 'text-red-500';
  if (percent >= 70) return 'text-amber-500';
  return 'text-emerald-500';
}

function formatValue(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

export function CapacityPanelWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<CapacityPanelData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.groups.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <BarChart3 className="h-5 w-5" />
        <div className="text-sm">Configure capacity data source</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-1">
      {data.groups.map((group) => (
        <div key={group.name} className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {group.name}
          </h4>
          <div className="space-y-2">
            {group.resources.map((resource) => {
              const percent =
                resource.total > 0
                  ? Math.min((resource.used / resource.total) * 100, 100)
                  : 0;
              const barColor = getUtilizationColor(percent);
              const textColor = getUtilizationTextColor(percent);

              return (
                <div key={`${group.name}-${resource.label}`} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium">{resource.label}</span>
                    <span className={`font-medium tabular-nums ${textColor}`}>
                      {formatValue(resource.used)} / {formatValue(resource.total)}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${barColor}`}
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                  <div className="text-right text-[10px] text-muted-foreground tabular-nums">
                    {percent.toFixed(1)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
