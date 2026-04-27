/**
 * ChangeLogWidget -- chronological list of infrastructure change events,
 * each with a type badge, timestamp, entity name, and description.
 *
 * Data binding:
 *   source: hydra::timeline
 *   endpoint: /timemachine/timeline
 *   params: { limit: 50 }
 *
 * Accepts two data shapes:
 *   1. Explicit envelope: { changes: ChangeEntry[] }
 *   2. TimelineResponse from /timemachine/timeline: { events: TimelineEvent[], ... }
 *      Maps: eventType → type (profile_submitted→update, node_registered→create,
 *            service_removed/node_archived→delete, else→update),
 *            entityId → entity, description → description
 *   3. Raw array: TimelineEvent[]
 *
 * Type badge colors: create=green, update=blue, delete=red, default=gray.
 */

import { useMemo } from 'react';
import { History } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ChangeEntry {
  timestamp: string;
  type: string;
  entity: string;
  description: string;
}

interface ChangeLogData {
  changes: ChangeEntry[];
}

/**
 * Map timeline event type to a change type badge: create | update | delete.
 */
function eventTypeToChangeType(eventType: string): string {
  switch (eventType) {
    case 'node_registered':
    case 'service_discovered':
    case 'network_created':
    case 'group_created':
      return 'create';
    case 'node_archived':
    case 'service_removed':
      return 'delete';
    default:
      return 'update';
  }
}

/**
 * Normalize incoming data to ChangeLogData.
 *
 * Handles:
 *   - Explicit { changes: ChangeEntry[] } envelope
 *   - TimelineResponse from /timemachine/timeline
 *   - Raw TimelineEvent[]
 */
function normalizeChangeLogData(raw: unknown): ChangeLogData | null {
  if (raw == null) return null;

  // Explicit envelope
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.changes)) {
      return { changes: obj.changes as ChangeEntry[] };
    }
    // TimelineResponse: { events: [...], since, until, total }
    if (Array.isArray(obj.events)) {
      return {
        changes: (obj.events as Record<string, unknown>[]).map((e) => ({
          timestamp: String(e.timestamp ?? ''),
          type: eventTypeToChangeType(String(e.eventType ?? '')),
          entity: String(e.entityId ?? e.entityType ?? ''),
          description: String(e.description ?? ''),
        })),
      };
    }
  }

  // Raw array
  if (Array.isArray(raw)) {
    return {
      changes: (raw as Record<string, unknown>[]).map((e) => ({
        timestamp: String(e.timestamp ?? ''),
        type: eventTypeToChangeType(String(e.eventType ?? e.type ?? '')),
        entity: String(e.entityId ?? e.entity ?? ''),
        description: String(e.description ?? ''),
      })),
    };
  }

  return null;
}

const TYPE_STYLES: Record<string, { bg: string; text: string }> = {
  create: { bg: 'bg-emerald-500/10', text: 'text-emerald-600' },
  update: { bg: 'bg-blue-500/10', text: 'text-blue-600' },
  delete: { bg: 'bg-red-500/10', text: 'text-red-600' },
};

const DEFAULT_TYPE_STYLE = { bg: 'bg-gray-500/10', text: 'text-gray-600' };

function formatTimestamp(isoString: string): string {
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return isoString;
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function ChangeLogWidget({
  data: rawData,
  isLoading,
  error,
}: WidgetComponentProps<unknown>) {
  const data = useMemo(() => normalizeChangeLogData(rawData), [rawData]);

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.changes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <History className="h-5 w-5" />
        <div className="text-sm">No changes recorded</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-1 overflow-auto p-1">
      {data.changes.map((change, index) => {
        const style =
          TYPE_STYLES[change.type.toLowerCase()] ?? DEFAULT_TYPE_STYLE;

        return (
          <div
            key={`${change.timestamp}-${index}`}
            className="flex items-start gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted/30"
          >
            {/* Type badge */}
            <span
              className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${style.bg} ${style.text}`}
            >
              {change.type}
            </span>

            {/* Content */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-xs font-semibold">
                  {change.entity}
                </span>
                <span className="shrink-0 text-[10px] text-muted-foreground tabular-nums">
                  {formatTimestamp(change.timestamp)}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                {change.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
