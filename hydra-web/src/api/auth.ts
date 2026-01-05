import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import { useAuthStore } from '@/stores/auth-store';
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  MeResponse,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  ChangePasswordRequest,
  RefreshRequest,
  RefreshResponse,
  ApprovalsResponse,
  ApproveRequest,
  CreateRegistrationTokenRequest,
  RegistrationToken,
  CreateApiKeyRequest,
  ApiKey,
} from '@/types/auth';
import type { ApiResponse } from '@/types/api';

// Login mutation
export function useLogin() {
  const login = useAuthStore((state) => state.login);

  return useMutation({
    mutationFn: async (data: LoginRequest) => {
      const response = await apiClient.post<LoginResponse>('/auth/login', data);
      return response.data;
    },
    onSuccess: (data) => {
      login(data.user, data.accessToken, data.refreshToken);
    },
  });
}

// Register mutation
export function useRegister() {
  return useMutation({
    mutationFn: async (data: RegisterRequest) => {
      const response = await apiClient.post<RegisterResponse>('/auth/register', data);
      return response.data;
    },
  });
}

// Logout mutation
export function useLogout() {
  const logout = useAuthStore((state) => state.logout);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      // No API call needed, just clear local state
      return Promise.resolve();
    },
    onSuccess: () => {
      logout();
      queryClient.clear();
    },
  });
}

// Get current user
export function useMe() {
  const setUser = useAuthStore((state) => state.setUser);
  const setLoading = useAuthStore((state) => state.setLoading);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: async () => {
      const response = await apiClient.get<MeResponse>('/auth/me');
      return response.data;
    },
    enabled: isAuthenticated,
    retry: false,
    staleTime: 1000 * 60 * 5, // 5 minutes
    onSuccess: (data: MeResponse) => {
      if (data.type === 'user') {
        setUser({
          userId: data.userId!,
          username: data.username!,
          email: data.email!,
          role: data.role,
          permissions: data.permissions,
          createdAt: '',
        });
      }
    },
    onSettled: () => {
      setLoading(false);
    },
  });
}

// Forgot password
export function useForgotPassword() {
  return useMutation({
    mutationFn: async (data: ForgotPasswordRequest) => {
      const response = await apiClient.post('/auth/password/forgot', data);
      return response.data;
    },
  });
}

// Reset password
export function useResetPassword() {
  return useMutation({
    mutationFn: async (data: ResetPasswordRequest) => {
      const response = await apiClient.post('/auth/password/reset', data);
      return response.data;
    },
  });
}

// Change password
export function useChangePassword() {
  return useMutation({
    mutationFn: async (data: ChangePasswordRequest) => {
      const response = await apiClient.post('/auth/password/change', data);
      return response.data;
    },
  });
}

// Refresh token
export function useRefreshToken() {
  const setTokens = useAuthStore((state) => state.setTokens);

  return useMutation({
    mutationFn: async (data: RefreshRequest) => {
      const response = await apiClient.post<RefreshResponse>('/auth/refresh', data);
      return response.data;
    },
    onSuccess: (data) => {
      const refreshToken = useAuthStore.getState().refreshToken;
      if (refreshToken) {
        setTokens(data.accessToken, refreshToken);
      }
    },
  });
}

// Get pending approvals
export function useApprovals(params?: { role?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: queryKeys.auth.approvals(params),
    queryFn: async () => {
      const response = await apiClient.get<ApprovalsResponse>('/auth/approvals', { params });
      return response.data;
    },
  });
}

// Approve user
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

// Reject user
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

// Create registration token
export function useCreateRegistrationToken() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateRegistrationTokenRequest) => {
      const response = await apiClient.post<RegistrationToken>('/auth/tokens', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.tokens() });
    },
  });
}

// Get registration tokens
export function useRegistrationTokens() {
  return useQuery({
    queryKey: queryKeys.auth.tokens(),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<RegistrationToken[]>>('/auth/tokens');
      return response.data.data; // Return the array directly
    },
  });
}

// Create API key
export function useCreateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateApiKeyRequest) => {
      const response = await apiClient.post<ApiKey>('/auth/apikeys', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.apikeys() });
    },
  });
}

// Get API keys
export function useApiKeys() {
  return useQuery({
    queryKey: queryKeys.auth.apikeys(),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ApiKey[]>>('/auth/apikeys');
      return response.data.data; // Return the array directly
    },
  });
}

// Revoke API key
export function useRevokeApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (keyId: string) => {
      const response = await apiClient.delete(`/auth/apikeys/${keyId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.apikeys() });
    },
  });
}

// Revoke registration token
export function useRevokeToken() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (tokenId: string) => {
      const response = await apiClient.delete(`/auth/tokens/${tokenId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.tokens() });
    },
  });
}

// Aliases for convenience
export { useRegistrationTokens as useTokens };
export { useCreateRegistrationToken as useCreateToken };
export { useForgotPassword as useRequestPasswordReset };
export { useRegister as useRegisterWithToken };
