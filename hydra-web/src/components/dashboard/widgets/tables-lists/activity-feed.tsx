/**
 * ActivityFeedWidget
 *
 * Chronological feed of infrastructure events. Each entry shows a
 * relative timestamp, an action description, and an optional
 * resource link for navigation.
 */

import { Clock, Activity, ExternalLink } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ActivityEvent {
  timestamp: string;
  action: string;
  description: string;
  resourceType?: string;
  resourceId?: string;
}

interface ActivityFeedData {
  events: ActivityEvent[];
}

/**
 * Compute a human-readable relative time string from an ISO timestamp.
 */
function relativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();

  if (Number.isNaN(then)) return isoString;

  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;

  return new Date(isoString).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

export function ActivityFeedWidget({
  data,
  config: _config,
  isLoading,
  error,
  onNavigate,
}: WidgetComponentProps<ActivityFeedData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Activity className="h-5 w-5" />
        <div className="text-sm">Configure a data source</div>
      </div>
    );
  }

  if (!data.events || data.events.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Activity className="h-5 w-5" />
        <div className="text-sm">No recent activity</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-0 overflow-y-auto">
      {data.events.map((event, idx) => {
        const hasLink = event.resourceType && event.resourceId;
        const linkPath = hasLink
          ? `/${event.resourceType}/${event.resourceId}`
          : null;

        return (
          <div
            key={`${event.timestamp}-${idx}`}
            className="flex gap-3 border-b border-border/40 px-1 py-2.5 last:border-0"
          >
            {/* Timestamp column */}
            <div className="flex flex-shrink-0 items-start gap-1 pt-0.5 text-muted-foreground">
              <Clock className="h-3 w-3 mt-0.5" />
              <span className="w-16 text-xs tabular-nums">
                {relativeTime(event.timestamp)}
              </span>
            </div>

            {/* Content */}
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium leading-snug">
                {event.action}
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                {event.description}
              </div>
            </div>

            {/* Optional resource link */}
            {linkPath && onNavigate && (
              <button
                type="button"
                className="flex-shrink-0 self-center rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                onClick={() => onNavigate(linkPath)}
                title={`View ${event.resourceType}: ${event.resourceId}`}
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
