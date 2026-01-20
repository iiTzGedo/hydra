import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type {
  UserListResponse,
  UserListParams,
  ElevateRoleRequest,
  GrantTemporaryRoleRequest,
} from '@/types/user';
import type { Role } from '@/types/auth';

export function useUsers(params?: UserListParams) {
  return useQuery({
    queryKey: queryKeys.users.list(params),
    queryFn: async () => {
      const response = await apiClient.get<UserListResponse>('/users', {
        params: {
          role: params?.role,
          status: params?.status,
          search: params?.search,
          limit: params?.limit,
          offset: params?.offset,
          sortBy: params?.sortBy,
          sortOrder: params?.sortOrder,
        },
      });
      const items = response.data.users.map((user) => ({
        ...user,
        lastLoginAt: user.lastLogin,
      }));
      return {
        items,
        total: response.data.total ?? items.length,
        limit: response.data.limit ?? params?.limit ?? 20,
        offset: response.data.offset ?? params?.offset ?? 0,
      };
    },
  });
}

export function useArchiveUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId: string) => {
      const response = await apiClient.delete(`/users/${userId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.list() });
    },
  });
}

export function useElevateRole() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, data }: { userId: string; data: ElevateRoleRequest }) => {
      const response = await apiClient.post(`/users/${userId}/roles/elevate`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.list() });
    },
  });
}

export function useGrantTemporaryRole() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      userId,
      data,
    }: {
      userId: string;
      data: GrantTemporaryRoleRequest;
    }) => {
      const response = await apiClient.post(`/users/${userId}/roles/grant-temporary`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.list() });
    },
  });
}

export function useRevokeTemporaryRole() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: Role }) => {
      const response = await apiClient.delete(`/users/${userId}/roles/temporary/${role}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.list() });
    },
  });
}
