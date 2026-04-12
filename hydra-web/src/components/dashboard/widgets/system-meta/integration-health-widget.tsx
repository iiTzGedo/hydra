/**
 * IntegrationHealthWidget -- grid of integration cards showing plugin
 * health status with a colored status dot.
 *
 * Data shape:
 *   { integrations: { pluginId: string; name: string; status: string;
 *     lastChecked?: string }[] }
 *
 * Status colors: healthy=green, degraded=yellow, unavailable=red.
 */

import { Plug } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface IntegrationEntry {
  pluginId: string;
  name: string;
  status: string;
  lastChecked?: string;
}

interface IntegrationHealthData {
  integrations: IntegrationEntry[];
}

const STATUS_DOT_COLORS: Record<string, string> = {
  healthy: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  unavailable: 'bg-red-500',
};

const STATUS_LABELS: Record<string, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  unavailable: 'Unavailable',
};

function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;

  if (Number.isNaN(diffMs)) return isoString;

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function IntegrationHealthWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<IntegrationHealthData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.integrations.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Plug className="h-5 w-5" />
        <div className="text-sm">No integrations configured</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-1">
      <div className="grid grid-cols-2 gap-2">
        {data.integrations.map((integration) => {
          const dotColor =
            STATUS_DOT_COLORS[integration.status.toLowerCase()] ?? 'bg-gray-400';
          const statusLabel =
            STATUS_LABELS[integration.status.toLowerCase()] ?? integration.status;

          return (
            <div
              key={integration.pluginId}
              className="flex items-start gap-2.5 rounded-lg border border-border/60 bg-muted/10 p-2.5 transition-colors hover:bg-muted/20"
            >
              <span
                className={`mt-1 h-2 w-2 shrink-0 rounded-full ${dotColor}`}
                title={statusLabel}
              />
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-semibold">
                  {integration.name}
                </div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">
                  {statusLabel}
                </div>
                {integration.lastChecked && (
                  <div className="mt-0.5 text-[10px] text-muted-foreground/60">
                    Checked {formatRelativeTime(integration.lastChecked)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
