/**
 * Pagination hook for list views.
 *
 * Provides consistent pagination state management across all list pages.
 * Handles page navigation, offset calculation, and total page count.
 *
 * @example
 * ```tsx
 * const { page, setPage, limit, offset, totalPages, queryParams } = usePagination({
 *   limit: 20,
 *   total: data?.total ?? 0,
 * });
 *
 * // Use in query
 * const { data } = useNodes({ ...filters, ...queryParams });
 *
 * // Use in pagination component
 * <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
 * ```
 */

import { useState, useMemo, useCallback } from 'react';

export interface UsePaginationOptions {
  /** Items per page (default: 20) */
  limit?: number;
  /** Total number of items from API response */
  total: number;
  /** Initial page (default: 0) */
  initialPage?: number;
}

export interface UsePaginationReturn {
  /** Current page (0-indexed) */
  page: number;
  /** Set the current page */
  setPage: (page: number) => void;
  /** Items per page */
  limit: number;
  /** Offset for API queries (page * limit) */
  offset: number;
  /** Total number of pages */
  totalPages: number;
  /** Query params object for API calls { limit, offset } */
  queryParams: { limit: number; offset: number };
  /** Go to next page (no-op if on last page) */
  nextPage: () => void;
  /** Go to previous page (no-op if on first page) */
  prevPage: () => void;
  /** Go to first page */
  firstPage: () => void;
  /** Go to last page */
  lastPage: () => void;
  /** Reset to first page */
  reset: () => void;
  /** Whether there is a next page */
  hasNextPage: boolean;
  /** Whether there is a previous page */
  hasPrevPage: boolean;
}

export function usePagination({
  limit: limitOption = 20,
  total,
  initialPage = 0,
}: UsePaginationOptions): UsePaginationReturn {
  const [page, setPageRaw] = useState(initialPage);
  const limit = limitOption;

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / limit)), [total, limit]);

  // Ensure page stays within bounds when total changes
  const boundedPage = useMemo(() => Math.min(page, Math.max(0, totalPages - 1)), [page, totalPages]);

  // Update page if it became out of bounds
  if (boundedPage !== page && totalPages > 0) {
    setPageRaw(boundedPage);
  }

  const setPage = useCallback(
    (newPage: number) => {
      const bounded = Math.max(0, Math.min(newPage, totalPages - 1));
      setPageRaw(bounded);
    },
    [totalPages]
  );

  const offset = boundedPage * limit;

  const queryParams = useMemo(() => ({ limit, offset }), [limit, offset]);

  const nextPage = useCallback(() => {
    if (boundedPage < totalPages - 1) {
      setPageRaw(boundedPage + 1);
    }
  }, [boundedPage, totalPages]);

  const prevPage = useCallback(() => {
    if (boundedPage > 0) {
      setPageRaw(boundedPage - 1);
    }
  }, [boundedPage]);

  const firstPage = useCallback(() => {
    setPageRaw(0);
  }, []);

  const lastPage = useCallback(() => {
    setPageRaw(Math.max(0, totalPages - 1));
  }, [totalPages]);

  const reset = useCallback(() => {
    setPageRaw(initialPage);
  }, [initialPage]);

  return {
    page: boundedPage,
    setPage,
    limit,
    offset,
    totalPages,
    queryParams,
    nextPage,
    prevPage,
    firstPage,
    lastPage,
    reset,
    hasNextPage: boundedPage < totalPages - 1,
    hasPrevPage: boundedPage > 0,
  };
}

export default usePagination;
