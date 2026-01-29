/**
 * Generic filters hook for list views.
 *
 * Provides typed filter state management with optional URL synchronization.
 * Automatically resets pagination when filters change.
 *
 * @example
 * ```tsx
 * interface NodeFilters {
 *   search?: string;
 *   class?: string;
 *   status?: string;
 * }
 *
 * const { filters, setFilter, setFilters, clearFilters, hasFilters } = useFilters<NodeFilters>({
 *   initial: { status: 'active' },
 *   onFilterChange: () => pagination.reset(), // Reset to page 0 on filter change
 * });
 *
 * // Use in query
 * const { data } = useNodes({ ...filters, ...pagination.queryParams });
 *
 * // Update single filter
 * <Select onValueChange={(v) => setFilter('status', v)} />
 *
 * // Clear all filters
 * <Button onClick={clearFilters}>Clear</Button>
 * ```
 */

import { useState, useCallback, useMemo } from 'react';

export interface UseFiltersOptions<T extends Record<string, unknown>> {
  /** Initial filter values */
  initial?: Partial<T>;
  /** Callback when any filter changes (useful for resetting pagination) */
  onFilterChange?: () => void;
}

export interface UseFiltersReturn<T extends Record<string, unknown>> {
  /** Current filter values */
  filters: T;
  /** Set a single filter value */
  setFilter: <K extends keyof T>(key: K, value: T[K]) => void;
  /** Set multiple filter values at once */
  setFilters: (updates: Partial<T>) => void;
  /** Clear all filters to initial state */
  clearFilters: () => void;
  /** Reset a single filter to its initial value */
  resetFilter: <K extends keyof T>(key: K) => void;
  /** Whether any non-initial filters are set */
  hasFilters: boolean;
  /** Count of active filters */
  filterCount: number;
  /** Get query params for API (excludes empty values) */
  queryParams: Record<string, unknown>;
}

export function useFilters<T extends Record<string, unknown>>({
  initial = {} as Partial<T>,
  onFilterChange,
}: UseFiltersOptions<T> = {}): UseFiltersReturn<T> {
  const [filters, setFiltersState] = useState<T>(initial as T);

  const setFilter = useCallback(
    <K extends keyof T>(key: K, value: T[K]) => {
      setFiltersState((prev) => {
        const newFilters = { ...prev, [key]: value };
        return newFilters;
      });
      onFilterChange?.();
    },
    [onFilterChange]
  );

  const setFilters = useCallback(
    (updates: Partial<T>) => {
      setFiltersState((prev) => ({ ...prev, ...updates }));
      onFilterChange?.();
    },
    [onFilterChange]
  );

  const clearFilters = useCallback(() => {
    setFiltersState(initial as T);
    onFilterChange?.();
  }, [initial, onFilterChange]);

  const resetFilter = useCallback(
    <K extends keyof T>(key: K) => {
      setFiltersState((prev) => ({
        ...prev,
        [key]: initial[key as keyof typeof initial],
      }));
      onFilterChange?.();
    },
    [initial, onFilterChange]
  );

  const hasFilters = useMemo(() => {
    return Object.entries(filters).some(([key, value]) => {
      const initialValue = initial[key as keyof typeof initial];
      return value !== initialValue && value !== '' && value !== undefined && value !== null;
    });
  }, [filters, initial]);

  const filterCount = useMemo(() => {
    return Object.entries(filters).filter(([key, value]) => {
      const initialValue = initial[key as keyof typeof initial];
      return value !== initialValue && value !== '' && value !== undefined && value !== null;
    }).length;
  }, [filters, initial]);

  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = {};
    Object.entries(filters).forEach(([key, value]) => {
      // Only include non-empty values in query params
      if (value !== '' && value !== undefined && value !== null) {
        params[key] = value;
      }
    });
    return params;
  }, [filters]);

  return {
    filters,
    setFilter,
    setFilters,
    clearFilters,
    resetFilter,
    hasFilters,
    filterCount,
    queryParams,
  };
}

export default useFilters;
