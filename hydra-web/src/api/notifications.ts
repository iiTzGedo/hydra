import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import type {
  Notification,
  NotificationBulkActionRequest,
  NotificationBulkActionResponse,
  NotificationListParams,
  NotificationStats,
} from '@/types/notification';

// ---------------------------------------------------------------------------
// List
// ---------------------------------------------------------------------------

export function useNotifications(params?: NotificationListParams) {
  return useQuery({
    queryKey: queryKeys.notifications.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Notification[]>>(
        '/notifications',
        { params }
      );
      return response.data;
    },
    refetchInterval: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

export function useNotificationStats() {
  return useQuery({
    queryKey: queryKeys.notifications.stats(),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<NotificationStats>>(
        '/notifications/stats'
      );
      return response.data.data;
    },
    refetchInterval: 15_000,
  });
}

// ---------------------------------------------------------------------------
// Detail
// ---------------------------------------------------------------------------

export function useNotification(notificationId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.notifications.detail(notificationId ?? ''),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Notification>>(
        `/notifications/${notificationId}`
      );
      return response.data.data;
    },
    enabled: !!notificationId,
  });
}

// ---------------------------------------------------------------------------
// Mark Read
// ---------------------------------------------------------------------------

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (notificationId: string) => {
      const response = await apiClient.patch<ApiResponse<{ notificationId: string; read: boolean }>>(
        `/notifications/${notificationId}/read`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    },
  });
}

// ---------------------------------------------------------------------------
// Mark All Read
// ---------------------------------------------------------------------------

export function useMarkAllRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body?: NotificationBulkActionRequest) => {
      const response = await apiClient.post<ApiResponse<NotificationBulkActionResponse>>(
        '/notifications/read-all',
        body ?? {}
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    },
  });
}

// ---------------------------------------------------------------------------
// Acknowledge
// ---------------------------------------------------------------------------

export function useAcknowledgeNotification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (notificationId: string) => {
      const response = await apiClient.patch<ApiResponse<Notification>>(
        `/notifications/${notificationId}/acknowledge`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    },
  });
}

// ---------------------------------------------------------------------------
// Acknowledge All
// ---------------------------------------------------------------------------

export function useAcknowledgeAllNotifications() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body?: NotificationBulkActionRequest) => {
      const response = await apiClient.post<ApiResponse<NotificationBulkActionResponse>>(
        '/notifications/acknowledge-all',
        body ?? {}
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    },
  });
}

// ---------------------------------------------------------------------------
// Resolve
// ---------------------------------------------------------------------------

export function useResolveNotification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (notificationId: string) => {
      const response = await apiClient.patch<ApiResponse<Notification>>(
        `/notifications/${notificationId}/resolve`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    },
  });
}

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------

export function useDeleteNotification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (notificationId: string) => {
      const response = await apiClient.delete<ApiResponse<{ notificationId: string; deleted: boolean }>>(
        `/notifications/${notificationId}`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    },
  });
}
