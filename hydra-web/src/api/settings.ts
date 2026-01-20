import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type {
  SystemSettingsResponse,
  SystemSettingsUpdate,
  UserSettingsResponse,
  UserSettingsUpdate,
} from '@/types/settings';

export function useUserSettings() {
  return useQuery({
    queryKey: queryKeys.settings.user(),
    queryFn: async () => {
      const response = await apiClient.get<UserSettingsResponse>('/settings');
      return response.data;
    },
  });
}

export function useUpdateUserSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UserSettingsUpdate) => {
      const response = await apiClient.put<UserSettingsResponse>('/settings', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.user() });
    },
  });
}

export function useSystemSettings() {
  return useQuery({
    queryKey: queryKeys.settings.system(),
    queryFn: async () => {
      const response = await apiClient.get<SystemSettingsResponse>('/settings/system');
      return response.data;
    },
  });
}

export function useUpdateSystemSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: SystemSettingsUpdate) => {
      const response = await apiClient.put<SystemSettingsResponse>('/settings/system', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.system() });
    },
  });
}
