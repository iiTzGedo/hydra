import { useRef, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface TimelineEvent {
  timestamp: Date;
  type: 'topology' | 'profile' | 'change';
  label: string;
  id: string;
}

interface TimelineScrubberProps {
  timeRange: { start: Date; end: Date };
  events: TimelineEvent[];
  currentTime: Date;
  compareTime: Date | null;
  onTimeChange: (timestamp: Date) => void;
}

export function TimelineScrubber({
  timeRange,
  events,
  currentTime,
  compareTime,
  onTimeChange,
}: TimelineScrubberProps) {
  const trackRef = useRef<HTMLDivElement>(null);

  const getPositionPercent = useCallback(
    (timestamp: Date) => {
      const range = timeRange.end.getTime() - timeRange.start.getTime();
      if (range === 0) return 0;
      const position = timestamp.getTime() - timeRange.start.getTime();
      return Math.max(0, Math.min(100, (position / range) * 100));
    },
    [timeRange]
  );

  const getTimeFromPosition = useCallback(
    (percent: number) => {
      const range = timeRange.end.getTime() - timeRange.start.getTime();
      return new Date(timeRange.start.getTime() + (percent / 100) * range);
    },
    [timeRange]
  );

  const handleTrackClick = useCallback(
    (e: React.MouseEvent) => {
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const percent = ((e.clientX - rect.left) / rect.width) * 100;
      onTimeChange(getTimeFromPosition(percent));
    },
    [getTimeFromPosition, onTimeChange]
  );

  const currentPercent = getPositionPercent(currentTime);
  const comparePercent = compareTime ? getPositionPercent(compareTime) : null;

  const timeLabels = useMemo(() => {
    const labels = [];
    const range = timeRange.end.getTime() - timeRange.start.getTime();
    const numLabels = 5;

    for (let i = 0; i <= numLabels; i++) {
      const time = new Date(timeRange.start.getTime() + (range * i) / numLabels);
      labels.push({
        percent: (i / numLabels) * 100,
        label: time.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }),
      });
    }
    return labels;
  }, [timeRange]);

  const eventTypeColors = {
    topology: 'bg-primary',
    profile: 'bg-success',
    change: 'bg-warning',
  };

  return (
    <div className="space-y-4">
      <div
        ref={trackRef}
        onClick={handleTrackClick}
        className="relative h-12 cursor-pointer"
      >
        <div className="absolute inset-x-0 top-5 h-2 rounded-full bg-muted" />

        <div
          className="absolute top-5 left-0 h-2 rounded-full bg-primary/30"
          style={{ width: `${currentPercent}%` }}
        />

        {comparePercent !== null && (
          <motion.div
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            className="absolute top-4 -translate-x-1/2"
            style={{ left: `${comparePercent}%` }}
          >
            <div className="h-4 w-4 rounded-full border-2 border-warning bg-background shadow-lg" />
            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs text-warning">
              Compare
            </div>
          </motion.div>
        )}

        {events.map((event) => {
          const percent = getPositionPercent(event.timestamp);
          return (
            <button
              key={event.id}
              onClick={(e) => {
                e.stopPropagation();
                onTimeChange(event.timestamp);
              }}
              className={cn(
                'absolute top-4 -translate-x-1/2 h-4 w-4 rounded-full',
                'hover:scale-125 transition-transform',
                eventTypeColors[event.type],
                'shadow-sm'
              )}
              style={{ left: `${percent}%` }}
              title={event.label}
            />
          );
        })}

        <motion.div
          className="absolute top-2 -translate-x-1/2 cursor-grab active:cursor-grabbing"
          style={{ left: `${currentPercent}%` }}
          drag="x"
          dragConstraints={trackRef}
          dragElastic={0}
          onDrag={(_, info) => {
            if (!trackRef.current) return;
            const rect = trackRef.current.getBoundingClientRect();
            const x = info.point.x - rect.left;
            const percent = Math.max(0, Math.min(100, (x / rect.width) * 100));
            onTimeChange(getTimeFromPosition(percent));
          }}
        >
          <div className="flex flex-col items-center">
            <div className="h-8 w-8 rounded-full border-4 border-primary bg-background shadow-lg flex items-center justify-center">
              <div className="h-3 w-3 rounded-full bg-primary" />
            </div>
          </div>
        </motion.div>
      </div>

      <div className="relative h-4">
        {timeLabels.map((label, i) => (
          <div
            key={i}
            className="absolute -translate-x-1/2 text-xs text-muted-foreground"
            style={{ left: `${label.percent}%` }}
          >
            {label.label}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-primary" />
          <span>Topology</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-success" />
          <span>Profile</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-warning" />
          <span>Change</span>
        </div>
      </div>
    </div>
  );
}
