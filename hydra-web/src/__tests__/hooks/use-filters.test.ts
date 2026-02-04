/**
 * Tests for useFilters hook.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFilters } from '@/hooks/use-filters';

interface TestFilters {
  search?: string;
  status?: string;
  category?: string;
  [key: string]: string | undefined;
}

describe('useFilters', () => {
  describe('initialization', () => {
    it('should initialize with empty filters by default', () => {
      const { result } = renderHook(() => useFilters<TestFilters>());

      expect(result.current.filters).toEqual({});
      expect(result.current.hasFilters).toBe(false);
      expect(result.current.filterCount).toBe(0);
    });

    it('should initialize with provided initial values', () => {
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ initial: { status: 'active' } })
      );

      expect(result.current.filters.status).toBe('active');
      expect(result.current.hasFilters).toBe(false); // Initial value doesn't count as active filter
    });
  });

  describe('setFilter', () => {
    it('should set a single filter value', () => {
      const { result } = renderHook(() => useFilters<TestFilters>());

      act(() => {
        result.current.setFilter('search', 'test');
      });

      expect(result.current.filters.search).toBe('test');
      expect(result.current.hasFilters).toBe(true);
      expect(result.current.filterCount).toBe(1);
    });

    it('should call onFilterChange callback', () => {
      const onFilterChange = vi.fn();
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ onFilterChange })
      );

      act(() => {
        result.current.setFilter('search', 'test');
      });

      expect(onFilterChange).toHaveBeenCalledTimes(1);
    });

    it('should update existing filter value', () => {
      const { result } = renderHook(() => useFilters<TestFilters>());

      act(() => {
        result.current.setFilter('search', 'first');
      });

      act(() => {
        result.current.setFilter('search', 'second');
      });

      expect(result.current.filters.search).toBe('second');
      expect(result.current.filterCount).toBe(1);
    });
  });

  describe('setFilters', () => {
    it('should set multiple filter values at once', () => {
      const { result } = renderHook(() => useFilters<TestFilters>());

      act(() => {
        result.current.setFilters({ search: 'test', status: 'active' });
      });

      expect(result.current.filters.search).toBe('test');
      expect(result.current.filters.status).toBe('active');
      expect(result.current.filterCount).toBe(2);
    });

    it('should merge with existing filters', () => {
      const { result } = renderHook(() => useFilters<TestFilters>());

      act(() => {
        result.current.setFilter('category', 'nodes');
      });

      act(() => {
        result.current.setFilters({ search: 'test' });
      });

      expect(result.current.filters.category).toBe('nodes');
      expect(result.current.filters.search).toBe('test');
    });
  });

  describe('clearFilters', () => {
    it('should reset all filters to initial state', () => {
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ initial: { status: 'active' } })
      );

      act(() => {
        result.current.setFilter('search', 'test');
        result.current.setFilter('category', 'nodes');
      });

      expect(result.current.filterCount).toBe(2);

      act(() => {
        result.current.clearFilters();
      });

      expect(result.current.filters).toEqual({ status: 'active' });
      expect(result.current.hasFilters).toBe(false);
    });

    it('should call onFilterChange callback', () => {
      const onFilterChange = vi.fn();
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ onFilterChange })
      );

      act(() => {
        result.current.setFilter('search', 'test');
      });

      onFilterChange.mockClear();

      act(() => {
        result.current.clearFilters();
      });

      expect(onFilterChange).toHaveBeenCalledTimes(1);
    });
  });

  describe('resetFilter', () => {
    it('should reset a single filter to its initial value', () => {
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ initial: { status: 'active' } })
      );

      act(() => {
        result.current.setFilter('status', 'inactive');
        result.current.setFilter('search', 'test');
      });

      act(() => {
        result.current.resetFilter('status');
      });

      expect(result.current.filters.status).toBe('active');
      expect(result.current.filters.search).toBe('test');
    });
  });

  describe('hasFilters', () => {
    it('should be false when filters match initial state', () => {
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ initial: { status: 'active' } })
      );

      expect(result.current.hasFilters).toBe(false);

      act(() => {
        result.current.setFilter('status', 'inactive');
      });

      expect(result.current.hasFilters).toBe(true);

      act(() => {
        result.current.setFilter('status', 'active');
      });

      expect(result.current.hasFilters).toBe(false);
    });

    it('should ignore empty/null/undefined values', () => {
      const { result } = renderHook(() => useFilters<TestFilters>());

      act(() => {
        result.current.setFilter('search', '');
      });

      expect(result.current.hasFilters).toBe(false);

      act(() => {
        result.current.setFilter('search', undefined);
      });

      expect(result.current.hasFilters).toBe(false);
    });
  });

  describe('filterCount', () => {
    it('should count active non-initial filters', () => {
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ initial: { status: 'active' } })
      );

      expect(result.current.filterCount).toBe(0);

      act(() => {
        result.current.setFilter('search', 'test');
      });

      expect(result.current.filterCount).toBe(1);

      act(() => {
        result.current.setFilter('category', 'nodes');
      });

      expect(result.current.filterCount).toBe(2);

      act(() => {
        result.current.setFilter('status', 'inactive');
      });

      expect(result.current.filterCount).toBe(3);
    });
  });

  describe('queryParams', () => {
    it('should exclude empty values from query params', () => {
      const { result } = renderHook(() => useFilters<TestFilters>());

      act(() => {
        result.current.setFilter('search', 'test');
        result.current.setFilter('status', '');
        result.current.setFilter('category', undefined);
      });

      expect(result.current.queryParams).toEqual({ search: 'test' });
    });

    it('should include all non-empty values', () => {
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ initial: { status: 'active' } })
      );

      act(() => {
        result.current.setFilter('search', 'test');
      });

      expect(result.current.queryParams).toEqual({
        status: 'active',
        search: 'test',
      });
    });
  });

  describe('integration with pagination reset', () => {
    it('should call onFilterChange for pagination reset', () => {
      const mockReset = vi.fn();
      const { result } = renderHook(() =>
        useFilters<TestFilters>({ onFilterChange: mockReset })
      );

      act(() => {
        result.current.setFilter('search', 'test');
      });

      expect(mockReset).toHaveBeenCalledTimes(1);

      act(() => {
        result.current.setFilters({ status: 'active' });
      });

      expect(mockReset).toHaveBeenCalledTimes(2);

      act(() => {
        result.current.clearFilters();
      });

      expect(mockReset).toHaveBeenCalledTimes(3);
    });
  });
});
