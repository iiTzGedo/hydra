import { useEffect, useMemo, useState, useRef } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { motion } from 'framer-motion';
import {
  History,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Calendar,
  Clock,
  Loader2,
  CalendarDays,
  List,
  Server,
  Boxes,
  GitBranch,
  FileText,
  Network,
  AlertTriangle,
  FolderOpen,
  ChevronRight,
  Expand,
  X,
} from 'lucide-react';
import { useTimeline, useTopologyStateAt } from '@/api/timemachine';
import { EVENT_META } from '@/components/timemachine/event-stream';
import { CalendarView } from '@/components/timemachine/calendar-view';
import { HistoricalTopology } from '@/components/timemachine/historical-topology';
import { useNavigate } from 'react-router-dom';
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

const EVENT_CATEGORIES = [
  {
    id: 'nodes',
    label: 'Node Events',
    types: ['node_registered', 'node_archived'],
    icon: Server,
    color: 'bg-emerald-500'
  },
  {
    id: 'services',
    label: 'Service Events',
    types: ['service_discovered', 'service_removed'],
    icon: Boxes,
    color: 'bg-blue-500'
  },
  {
    id: 'networks',
    label: 'Network Events',
    types: ['network_created'],
    icon: Network,
    color: 'bg-cyan-500'
  },
  {
    id: 'groups',
    label: 'Group Events',
    types: ['group_created'],
    icon: FolderOpen,
    color: 'bg-lime-500'
  },
  {
    id: 'topology',
    label: 'Topology Events',
    types: ['topology_generated'],
    icon: GitBranch,
    color: 'bg-purple-500'
  },
  {
    id: 'profiles',
    label: 'Profile Events',
    types: ['profile_submitted'],
    icon: FileText,
    color: 'bg-amber-500'
  },
];

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
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          <History className="h-4 w-4" />
          Event Atlas
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {EVENT_CATEGORIES.map((category) => {
          const categoryEvents = eventsByCategory.get(category.id);
          if (!categoryEvents || categoryEvents.length === 0) return null;

          const Icon = category.icon;
          const rangeMs = range.end.getTime() - range.start.getTime();

          return (
            <div key={category.id} className="space-y-2">
              <div className="flex items-center gap-2">
                <div className={cn('h-6 w-6 rounded flex items-center justify-center', category.color)}>
                  <Icon className="h-3.5 w-3.5 text-foreground" />
                </div>
                <span className="text-xs font-medium text-foreground">{category.label}</span>
                <Badge variant="secondary" className="text-[9px] px-1.5 h-4 bg-muted text-muted-foreground">
                  {categoryEvents.length}
                </Badge>
              </div>

              <div className="relative my-3">
                <div className="absolute top-1/2 -translate-y-1/2 left-0 right-0 h-0.5 bg-muted" />

                <ScrollArea
                  className="w-full"
                  ref={(el) => scrollRefs.current.set(category.id, el)}
                >
                  <div className="flex items-center gap-2 py-2 px-2 min-w-max relative">
                    {categoryEvents.map((event) => {
                      const meta = EVENT_META[event.eventType as TimelineEventType];
                      const EventIcon = meta?.icon || History;
                      const isSelected = event.eventId === selectedEventId;
                      const eventTime = new Date(event.timestamp).getTime();

                      return (
                        <Tooltip key={event.eventId}>
                          <TooltipTrigger asChild>
                            <button
                              data-event-id={event.eventId}
                              onClick={() => onSelect(event)}
                              className={cn(
                                'relative flex flex-col items-center group transition-all duration-200 px-1',
                                isSelected && 'scale-110 z-10'
                              )}
                            >
                              <div
                                className={cn(
                                  'h-6 w-6 rounded-full flex items-center justify-center transition-all',
                                  isSelected
                                    ? 'ring-2 ring-border ring-offset-2 ring-offset-background'
                                    : 'group-hover:scale-110',
                                  category.color
                                )}
                              >
                                <EventIcon className="h-3 w-3 text-foreground" />
                              </div>

                              {isSelected && (
                                <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-blue-500" />
                              )}
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="bg-popover border-border text-popover-foreground max-w-xs">
                            <div className="text-xs">
                              <div className="font-medium">{meta?.label || event.eventType}</div>
                              <div className="text-muted-foreground line-clamp-2">{event.description}</div>
                              <div className="text-muted-foreground mt-1">
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

        <div className="flex items-center justify-between pt-2 text-[10px] text-muted-foreground border-t border-border">
          <span>{formatDate(range.start)}</span>
          <span>{events.length} total events</span>
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
        <div className="absolute left-[15px] top-0 bottom-0 w-px bg-muted" />

        <div className="space-y-3">
          {events.slice(0, 50).map((event) => {
            const meta = EVENT_META[event.eventType as TimelineEventType];
            const Icon = meta?.icon || History;
            const isSelected = event.eventId === selectedEventId;

            return (
              <div
                key={event.eventId}
                ref={isSelected ? selectedRef : null}
                className={cn(
                  'relative flex gap-3 cursor-pointer group',
                  isSelected ? 'opacity-100' : 'opacity-70 hover:opacity-100'
                )}
                onClick={() => onSelect(event)}
              >
                <div
                  className={cn(
                    'relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-all',
                    isSelected
                      ? 'ring-2 ring-blue-500'
                      : 'group-hover:ring-2 group-hover:ring-border',
                    meta?.color || 'bg-muted'
                  )}
                >
                  <Icon className="h-4 w-4 text-foreground" />
                </div>

                <div
                  className={cn(
                    'flex-1 rounded-lg p-3 transition-colors',
                    isSelected
                      ? 'bg-muted border border-blue-500/30'
                      : 'bg-muted/60 group-hover:bg-muted'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {meta?.label || event.eventType}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                        {event.description}
                      </p>
                    </div>
                    <span className="text-[10px] text-muted-foreground/70 whitespace-nowrap shrink-0">
                      {formatDateTime(new Date(event.timestamp))}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="outline" className="text-[9px] border-border text-muted-foreground h-5">
                      {event.eventType.replace(/_/g, ' ')}
                    </Badge>
                    <Badge variant="outline" className="text-[9px] border-border text-muted-foreground h-5">
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
  const navigate = useNavigate();

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

  const eventStats = useMemo(() => {
    if (!events.length) return { nodeEvents: 0, serviceEvents: 0, topologyEvents: 0, profiles: 0 };
    return {
      nodeEvents: events.filter((e) =>
        ['node_registered', 'node_archived'].includes(e.eventType)
      ).length,
      serviceEvents: events.filter((e) =>
        ['service_discovered', 'service_removed'].includes(e.eventType)
      ).length,
      topologyEvents: events.filter((e) => e.eventType === 'topology_generated').length,
      profiles: events.filter((e) => e.eventType === 'profile_submitted').length,
    };
  }, [events]);

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
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-blue-500" />
            <p className="mt-2 text-muted-foreground">Loading time machine...</p>
          </div>
        </div>
      </TooltipProvider>
    );
  }

  return (
    <TooltipProvider>
      <div className="p-6 space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Time Machine</h1>
            <p className="text-muted-foreground">
              Navigate through historical infrastructure states
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <DateRangeSelector
              preset={dateRangePreset}
              onPresetChange={setDateRangePreset}
              startDate={startDate}
              endDate={endDate}
              onStartChange={setStartDate}
              onEndChange={setEndDate}
            />

            <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as ViewMode)}>
              <TabsList className="h-8 bg-muted border-border">
                <TabsTrigger value="atlas" className="gap-1.5 text-xs px-2 h-6 data-[state=active]:bg-muted data-[state=active]:text-foreground">
                  <List className="h-3 w-3" />
                  Atlas
                </TabsTrigger>
                <TabsTrigger value="calendar" className="gap-1.5 text-xs px-2 h-6 data-[state=active]:bg-muted data-[state=active]:text-foreground">
                  <CalendarDays className="h-3 w-3" />
                  Calendar
                </TabsTrigger>
              </TabsList>
            </Tabs>

            <div className="flex items-center gap-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 border-border text-foreground hover:bg-muted bg-transparent"
                    onClick={handleStepBack}
                    disabled={selectedChronologicalIndex <= 0}
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
                        ? 'bg-blue-600 hover:bg-blue-700 text-white'
                        : 'border-border text-foreground hover:bg-muted bg-transparent'
                    )}
                    onClick={() => setIsPlaying(!isPlaying)}
                    disabled={!events.length}
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
                    disabled={selectedChronologicalIndex === -1 || selectedChronologicalIndex >= chronologicalEvents.length - 1}
                  >
                    <SkipForward className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent className="bg-popover border-border text-popover-foreground">Next event</TooltipContent>
              </Tooltip>

              <div className="ml-2 px-2 py-1 rounded bg-muted text-[10px] text-muted-foreground">
                {selectedChronologicalIndex >= 0
                  ? `${selectedChronologicalIndex + 1} / ${chronologicalEvents.length}`
                  : `${chronologicalEvents.length} events`}
              </div>
            </div>
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
            <Card className="bg-card border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Event Timeline
                  <Badge variant="secondary" className="text-[9px] px-1.5 h-4 bg-muted text-muted-foreground ml-auto">
                    {events.length} events
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <EventTimeline
                  events={events}
                  selectedEventId={selectedEventId}
                  onSelect={selectEvent}
                />
              </CardContent>
            </Card>
          </motion.div>

          <motion.div variants={staggerItemVariants}>
            <Card className="bg-card border-border h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                  Event Details
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!selectedEvent || !selectedTimestamp ? (
                  <div className="h-32 flex flex-col items-center justify-center text-center text-muted-foreground">
                    <History className="h-10 w-10" />
                    <p className="mt-3 text-sm">
                      Select an event to view details
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-3">
                      <div className={cn('rounded-lg p-2', selectedMeta?.color || 'bg-muted')}>
                        {SelectedIcon ? (
                          <SelectedIcon className="h-4 w-4 text-foreground" />
                        ) : (
                          <History className="h-4 w-4 text-foreground" />
                        )}
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground">
                          {selectedMeta?.label || selectedEvent.eventType}
                        </h3>
                        <p className="text-sm text-muted-foreground">{selectedEvent.description}</p>
                      </div>
                    </div>

                    <div className="mt-4 space-y-2 text-sm">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Calendar className="h-4 w-4" />
                        <span>{formatDate(selectedTimestamp)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Clock className="h-4 w-4" />
                        <span>{formatDateTime(selectedTimestamp)}</span>
                      </div>
                      <Badge variant="secondary" className="font-mono text-xs bg-muted text-foreground">
                        {selectedEvent.entityType}: {selectedEvent.entityId}
                      </Badge>
                    </div>

                    {metadataEntries.length > 0 && (
                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                          Metadata
                        </p>
                        <div className="space-y-1.5 text-sm">
                          {metadataEntries.slice(0, 6).map(([key, value]) => (
                            <div key={key} className="flex items-start justify-between gap-4">
                              <span className="text-muted-foreground">{key}</span>
                              <span className="text-right font-mono text-xs truncate max-w-[180px] text-foreground">
                                {typeof value === 'string' ? value : JSON.stringify(value)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedEvent.entityId && (() => {
                      const route = getEntityRoute(selectedEvent.entityType, selectedEvent.entityId);
                      return route ? (
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full mt-4 border-border text-foreground hover:bg-muted bg-transparent"
                          onClick={() => navigate(route)}
                        >
                          View {selectedEvent.entityType}
                          <ChevronRight className="ml-2 h-4 w-4" />
                        </Button>
                      ) : null;
                    })()}
                  </>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>

        <motion.div variants={staggerItemVariants}>
          <Card className="overflow-hidden bg-card border-border">
            <CardHeader className="border-b border-border py-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-foreground">Topology Snapshot</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {selectedTimestamp ? formatDateTime(selectedTimestamp) : 'Select an event'}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {selectedTimestamp && (
                    <Badge variant="outline" className="border-border text-foreground">
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
                      >
                        <Expand className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="bg-popover border-border text-popover-foreground">
                      Expand topology view
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>
            </CardHeader>
            <div className="h-[400px]">
              <HistoricalTopology
                timestamp={selectedTimestamp || now}
                compareTimestamp={null}
                topologyState={topologyData}
                isLoading={topologyLoading}
              />
            </div>
          </Card>
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
