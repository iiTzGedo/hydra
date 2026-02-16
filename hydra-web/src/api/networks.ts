import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import {
  createListHook,
  createDetailHook,
  createCreateMutation,
  createUpdateMutation,
} from '@/api/create-entity-hooks';
import type { ApiResponse } from '@/types/api';
import type {
  Network,
  NetworkSummary,
  NetworkListParams,
  CreateNetworkRequest,
  UpdateNetworkRequest,
  NetworkNodeInfo,
} from '@/types/network';

export const useNetworks = createListHook<NetworkSummary, NetworkListParams>({
  endpoint: '/networks',
  idField: 'networkId',
  queryKey: queryKeys.networks.list,
});

export const useNetwork = createDetailHook<Network>({
  endpoint: '/networks',
  idField: 'networkId',
  queryKey: queryKeys.networks.detail,
});

export function useNetworkNodes(networkId: string) {
  return useQuery({
    queryKey: queryKeys.networks.nodes(networkId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<NetworkNodeInfo[]>>(
        `/networks/${networkId}/nodes`
      );
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
      };
    },
    enabled: !!networkId,
  });
}

export const useCreateNetwork = createCreateMutation<CreateNetworkRequest, Network>({
  endpoint: '/networks',
  listQueryKey: queryKeys.networks.list,
});

export const useUpdateNetwork = createUpdateMutation<UpdateNetworkRequest, Network>({
  endpoint: '/networks',
  method: 'patch',
  listQueryKey: queryKeys.networks.list,
  detailQueryKey: queryKeys.networks.detail,
});

// Custom delete — supports `force` parameter
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
