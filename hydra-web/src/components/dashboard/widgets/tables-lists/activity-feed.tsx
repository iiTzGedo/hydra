/**
 * ActivityFeedWidget
 *
 * Chronological feed of infrastructure events. Each entry shows a
 * relative timestamp, an action description, and an optional
 * resource link for navigation.
 *
 * Data binding:
 *   source: hydra::timeline
 *   endpoint: /timemachine/timeline
 *   params: { limit: 25 }
 *
 * Accepts two data shapes:
 *   1. Envelope: { events: ActivityEvent[] }
 *   2. TimelineResponse from /timemachine/timeline: { events: TimelineEvent[], ... }
 *      Maps: eventType → action, description → description,
 *            entityType → resourceType, entityId → resourceId
 *   3. Raw array: TimelineEvent[] (auto-normalized)
 *
 * Config options:
 *   limit: number (max events to display, default 25)
 *   showAvatars: boolean (currently no-op, reserved)
 */

import { useMemo } from 'react';
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

interface ActivityFeedConfig extends Record<string, unknown> {
  limit?: number;
  showAvatars?: boolean;
}

/**
 * Map a timeline eventType string to a human-readable action label.
 */
function eventTypeToAction(eventType: string): string {
  switch (eventType) {
    case 'profile_submitted': return 'Profile submitted';
    case 'service_discovered': return 'Service discovered';
    case 'service_removed': return 'Service removed';
    case 'topology_generated': return 'Topology generated';
    case 'node_registered': return 'Node registered';
    case 'node_archived': return 'Node archived';
    case 'network_created': return 'Network created';
    case 'group_created': return 'Group created';
    default:
      return eventType
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

/**
 * Map entityType to a URL-safe path segment.
 */
function entityTypeToPath(entityType: string): string {
  const MAP: Record<string, string> = {
    node: 'nodes',
    service: 'services',
    network: 'networks',
    group: 'groups',
    topology: 'topologies',
  };
  return MAP[entityType] ?? entityType;
}

/**
 * Normalize incoming data to ActivityFeedData envelope.
 *
 * Handles:
 *   - Explicit envelope { events: ActivityEvent[] }
 *   - TimelineResponse: { events: TimelineEvent[], since, until, total }
 *   - Raw array of TimelineEvent
 */
function normalizeActivityFeedData(raw: unknown): ActivityFeedData | null {
  if (raw == null) return null;

  // Envelope or TimelineResponse with events array
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.events)) {
      // Already ActivityEvent shape
      const first = obj.events[0] as Record<string, unknown> | undefined;
      if (!first || 'action' in first) {
        return { events: obj.events as ActivityEvent[] };
      }
      // TimelineEvent shape from /timemachine/timeline
      return {
        events: (obj.events as Record<string, unknown>[]).map((e) => ({
          timestamp: String(e.timestamp ?? ''),
          action: eventTypeToAction(String(e.eventType ?? '')),
          description: String(e.description ?? ''),
          resourceType: typeof e.entityType === 'string'
            ? entityTypeToPath(e.entityType)
            : undefined,
          resourceId: typeof e.entityId === 'string' ? e.entityId : undefined,
        })),
      };
    }
  }

  // Raw array of TimelineEvent
  if (Array.isArray(raw)) {
    return {
      events: (raw as Record<string, unknown>[]).map((e) => ({
        timestamp: String(e.timestamp ?? ''),
        action: eventTypeToAction(String(e.eventType ?? '')),
        description: String(e.description ?? ''),
        resourceType: typeof e.entityType === 'string'
          ? entityTypeToPath(e.entityType)
          : undefined,
        resourceId: typeof e.entityId === 'string' ? e.entityId : undefined,
      })),
    };
  }

  return null;
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
  data: rawData,
  config,
  isLoading,
  error,
  onNavigate,
}: WidgetComponentProps<unknown, ActivityFeedConfig>) {
  const data = useMemo(() => normalizeActivityFeedData(rawData), [rawData]);
  const typedConfig = config as ActivityFeedConfig;
  const limit = (typedConfig.limit as number | undefined) ?? 25;

  const visibleEvents = useMemo(
    () => (data?.events ?? []).slice(0, limit),
    [data, limit],
  );

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

  if (visibleEvents.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Activity className="h-5 w-5" />
        <div className="text-sm">No recent activity</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-0 overflow-y-auto">
      {visibleEvents.map((event, idx) => {
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
