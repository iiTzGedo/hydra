import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  History,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Calendar,
  Clock,
  Server,
  GitCompare,
  Loader2,
} from 'lucide-react';
import { useTopologies } from '@/api/topologies';
import { useTimeline, useTopologyStateAt } from '@/api/timemachine';
import { PageHeader } from '@/components/layout/page-header';
import { TimelineScrubber } from '@/components/timemachine/timeline-scrubber';
import { HistoricalTopology } from '@/components/timemachine/historical-topology';
import { cn, formatDate } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function TimeMachinePage() {
  const [selectedTimestamp, setSelectedTimestamp] = useState<Date>(new Date());
  const [isPlaying, setIsPlaying] = useState(false);
  const [comparisonMode, setComparisonMode] = useState(false);
  const [compareTimestamp, setCompareTimestamp] = useState<Date | null>(null);

  const { data: topologies, isLoading: topologiesLoading } = useTopologies({ limit: 50 });
  const { data: timeline, isLoading: timelineLoading } = useTimeline();
  const { data: topologyState, isLoading: stateLoading } = useTopologyStateAt(
    selectedTimestamp.toISOString()
  );

  const isLoading = topologiesLoading || timelineLoading;

  // Generate timeline events from topologies
  const timelineEvents = useMemo(() => {
    if (!topologies?.items) return [];

    return topologies.items.map((t) => ({
      timestamp: new Date(t.createdAt),
      type: 'topology' as const,
      label: `Topology ${t.topologyId.slice(0, 8)}`,
      id: t.topologyId,
    }));
  }, [topologies]);

  // Calculate time range from events
  const timeRange = useMemo(() => {
    if (!timelineEvents.length) {
      const now = new Date();
      return {
        start: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000),
        end: now,
      };
    }

    const timestamps = timelineEvents.map((e) => e.timestamp.getTime());
    return {
      start: new Date(Math.min(...timestamps)),
      end: new Date(Math.max(...timestamps)),
    };
  }, [timelineEvents]);

  const handleTimeChange = (timestamp: Date) => {
    setSelectedTimestamp(timestamp);
  };

  const handleStepBack = () => {
    // Find the previous event
    const prevEvents = timelineEvents.filter(
      (e) => e.timestamp.getTime() < selectedTimestamp.getTime()
    );
    if (prevEvents.length > 0) {
      setSelectedTimestamp(prevEvents[prevEvents.length - 1].timestamp);
    }
  };

  const handleStepForward = () => {
    // Find the next event
    const nextEvents = timelineEvents.filter(
      (e) => e.timestamp.getTime() > selectedTimestamp.getTime()
    );
    if (nextEvents.length > 0) {
      setSelectedTimestamp(nextEvents[0].timestamp);
    }
  };

  const toggleComparisonMode = () => {
    if (!comparisonMode) {
      setCompareTimestamp(selectedTimestamp);
    } else {
      setCompareTimestamp(null);
    }
    setComparisonMode(!comparisonMode);
  };

  if (isLoading) {
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
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Header */}
      <div className="border-b p-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2">
              <History className="h-5 w-5" />
              Time Machine
            </h1>
            <p className="text-sm text-muted-foreground">
              Navigate through historical infrastructure states
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleComparisonMode}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm',
                'border transition-colors',
                comparisonMode
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted'
              )}
            >
              <GitCompare className="h-4 w-4" />
              {comparisonMode ? 'Exit Compare' : 'Compare'}
            </button>
          </div>
        </div>
      </div>

      {/* Current time display */}
      <div className="border-b bg-muted/30 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">{formatDate(selectedTimestamp)}</span>
            </div>
            {comparisonMode && compareTimestamp && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <span>vs</span>
                <span>{formatDate(compareTimestamp)}</span>
              </div>
            )}
          </div>

          {/* Playback controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={handleStepBack}
              className="rounded-lg p-2 hover:bg-muted transition-colors"
              title="Previous event"
            >
              <SkipBack className="h-4 w-4" />
            </button>
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className={cn(
                'rounded-lg p-2 transition-colors',
                isPlaying ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
              )}
              title={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </button>
            <button
              onClick={handleStepForward}
              className="rounded-lg p-2 hover:bg-muted transition-colors"
              title="Next event"
            >
              <SkipForward className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Timeline scrubber */}
      <div className="border-b p-4 bg-card">
        <TimelineScrubber
          timeRange={timeRange}
          events={timelineEvents}
          currentTime={selectedTimestamp}
          compareTime={compareTimestamp}
          onTimeChange={handleTimeChange}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-hidden">
        <HistoricalTopology
          timestamp={selectedTimestamp}
          compareTimestamp={compareTimestamp}
          topologyState={topologyState ? {
            nodes: topologyState.graph?.nodes?.map(n => ({
              id: n.id,
              class: n.data?.class as string || 'compute',
              type: n.data?.type as string || n.type,
              kind: n.data?.kind as string || 'unknown',
              status: n.data?.status as string || 'unknown',
              profileVersion: n.data?.profileVersion as string | undefined,
            })),
            edges: topologyState.graph?.edges?.map(e => ({
              from: e.source,
              to: e.target,
              type: e.type,
            })),
          } : null}
          isLoading={stateLoading}
        />
      </div>
    </div>
  );
}
