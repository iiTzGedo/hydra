import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import {
  createListHook,
  createDetailHook,
  createCreateMutation,
  createUpdateMutation,
  createDeleteMutation,
} from '@/api/create-entity-hooks';
import type { ApiResponse } from '@/types/api';
import type {
  Group,
  GroupSummary,
  GroupListParams,
  GroupMember,
  GroupMembersResponse,
  CreateGroupRequest,
  UpdateGroupRequest,
} from '@/types/group';

type GroupWithId = GroupSummary & { id: string };

export const useGroups = createListHook<GroupSummary, GroupListParams>({
  endpoint: '/groups',
  idField: 'groupId',
  queryKey: queryKeys.groups.list,
});

export const useGroup = createDetailHook<Group>({
  endpoint: '/groups',
  idField: 'groupId',
  queryKey: queryKeys.groups.detail,
});

export function useGroupMembers(
  groupId: string,
  params?: { limit?: number; offset?: number; entityType?: 'node' | 'service' }
) {
  return useQuery({
    queryKey: queryKeys.groups.members(groupId, params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<GroupMembersResponse>>(
        `/groups/${groupId}/members`,
        { params }
      );
      const nodes = response.data.data.nodes.map((node) => ({
        id: node.nodeId,
        type: 'node' as const,
        displayName: node.displayName,
        matchedBy: node.matchedSelectors,
      }));
      const services = response.data.data.services.map((service) => ({
        id: service.serviceId,
        type: 'service' as const,
        displayName: service.name,
        matchedBy: service.matchedSelectors,
        nodeId: service.nodeId,
      }));
      const items: GroupMember[] = [...nodes, ...services];
      return {
        items,
        total: response.data.meta?.total ?? items.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
    enabled: !!groupId,
  });
}

export const useCreateGroup = createCreateMutation<CreateGroupRequest, Group>({
  endpoint: '/groups',
  listQueryKey: queryKeys.groups.list,
});

export const useUpdateGroup = createUpdateMutation<UpdateGroupRequest, Group>({
  endpoint: '/groups',
  method: 'patch',
  listQueryKey: queryKeys.groups.list,
  detailQueryKey: queryKeys.groups.detail,
});

export const useDeleteGroup = createDeleteMutation({
  endpoint: '/groups',
  listQueryKey: queryKeys.groups.list,
});

export function useResolveGroup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (groupId: string) => {
      const response = await apiClient.post(`/groups/${groupId}/resolve`);
      return response.data;
    },
    onSuccess: (_data, groupId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.groups.detail(groupId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.groups.members(groupId) });
    },
  });
}

// Queries groups for a specific node via server-side selector evaluation
export function useNodeGroups(nodeId: string) {
  return useQuery({
    queryKey: [...queryKeys.groups.list(), 'node', nodeId],
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<GroupSummary[]>>(
        `/nodes/${nodeId}/groups`
      );
      const groups = response.data.data;
      const groupsWithId: GroupWithId[] = groups.map((g) => ({
        ...g,
        id: g.groupId,
      }));
      return {
        items: groupsWithId,
        total: groupsWithId.length,
      };
    },
    enabled: !!nodeId,
    staleTime: 60 * 1000,
  });
}
