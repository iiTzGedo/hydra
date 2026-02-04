/**
 * Tests for notification-store.ts
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useNotificationStore } from '@/stores/notification-store';
import type { Notification } from '@/types/notification';

describe('notification-store', () => {
  // Mock notification data
  const createMockNotification = (id: string, overrides?: Partial<Notification>): Notification => ({
    notificationId: id,
    type: 'system.update',
    tier: 2,
    tierLabel: 'low_system',
    source: {
      component: 'hydra-api',
      service: 'auth',
    },
    title: `Notification ${id}`,
    message: `This is notification ${id}`,
    targetRoles: ['admin'],
    groupKey: `group-${id}`,
    status: 'active',
    createdAt: new Date().toISOString(),
    ...overrides,
  });

  beforeEach(() => {
    // Reset store state
    useNotificationStore.setState({
      unreadCount: 0,
      recentNotifications: [],
      panelOpen: false,
    });
  });

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(0);
      expect(state.recentNotifications).toEqual([]);
      expect(state.panelOpen).toBe(false);
    });
  });

  describe('addNotification', () => {
    it('should prepend new notification to the list', () => {
      const { addNotification } = useNotificationStore.getState();
      const notification = createMockNotification('notif-1');

      addNotification(notification);

      const state = useNotificationStore.getState();
      expect(state.recentNotifications).toHaveLength(1);
      expect(state.recentNotifications[0]).toEqual(notification);
    });

    it('should increment unreadCount when adding unread notification', () => {
      const { addNotification } = useNotificationStore.getState();
      const notification = createMockNotification('notif-1');

      addNotification(notification);

      const state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(1);
    });

    it('should not increment unreadCount when adding read notification', () => {
      const { addNotification } = useNotificationStore.getState();
      const notification = createMockNotification('notif-1', {
        readAt: new Date().toISOString(),
      });

      addNotification(notification);

      const state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(0);
    });

    it('should cap notifications at MAX_RECENT (20)', () => {
      const { addNotification } = useNotificationStore.getState();

      // Add 25 notifications
      for (let i = 1; i <= 25; i++) {
        addNotification(createMockNotification(`notif-${i}`));
      }

      const state = useNotificationStore.getState();
      expect(state.recentNotifications).toHaveLength(20);
      expect(state.recentNotifications[0].notificationId).toBe('notif-25');
      expect(state.recentNotifications[19].notificationId).toBe('notif-6');
    });

    it('should update existing notification by notificationId', () => {
      const { addNotification } = useNotificationStore.getState();
      const original = createMockNotification('notif-1', { title: 'Original Title' });
      const updated = createMockNotification('notif-1', { title: 'Updated Title' });

      addNotification(original);
      addNotification(updated);

      const state = useNotificationStore.getState();
      expect(state.recentNotifications).toHaveLength(1);
      expect(state.recentNotifications[0].title).toBe('Updated Title');
    });

    it('should adjust unreadCount when updating from unread to read', () => {
      const { addNotification } = useNotificationStore.getState();
      const original = createMockNotification('notif-1');
      const updated = createMockNotification('notif-1', {
        readAt: new Date().toISOString(),
      });

      addNotification(original);
      expect(useNotificationStore.getState().unreadCount).toBe(1);

      addNotification(updated);
      expect(useNotificationStore.getState().unreadCount).toBe(0);
    });

    it('should adjust unreadCount when updating from read to unread', () => {
      const { addNotification } = useNotificationStore.getState();
      const original = createMockNotification('notif-1', {
        readAt: new Date().toISOString(),
      });
      const updated = createMockNotification('notif-1', { readAt: null });

      addNotification(original);
      expect(useNotificationStore.getState().unreadCount).toBe(0);

      addNotification(updated);
      expect(useNotificationStore.getState().unreadCount).toBe(1);
    });

    it('should not change unreadCount when both old and new are unread', () => {
      const { addNotification } = useNotificationStore.getState();
      const original = createMockNotification('notif-1');
      const updated = createMockNotification('notif-1', { title: 'Updated' });

      addNotification(original);
      expect(useNotificationStore.getState().unreadCount).toBe(1);

      addNotification(updated);
      expect(useNotificationStore.getState().unreadCount).toBe(1);
    });
  });

  describe('markRead', () => {
    it('should set readAt timestamp on the notification', () => {
      const { addNotification, markRead } = useNotificationStore.getState();
      const notification = createMockNotification('notif-1');

      addNotification(notification);
      markRead('notif-1');

      const state = useNotificationStore.getState();
      expect(state.recentNotifications[0].readAt).toBeTruthy();
      expect(typeof state.recentNotifications[0].readAt).toBe('string');
    });

    it('should decrement unreadCount when marking unread notification as read', () => {
      const { addNotification, markRead } = useNotificationStore.getState();
      const notification = createMockNotification('notif-1');

      addNotification(notification);
      expect(useNotificationStore.getState().unreadCount).toBe(1);

      markRead('notif-1');
      expect(useNotificationStore.getState().unreadCount).toBe(0);
    });

    it('should not decrement unreadCount when marking already read notification', () => {
      const { addNotification, markRead } = useNotificationStore.getState();
      const notification = createMockNotification('notif-1', {
        readAt: new Date().toISOString(),
      });

      addNotification(notification);
      expect(useNotificationStore.getState().unreadCount).toBe(0);

      markRead('notif-1');
      expect(useNotificationStore.getState().unreadCount).toBe(0);
    });

    it('should not go below 0 for unreadCount', () => {
      const { markRead } = useNotificationStore.getState();
      useNotificationStore.setState({ unreadCount: 0 });

      markRead('non-existent-id');
      expect(useNotificationStore.getState().unreadCount).toBe(0);
    });

    it('should handle marking non-existent notification gracefully', () => {
      const { markRead } = useNotificationStore.getState();
      markRead('non-existent-id');

      const state = useNotificationStore.getState();
      expect(state.recentNotifications).toHaveLength(0);
    });
  });

  describe('setUnreadCount', () => {
    it('should set unreadCount to specified value', () => {
      const { setUnreadCount } = useNotificationStore.getState();
      setUnreadCount(10);
      expect(useNotificationStore.getState().unreadCount).toBe(10);
    });

    it('should allow setting unreadCount to 0', () => {
      const { setUnreadCount } = useNotificationStore.getState();
      setUnreadCount(5);
      setUnreadCount(0);
      expect(useNotificationStore.getState().unreadCount).toBe(0);
    });
  });

  describe('setPanelOpen', () => {
    it('should set panelOpen to true', () => {
      const { setPanelOpen } = useNotificationStore.getState();
      setPanelOpen(true);
      expect(useNotificationStore.getState().panelOpen).toBe(true);
    });

    it('should set panelOpen to false', () => {
      const { setPanelOpen } = useNotificationStore.getState();
      setPanelOpen(true);
      setPanelOpen(false);
      expect(useNotificationStore.getState().panelOpen).toBe(false);
    });
  });

  describe('togglePanel', () => {
    it('should toggle panelOpen from false to true', () => {
      const { togglePanel } = useNotificationStore.getState();
      expect(useNotificationStore.getState().panelOpen).toBe(false);
      togglePanel();
      expect(useNotificationStore.getState().panelOpen).toBe(true);
    });

    it('should toggle panelOpen from true to false', () => {
      const { setPanelOpen, togglePanel } = useNotificationStore.getState();
      setPanelOpen(true);
      togglePanel();
      expect(useNotificationStore.getState().panelOpen).toBe(false);
    });
  });

  describe('clearRecent', () => {
    it('should clear all recent notifications and reset unreadCount', () => {
      const { addNotification, clearRecent } = useNotificationStore.getState();

      addNotification(createMockNotification('notif-1'));
      addNotification(createMockNotification('notif-2'));
      addNotification(createMockNotification('notif-3'));

      expect(useNotificationStore.getState().recentNotifications).toHaveLength(3);
      expect(useNotificationStore.getState().unreadCount).toBe(3);

      clearRecent();

      const state = useNotificationStore.getState();
      expect(state.recentNotifications).toEqual([]);
      expect(state.unreadCount).toBe(0);
    });
  });

  describe('Multiple notifications', () => {
    it('should maintain correct unreadCount with multiple notifications', () => {
      const { addNotification } = useNotificationStore.getState();

      addNotification(createMockNotification('notif-1'));
      addNotification(createMockNotification('notif-2'));
      addNotification(createMockNotification('notif-3', { readAt: new Date().toISOString() }));

      expect(useNotificationStore.getState().unreadCount).toBe(2);
    });

    it('should maintain correct order when prepending notifications', () => {
      const { addNotification } = useNotificationStore.getState();

      addNotification(createMockNotification('notif-1'));
      addNotification(createMockNotification('notif-2'));
      addNotification(createMockNotification('notif-3'));

      const state = useNotificationStore.getState();
      expect(state.recentNotifications[0].notificationId).toBe('notif-3');
      expect(state.recentNotifications[1].notificationId).toBe('notif-2');
      expect(state.recentNotifications[2].notificationId).toBe('notif-1');
    });
  });
});
