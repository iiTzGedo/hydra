import { Search } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface GroupFilterState {
  search: string;
}

interface GroupFiltersProps {
  filters: GroupFilterState;
  onFiltersChange: (filters: GroupFilterState) => void;
}

export function GroupFilters({ filters, onFiltersChange }: GroupFiltersProps) {
  const updateFilter = <K extends keyof GroupFilterState>(key: K, value: GroupFilterState[K]) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search groups..."
          value={filters.search}
          onChange={(e) => updateFilter('search', e.target.value)}
          className={cn(
            'w-full rounded-lg border bg-background pl-10 pr-4 py-2 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-ring',
            'placeholder:text-muted-foreground'
          )}
        />
      </div>
    </div>
  );
}
