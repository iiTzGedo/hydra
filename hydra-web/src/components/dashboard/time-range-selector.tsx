import { useState } from 'react';
import { Calendar, ChevronDown, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useDashboardStore, type TimeRangePreset } from '@/stores/dashboard-store';
import { cn } from '@/lib/utils';

const TIME_RANGE_PRESETS: { value: TimeRangePreset; label: string }[] = [
  { value: 'last1h', label: 'Last Hour' },
  { value: 'last24h', label: 'Last 24 Hours' },
  { value: 'last7d', label: 'Last 7 Days' },
  { value: 'last30d', label: 'Last 30 Days' },
];

/**
 * TimeRangeSelector - Dashboard time range filter
 *
 * Filters the Recent Activity widget by the selected time range.
 * The selected range is persisted in the dashboard store (localStorage).
 */
export function TimeRangeSelector() {
  const { timeRange, setTimeRange, setCustomTimeRange, getTimeRangeLabel } = useDashboardStore();
  const [isOpen, setIsOpen] = useState(false);
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  const handlePresetSelect = (preset: TimeRangePreset) => {
    setTimeRange(preset);
    setIsOpen(false);
  };

  const handleCustomApply = () => {
    if (customFrom && customTo) {
      setCustomTimeRange({
        from: new Date(customFrom),
        to: new Date(customTo),
      });
      setIsOpen(false);
    }
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="bg-card border-border text-foreground hover:bg-muted gap-2"
          title="Filter dashboard activity by time range"
        >
          <Clock className="h-4 w-4" />
          <span className="hidden sm:inline">{getTimeRangeLabel()}</span>
          <ChevronDown className="h-3 w-3 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0 bg-card border-border" align="end">
        <div className="p-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide px-2 py-1.5 mb-1">
            <Calendar className="h-3 w-3" />
            Quick Select
          </div>
          <div className="space-y-0.5">
            {TIME_RANGE_PRESETS.map((preset) => (
              <button
                key={preset.value}
                onClick={() => handlePresetSelect(preset.value)}
                className={cn(
                  "w-full text-left px-3 py-2 text-sm rounded-md transition-colors",
                  timeRange === preset.value
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground hover:bg-muted"
                )}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
        
        <div className="border-t border-border p-3">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide px-2 py-1.5 mb-2">
            Custom Range
          </div>
          <div className="space-y-3 px-2">
            <div className="space-y-1.5">
              <Label htmlFor="from-date" className="text-xs text-muted-foreground">
                From
              </Label>
              <Input
                id="from-date"
                type="datetime-local"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="h-8 text-xs bg-background border-border"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="to-date" className="text-xs text-muted-foreground">
                To
              </Label>
              <Input
                id="to-date"
                type="datetime-local"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className="h-8 text-xs bg-background border-border"
              />
            </div>
            <Button
              onClick={handleCustomApply}
              disabled={!customFrom || !customTo}
              size="sm"
              className="w-full"
              variant="secondary"
            >
              Apply Custom Range
            </Button>
          </div>
        </div>
        
        {/* Info notice */}
        <div className="border-t border-border p-3 bg-muted/30">
          <p className="text-[10px] text-muted-foreground text-center">
            Filters recent activity by time range
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
