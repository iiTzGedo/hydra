import { useCallback, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { useWebSocket } from '@/hooks/use-websocket';
import { useNotificationStore } from '@/stores/notification-store';
import { useAuthStore } from '@/stores/auth-store';
import { queryKeys } from '@/lib/query-client';
import type { Notification } from '@/types/notification';

export function useNotificationsSocket() {
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuthStore();
  const addNotification = useNotificationStore((state) => state.addNotification);

  const handleMessage = useCallback((data: Record<string, unknown>) => {
    if (data.type === 'notification') {
      const payload = data.data as Partial<Notification> | undefined;
      if (payload?.notificationId) {
        addNotification(payload as Notification);
        queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
        queryClient.invalidateQueries({ queryKey: queryKeys.notifications.stats() });
      }
    }
  }, [addNotification, queryClient]);

  const { isConnected, connect, disconnect } = useWebSocket({
    path: '/notifications/ws',
    pingType: 'ping',
    onMessage: handleMessage,
  });

  useEffect(() => {
    if (isAuthenticated) {
      connect();
      return () => disconnect();
    }
    disconnect();
    return undefined;
  }, [isAuthenticated, connect, disconnect]);

  return { isConnected };
}
