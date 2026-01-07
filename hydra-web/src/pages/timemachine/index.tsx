import { useEffect, useMemo, useState } from 'react';
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
  Settings2,
} from 'lucide-react';
import { useTimeline, useTopologyStateAt } from '@/api/timemachine';
import { PageHeader } from '@/components/layout/page-header';
import { EventStream, EVENT_META } from '@/components/timemachine/event-stream';
import { CalendarView } from '@/components/timemachine/calendar-view';
import { HistoricalTopology } from '@/components/timemachine/historical-topology';
import { cn, formatDate, formatDateTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import type { TimelineEvent } from '@/types/timemachine';

type ViewMode = 'timeline' | 'calendar';
type DateRangePreset = '7d' | '14d' | '30d' | '90d' | 'custom';

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
      <div className="flex rounded-lg border bg-muted/40 p-0.5">
        {(['7d', '14d', '30d', '90d'] as DateRangePreset[]).map((p) => (
          <button
            key={p}
            onClick={() => onPresetChange(p)}
            className={cn(
              'px-2 py-1 text-xs rounded-md transition-colors',
              preset === p ? 'bg-background shadow-sm' : 'hover:bg-background/50'
            )}
          >
            {p === '7d' ? '7 Days' : p === '14d' ? '14 Days' : p === '30d' ? '30 Days' : '90 Days'}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-1 text-sm">
        <input
          type="date"
          value={startDate.toISOString().split('T')[0]}
          onChange={(e) => {
            const date = new Date(e.target.value);
            if (!isNaN(date.getTime())) {
              onStartChange(date);
              onPresetChange('custom');
            }
          }}
          className="px-2 py-1 text-xs rounded-lg border bg-background"
        />
        <span className="text-muted-foreground">to</span>
        <input
          type="date"
          value={endDate.toISOString().split('T')[0]}
          onChange={(e) => {
            const date = new Date(e.target.value);
            if (!isNaN(date.getTime())) {
              onEndChange(date);
              onPresetChange('custom');
            }
          }}
          className="px-2 py-1 text-xs rounded-lg border bg-background"
        />
      </div>
    </div>
  );
}

export default function TimeMachinePage() {
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedTimestamp, setSelectedTimestamp] = useState<Date | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('timeline');
  const [dateRangePreset, setDateRangePreset] = useState<DateRangePreset>('7d');

  const now = useMemo(() => new Date(), []);
  const [endDate, setEndDate] = useState<Date>(now);
  const [startDate, setStartDate] = useState<Date>(
    new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  );

  // Update date range when preset changes
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
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }, [timeline]);

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
      const latest = events[events.length - 1];
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
      return {
        start: new Date(events[0].timestamp),
        end: new Date(events[events.length - 1].timestamp),
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
    // Find the closest event to the selected date
    const targetTime = date.getTime();
    let closestEvent: TimelineEvent | null = null;
    let closestDiff = Infinity;

    // Get events for this day first
    const dayStart = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
    const dayEnd = dayStart + 24 * 60 * 60 * 1000;

    const dayEvents = events.filter((e) => {
      const eventTime = new Date(e.timestamp).getTime();
      return eventTime >= dayStart && eventTime < dayEnd;
    });

    if (dayEvents.length > 0) {
      // Select the last event of that day
      closestEvent = dayEvents[dayEvents.length - 1];
    } else {
      // Find closest event before or after
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
      // No events, just set the timestamp
      setSelectedTimestamp(date);
    }
  };

  const selectedIndex = events.findIndex((event) => event.eventId === selectedEventId);

  const handleStepBack = () => {
    if (selectedIndex > 0) {
      selectEvent(events[selectedIndex - 1]);
    }
  };

  const handleStepForward = () => {
    if (selectedIndex >= 0 && selectedIndex < events.length - 1) {
      selectEvent(events[selectedIndex + 1]);
    }
  };

  useEffect(() => {
    if (!isPlaying || events.length < 2) return;

    const interval = setInterval(() => {
      const index = events.findIndex((event) => event.eventId === selectedEventId);
      if (index === -1 || index >= events.length - 1) {
        setIsPlaying(false);
        return;
      }
      selectEvent(events[index + 1]);
    }, 2500);

    return () => clearInterval(interval);
  }, [isPlaying, events, selectedEventId]);

  const selectedMeta = selectedEvent ? EVENT_META[selectedEvent.eventType] : null;
  const SelectedIcon = selectedMeta?.icon;
  const metadataEntries = selectedEvent?.metadata
    ? Object.entries(selectedEvent.metadata)
    : [];

  if (timelineLoading) {
    return (
      <div className="h-[calc(100vh-3.5rem)] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-2 text-muted-foreground">Loading time machine...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Time Machine"
        description="Navigate through historical infrastructure states"
        actions={
          <div className="flex items-center gap-4">
            {/* Date Range Selector */}
            <DateRangeSelector
              preset={dateRangePreset}
              onPresetChange={setDateRangePreset}
              startDate={startDate}
              endDate={endDate}
              onStartChange={setStartDate}
              onEndChange={setEndDate}
            />

            {/* View Mode Toggle */}
            <div className="flex rounded-lg border bg-muted/40 p-0.5">
              <button
                onClick={() => setViewMode('timeline')}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 text-xs rounded-md transition-colors',
                  viewMode === 'timeline' ? 'bg-background shadow-sm' : 'hover:bg-background/50'
                )}
              >
                <List className="h-3 w-3" />
                Timeline
              </button>
              <button
                onClick={() => setViewMode('calendar')}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 text-xs rounded-md transition-colors',
                  viewMode === 'calendar' ? 'bg-background shadow-sm' : 'hover:bg-background/50'
                )}
              >
                <CalendarDays className="h-3 w-3" />
                Calendar
              </button>
            </div>

            {/* Playback Controls */}
            <div className="flex items-center gap-1">
              <button
                onClick={handleStepBack}
                className="rounded-lg border px-3 py-2 text-sm hover:bg-muted transition-colors disabled:opacity-50"
                title="Previous event"
                disabled={selectedIndex <= 0}
              >
                <SkipBack className="h-4 w-4" />
              </button>
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className={cn(
                  'rounded-lg border px-3 py-2 text-sm transition-colors',
                  isPlaying ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
                )}
                title={isPlaying ? 'Pause' : 'Play'}
                disabled={!events.length}
              >
                {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              </button>
              <button
                onClick={handleStepForward}
                className="rounded-lg border px-3 py-2 text-sm hover:bg-muted transition-colors disabled:opacity-50"
                title="Next event"
                disabled={selectedIndex === -1 || selectedIndex >= events.length - 1}
              >
                <SkipForward className="h-4 w-4" />
              </button>
            </div>
          </div>
        }
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]"
      >
        <motion.div variants={staggerItemVariants}>
          {viewMode === 'timeline' ? (
            <EventStream
              events={events}
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
            />
          )}
        </motion.div>

        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-5 shadow-sm"
        >
          {!selectedEvent || !selectedTimestamp ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
              <History className="h-10 w-10" />
              <p className="mt-3 text-sm">
                No events yet. Once nodes, networks, or profiles change, they&apos;ll appear here.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <div className={cn('rounded-lg p-2', selectedMeta?.color || 'bg-muted')}>
                  {SelectedIcon ? (
                    <SelectedIcon className="h-4 w-4 text-white" />
                  ) : (
                    <History className="h-4 w-4 text-white" />
                  )}
                </div>
                <div>
                  <h3 className="text-lg font-semibold">
                    {selectedMeta?.label || selectedEvent.eventType}
                  </h3>
                  <p className="text-sm text-muted-foreground">{selectedEvent.description}</p>
                </div>
              </div>

              <div className="mt-5 space-y-3 text-sm">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span>{formatDate(selectedTimestamp)}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  <span>{formatDateTime(selectedTimestamp)}</span>
                </div>
                <div className="rounded-lg border bg-muted/40 px-3 py-2 text-xs font-mono">
                  {selectedEvent.entityType}: {selectedEvent.entityId}
                </div>
              </div>

              {metadataEntries.length > 0 && (
                <div className="mt-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Metadata
                  </p>
                  <div className="mt-2 space-y-2 text-sm">
                    {metadataEntries.slice(0, 6).map(([key, value]) => (
                      <div key={key} className="flex items-start justify-between gap-4">
                        <span className="text-muted-foreground">{key}</span>
                        <span className="text-right font-mono text-xs">
                          {typeof value === 'string' ? value : JSON.stringify(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </motion.div>
      </motion.div>

      <motion.div
        variants={staggerItemVariants}
        className="rounded-xl border bg-card overflow-hidden shadow-sm"
      >
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <h3 className="text-lg font-semibold">Topology Snapshot</h3>
            <p className="text-sm text-muted-foreground">
              {selectedTimestamp ? formatDateTime(selectedTimestamp) : 'Select an event'}
            </p>
          </div>
        </div>
        <div className="h-[540px]">
          <HistoricalTopology
            timestamp={selectedTimestamp || now}
            compareTimestamp={null}
            topologyState={
              topologyState?.graph
                ? {
                    nodes: topologyState.graph.nodes?.map((node) => ({
                      id: node.id,
                      class: (node.data?.class as string) || 'compute',
                      type: (node.data?.type as string) || node.type,
                      kind: (node.data?.kind as string) || 'unknown',
                      status: (node.data?.status as string) || 'unknown',
                      profileVersion: node.data?.profileVersion as string | undefined,
                    })),
                    edges: topologyState.graph.edges?.map((edge) => ({
                      from: edge.source,
                      to: edge.target,
                      type: edge.type,
                    })),
                  }
                : null
            }
            isLoading={topologyLoading}
          />
        </div>
      </motion.div>
    </div>
  );
}
