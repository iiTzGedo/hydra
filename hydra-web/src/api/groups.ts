import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  Group,
  GroupListParams,
  GroupMember,
  CreateGroupRequest,
  UpdateGroupRequest,
} from '@/types/group';

// Extended Group with id alias for component convenience
type GroupWithId = Group & { id: string };

// List groups
export function useGroups(params?: GroupListParams) {
  return useQuery({
    queryKey: queryKeys.groups.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Group[]>>('/groups', {
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
        total: response.data.meta?.total ?? response.data.data.length,
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
  params?: { limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: queryKeys.groups.members(groupId, params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<GroupMember[]>>(
        `/groups/${groupId}/members`,
        { params }
      );
      // Transform to expected paginated format
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
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
