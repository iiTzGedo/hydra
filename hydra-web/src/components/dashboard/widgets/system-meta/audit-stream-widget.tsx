/**
 * AuditStreamWidget -- scrollable feed of audit log entries showing
 * action, resource, actor, and success/failure status.
 *
 * Data shape:
 *   { entries: { timestamp: string; action: string; resourceType: string;
 *     resourceId: string; actorId?: string; success?: boolean }[] }
 */

import { ScrollText, Check, X } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface AuditEntry {
  timestamp: string;
  action: string;
  resourceType: string;
  resourceId: string;
  actorId?: string;
  success?: boolean;
}

interface AuditStreamData {
  entries: AuditEntry[];
}

function formatTimestamp(isoString: string): string {
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return isoString;
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function AuditStreamWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<AuditStreamData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.entries.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <ScrollText className="h-5 w-5" />
        <div className="text-sm">No audit entries</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-auto p-1">
      <div className="space-y-0.5">
        {data.entries.map((entry, index) => {
          const isSuccess = entry.success !== false;

          return (
            <div
              key={`${entry.timestamp}-${index}`}
              className="flex items-start gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted/30"
            >
              {/* Success/failure indicator */}
              <div className="mt-0.5 shrink-0">
                {isSuccess ? (
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                ) : (
                  <X className="h-3.5 w-3.5 text-red-500" />
                )}
              </div>

              {/* Content */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="rounded bg-muted px-1 py-0.5 text-[10px] font-semibold uppercase text-muted-foreground">
                    {entry.action}
                  </span>
                  <span className="text-[10px] text-muted-foreground/60">
                    {entry.resourceType}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2">
                  <span className="truncate font-mono text-xs text-foreground">
                    {entry.resourceId}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground/60">
                  <span className="tabular-nums">
                    {formatTimestamp(entry.timestamp)}
                  </span>
                  {entry.actorId && (
                    <>
                      <span className="text-border">|</span>
                      <span className="truncate">{entry.actorId}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
