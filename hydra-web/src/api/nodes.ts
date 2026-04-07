import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import {
  createListHook,
  createDetailHook,
  createUpdateMutation,
  createDeleteMutation,
} from '@/api/create-entity-hooks';
import type { ApiResponse } from '@/types/api';
import type {
  Node,
  NodeSummary,
  NodeListParams,
  UpdateNodeRequest,
  NodeRegistrationRequest,
  NodeRegistrationResponse,
} from '@/types/node';

export const useNodes = createListHook<NodeSummary, NodeListParams>({
  endpoint: '/nodes',
  idField: 'nodeId',
  queryKey: queryKeys.nodes.list,
});

export const useNode = createDetailHook<Node>({
  endpoint: '/nodes',
  idField: 'nodeId',
  queryKey: queryKeys.nodes.detail,
});

export function useNodeChildren(nodeId: string) {
  return useQuery({
    queryKey: queryKeys.nodes.children(nodeId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<NodeSummary[]>>(
        `/nodes/${nodeId}/children`
      );
      return response.data.data.map(item => ({ ...item, id: item.nodeId }));
    },
    enabled: !!nodeId,
  });
}

export const useUpdateNode = createUpdateMutation<UpdateNodeRequest, Node>({
  endpoint: '/nodes',
  method: 'patch',
  listQueryKey: queryKeys.nodes.list,
  detailQueryKey: queryKeys.nodes.detail,
});

export const useArchiveNode = createDeleteMutation({
  endpoint: '/nodes',
  listQueryKey: queryKeys.nodes.list,
});

export function useRegisterNode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: NodeRegistrationRequest) => {
      const response = await apiClient.post<NodeRegistrationResponse>('/nodes/register', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.nodes.list() });
    },
  });
}
