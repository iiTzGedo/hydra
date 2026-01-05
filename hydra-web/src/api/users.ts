import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import type {
  UserSummary,
  UserListParams,
  ElevateRoleRequest,
  GrantTemporaryRoleRequest,
  AuditLogEntry,
  AuditLogParams,
} from '@/types/user';
import type { Role } from '@/types/auth';

// List users
export function useUsers(params?: UserListParams) {
  return useQuery({
    queryKey: queryKeys.users.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<UserSummary[]>>('/users', {
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
      // Transform to expected paginated format
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 20,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
  });
}

// Archive user
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

// Elevate user role
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

// Grant temporary role
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

// Revoke temporary role
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

// Get audit log
export function useAuditLog(params?: AuditLogParams) {
  return useQuery({
    queryKey: ['audit', 'log', params],
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<AuditLogEntry[]>>('/audit', {
        params: {
          action: params?.action,
          resource: params?.resource,
          actorId: params?.actorId,
          since: params?.since,
          until: params?.until,
          search: params?.search,
          limit: params?.limit,
          offset: params?.offset,
          sortBy: params?.sortBy,
          sortOrder: params?.sortOrder,
        },
      });
      // Transform to expected paginated format
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
  });
}

// Approval-related hooks are exported from auth.ts to avoid conflicts
// Import from '@/api/auth' if needed: useApprovals, useApproveUser, useRejectUser
