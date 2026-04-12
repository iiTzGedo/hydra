/**
 * ApiStatusWidget -- health dashboard card showing overall API status,
 * version, uptime, and per-check health rows.
 *
 * Data shape:
 *   { status: string; version?: string; uptime?: string;
 *     checks: { name: string; status: string; latencyMs?: number }[] }
 */

import { Activity, CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface HealthCheck {
  name: string;
  status: string;
  latencyMs?: number;
}

interface ApiStatusData {
  status: string;
  version?: string;
  uptime?: string;
  checks: HealthCheck[];
}

const STATUS_CONFIG: Record<
  string,
  { Icon: typeof CheckCircle2; color: string; bg: string; label: string }
> = {
  healthy: {
    Icon: CheckCircle2,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    label: 'Healthy',
  },
  degraded: {
    Icon: AlertCircle,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
    label: 'Degraded',
  },
  unhealthy: {
    Icon: XCircle,
    color: 'text-red-500',
    bg: 'bg-red-500/10',
    label: 'Unhealthy',
  },
};

const DEFAULT_STATUS_CONFIG = {
  Icon: Activity,
  color: 'text-gray-400',
  bg: 'bg-gray-500/10',
  label: 'Unknown',
};

function getCheckStatusDot(status: string): string {
  const s = status.toLowerCase();
  if (s === 'healthy' || s === 'ok' || s === 'pass') return 'bg-emerald-500';
  if (s === 'degraded' || s === 'warn') return 'bg-amber-500';
  return 'bg-red-500';
}

export function ApiStatusWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<ApiStatusData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Activity className="h-5 w-5" />
        <div className="text-sm">API status unavailable</div>
      </div>
    );
  }

  const config =
    STATUS_CONFIG[data.status.toLowerCase()] ?? DEFAULT_STATUS_CONFIG;
  const { Icon: StatusIcon, color, bg, label } = config;

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-1">
      {/* Overall status */}
      <div className={`flex items-center gap-3 rounded-lg p-2.5 ${bg}`}>
        <StatusIcon className={`h-6 w-6 shrink-0 ${color}`} />
        <div className="min-w-0 flex-1">
          <div className={`text-sm font-semibold ${color}`}>{label}</div>
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
            {data.version && <span>v{data.version}</span>}
            {data.version && data.uptime && <span className="text-border">|</span>}
            {data.uptime && <span>Up: {data.uptime}</span>}
          </div>
        </div>
      </div>

      {/* Health checks */}
      {data.checks.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Checks
          </div>
          {data.checks.map((check) => (
            <div
              key={check.name}
              className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/20"
            >
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${getCheckStatusDot(check.status)}`}
              />
              <span className="flex-1 truncate text-xs">{check.name}</span>
              <span className="shrink-0 text-[10px] capitalize text-muted-foreground">
                {check.status}
              </span>
              {check.latencyMs != null && (
                <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground/60">
                  {check.latencyMs}ms
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
