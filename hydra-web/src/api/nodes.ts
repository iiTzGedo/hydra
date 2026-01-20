import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  Node,
  NodeSummary,
  NodeListParams,
  UpdateNodeRequest,
  NodeRegistrationRequest,
  NodeRegistrationResponse,
} from '@/types/node';

type NodeSummaryWithId = NodeSummary & { id: string };

export function useNodes(params?: NodeListParams) {
  return useQuery({
    queryKey: queryKeys.nodes.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<NodeSummary[]>>('/nodes', {
        params: {
          class: params?.class,
          type: params?.type,
          kind: params?.kind,
          status: params?.status,
          tags: params?.tags,
          parentNodeId: params?.parentNodeId,
          networkId: params?.networkId,
          search: params?.search,
          limit: params?.limit ?? 20,
          offset: params?.offset ?? 0,
          sortBy: params?.sortBy,
          sortOrder: params?.sortOrder,
        },
      });
      const items: NodeSummaryWithId[] = response.data.data.map(node => ({
        ...node,
        id: node.nodeId,
      }));
      const result: PaginatedResponse<NodeSummaryWithId> = {
        items,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 20,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
      return result;
    },
  });
}

export function useNode(nodeId: string) {
  return useQuery({
    queryKey: queryKeys.nodes.detail(nodeId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Node>>(`/nodes/${nodeId}`);
      const node = response.data.data;
      return { ...node, id: node.nodeId };
    },
    enabled: !!nodeId,
  });
}

export function useNodeChildren(nodeId: string) {
  return useQuery({
    queryKey: queryKeys.nodes.children(nodeId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<NodeSummary[]>>(
        `/nodes/${nodeId}/children`
      );
      return response.data.data;
    },
    enabled: !!nodeId,
  });
}

export function useUpdateNode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ nodeId, data }: { nodeId: string; data: UpdateNodeRequest }) => {
      const response = await apiClient.patch<ApiResponse<Node>>(`/nodes/${nodeId}`, data);
      return response.data.data;
    },
    onSuccess: (_data, { nodeId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.nodes.detail(nodeId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.nodes.list() });
    },
  });
}

export function useArchiveNode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (nodeId: string) => {
      const response = await apiClient.delete<ApiResponse<Node>>(`/nodes/${nodeId}`);
      return response.data.data;
    },
    onSuccess: (_data, nodeId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.nodes.detail(nodeId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.nodes.list() });
    },
  });
}

export function useRegisterNode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: NodeRegistrationRequest) => {
      const response = await apiClient.post<NodeRegistrationResponse>('/node/register', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.nodes.list() });
    },
  });
}
