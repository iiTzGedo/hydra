import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-react';
import type { TimelineEvent, TimelineEventType } from '@/types/timemachine';
import { cn } from '@/lib/utils';
import { EVENT_META } from './event-stream';

type CalendarGranularity = 'day' | 'week' | 'month';

interface CalendarViewProps {
  events: TimelineEvent[];
  selectedDate: Date | null;
  onSelectDate: (date: Date) => void;
  range: { start: Date; end: Date };
  onRangeChange?: (start: Date, end: Date) => void;
}

interface DayData {
  date: Date;
  events: TimelineEvent[];
  isCurrentMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
}

function getEventTypeCounts(events: TimelineEvent[]): Record<string, number> {
  return events.reduce((acc, event) => {
    acc[event.eventType] = (acc[event.eventType] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
}

function getDaysInMonth(year: number, month: number): Date[] {
  const days: Date[] = [];
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);

  const startPadding = firstDay.getDay();
  for (let i = startPadding - 1; i >= 0; i--) {
    days.push(new Date(year, month, -i));
  }

  for (let d = 1; d <= lastDay.getDate(); d++) {
    days.push(new Date(year, month, d));
  }

  const endPadding = 6 - lastDay.getDay();
  for (let i = 1; i <= endPadding; i++) {
    days.push(new Date(year, month + 1, i));
  }

  return days;
}

function isSameDay(d1: Date, d2: Date): boolean {
  return d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate();
}

function EventMarkers({ events }: { events: TimelineEvent[] }) {
  const counts = getEventTypeCounts(events);
  const types = Object.keys(counts) as TimelineEventType[];

  if (types.length === 0) return null;

  const displayTypes = types.slice(0, 3);

  return (
    <div className="flex gap-0.5 justify-center mt-1">
      {displayTypes.map((type) => {
        const meta = EVENT_META[type];
        return (
          <span
            key={type}
            className={cn('h-1.5 w-1.5 rounded-full', meta?.color || 'bg-muted-foreground')}
            title={`${counts[type]} ${meta?.label || type}`}
          />
        );
      })}
      {types.length > 3 && (
        <span className="text-[8px] text-muted-foreground">+{types.length - 3}</span>
      )}
    </div>
  );
}

export function CalendarView({
  events,
  selectedDate,
  onSelectDate,
  range: _range,
  onRangeChange,
}: CalendarViewProps) {
  const today = useMemo(() => new Date(), []);
  const [currentMonth, setCurrentMonth] = useState(() => selectedDate || today);
  const [granularity, setGranularity] = useState<CalendarGranularity>('month');

  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();

  const days = useMemo(() => getDaysInMonth(year, month), [year, month]);

  const dayData: DayData[] = useMemo(() => {
    return days.map((date) => {
      const dayStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());
      const dayEnd = new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1);

      const dayEvents = events.filter((event) => {
        const eventDate = new Date(event.timestamp);
        return eventDate >= dayStart && eventDate < dayEnd;
      });

      return {
        date,
        events: dayEvents,
        isCurrentMonth: date.getMonth() === month,
        isToday: isSameDay(date, today),
        isSelected: selectedDate ? isSameDay(date, selectedDate) : false,
      };
    });
  }, [days, events, month, today, selectedDate]);

  const prevMonth = () => {
    const newDate = new Date(year, month - 1, 1);
    setCurrentMonth(newDate);
    if (onRangeChange) {
      const start = new Date(newDate.getFullYear(), newDate.getMonth(), 1);
      const end = new Date(newDate.getFullYear(), newDate.getMonth() + 1, 0);
      onRangeChange(start, end);
    }
  };

  const nextMonth = () => {
    const newDate = new Date(year, month + 1, 1);
    setCurrentMonth(newDate);
    if (onRangeChange) {
      const start = new Date(newDate.getFullYear(), newDate.getMonth(), 1);
      const end = new Date(newDate.getFullYear(), newDate.getMonth() + 1, 0);
      onRangeChange(start, end);
    }
  };

  const goToToday = () => {
    setCurrentMonth(today);
    onSelectDate(today);
  };

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const totalEvents = events.filter((event) => {
    const eventDate = new Date(event.timestamp);
    const monthStart = new Date(year, month, 1);
    const monthEnd = new Date(year, month + 1, 0);
    return eventDate >= monthStart && eventDate <= monthEnd;
  }).length;

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-5 w-5 text-muted-foreground" />
          <div>
            <h3 className="text-lg font-semibold">Calendar View</h3>
            <p className="text-sm text-muted-foreground">
              {totalEvents} events in {monthNames[month]}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border bg-muted/40 p-0.5">
            <button
              onClick={() => setGranularity('day')}
              className={cn(
                'px-2 py-1 text-xs rounded-md transition-colors',
                granularity === 'day' ? 'bg-background shadow-sm' : 'hover:bg-background/50'
              )}
            >
              Day
            </button>
            <button
              onClick={() => setGranularity('week')}
              className={cn(
                'px-2 py-1 text-xs rounded-md transition-colors',
                granularity === 'week' ? 'bg-background shadow-sm' : 'hover:bg-background/50'
              )}
            >
              Week
            </button>
            <button
              onClick={() => setGranularity('month')}
              className={cn(
                'px-2 py-1 text-xs rounded-md transition-colors',
                granularity === 'month' ? 'bg-background shadow-sm' : 'hover:bg-background/50'
              )}
            >
              Month
            </button>
          </div>

          <button
            onClick={goToToday}
            className="px-2 py-1 text-xs rounded-lg border hover:bg-muted transition-colors"
          >
            Today
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <button
          onClick={prevMonth}
          className="p-1 rounded-lg hover:bg-muted transition-colors"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h4 className="text-md font-semibold">
          {monthNames[month]} {year}
        </h4>
        <button
          onClick={nextMonth}
          className="p-1 rounded-lg hover:bg-muted transition-colors"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 mb-2">
        {dayNames.map((day) => (
          <div
            key={day}
            className="text-center text-xs font-medium text-muted-foreground py-1"
          >
            {day}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {dayData.map((day, idx) => (
          <motion.button
            key={idx}
            onClick={() => onSelectDate(day.date)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={cn(
              'aspect-square p-1 rounded-lg text-sm transition-colors relative',
              'hover:bg-muted/60',
              day.isCurrentMonth ? 'text-foreground' : 'text-muted-foreground/50',
              day.isToday && 'ring-2 ring-primary',
              day.isSelected && 'bg-primary text-primary-foreground',
              day.events.length > 0 && !day.isSelected && 'bg-muted/40'
            )}
          >
            <div className="flex flex-col items-center justify-center h-full">
              <span className={cn(
                'text-xs font-medium',
                day.isSelected && 'font-bold'
              )}>
                {day.date.getDate()}
              </span>
              {!day.isSelected && <EventMarkers events={day.events} />}
              {day.isSelected && day.events.length > 0 && (
                <span className="text-[9px] mt-0.5">
                  {day.events.length}
                </span>
              )}
            </div>
          </motion.button>
        ))}
      </div>

      <div className="mt-4 pt-3 border-t">
        <p className="text-xs font-medium text-muted-foreground mb-2">Event Types</p>
        <div className="flex flex-wrap gap-3">
          {(Object.entries(EVENT_META) as [TimelineEventType, typeof EVENT_META[TimelineEventType]][])
            .filter(([type]) =>
              type === 'profile_submitted' ||
              type === 'node_registered' ||
              type === 'node_archived'
            )
            .map(([type, meta]) => (
              <div key={type} className="flex items-center gap-1.5">
                <span className={cn('h-2 w-2 rounded-full', meta.color)} />
                <span className="text-xs text-muted-foreground">{meta.label}</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
