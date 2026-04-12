/**
 * Data binding hooks for dashboard widgets.
 *
 * Per Dashboard Technical Specification §6 and §14, provides:
 * - {@link useWidgetData} — single-source data binding resolution
 * - {@link useMultiSourceWidgetData} — concurrent multi-source resolution
 *
 * Both hooks wrap {@link resolveDataBinding} with TanStack Query for
 * automatic caching, deduplication, refetch intervals, and stale detection.
 */

import { useQueries, useQuery, keepPreviousData } from '@tanstack/react-query';
import { resolveDataBinding, substituteParams } from '@/lib/resolve-data-binding';
import type {
  DashboardDataBinding,
  DashboardMultiSourceBinding,
} from '@/types/dashboard';

// ── Result shape ─────────────────────────────────────────────────────

export interface WidgetDataResult<T = unknown> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  isStale: boolean;
  isFetching: boolean;
}

// ── Default refresh interval (seconds) ──────────────────────────────

const DEFAULT_REFRESH_SECONDS = 30;

// ── Single-source hook (T016) ────────────────────────────────────────

/**
 * Resolve a single data binding via TanStack Query.
 *
 * The hook is disabled when `binding` is null/undefined (config-backed
 * widgets without data bindings), returning `data: null` without any
 * network requests.
 *
 * Query key structure: `['widget-data', source, query]` — TanStack
 * automatically deduplicates when two widget instances share the same
 * binding configuration.
 */
export function useWidgetData<T = unknown>(
  binding: DashboardDataBinding | null | undefined,
): WidgetDataResult<T> {
  const refreshSeconds = binding?.refreshInterval ?? DEFAULT_REFRESH_SECONDS;
  const refreshMs = refreshSeconds * 1000;

  const query = useQuery<unknown, Error>({
    queryKey: ['widget-data', binding?.source ?? null, binding?.query ?? null],
    queryFn: () => {
      if (!binding) throw new Error('No binding configured');
      return resolveDataBinding(binding);
    },
    enabled: !!binding?.source,
    refetchInterval: refreshMs,
    staleTime: Math.floor(refreshMs / 2),
    gcTime: refreshMs * 5,
    placeholderData: keepPreviousData,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });

  return {
    data: (query.data as T) ?? null,
    isLoading: query.isLoading,
    error: query.error,
    isStale: query.isStale,
    isFetching: query.isFetching,
  };
}

// ── Multi-source hook (T018) ─────────────────────────────────────────

/**
 * Resolve multiple data sources concurrently for composite widgets.
 *
 * Each key in `multiBinding.sources` produces an independent TanStack
 * Query. `{placeholder}` tokens in endpoint paths and query params are
 * substituted from `multiBinding.params` before resolution.
 *
 * Returns a `Record<string, WidgetDataResult>` keyed by the same keys
 * as `multiBinding.sources`.
 */
export function useMultiSourceWidgetData(
  multiBinding: DashboardMultiSourceBinding | null | undefined,
): Record<string, WidgetDataResult> {
  const entries = Object.entries(multiBinding?.sources ?? {});
  const globalParams = multiBinding?.params ?? {};
  const refreshSeconds = multiBinding?.refreshInterval ?? DEFAULT_REFRESH_SECONDS;
  const refreshMs = refreshSeconds * 1000;

  const queries = useQueries({
    queries: entries.map(([key, entry]) => {
      // Substitute {placeholder} values from global params
      const resolvedParams = substituteParams(
        entry.query.params as Record<string, unknown> | undefined,
        globalParams,
      );
      const resolvedEndpoint = entry.query.endpoint
        ? entry.query.endpoint.replace(/\{(\w+)\}/g, (_m: string, k: string) =>
            String(globalParams[k] ?? `{${k}}`),
          )
        : entry.query.endpoint;

      const binding: DashboardDataBinding = {
        source: entry.source,
        query: {
          ...entry.query,
          endpoint: resolvedEndpoint,
          params: resolvedParams,
        },
      };

      return {
        queryKey: ['widget-data', key, binding.source, binding.query],
        queryFn: () => resolveDataBinding(binding),
        refetchInterval: refreshMs,
        staleTime: Math.floor(refreshMs / 2),
        gcTime: refreshMs * 5,
        placeholderData: keepPreviousData,
        retry: 2,
        retryDelay: (attempt: number) => Math.min(1000 * 2 ** attempt, 30000),
        enabled: !!entry.source,
      };
    }),
  });

  const result: Record<string, WidgetDataResult> = {};
  entries.forEach(([key], index) => {
    const q = queries[index];
    result[key] = {
      data: q.data ?? null,
      isLoading: q.isLoading,
      error: (q.error as Error) ?? null,
      isStale: q.isStale,
      isFetching: q.isFetching,
    };
  });

  return result;
}
