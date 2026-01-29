import { useCallback, useState } from 'react';
import { Search, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export interface FilterOption {
  value: string;
  label: string;
}

export interface SelectFilterConfig {
  type: 'select';
  key: string;
  label: string;
  options: FilterOption[];
  allLabel?: string;
  className?: string;
}

export interface SearchFilterConfig {
  type: 'search';
  key: string;
  placeholder?: string;
  className?: string;
}

export type FilterConfig = SelectFilterConfig | SearchFilterConfig;

export interface FilterBarProps<T extends Record<string, string>> {
  filters: T;
  onFilterChange: (key: keyof T, value: string) => void;
  onClearAll?: () => void;
  config: FilterConfig[];
  className?: string;
  children?: React.ReactNode;
}

export function FilterBar<T extends Record<string, string>>({
  filters,
  onFilterChange,
  onClearAll,
  config,
  className,
  children,
}: FilterBarProps<T>) {
  const hasActiveFilters = Object.entries(filters).some(([key, value]) => {
    const filterConfig = config.find((c) => c.key === key);
    if (!filterConfig) return false;
    if (filterConfig.type === 'search') return value !== '';
    if (filterConfig.type === 'select') return value !== 'all';
    return false;
  });

  const handleClear = useCallback(() => {
    if (onClearAll) {
      onClearAll();
    }
  }, [onClearAll]);

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      {config.map((filterConfig) => {
        if (filterConfig.type === 'search') {
          return (
            <div key={filterConfig.key} className={cn('relative', filterConfig.className)}>
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={filterConfig.placeholder ?? 'Search...'}
                value={filters[filterConfig.key as keyof T] ?? ''}
                onChange={(e) => onFilterChange(filterConfig.key as keyof T, e.target.value)}
                className="pl-8 w-[200px] sm:w-[250px]"
              />
            </div>
          );
        }

        if (filterConfig.type === 'select') {
          return (
            <Select
              key={filterConfig.key}
              value={filters[filterConfig.key as keyof T] ?? 'all'}
              onValueChange={(value) => onFilterChange(filterConfig.key as keyof T, value)}
            >
              <SelectTrigger className={cn('w-[140px]', filterConfig.className)}>
                <SelectValue placeholder={filterConfig.label} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{filterConfig.allLabel ?? `All ${filterConfig.label}`}</SelectItem>
                {filterConfig.options.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          );
        }

        return null;
      })}

      {hasActiveFilters && onClearAll && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClear}
              className="h-9 px-2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4 mr-1" />
              Clear
            </Button>
          </TooltipTrigger>
          <TooltipContent>Clear all filters</TooltipContent>
        </Tooltip>
      )}

      {children}
    </div>
  );
}

export function getDefaultFilters<T extends Record<string, string>>(
  config: FilterConfig[]
): T {
  const defaults = {} as T;
  for (const filterConfig of config) {
    if (filterConfig.type === 'search') {
      (defaults as Record<string, string>)[filterConfig.key] = '';
    } else if (filterConfig.type === 'select') {
      (defaults as Record<string, string>)[filterConfig.key] = 'all';
    }
  }
  return defaults;
}

export function useFilterState<T extends Record<string, string>>(
  initialState: T
): [T, (key: keyof T, value: string) => void, () => void] {
  const [filters, setFilters] = useState<T>(initialState);

  const updateFilter = useCallback((key: keyof T, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const clearFilters = useCallback(() => {
    const cleared = {} as T;
    for (const key of Object.keys(initialState)) {
      const typedKey = key as keyof T;
      const initialValue = initialState[typedKey];
      (cleared as Record<string, string>)[key] = typeof initialValue === 'string' && initialValue !== '' ? '' : 'all';
    }
    setFilters(cleared);
  }, [initialState]);

  return [filters, updateFilter, clearFilters];
}
