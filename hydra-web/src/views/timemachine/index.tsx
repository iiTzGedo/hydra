import React, { useEffect, useMemo, useState, useRef } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { PageBreadcrumbs } from '@/components/layout/page-breadcrumbs';
import { usePageTitleStore } from '@/stores/page-title-store';
import { motion } from 'framer-motion';
import {
  History,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Clock,
  Loader2,
  CalendarDays,
  List,
  Server,
  Boxes,
  GitBranch,
  FileText,
  Network,
  FolderOpen,
  ChevronRight,
  Expand,
  X,
} from 'lucide-react';
import { useTimeline, useTopologyStateAt } from '@/api/timemachine';
import { EVENT_META } from '@/components/timemachine/event-stream';
import { CalendarView } from '@/components/timemachine/calendar-view';
import { HistoricalTopology } from '@/components/timemachine/historical-topology';
import { TimeMachinePanel } from '@/components/timemachine/time-machine-panel';
import { useRouter } from 'next/navigation';
import { cn, formatDate, formatDateTime } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import type { TimelineEvent, TimelineEventType } from '@/types/timemachine';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

type ViewMode = 'atlas' | 'calendar';
type DateRangePreset = '7d' | '14d' | '30d' | '90d' | 'custom';

const DATE_PRESETS: { value: DateRangePreset; label: string }[] = [
  { value: '7d', label: '7 Days' },
  { value: '14d', label: '14 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
];

// Helper functions to handle local dates properly (avoid timezone issues with date inputs)
function formatDateForInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseDateInput(value: string): Date | null {
  const [year, month, day] = value.split('-').map(Number);
  if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
  return new Date(year, month - 1, day);
}

type EventCategory = {
  id: string;
  label: string;
  types: TimelineEventType[];
  icon: typeof Server;
  /**
   * Name of the CSS custom property (defined in src/index.css) that carries the
   * category's HSL triplet. We apply it via inline ``style`` so the colors
   * resolve even when Tailwind's JIT hasn't been rebuilt for a new class
   * combination (e.g. after a dev-server reload without config refresh).
   */
  cssVar: string;
};

const EVENT_CATEGORIES: EventCategory[] = [
  { id: 'nodes', label: 'Node Events', types: ['node_registered', 'node_archived'], icon: Server, cssVar: '--event-node-added' },
  { id: 'services', label: 'Service Events', types: ['service_discovered', 'service_removed'], icon: Boxes, cssVar: '--event-service-added' },
  { id: 'networks', label: 'Network Events', types: ['network_created'], icon: Network, cssVar: '--event-network' },
  { id: 'groups', label: 'Group Events', types: ['group_created'], icon: FolderOpen, cssVar: '--event-group' },
  { id: 'topology', label: 'Topology Events', types: ['topology_generated'], icon: GitBranch, cssVar: '--event-topology' },
  { id: 'profiles', label: 'Profile Events', types: ['profile_submitted'], icon: FileText, cssVar: '--event-profile' },
];

/** Translate a category ``cssVar`` into a set of inline style primitives. */
function accentStyles(cssVar: string): {
  bar: React.CSSProperties;
  chip: React.CSSProperties;
  text: React.CSSProperties;
} {
  return {
    bar: { backgroundColor: `hsl(var(${cssVar}))` },
    chip: {
      backgroundColor: `hsl(var(${cssVar}) / 0.12)`,
      borderColor: `hsl(var(${cssVar}) / 0.3)`,
      color: `hsl(var(${cssVar}))`,
    },
    text: { color: `hsl(var(${cssVar}))` },
  };
}

/** Event-type → CSS variable (mirrors ``EVENT_META`` keys from event-stream.tsx). */
const EVENT_TYPE_VAR: Record<TimelineEventType, string> = {
  profile_submitted: '--event-profile',
  service_discovered: '--event-service-added',
  service_removed: '--event-service-removed',
  topology_generated: '--event-topology',
  node_registered: '--event-node-added',
  node_archived: '--event-node-removed',
  network_created: '--event-network',
  group_created: '--event-group',
};

function eventStyles(eventType: TimelineEventType | undefined): React.CSSProperties {
  const v = eventType ? EVENT_TYPE_VAR[eventType] : null;
  if (!v) return { backgroundColor: 'hsl(var(--muted))', color: 'hsl(var(--muted-foreground))' };
  return {
    backgroundColor: `hsl(var(${v}) / 0.12)`,
    borderColor: `hsl(var(${v}) / 0.3)`,
    color: `hsl(var(${v}))`,
  };
}

function DateRangeSelector({
  preset,
  onPresetChange,
  startDate,
  endDate,
  onStartChange,
  onEndChange,
}: {
  preset: DateRangePreset;
  onPresetChange: (preset: DateRangePreset) => void;
  startDate: Date;
  endDate: Date;
  onStartChange: (date: Date) => void;
  onEndChange: (date: Date) => void;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Tabs value={preset} onValueChange={(v) => onPresetChange(v as DateRangePreset)}>
        <TabsList className="h-8 bg-muted border-border">
          {DATE_PRESETS.map((p) => (
            <TabsTrigger
              key={p.value}
              value={p.value}
              className="text-xs px-2 h-6 data-[state=active]:bg-muted data-[state=active]:text-foreground"
            >
              {p.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <div className="flex items-center gap-1.5 text-sm">
        <Input
          type="date"
          value={formatDateForInput(startDate)}
          onChange={(e) => {
            const date = parseDateInput(e.target.value);
            if (date) {
              onStartChange(date);
              onPresetChange('custom');
            }
          }}
          className="h-8 w-[130px] text-xs bg-muted border-border text-foreground"
        />
        <span className="text-muted-foreground text-xs">to</span>
        <Input
          type="date"
          value={formatDateForInput(endDate)}
          onChange={(e) => {
            const date = parseDateInput(e.target.value);
            if (date) {
              onEndChange(date);
              onPresetChange('custom');
            }
          }}
          className="h-8 w-[130px] text-xs bg-muted border-border text-foreground"
        />
      </div>
    </div>
  );
}

function EventAtlas({
  events,
  selectedEventId,
  onSelect,
  range,
}: {
  events: TimelineEvent[];
  selectedEventId: string | null;
  onSelect: (event: TimelineEvent) => void;
  range: { start: Date; end: Date };
}) {
  const scrollRefs = useRef<Map<string, HTMLDivElement | null>>(new Map());

  const eventsByCategory = useMemo(() => {
    const groups = new Map<string, TimelineEvent[]>();
    EVENT_CATEGORIES.forEach((cat) => {
      const categoryEvents = events.filter((e) => cat.types.includes(e.eventType));
      if (categoryEvents.length > 0) {
        groups.set(cat.id, categoryEvents);
      }
    });
    return groups;
  }, [events]);

  useEffect(() => {
    if (!selectedEventId) return;
    const event = events.find((e) => e.eventId === selectedEventId);
    if (!event) return;

    const category = EVENT_CATEGORIES.find((c) => c.types.includes(event.eventType));
    if (!category) return;

    const scrollRef = scrollRefs.current.get(category.id);
    if (scrollRef) {
      const eventEl = scrollRef.querySelector(`[data-event-id="${selectedEventId}"]`);
      if (eventEl) {
        eventEl.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      }
    }
  }, [selectedEventId, events]);

  if (events.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="py-12 text-center">
          <History className="h-12 w-12 mx-auto text-muted-foreground/70" />
          <p className="mt-4 text-muted-foreground">No events in selected range</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
          <History className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          Event Atlas
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {EVENT_CATEGORIES.map((category) => {
          const categoryEvents = eventsByCategory.get(category.id);
          if (!categoryEvents || categoryEvents.length === 0) return null;

          const Icon = category.icon;
          const accent = accentStyles(category.cssVar);

          return (
            <div
              key={category.id}
              className="relative pl-4 space-y-2"
            >
              {/* Left accent bar — identifies the event category by color */}
              <span
                aria-hidden="true"
                className="absolute left-0 top-1 bottom-1 w-1 rounded-full"
                style={accent.bar}
              />

              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4" style={accent.text} aria-hidden="true" />
                <span className="text-sm font-medium text-foreground">{category.label}</span>
                <span
                  className="inline-flex items-center text-[10px] leading-none px-1.5 h-5 rounded-full border tabular-nums font-medium"
                  style={accent.chip}
                >
                  {categoryEvents.length}
                </span>
              </div>

              {/* Swim lane — rail is inset from the lane edges so nothing clips. */}
              <div className="relative">
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute top-1/2 left-3 right-3 h-px -translate-y-1/2 bg-border"
                />

                <ScrollArea
                  className="w-full"
                  ref={((el: HTMLDivElement | null) => { scrollRefs.current.set(category.id, el); }) as React.LegacyRef<HTMLDivElement>}
                >
                  <div className="flex items-center gap-2 py-3 px-3 min-w-max relative">
                    {categoryEvents.map((event) => {
                      const meta = EVENT_META[event.eventType as TimelineEventType];
                      const EventIcon = meta?.icon || History;
                      const isSelected = event.eventId === selectedEventId;
                      const eventType = event.eventType as TimelineEventType;
                      const chipStyle = eventStyles(eventType);
                      const label = meta?.label || event.eventType;

                      return (
                        <Tooltip key={event.eventId}>
                          <TooltipTrigger asChild>
                            <button
                              data-event-id={event.eventId}
                              onClick={() => onSelect(event)}
                              aria-label={`${label} at ${formatDateTime(new Date(event.timestamp))}`}
                              aria-pressed={isSelected}
                              style={{ ...chipStyle, borderWidth: 1, borderStyle: 'solid' }}
                              className={cn(
                                'relative flex items-center justify-center transition-transform duration-200',
                                'h-7 w-7 rounded-full',
                                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card',
                                isSelected
                                  ? 'ring-2 ring-inset ring-foreground/20 scale-110 z-10'
                                  : 'hover:scale-110',
                              )}
                            >
                              <EventIcon className="h-3.5 w-3.5" aria-hidden="true" />

                              {isSelected && (
                                <span
                                  aria-hidden="true"
                                  className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[3px] border-r-[3px] border-t-[3px] border-transparent border-t-foreground"
                                />
                              )}
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="bg-popover border-border text-popover-foreground max-w-xs">
                            <div className="text-xs">
                              <div className="font-medium">{label}</div>
                              <div className="text-muted-foreground line-clamp-2">{event.description}</div>
                              <div className="text-muted-foreground mt-1 tabular-nums">
                                {formatDateTime(new Date(event.timestamp))}
                              </div>
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      );
                    })}
                  </div>
                  <ScrollBar orientation="horizontal" className="h-1.5" />
                </ScrollArea>
              </div>
            </div>
          );
        })}

        <div className="flex items-center justify-between pt-3 px-1 text-[11px] text-muted-foreground border-t border-border tabular-nums">
          <span>{formatDate(range.start)}</span>
          <span className="text-foreground/70">{events.length} total events</span>
          <span>{formatDate(range.end)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function EventTimeline({
  events,
  selectedEventId,
  onSelect,
}: {
  events: TimelineEvent[];
  selectedEventId: string | null;
  onSelect: (event: TimelineEvent) => void;
}) {
  const selectedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedRef.current) {
      selectedRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selectedEventId]);

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Clock className="h-12 w-12 text-muted-foreground/70 mb-4" />
        <p className="text-muted-foreground">No events to display</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[400px] pr-4">
      <div className="relative">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-4 top-2 bottom-2 w-px bg-border"
        />

        <div className="space-y-3">
          {events.slice(0, 50).map((event) => {
            const eventType = event.eventType as TimelineEventType;
            const meta = EVENT_META[eventType];
            const Icon = meta?.icon || History;
            const isSelected = event.eventId === selectedEventId;
            const chipStyle = eventStyles(eventType);

            return (
              <div
                key={event.eventId}
                ref={isSelected ? selectedRef : null}
                className={cn(
                  'relative flex gap-3 cursor-pointer group rounded-lg p-2 -ml-2 transition-colors',
                  // Fix #12: differentiate selected/unselected via bg, not opacity.
                  isSelected
                    ? 'bg-accent text-accent-foreground'
                    : 'hover:bg-muted/50',
                )}
                role="button"
                tabIndex={0}
                aria-label={`Select event ${meta?.label || event.eventType}`}
                aria-pressed={isSelected}
                onClick={() => onSelect(event)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(event); } }}
              >
                <div
                  className={cn(
                    'relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-all border',
                    isSelected
                      ? 'ring-2 ring-inset ring-foreground/20'
                      : 'group-hover:ring-2 group-hover:ring-inset group-hover:ring-foreground/10',
                  )}
                  style={chipStyle}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-foreground truncate">
                        {meta?.label || event.eventType}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                        {event.description}
                      </p>
                    </div>
                    <span className="text-[10px] text-muted-foreground whitespace-nowrap shrink-0 tabular-nums pt-0.5">
                      {formatDateTime(new Date(event.timestamp))}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1.5">
                    {/* Fix #11: event-type pill carries its own icon + color, not color-only. */}
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium leading-none border"
                      style={chipStyle}
                    >
                      <Icon className="h-3 w-3" aria-hidden="true" />
                      {event.eventType.replace(/_/g, ' ')}
                    </span>
                    <Badge
                      variant="outline"
                      className="text-[10px] leading-none border-border text-muted-foreground h-5 px-2 py-0 capitalize"
                    >
                      {event.entityType}
                    </Badge>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </ScrollArea>
  );
}

function getEntityRoute(entityType: string, entityId: string): string | null {
  switch (entityType) {
    case 'node':
      return `${ROUTES.NODES}/${encodeURIComponent(entityId)}`;
    case 'service':
      return `${ROUTES.SERVICES}/${encodeURIComponent(entityId)}`;
    case 'network':
      return `${ROUTES.NETWORKS}/${encodeURIComponent(entityId)}`;
    case 'group':
      return `${ROUTES.GROUPS}/${encodeURIComponent(entityId)}`;
    case 'topology':
      return ROUTES.TOPOLOGY;
    case 'profile':
      return null; // Profiles need nodeId context, not navigable directly
    default:
      return null;
  }
}

export default function TimeMachinePage() {
  useDocumentTitle('Time Machine');
  const setPageTitle = usePageTitleStore((s) => s.setPageTitle);
  const clearPageTitle = usePageTitleStore((s) => s.clearPageTitle);
  useEffect(() => {
    setPageTitle('Time Machine', 'Navigate through historical infrastructure states');
    return () => clearPageTitle();
  }, [setPageTitle, clearPageTitle]);
  const router = useRouter();

  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedTimestamp, setSelectedTimestamp] = useState<Date | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('atlas');
  const [dateRangePreset, setDateRangePreset] = useState<DateRangePreset>('7d');
  const [showTopologyModal, setShowTopologyModal] = useState(false);

  const now = useMemo(() => new Date(), []);
  const [endDate, setEndDate] = useState<Date>(now);
  const [startDate, setStartDate] = useState<Date>(
    new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  );

  useEffect(() => {
    if (dateRangePreset === 'custom') return;

    const days = dateRangePreset === '7d' ? 7 : dateRangePreset === '14d' ? 14 : dateRangePreset === '30d' ? 30 : 90;
    setEndDate(now);
    setStartDate(new Date(now.getTime() - days * 24 * 60 * 60 * 1000));
  }, [dateRangePreset, now]);

  const { data: timeline, isLoading: timelineLoading } = useTimeline({
    since: startDate.toISOString(),
    until: endDate.toISOString(),
    limit: 500,
  });

  const events = useMemo(() => {
    if (!timeline?.events) return [];
    return [...timeline.events].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [timeline]);

  const chronologicalEvents = useMemo(() => {
    return [...events].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }, [events]);

  useEffect(() => {
    if (!events.length) {
      setSelectedEventId(null);
      setSelectedTimestamp(null);
      return;
    }

    const current = selectedEventId
      ? events.find((event) => event.eventId === selectedEventId)
      : null;

    if (!current) {
      const latest = events[0]; // Most recent (reverse sorted)
      setSelectedEventId(latest.eventId);
      setSelectedTimestamp(new Date(latest.timestamp));
      return;
    }

    if (!selectedTimestamp) {
      setSelectedTimestamp(new Date(current.timestamp));
    }
  }, [events, selectedEventId, selectedTimestamp]);

  const selectedEvent = useMemo(
    () => events.find((event) => event.eventId === selectedEventId) || null,
    [events, selectedEventId]
  );

  const timeRange = useMemo(() => {
    if (timeline?.since && timeline?.until) {
      return {
        start: new Date(timeline.since),
        end: new Date(timeline.until),
      };
    }
    if (events.length > 0) {
      const timestamps = events.map((e) => new Date(e.timestamp).getTime());
      return {
        start: new Date(Math.min(...timestamps)),
        end: new Date(Math.max(...timestamps)),
      };
    }
    return {
      start: startDate,
      end: endDate,
    };
  }, [timeline, events, startDate, endDate]);

  const selectedTimestampIso = selectedTimestamp ? selectedTimestamp.toISOString() : '';
  const { data: topologyState, isLoading: topologyLoading } = useTopologyStateAt(
    selectedTimestampIso
  );

  const selectEvent = (event: TimelineEvent) => {
    setSelectedEventId(event.eventId);
    setSelectedTimestamp(new Date(event.timestamp));
  };

  const selectDate = (date: Date) => {
    const targetTime = date.getTime();
    let closestEvent: TimelineEvent | null = null;
    let closestDiff = Infinity;

    const dayStart = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
    const dayEnd = dayStart + 24 * 60 * 60 * 1000;

    const dayEvents = events.filter((e) => {
      const eventTime = new Date(e.timestamp).getTime();
      return eventTime >= dayStart && eventTime < dayEnd;
    });

    if (dayEvents.length > 0) {
      closestEvent = dayEvents[0]; // Most recent of the day
    } else {
      for (const event of events) {
        const eventTime = new Date(event.timestamp).getTime();
        const diff = Math.abs(eventTime - targetTime);
        if (diff < closestDiff) {
          closestDiff = diff;
          closestEvent = event;
        }
      }
    }

    if (closestEvent) {
      setSelectedEventId(closestEvent.eventId);
      setSelectedTimestamp(new Date(closestEvent.timestamp));
    } else {
      setSelectedTimestamp(date);
    }
  };

  const selectedChronologicalIndex = chronologicalEvents.findIndex(
    (event) => event.eventId === selectedEventId
  );

  const handleStepBack = () => {
    if (selectedChronologicalIndex > 0) {
      selectEvent(chronologicalEvents[selectedChronologicalIndex - 1]);
    }
  };

  const handleStepForward = () => {
    if (selectedChronologicalIndex >= 0 && selectedChronologicalIndex < chronologicalEvents.length - 1) {
      selectEvent(chronologicalEvents[selectedChronologicalIndex + 1]);
    }
  };

  useEffect(() => {
    if (!isPlaying || chronologicalEvents.length < 2) return;

    const interval = setInterval(() => {
      const index = chronologicalEvents.findIndex((event) => event.eventId === selectedEventId);
      if (index === -1 || index >= chronologicalEvents.length - 1) {
        setIsPlaying(false);
        return;
      }
      selectEvent(chronologicalEvents[index + 1]);
    }, 2500);

    return () => clearInterval(interval);
  }, [isPlaying, chronologicalEvents, selectedEventId]);

  const selectedMeta = selectedEvent ? EVENT_META[selectedEvent.eventType as TimelineEventType] : null;
  const SelectedIcon = selectedMeta?.icon;
  const metadataEntries = selectedEvent?.metadata
    ? Object.entries(selectedEvent.metadata)
    : [];

  const topologyData = useMemo(() => {
    if (!topologyState?.graph) return null;
    return {
      nodes: topologyState.graph.nodes?.map((node) => ({
        id: node.id,
        class: (node.data?.class as string) || 'compute',
        type: (node.data?.type as string) || node.type,
        kind: (node.data?.kind as string) || 'unknown',
        status: (node.data?.status as string) || 'unknown',
      })),
      edges: topologyState.graph.edges?.map((edge) => ({
        from: edge.source,
        to: edge.target,
        type: edge.type,
      })),
    };
  }, [topologyState]);

  if (timelineLoading) {
    return (
      <TooltipProvider>
        <div className="h-[calc(100vh-3.5rem)] flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
            <p className="mt-2 text-muted-foreground">Loading time machine...</p>
          </div>
        </div>
      </TooltipProvider>
    );
  }

  const atEnd = selectedChronologicalIndex >= 0
    && selectedChronologicalIndex === chronologicalEvents.length - 1;
  const atStart = selectedChronologicalIndex === 0;

  return (
    <TooltipProvider>
      <div className="p-6 space-y-6">
        <div className="flex flex-col gap-4">
          <h1 className="sr-only">Time Machine</h1>
          <PageBreadcrumbs />

          {/* Row 1 — subtitle and playback. Playback is semantically tied to the
              currently-selected event, so it lives with the page lead text. */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              Navigate through historical infrastructure states
            </p>

            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 border-border text-foreground hover:bg-muted bg-transparent"
                      onClick={handleStepBack}
                      disabled={atStart || selectedChronologicalIndex < 0}
                      aria-label="Previous event"
                    >
                      <SkipBack className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="bg-popover border-border text-popover-foreground">Previous event</TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant={isPlaying ? 'default' : 'outline'}
                      size="icon"
                      className={cn(
                        'h-8 w-8',
                        isPlaying
                          ? 'bg-primary hover:bg-primary/90 text-primary-foreground'
                          : 'border-border text-foreground hover:bg-muted bg-transparent',
                      )}
                      onClick={() => setIsPlaying(!isPlaying)}
                      disabled={!events.length}
                      aria-label={isPlaying ? 'Pause playback' : 'Play events'}
                      aria-pressed={isPlaying}
                    >
                      {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="bg-popover border-border text-popover-foreground">{isPlaying ? 'Pause' : 'Play'}</TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 border-border text-foreground hover:bg-muted bg-transparent"
                      onClick={handleStepForward}
                      disabled={selectedChronologicalIndex === -1 || atEnd}
                      aria-label="Next event"
                    >
                      <SkipForward className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="bg-popover border-border text-popover-foreground">Next event</TooltipContent>
                </Tooltip>
              </div>

              {/* Fix #5: counter reads as a sentence, not a fraction. */}
              <div
                className="h-8 inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2.5 text-xs text-muted-foreground tabular-nums"
                aria-live="polite"
              >
                {selectedChronologicalIndex >= 0 ? (
                  <>
                    <span className="text-foreground">Event {selectedChronologicalIndex + 1}</span>
                    <span>of {chronologicalEvents.length}</span>
                    {atEnd && <span className="text-warning ml-1">· latest</span>}
                  </>
                ) : (
                  <span>{chronologicalEvents.length} events</span>
                )}
              </div>
            </div>
          </div>

          {/* Row 2 — toolbar: range presets, custom dates, view toggle grouped in a single panel. */}
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/30 p-2 lg:flex-row lg:items-center lg:justify-between">
            <DateRangeSelector
              preset={dateRangePreset}
              onPresetChange={setDateRangePreset}
              startDate={startDate}
              endDate={endDate}
              onStartChange={setStartDate}
              onEndChange={setEndDate}
            />

            <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as ViewMode)}>
              <TabsList className="h-8 bg-background border border-border">
                <TabsTrigger
                  value="atlas"
                  className="gap-1.5 text-xs px-3 h-6 data-[state=active]:bg-muted data-[state=active]:text-foreground"
                >
                  <List className="h-3.5 w-3.5" aria-hidden="true" />
                  Atlas
                </TabsTrigger>
                <TabsTrigger
                  value="calendar"
                  className="gap-1.5 text-xs px-3 h-6 data-[state=active]:bg-muted data-[state=active]:text-foreground"
                >
                  <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
                  Calendar
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>

        <motion.div variants={staggerContainerVariants} initial="hidden" animate="visible">
          <motion.div variants={staggerItemVariants}>
            {viewMode === 'atlas' ? (
              <EventAtlas
                events={chronologicalEvents}
                selectedEventId={selectedEventId}
                onSelect={selectEvent}
                range={timeRange}
              />
            ) : (
              <CalendarView
                events={events}
                selectedDate={selectedTimestamp}
                onSelectDate={selectDate}
                range={timeRange}
                onRangeChange={(start, end) => {
                  setStartDate(start);
                  setEndDate(end);
                  setDateRangePreset('custom');
                }}
              />
            )}
          </motion.div>
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
          <motion.div variants={staggerItemVariants}>
            <TimeMachinePanel>
              <TimeMachinePanel.Header>
                <TimeMachinePanel.Title className="text-base font-semibold text-foreground">
                  Event Timeline
                </TimeMachinePanel.Title>
                <TimeMachinePanel.Actions>
                  <Badge
                    variant="secondary"
                    className="text-[10px] leading-none px-2 h-5 bg-muted text-muted-foreground tabular-nums"
                  >
                    {events.length} events
                  </Badge>
                </TimeMachinePanel.Actions>
              </TimeMachinePanel.Header>
              <TimeMachinePanel.Body>
                <EventTimeline
                  events={events}
                  selectedEventId={selectedEventId}
                  onSelect={selectEvent}
                />
              </TimeMachinePanel.Body>
            </TimeMachinePanel>
          </motion.div>

          <motion.div variants={staggerItemVariants}>
            <TimeMachinePanel className="h-full">
              <TimeMachinePanel.Header>
                <TimeMachinePanel.Title className="text-base font-semibold text-foreground">
                  Event Details
                </TimeMachinePanel.Title>
              </TimeMachinePanel.Header>
              <TimeMachinePanel.Body>
                {!selectedEvent || !selectedTimestamp ? (
                  <div className="h-32 flex flex-col items-center justify-center text-center text-muted-foreground">
                    <History className="h-10 w-10" aria-hidden="true" />
                    <p className="mt-3 text-sm">
                      Select an event to view details
                    </p>
                  </div>
                ) : (() => {
                  const eventType = selectedEvent.eventType as TimelineEventType;
                  const chipStyle = eventStyles(eventType);
                  const route = selectedEvent.entityId
                    ? getEntityRoute(selectedEvent.entityType, selectedEvent.entityId)
                    : null;
                  return (
                    <>
                      <div className="flex items-start gap-3">
                        <div
                          className="rounded-lg p-2 shrink-0 border"
                          style={chipStyle}
                        >
                          {SelectedIcon ? (
                            <SelectedIcon className="h-4 w-4" aria-hidden="true" />
                          ) : (
                            <History className="h-4 w-4" aria-hidden="true" />
                          )}
                        </div>
                        <div className="min-w-0">
                          {/* Fix #4: single title — description moves out to avoid duplication with Timeline card. */}
                          <h3 className="text-sm font-semibold text-foreground truncate">
                            {selectedMeta?.label || selectedEvent.eventType}
                          </h3>
                          {/* One combined timestamp row (was Calendar + Clock rows). */}
                          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums">
                            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                            {formatDateTime(selectedTimestamp)}
                          </p>
                        </div>
                      </div>

                      <p className="mt-3 text-sm text-muted-foreground">
                        {selectedEvent.description}
                      </p>

                      {metadataEntries.length > 0 && (
                        <div className="mt-4 rounded-md border border-border bg-muted/30 p-3">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                            Metadata
                          </p>
                          <div className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
                            {metadataEntries.slice(0, 6).map(([key, value]) => (
                              <React.Fragment key={key}>
                                <span className="text-muted-foreground font-mono text-xs">{key}</span>
                                <span
                                  className="text-right font-mono text-xs truncate text-foreground"
                                  title={typeof value === 'string' ? value : JSON.stringify(value)}
                                >
                                  {typeof value === 'string' ? value : JSON.stringify(value)}
                                </span>
                              </React.Fragment>
                            ))}
                          </div>
                        </div>
                      )}

                      {route ? (
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full mt-4 border-border text-foreground hover:bg-muted bg-transparent"
                          onClick={() => router.push(route)}
                        >
                          View {selectedEvent.entityType}
                          <ChevronRight className="ml-2 h-4 w-4" aria-hidden="true" />
                        </Button>
                      ) : null}
                    </>
                  );
                })()}
              </TimeMachinePanel.Body>
            </TimeMachinePanel>
          </motion.div>
        </div>

        <motion.div variants={staggerItemVariants}>
          <TimeMachinePanel>
            <TimeMachinePanel.Header>
              <div>
                <TimeMachinePanel.Title className="text-base font-semibold text-foreground">
                  Topology Snapshot
                </TimeMachinePanel.Title>
                <TimeMachinePanel.Subtitle className="tabular-nums">
                  {selectedTimestamp ? formatDateTime(selectedTimestamp) : 'Select an event'}
                </TimeMachinePanel.Subtitle>
              </div>
              <TimeMachinePanel.Actions>
                {selectedTimestamp && (
                  <Badge variant="outline" className="border-border text-foreground tabular-nums">
                    {events.length} events in range
                  </Badge>
                )}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 border-border text-foreground hover:bg-muted bg-transparent"
                      onClick={() => setShowTopologyModal(true)}
                      disabled={!topologyData}
                      aria-label="Expand topology view"
                    >
                      <Expand className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="bg-popover border-border text-popover-foreground">
                    Expand topology view
                  </TooltipContent>
                </Tooltip>
              </TimeMachinePanel.Actions>
            </TimeMachinePanel.Header>
            {/* Fix #9: collapse empty state to a compact banner so no-data doesn't
                dominate the page; full 400px reserved for real topologies. */}
            <div className={cn(topologyData ? 'h-[400px]' : 'h-32')}>
              <HistoricalTopology
                timestamp={selectedTimestamp || now}
                compareTimestamp={null}
                topologyState={topologyData}
                isLoading={topologyLoading}
              />
            </div>
          </TimeMachinePanel>
        </motion.div>
      </div>

      <Dialog open={showTopologyModal} onOpenChange={setShowTopologyModal}>
        <DialogContent className="max-w-[95vw] max-h-[95vh] w-full h-full bg-card border-border p-0">
          <DialogHeader className="p-4 border-b border-border">
            <div className="flex items-center justify-between">
              <div>
                <DialogTitle className="text-foreground">Topology Snapshot</DialogTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  {selectedTimestamp ? formatDateTime(selectedTimestamp) : 'Select an event'}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowTopologyModal(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
          </DialogHeader>
          <div className="flex-1 h-[calc(95vh-80px)]">
            <HistoricalTopology
              timestamp={selectedTimestamp || now}
              compareTimestamp={null}
              topologyState={topologyData}
              isLoading={topologyLoading}
            />
          </div>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  );
}
