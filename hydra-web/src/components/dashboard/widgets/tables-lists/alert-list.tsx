/**
 * AlertListWidget
 *
 * Prioritized alert list with severity-based icons and colors.
 * Acknowledged alerts are visually dimmed. An empty state shows
 * a green check icon indicating no active alerts.
 *
 * Data binding:
 *   source: hydra::notifications
 *   endpoint: /notifications
 *   params: { status: "active", tierMin: 3 }  (warning tier and above)
 *
 * Accepts two data shapes:
 *   1. Envelope: { alerts: Alert[] }
 *   2. Raw array: Notification[] from /notifications API (auto-normalized)
 *      Maps: notificationId → id, tier → severity (5=critical,4=warning,1-3=info),
 *            createdAt → timestamp, acknowledgedAt → acknowledged
 *
 * Config options:
 *   severityFilter: "all" | "critical" | "warning" | "info"
 *   limit: number (max items to display)
 */

import { useMemo } from 'react';
import { AlertTriangle, Info, CheckCircle, Bell } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface Alert {
  id: string;
  title: string;
  severity: string;
  timestamp: string;
  acknowledged?: boolean;
}

interface AlertListData {
  alerts: Alert[];
}

interface AlertListConfig extends Record<string, unknown> {
  severityFilter?: string;
  limit?: number;
}

/**
 * Map a notification tier number to a severity string.
 * Tier 5 = critical, 4 = warning, 3 = warning, 1-2 = info
 */
function tierToSeverity(tier: unknown): string {
  const t = Number(tier);
  if (t >= 5) return 'critical';
  if (t >= 3) return 'warning';
  return 'info';
}

/**
 * Normalize incoming data to AlertListData envelope.
 * Handles both explicit envelope and raw Notification[] from the API.
 */
function normalizeAlertListData(raw: unknown): AlertListData | null {
  if (raw == null) return null;

  // Already envelope-shaped
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.alerts)) {
      return { alerts: obj.alerts as Alert[] };
    }
  }

  // Raw array of Notification from /notifications API
  if (Array.isArray(raw)) {
    return {
      alerts: (raw as Record<string, unknown>[]).map((n) => ({
        id: String(n.notificationId ?? n.id ?? ''),
        title: String(n.title ?? n.message ?? ''),
        severity: typeof n.severity === 'string'
          ? n.severity
          : tierToSeverity(n.tier),
        timestamp: String(n.createdAt ?? n.timestamp ?? new Date().toISOString()),
        acknowledged: Boolean(n.acknowledgedAt),
      })),
    };
  }

  return null;
}

/** Severity ordering for sort priority (lower = more severe). */
const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  warning: 1,
  info: 2,
};

function getSeverityIcon(severity: string) {
  switch (severity.toLowerCase()) {
    case 'critical':
      return <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-500" />;
    case 'warning':
      return <AlertTriangle className="h-4 w-4 flex-shrink-0 text-yellow-500" />;
    case 'info':
      return <Info className="h-4 w-4 flex-shrink-0 text-blue-500" />;
    default:
      return <Info className="h-4 w-4 flex-shrink-0 text-muted-foreground" />;
  }
}

function getSeverityBorder(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical':
      return 'border-l-red-500';
    case 'warning':
      return 'border-l-yellow-500';
    case 'info':
      return 'border-l-blue-500';
    default:
      return 'border-l-muted';
  }
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;

  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHr = Math.floor(diffMin / 60);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function AlertListWidget({
  data: rawData,
  config,
  isLoading,
  error,
}: WidgetComponentProps<unknown, AlertListConfig>) {
  const data = useMemo(() => normalizeAlertListData(rawData), [rawData]);
  const typedConfig = config as AlertListConfig;

  // Apply severity filter and limit from config
  const visibleAlerts = useMemo(() => {
    if (!data?.alerts) return [];
    let alerts = data.alerts;

    const severityFilter = typedConfig.severityFilter ?? 'all';
    if (severityFilter !== 'all') {
      const SEVERITY_HIERARCHY: Record<string, number> = { critical: 3, warning: 2, info: 1 };
      const minLevel = SEVERITY_HIERARCHY[severityFilter] ?? 1;
      alerts = alerts.filter((a) => (SEVERITY_HIERARCHY[a.severity.toLowerCase()] ?? 1) >= minLevel);
    }

    const limit = (typedConfig.limit as number | undefined) ?? 50;
    return alerts.slice(0, limit);
  }, [data, typedConfig]);

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Bell className="h-5 w-5" />
        <div className="text-sm">Configure a data source</div>
      </div>
    );
  }

  if (visibleAlerts.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2">
        <CheckCircle className="h-6 w-6 text-emerald-500" />
        <div className="text-sm text-muted-foreground">No active alerts</div>
      </div>
    );
  }

  // Sort by severity priority (critical first), then by timestamp (newest first)
  const sorted = [...visibleAlerts].sort((a, b) => {
    const aSev = SEVERITY_ORDER[a.severity.toLowerCase()] ?? 3;
    const bSev = SEVERITY_ORDER[b.severity.toLowerCase()] ?? 3;
    if (aSev !== bSev) return aSev - bSev;

    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  return (
    <div className="flex h-full flex-col gap-1.5 overflow-y-auto">
      {sorted.map((alert) => (
        <div
          key={alert.id}
          className={`flex items-start gap-2.5 rounded-md border-l-2 bg-muted/20 px-3 py-2 ${getSeverityBorder(alert.severity)} ${
            alert.acknowledged ? 'opacity-50' : ''
          }`}
        >
          {getSeverityIcon(alert.severity)}

          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span
                className={`truncate text-sm font-medium ${
                  alert.acknowledged
                    ? 'text-muted-foreground line-through'
                    : 'text-foreground'
                }`}
              >
                {alert.title}
              </span>
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">
              {formatTimestamp(alert.timestamp)}
              {alert.acknowledged && (
                <span className="ml-2 text-emerald-600">Acknowledged</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
