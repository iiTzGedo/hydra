import { create } from 'zustand';
import type { Notification } from '@/types/notification';

/** Maximum number of recent notifications held in-memory for the dropdown. */
const MAX_RECENT = 20;

interface NotificationState {
  /** Unread count sourced from real-time WebSocket pushes (optimistic). */
  unreadCount: number;
  /** Recent notifications received via WebSocket for the header dropdown. */
  recentNotifications: Notification[];
  /** Whether the notification panel dropdown is open. */
  panelOpen: boolean;

  // Actions
  addNotification: (notification: Notification) => void;
  markRead: (notificationId: string) => void;
  setUnreadCount: (count: number) => void;
  setPanelOpen: (open: boolean) => void;
  togglePanel: () => void;
  clearRecent: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  unreadCount: 0,
  recentNotifications: [],
  panelOpen: false,

  addNotification: (notification) =>
    set((state) => {
      const existingIndex = state.recentNotifications.findIndex(
        (n) => n.notificationId === notification.notificationId
      );

      if (existingIndex >= 0) {
        const updated = [...state.recentNotifications];
        const previous = updated[existingIndex];
        updated[existingIndex] = { ...previous, ...notification };

        const wasUnread = !previous.readAt;
        const isUnread = !notification.readAt;
        const unreadCount = state.unreadCount + (isUnread ? 1 : 0) - (wasUnread ? 1 : 0);

        return {
          recentNotifications: updated,
          unreadCount: Math.max(unreadCount, 0),
        };
      }

      // Prepend and cap at MAX_RECENT
      const updated = [notification, ...state.recentNotifications].slice(0, MAX_RECENT);
      const isUnread = !notification.readAt;
      return {
        recentNotifications: updated,
        unreadCount: state.unreadCount + (isUnread ? 1 : 0),
      };
    }),

  markRead: (notificationId) =>
    set((state) => {
      const updated = state.recentNotifications.map((n) =>
        n.notificationId === notificationId
          ? { ...n, readAt: new Date().toISOString() }
          : n
      );
      const wasUnread = state.recentNotifications.some(
        (n) => n.notificationId === notificationId && !n.readAt
      );
      return {
        recentNotifications: updated,
        unreadCount: wasUnread ? Math.max(state.unreadCount - 1, 0) : state.unreadCount,
      };
    }),

  setUnreadCount: (count) => set({ unreadCount: count }),

  setPanelOpen: (open) => set({ panelOpen: open }),

  togglePanel: () => set((state) => ({ panelOpen: !state.panelOpen })),

  clearRecent: () => set({ recentNotifications: [], unreadCount: 0 }),
}));
