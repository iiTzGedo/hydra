import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { NODE_KIND_LABELS } from '@/lib/constants';
import { NodeClass, NodeType } from '@/types/node';

export interface NodeFilterState {
  search: string;
  class: NodeClass | null;
  type: NodeType | null;
  kind: string | null;
  status: 'active' | 'inactive' | 'archived' | null;
}

interface NodeFiltersProps {
  filters: NodeFilterState;
  onFiltersChange: (filters: NodeFilterState) => void;
}

export function NodeFilters({ filters, onFiltersChange }: NodeFiltersProps) {
  const updateFilter = <K extends keyof NodeFilterState>(key: K, value: NodeFilterState[K]) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    onFiltersChange({
      search: '',
      class: null,
      type: null,
      kind: null,
      status: null,
    });
  };

  const hasActiveFilters = filters.class || filters.type || filters.kind || filters.status;

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search nodes..."
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
            value={filters.class || ''}
            onChange={(e) => updateFilter('class', (e.target.value as NodeClass) || null)}
            className={cn(
              'rounded-lg border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring'
            )}
          >
            <option value="">All Classes</option>
            <option value="compute">Compute</option>
            <option value="networking">Networking</option>
            <option value="iot">IoT</option>
          </select>

          <select
            value={filters.type || ''}
            onChange={(e) => updateFilter('type', (e.target.value as NodeType) || null)}
            className={cn(
              'rounded-lg border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring'
            )}
          >
            <option value="">All Types</option>
            <option value="physical">Physical</option>
            <option value="logical">Logical</option>
          </select>

          <select
            value={filters.kind || ''}
            onChange={(e) => updateFilter('kind', e.target.value || null)}
            className={cn(
              'rounded-lg border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring'
            )}
          >
            <option value="">All Kinds</option>
            {Object.entries(NODE_KIND_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <select
            value={filters.status || ''}
            onChange={(e) => updateFilter('status', (e.target.value as 'active' | 'inactive' | 'archived') || null)}
            className={cn(
              'rounded-lg border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring'
            )}
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="archived">Archived</option>
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
