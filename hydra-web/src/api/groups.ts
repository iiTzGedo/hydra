import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  Group,
  GroupSummary,
  GroupListParams,
  GroupMember,
  GroupMembersResponse,
  CreateGroupRequest,
  UpdateGroupRequest,
} from '@/types/group';

// Extended Group summary with id alias for component convenience
type GroupWithId = GroupSummary & { id: string };

// List groups
export function useGroups(params?: GroupListParams) {
  return useQuery({
    queryKey: queryKeys.groups.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<GroupSummary[]>>('/groups', {
        params: {
          types: params?.types,
          parentGroupId: params?.parentGroupId,
          tags: params?.tags,
          search: params?.search,
          limit: params?.limit ?? 20,
          offset: params?.offset ?? 0,
          sortBy: params?.sortBy,
          sortOrder: params?.sortOrder,
        },
      });
      // Transform to PaginatedResponse with id alias
      const items: GroupWithId[] = response.data.data.map(group => ({
        ...group,
        id: group.groupId,
      }));
      const result: PaginatedResponse<GroupWithId> = {
        items,
        total: response.data.meta?.total ?? items.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 20,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
      return result;
    },
  });
}

// Get single group
export function useGroup(groupId: string) {
  return useQuery({
    queryKey: queryKeys.groups.detail(groupId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Group>>(`/groups/${groupId}`);
      return response.data.data;
    },
    enabled: !!groupId,
  });
}

// Get group members
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

// Create group
export function useCreateGroup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateGroupRequest) => {
      const response = await apiClient.post<ApiResponse<Group>>('/groups', data);
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.groups.list() });
    },
  });
}

// Update group
export function useUpdateGroup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ groupId, data }: { groupId: string; data: UpdateGroupRequest }) => {
      const response = await apiClient.put<ApiResponse<Group>>(`/groups/${groupId}`, data);
      return response.data.data;
    },
    onSuccess: (_data, { groupId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.groups.detail(groupId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.groups.list() });
    },
  });
}

// Delete group
export function useDeleteGroup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (groupId: string) => {
      const response = await apiClient.delete(`/groups/${groupId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.groups.list() });
    },
  });
}

// Resolve group members
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

// Get groups that contain a specific node
// This queries all groups and checks membership via selectors
export function useNodeGroups(nodeId: string) {
  return useQuery({
    queryKey: [...queryKeys.groups.list(), 'node', nodeId],
    queryFn: async () => {
      // First, fetch all groups
      const groupsResponse = await apiClient.get<ApiResponse<GroupSummary[]>>('/groups', {
        params: { limit: 100 },
      });
      const allGroups = groupsResponse.data.data;

      // For each group that might contain nodes, check if this node is a member
      const groupsWithNode: GroupWithId[] = [];

      for (const group of allGroups) {
        // Only check groups that support node membership
        if (group.types?.includes('node') || !group.types || group.types.length === 0) {
          try {
            const membersResponse = await apiClient.get<ApiResponse<GroupMembersResponse>>(
              `/groups/${group.groupId}/members`,
              { params: { entityType: 'node', limit: 200 } }
            );
            const nodeIds = membersResponse.data.data.nodes.map(n => n.nodeId);
            if (nodeIds.includes(nodeId)) {
              groupsWithNode.push({
                ...group,
                id: group.groupId,
              });
            }
          } catch {
            // If we can't fetch members, skip this group
          }
        }
      }

      return {
        items: groupsWithNode,
        total: groupsWithNode.length,
      };
    },
    enabled: !!nodeId,
    staleTime: 60 * 1000, // Cache for 1 minute since this is expensive
  });
}
