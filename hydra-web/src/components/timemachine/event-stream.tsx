import { motion } from 'framer-motion';
import {
  Server,
  FileText,
  Boxes,
  GitFork,
  Network,
  Users,
  Archive,
} from 'lucide-react';
import type { TimelineEvent, TimelineEventType } from '@/types/timemachine';
import { cn, formatDateTime } from '@/lib/utils';

type EventShape = 'circle' | 'square' | 'diamond' | 'triangle' | 'triangle-down' | 'hex';

export type EventTypeMeta = {
  label: string;
  color: string;
  icon: typeof Server;
  shape: EventShape;
};

export const EVENT_META: Record<TimelineEventType, EventTypeMeta> = {
  profile_submitted: {
    label: 'Profile Submitted',
    color: 'bg-amber-500',
    icon: FileText,
    shape: 'square',
  },
  service_discovered: {
    label: 'Service Discovered',
    color: 'bg-emerald-500',
    icon: Boxes,
    shape: 'triangle',
  },
  service_removed: {
    label: 'Service Removed',
    color: 'bg-rose-500',
    icon: Boxes,
    shape: 'triangle-down',
  },
  topology_generated: {
    label: 'Topology Generated',
    color: 'bg-sky-500',
    icon: GitFork,
    shape: 'hex',
  },
  node_registered: {
    label: 'Node Registered',
    color: 'bg-blue-500',
    icon: Server,
    shape: 'circle',
  },
  node_archived: {
    label: 'Node Archived',
    color: 'bg-slate-500',
    icon: Archive,
    shape: 'diamond',
  },
  network_created: {
    label: 'Network Created',
    color: 'bg-cyan-500',
    icon: Network,
    shape: 'square',
  },
  group_created: {
    label: 'Group Created',
    color: 'bg-lime-500',
    icon: Users,
    shape: 'circle',
  },
};

const shapeStyles: Record<EventShape, { className: string; style?: React.CSSProperties }> = {
  circle: { className: 'rounded-full' },
  square: { className: 'rounded-sm' },
  diamond: { className: 'rounded-sm rotate-45' },
  triangle: { className: '', style: { clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' } },
  'triangle-down': {
    className: 'rotate-180',
    style: { clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' },
  },
  hex: {
    className: '',
    style: {
      clipPath: 'polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)',
    },
  },
};

function EventGlyph({
  shape,
  className,
}: {
  shape: EventShape;
  className: string;
}) {
  const styles = shapeStyles[shape];
  return (
    <span
      className={cn('h-3 w-3', styles.className, className)}
      style={styles.style}
    />
  );
}

interface EventStreamProps {
  events: TimelineEvent[];
  selectedEventId?: string | null;
  onSelect: (event: TimelineEvent) => void;
  range: { start: Date; end: Date };
}

export function EventStream({ events, selectedEventId, onSelect, range }: EventStreamProps) {
  const start = range.start.getTime();
  const end = range.end.getTime();
  const span = Math.max(end - start, 1);

  const grouped = Object.entries(EVENT_META).map(([type, meta]) => ({
    type: type as TimelineEventType,
    meta,
    events: events.filter((event) => event.eventType === type),
  }));

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h3 className="text-lg font-semibold">Event Atlas</h3>
          <p className="text-sm text-muted-foreground">
            Visual history of infrastructure changes
          </p>
        </div>
        <div className="text-xs text-muted-foreground">
          {formatDateTime(range.start)} → {formatDateTime(range.end)}
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {grouped.map((row) => {
          const Icon = row.meta.icon;
          return (
            <div key={row.type} className="flex flex-col gap-2 md:flex-row md:items-center">
              <div className="w-full md:w-44">
                <div className="flex items-center gap-2">
                  <span className={cn('h-2 w-2 rounded-full', row.meta.color)} />
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{row.meta.label}</span>
                </div>
                <div className="text-xs text-muted-foreground">{row.events.length} events</div>
              </div>

              <div className="relative flex-1 rounded-lg bg-muted/40 px-2 py-3">
                <div className="absolute inset-x-2 top-1/2 h-px -translate-y-1/2 bg-border" />
                {row.events.map((event) => {
                  const rawPosition =
                    ((new Date(event.timestamp).getTime() - start) / span) * 100;
                  const position = Math.max(0, Math.min(100, rawPosition));
                  const isSelected = event.eventId === selectedEventId;
                  return (
                    <motion.button
                      key={event.eventId}
                      onClick={() => onSelect(event)}
                      className={cn(
                        'absolute top-1/2 -translate-y-1/2',
                        'h-6 w-6 rounded-full',
                        'flex items-center justify-center transition-transform',
                        isSelected && 'scale-110'
                      )}
                      style={{ left: `${position}%` }}
                      title={`${row.meta.label} • ${formatDateTime(event.timestamp)}`}
                      whileHover={{ scale: 1.15 }}
                    >
                      <EventGlyph shape={row.meta.shape} className={row.meta.color} />
                    </motion.button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
