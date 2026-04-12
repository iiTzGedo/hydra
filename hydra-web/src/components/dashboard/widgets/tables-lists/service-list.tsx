/**
 * ServiceListWidget
 *
 * Compact service list with status indicators, runtime badges, and
 * optional port display. Each row shows a colored status dot reflecting
 * the service's current state.
 */

import { Server } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ServiceEntry {
  serviceId: string;
  name: string;
  runtime: string;
  status: string;
  port?: number;
}

interface ServiceListData {
  services: ServiceEntry[];
}

const STATUS_COLORS: Record<string, string> = {
  running: 'bg-emerald-500',
  active: 'bg-emerald-500',
  healthy: 'bg-emerald-500',
  failed: 'bg-red-500',
  error: 'bg-red-500',
  stopped: 'bg-slate-400',
  inactive: 'bg-slate-400',
  disabled: 'bg-slate-400',
  unknown: 'bg-yellow-500',
  degraded: 'bg-yellow-500',
  starting: 'bg-yellow-500',
  restarting: 'bg-yellow-500',
};

function getStatusColor(status: string): string {
  return STATUS_COLORS[status.toLowerCase()] ?? 'bg-yellow-500';
}

export function ServiceListWidget({
  data,
  config: _config,
  isLoading,
  error,
}: WidgetComponentProps<ServiceListData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Server className="h-5 w-5" />
        <div className="text-sm">Configure a data source</div>
      </div>
    );
  }

  if (!data.services || data.services.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Server className="h-5 w-5" />
        <div className="text-sm">No services</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-1 overflow-y-auto">
      {data.services.map((svc) => (
        <div
          key={svc.serviceId}
          className="flex items-center gap-3 rounded-md px-2 py-1.5 transition-colors hover:bg-muted/40"
        >
          {/* Status dot */}
          <span
            className={`h-2 w-2 flex-shrink-0 rounded-full ${getStatusColor(svc.status)}`}
            title={svc.status}
          />

          {/* Service name */}
          <span className="min-w-0 flex-1 truncate text-sm font-medium">
            {svc.name}
          </span>

          {/* Runtime badge */}
          <span className="flex-shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {svc.runtime}
          </span>

          {/* Port (if present) */}
          {svc.port !== undefined && svc.port !== null && (
            <span className="flex-shrink-0 text-xs tabular-nums text-muted-foreground">
              :{svc.port}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
