import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  useGenerateTopology,
  useLatestTopology,
  usePrefetchTopologyModes,
  useTopologies,
  useTopology,
  useTopologyDiff,
  useTopologySubgraph,
} from '@/api/topologies';
import { queryKeys } from '@/lib/query-client';
import { createTestQueryClient, renderWithQuery } from '../msw/test-utils';

describe('Topologies API Hooks', () => {
  it('fetches topology summaries as a paginated response', async () => {
    const { result } = renderWithQuery(() =>
      useTopologies({ mode: 'infrastructure', limit: 1, offset: 0 })
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].topologyId).toBe('topology-infra-001');
    expect(result.current.data?.total).toBe(2);
  });

  it('fetches the latest topology for a mode', async () => {
    const { result } = renderWithQuery(() => useLatestTopology('network'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.topologyId).toBe('topology-network-001');
    expect(result.current.data?.graph?.nodes).toHaveLength(3);
  });

  it('disables topology detail when topologyId is empty', () => {
    const { result } = renderWithQuery(() => useTopology(''));

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('fetches topology diff and subgraph data', async () => {
    const diff = renderWithQuery(() =>
      useTopologyDiff('topology-infra-001', 'topology-infra-002', 'infrastructure')
    ).result;
    const subgraph = renderWithQuery(() => useTopologySubgraph('proxmox-01', 1)).result;

    await waitFor(() => {
      expect(diff.current.data?.summary.nodesAdded).toBe(1);
    }, { timeout: 3000 });
    await waitFor(() => {
      expect(subgraph.current.data?.centerNodeId).toBe('proxmox-01');
    }, { timeout: 3000 });

    expect(diff.current.data?.summary.nodesAdded).toBe(1);
    expect(subgraph.current.data?.centerNodeId).toBe('proxmox-01');
  });

  it('invalidates list and latest queries when a topology is generated', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderWithQuery(() => useGenerateTopology(), { queryClient });

    result.current.mutate({ mode: 'infrastructure' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.mode).toBe('infrastructure');
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.topologies.list() });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.topologies.latest('infrastructure'),
    });
  });

  it('prefetches the other topology modes into the query cache', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 60_000,
          staleTime: 0,
        },
        mutations: {
          retry: false,
        },
      },
    });
    const { result } = renderWithQuery(() => usePrefetchTopologyModes(), { queryClient });

    result.current.prefetch('infrastructure');

    await waitFor(() => {
      expect(queryClient.getQueryData(queryKeys.topologies.latest('network'))).toBeDefined();
      expect(queryClient.getQueryData(queryKeys.topologies.latest('service'))).toBeDefined();
    });
  });
});
