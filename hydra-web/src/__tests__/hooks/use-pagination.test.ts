/**
 * Tests for usePagination hook.
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePagination } from '@/hooks/use-pagination';

describe('usePagination', () => {
  describe('initialization', () => {
    it('should initialize with default values', () => {
      const { result } = renderHook(() => usePagination({ total: 100 }));

      expect(result.current.page).toBe(0);
      expect(result.current.limit).toBe(20);
      expect(result.current.offset).toBe(0);
      expect(result.current.totalPages).toBe(5);
    });

    it('should respect custom limit', () => {
      const { result } = renderHook(() => usePagination({ total: 100, limit: 10 }));

      expect(result.current.limit).toBe(10);
      expect(result.current.totalPages).toBe(10);
    });

    it('should respect initial page', () => {
      const { result } = renderHook(() =>
        usePagination({ total: 100, initialPage: 2 })
      );

      expect(result.current.page).toBe(2);
      expect(result.current.offset).toBe(40);
    });
  });

  describe('page navigation', () => {
    it('should navigate to next page', () => {
      const { result } = renderHook(() => usePagination({ total: 100 }));

      act(() => {
        result.current.nextPage();
      });

      expect(result.current.page).toBe(1);
      expect(result.current.offset).toBe(20);
    });

    it('should not go past last page', () => {
      const { result } = renderHook(() =>
        usePagination({ total: 100, initialPage: 4 })
      );

      act(() => {
        result.current.nextPage();
      });

      expect(result.current.page).toBe(4);
    });

    it('should navigate to previous page', () => {
      const { result } = renderHook(() =>
        usePagination({ total: 100, initialPage: 2 })
      );

      act(() => {
        result.current.prevPage();
      });

      expect(result.current.page).toBe(1);
    });

    it('should not go before first page', () => {
      const { result } = renderHook(() => usePagination({ total: 100 }));

      act(() => {
        result.current.prevPage();
      });

      expect(result.current.page).toBe(0);
    });

    it('should navigate to first page', () => {
      const { result } = renderHook(() =>
        usePagination({ total: 100, initialPage: 3 })
      );

      act(() => {
        result.current.firstPage();
      });

      expect(result.current.page).toBe(0);
    });

    it('should navigate to last page', () => {
      const { result } = renderHook(() => usePagination({ total: 100 }));

      act(() => {
        result.current.lastPage();
      });

      expect(result.current.page).toBe(4);
    });

    it('should reset to initial page', () => {
      const { result } = renderHook(() =>
        usePagination({ total: 100, initialPage: 1 })
      );

      act(() => {
        result.current.setPage(4);
      });

      expect(result.current.page).toBe(4);

      act(() => {
        result.current.reset();
      });

      expect(result.current.page).toBe(1);
    });
  });

  describe('setPage', () => {
    it('should set valid page', () => {
      const { result } = renderHook(() => usePagination({ total: 100 }));

      act(() => {
        result.current.setPage(3);
      });

      expect(result.current.page).toBe(3);
    });

    it('should bound page to valid range', () => {
      const { result } = renderHook(() => usePagination({ total: 100 }));

      act(() => {
        result.current.setPage(10);
      });

      expect(result.current.page).toBe(4); // Last valid page

      act(() => {
        result.current.setPage(-5);
      });

      expect(result.current.page).toBe(0); // First page
    });
  });

  describe('hasNextPage / hasPrevPage', () => {
    it('should indicate next page availability', () => {
      const { result } = renderHook(() => usePagination({ total: 40 }));

      expect(result.current.hasNextPage).toBe(true);
      expect(result.current.hasPrevPage).toBe(false);

      act(() => {
        result.current.lastPage();
      });

      expect(result.current.hasNextPage).toBe(false);
      expect(result.current.hasPrevPage).toBe(true);
    });

    it('should handle single page', () => {
      const { result } = renderHook(() => usePagination({ total: 10 }));

      expect(result.current.hasNextPage).toBe(false);
      expect(result.current.hasPrevPage).toBe(false);
      expect(result.current.totalPages).toBe(1);
    });
  });

  describe('queryParams', () => {
    it('should provide correct query params', () => {
      const { result } = renderHook(() =>
        usePagination({ total: 100, limit: 25 })
      );

      expect(result.current.queryParams).toEqual({ limit: 25, offset: 0 });

      act(() => {
        result.current.setPage(2);
      });

      expect(result.current.queryParams).toEqual({ limit: 25, offset: 50 });
    });
  });

  describe('edge cases', () => {
    it('should handle zero total', () => {
      const { result } = renderHook(() => usePagination({ total: 0 }));

      expect(result.current.totalPages).toBe(1);
      expect(result.current.page).toBe(0);
    });

    it('should adjust page when total decreases', () => {
      const { result, rerender } = renderHook(
        ({ total }) => usePagination({ total }),
        { initialProps: { total: 100 } }
      );

      act(() => {
        result.current.setPage(4);
      });

      expect(result.current.page).toBe(4);

      // Simulate total decreasing (e.g., items deleted)
      rerender({ total: 50 });

      // Page should be adjusted to be within bounds
      expect(result.current.page).toBeLessThanOrEqual(2);
    });
  });
});
