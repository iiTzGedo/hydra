/**
 * ServiceListWidget
 *
 * Compact service list with status indicators, runtime badges, and
 * optional port display. Each row shows a colored status dot reflecting
 * the service's current state.
 *
 * Data binding:
 *   source: hydra::services
 *   endpoint: /services  (optionally with nodeId param)
 *
 * Accepts two data shapes:
 *   1. Envelope: { services: ServiceEntry[] }
 *   2. Raw array: ServiceSummary[] from /services API (auto-normalized)
 *
 * Config options:
 *   filterByStatus: "all" | "running" | "stopped" | "failed" | "unknown"
 *   groupByNode: boolean (visual grouping, applied client-side)
 */

import { useMemo } from 'react';
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
  nodeId?: string;
}

interface ServiceListData {
  services: ServiceEntry[];
}

interface ServiceListConfig extends Record<string, unknown> {
  filterByStatus?: string;
  groupByNode?: boolean;
}

/**
 * Normalize incoming data to ServiceListData envelope.
 * Handles both explicit envelope and raw ServiceSummary[] from the API.
 */
function normalizeServiceListData(raw: unknown): ServiceListData | null {
  if (raw == null) return null;

  // Already envelope-shaped
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.services)) {
      return { services: obj.services as ServiceEntry[] };
    }
  }

  // Raw array of ServiceSummary from API
  if (Array.isArray(raw)) {
    return {
      services: (raw as Record<string, unknown>[]).map((svc) => ({
        serviceId: String(svc.serviceId ?? svc.id ?? ''),
        name: String(svc.name ?? svc.displayName ?? ''),
        runtime: String(svc.runtime ?? 'unknown'),
        status: String(svc.status ?? 'unknown'),
        nodeId: typeof svc.nodeId === 'string' ? svc.nodeId : undefined,
        // Extract first port from exposure.ports if present
        port:
          typeof svc.exposure === 'object' &&
          svc.exposure !== null &&
          Array.isArray((svc.exposure as Record<string, unknown>).ports) &&
          ((svc.exposure as Record<string, unknown>).ports as unknown[]).length > 0
            ? Number(
                ((svc.exposure as Record<string, unknown>).ports as Record<string, unknown>[])[0]
                  .port,
              ) || undefined
            : undefined,
      })),
    };
  }

  return null;
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
  data: rawData,
  config,
  isLoading,
  error,
}: WidgetComponentProps<unknown, ServiceListConfig>) {
  const data = useMemo(() => normalizeServiceListData(rawData), [rawData]);
  const typedConfig = config as ServiceListConfig;

  // Apply status filter from config
  const visibleServices = useMemo(() => {
    if (!data?.services) return [];
    const filter = typedConfig.filterByStatus ?? 'all';
    if (filter === 'all') return data.services;
    return data.services.filter((s) => s.status.toLowerCase() === filter.toLowerCase());
  }, [data, typedConfig.filterByStatus]);

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

  if (visibleServices.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Server className="h-5 w-5" />
        <div className="text-sm">
          {typedConfig.filterByStatus && typedConfig.filterByStatus !== 'all'
            ? `No ${typedConfig.filterByStatus} services`
            : 'No services'}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-1 overflow-y-auto">
      {visibleServices.map((svc) => (
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
