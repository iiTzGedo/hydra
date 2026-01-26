import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { NETWORK_TYPE_LABELS } from '@/lib/constants';
import { NetworkType } from '@/types/network';

export interface NetworkFilterState {
  search: string;
  type: NetworkType | null;
}

interface NetworkFiltersProps {
  filters: NetworkFilterState;
  onFiltersChange: (filters: NetworkFilterState) => void;
}

export function NetworkFilters({ filters, onFiltersChange }: NetworkFiltersProps) {
  const updateFilter = <K extends keyof NetworkFilterState>(key: K, value: NetworkFilterState[K]) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    onFiltersChange({
      search: '',
      type: null,
    });
  };

  const hasActiveFilters = filters.type;

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search networks..."
            value={filters.search}
            onChange={(e) => updateFilter('search', e.target.value)}
            className={cn(
              'w-full rounded-lg border bg-background pl-10 pr-4 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring',
              'placeholder:text-muted-foreground'
            )}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={filters.type || ''}
            onChange={(e) => updateFilter('type', (e.target.value as NetworkType) || null)}
            className={cn(
              'rounded-lg border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring'
            )}
          >
            <option value="">All Types</option>
            {Object.entries(NETWORK_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className={cn(
                'inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm',
                'text-muted-foreground hover:text-foreground hover:bg-muted',
                'transition-colors'
              )}
            >
              <X className="h-4 w-4" />
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
