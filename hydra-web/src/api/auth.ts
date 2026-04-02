import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import { useAuthStore } from '@/stores/auth-store';
import type {
  LoginRequest,
  RegisterRequest,
  RegisterResponse,
  MeResponse,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  ChangePasswordRequest,
  ApprovalsResponse,
  ApproveRequest,
  CreateRegistrationTokenRequest,
  RegistrationToken,
  CreateApiKeyRequest,
  ApiKey,
  ApiKeyListResponse,
  SessionLoginResponse,
  SessionRefreshResponse,
} from '@/types/auth';

export function useLogin() {
  const login = useAuthStore((state) => state.login);

  return useMutation({
    mutationFn: async (data: LoginRequest) => {
      const response = await apiClient.post<SessionLoginResponse>('/auth/session/login', data);
      return response.data;
    },
    onSuccess: (data) => {
      login(data.user);
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (data: RegisterRequest) => {
      const response = await apiClient.post<RegisterResponse>('/auth/register', data);
      return response.data;
    },
  });
}

export function useLogout() {
  const logout = useAuthStore((state) => state.logout);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      return Promise.resolve();
    },
    onSuccess: () => {
      logout();
      queryClient.clear();
    },
  });
}

export function useMe() {
  const setUser = useAuthStore((state) => state.setUser);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const setLoading = useAuthStore((state) => state.setLoading);

  const query = useQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: async () => {
      const response = await apiClient.get<MeResponse>('/auth/me');
      return response.data;
    },
    retry: false,
    staleTime: 1000 * 60 * 5,
  });

  useEffect(() => {
    if (query.data?.type === 'user') {
      setUser({
        userId: query.data.userId!,
        username: query.data.username!,
        email: query.data.email!,
        role: query.data.role!,
        permissions: query.data.permissions,
        temporaryRoles: [],
      });
      setLoading(false);
      return;
    }

    if (query.data?.type === 'agent') {
      clearAuth();
      return;
    }

    if (query.isError) {
      clearAuth();
    }
  }, [clearAuth, query.data, query.isError, setLoading, setUser]);

  useEffect(() => {
    if (query.isFetched) {
      setLoading(false);
    }
  }, [query.isFetched, setLoading]);

  return query;
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: async (data: ForgotPasswordRequest) => {
      const response = await apiClient.post('/auth/password/forgot', data);
      return response.data;
    },
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: async (data: ResetPasswordRequest) => {
      const response = await apiClient.post('/auth/password/reset', data);
      return response.data;
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (data: ChangePasswordRequest) => {
      const response = await apiClient.post('/auth/password/change', data);
      return response.data;
    },
  });
}

export function useRefreshToken() {
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post<SessionRefreshResponse>('/auth/session/refresh');
      return response.data;
    },
  });
}

export function useApprovals(params?: { role?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: queryKeys.auth.approvals(params),
    queryFn: async () => {
      const response = await apiClient.get<ApprovalsResponse>('/auth/approvals', { params });
      return response.data;
    },
  });
}

export function useApproveUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ApproveRequest) => {
      const response = await apiClient.post('/auth/approvals', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.approvals() });
    },
  });
}

export function useRejectUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId: string) => {
      const response = await apiClient.delete(`/auth/approvals/${userId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.approvals() });
    },
  });
}

export function useCreateRegistrationToken() {
  return useMutation({
    mutationFn: async (data: CreateRegistrationTokenRequest) => {
      const response = await apiClient.post<RegistrationToken>('/auth/tokens', data);
      return response.data;
    },
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateApiKeyRequest) => {
      const response = await apiClient.post<ApiKey>('/auth/apikeys', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.apiKeys() });
    },
  });
}

export function useApiKeys() {
  return useQuery({
    queryKey: queryKeys.auth.apiKeys(),
    queryFn: async () => {
      const response = await apiClient.get<ApiKeyListResponse>('/auth/apikeys');
      return response.data.apiKeys;
    },
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (keyId: string) => {
      const response = await apiClient.delete(`/auth/apikeys/${keyId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.apiKeys() });
    },
  });
}

export { useCreateRegistrationToken as useCreateToken };
export { useForgotPassword as useRequestPasswordReset };
export { useRegister as useRegisterWithToken };
