import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import type {
  Topology,
  TopologySummary,
  TopologyListParams,
  TopologyMode,
  TopologyDiffResponse,
  GenerateTopologyRequest,
} from '@/types/topology';

export function useTopologies(params?: TopologyListParams) {
  return useQuery({
    queryKey: queryKeys.topologies.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<TopologySummary[]>>('/topologies', {
        params: {
          mode: params?.mode,
          since: params?.since,
          until: params?.until,
          limit: params?.limit,
          offset: params?.offset,
        },
      });
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 20,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
  });
}

export function useLatestTopology(mode: TopologyMode = 'infrastructure', includeGraph = true) {
  return useQuery({
    queryKey: queryKeys.topologies.latest(mode),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Topology>>('/topologies/latest', {
        params: { mode, includeGraph },
      });
      return response.data.data;
    },
  });
}

export function useTopology(topologyId: string, includeGraph = true) {
  return useQuery({
    queryKey: queryKeys.topologies.detail(topologyId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Topology>>(
        `/topologies/${topologyId}`,
        {
          params: { includeGraph },
        }
      );
      return response.data.data;
    },
    enabled: !!topologyId,
  });
}

export function useGenerateTopology() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: GenerateTopologyRequest) => {
      const response = await apiClient.post<ApiResponse<Topology>>(
        '/topologies/generate',
        data
      );
      return response.data.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.topologies.list() });
      queryClient.invalidateQueries({ queryKey: queryKeys.topologies.latest(data.mode) });
    },
  });
}

export function useTopologyDiff(fromId?: string, toId?: string, mode?: TopologyMode) {
  return useQuery({
    queryKey: queryKeys.topologies.diff(fromId, toId, mode),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<TopologyDiffResponse>>('/topologies/diff', {
        params: { fromId, toId, mode },
      });
      return response.data.data;
    },
    enabled: !!(fromId || toId || mode),
  });
}
