import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  Network,
  NetworkSummary,
  NetworkListParams,
  CreateNetworkRequest,
  UpdateNetworkRequest,
} from '@/types/network';
import type { NodeSummary } from '@/types/node';

// Extended NetworkSummary with id alias for component convenience
type NetworkSummaryWithId = NetworkSummary & { id: string };

// List networks
export function useNetworks(params?: NetworkListParams) {
  return useQuery({
    queryKey: queryKeys.networks.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<NetworkSummary[]>>('/networks', {
        params: {
          type: params?.type,
          parentNetworkId: params?.parentNetworkId,
          routerNodeId: params?.routerNodeId,
          cidr: params?.cidr,
          tags: params?.tags,
          search: params?.search,
          limit: params?.limit ?? 20,
          offset: params?.offset ?? 0,
          sortBy: params?.sortBy,
          sortOrder: params?.sortOrder,
        },
      });
      // Transform to PaginatedResponse with id alias
      const items: NetworkSummaryWithId[] = response.data.data.map(network => ({
        ...network,
        id: network.networkId,
      }));
      const result: PaginatedResponse<NetworkSummaryWithId> = {
        items,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 20,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
      return result;
    },
  });
}

// Get single network
export function useNetwork(networkId: string) {
  return useQuery({
    queryKey: queryKeys.networks.detail(networkId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Network>>(`/networks/${networkId}`);
      return response.data.data;
    },
    enabled: !!networkId,
  });
}

// Get nodes in network
export function useNetworkNodes(networkId: string) {
  return useQuery({
    queryKey: queryKeys.networks.nodes(networkId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<NodeSummary[]>>(
        `/networks/${networkId}/nodes`
      );
      // Transform to expected paginated format
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
      };
    },
    enabled: !!networkId,
  });
}

// Create network
export function useCreateNetwork() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateNetworkRequest) => {
      const response = await apiClient.post<ApiResponse<Network>>('/networks', data);
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.networks.list() });
    },
  });
}

// Update network
export function useUpdateNetwork() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      networkId,
      data,
    }: {
      networkId: string;
      data: UpdateNetworkRequest;
    }) => {
      const response = await apiClient.put<ApiResponse<Network>>(
        `/networks/${networkId}`,
        data
      );
      return response.data.data;
    },
    onSuccess: (_data, { networkId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.networks.detail(networkId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.networks.list() });
    },
  });
}

// Delete network
export function useDeleteNetwork() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ networkId, force }: { networkId: string; force?: boolean }) => {
      const response = await apiClient.delete(`/networks/${networkId}`, {
        params: { force },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.networks.list() });
    },
  });
}
