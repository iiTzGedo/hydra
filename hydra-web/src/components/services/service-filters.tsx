import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SERVICE_RUNTIME_LABELS } from '@/lib/constants';
import { ServiceRuntime, ServiceStatus } from '@/types/service';
import { EntityCombobox } from '@/components/ui/entity-combobox';

export interface ServiceFilterState {
  search: string;
  runtime: ServiceRuntime | null;
  status: ServiceStatus | null;
  nodeId: string | null;
}

interface ServiceFiltersProps {
  filters: ServiceFilterState;
  onFiltersChange: (filters: ServiceFilterState) => void;
}

export function ServiceFilters({ filters, onFiltersChange }: ServiceFiltersProps) {
  const updateFilter = <K extends keyof ServiceFilterState>(key: K, value: ServiceFilterState[K]) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    onFiltersChange({
      search: '',
      runtime: null,
      status: null,
      nodeId: null,
    });
  };

  const hasActiveFilters = filters.runtime || filters.status || filters.nodeId;

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search services..."
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
            value={filters.runtime || ''}
            onChange={(e) => updateFilter('runtime', (e.target.value as ServiceRuntime) || null)}
            className={cn(
              'rounded-lg border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring'
            )}
          >
            <option value="">All Runtimes</option>
            {Object.entries(SERVICE_RUNTIME_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <select
            value={filters.status || ''}
            onChange={(e) => updateFilter('status', (e.target.value as ServiceStatus) || null)}
            className={cn(
              'rounded-lg border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring'
            )}
          >
            <option value="">All Statuses</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="paused">Paused</option>
            <option value="error">Error</option>
            <option value="unknown">Unknown</option>
          </select>

          <EntityCombobox
            entityType="node"
            value={filters.nodeId ?? ''}
            onValueChange={(val) => updateFilter('nodeId', val || null)}
            clearable
            placeholder="Filter by node..."
            className="w-48"
          />

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
