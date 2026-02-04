/**
 * Tests for auth-store.ts
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAuthStore } from '@/stores/auth-store';
import { storage } from '@/lib/storage';
import type { User, Role } from '@/types/auth';

// Mock storage module
vi.mock('@/lib/storage', () => ({
  storage: {
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
  },
}));

describe('auth-store', () => {
  // Mock user data
  const mockUser: User = {
    userId: 'user-123',
    username: 'testuser',
    email: 'test@example.com',
    role: 'admin' as Role,
    permissions: ['nodes:read', 'nodes:write', 'users:*', '*:delete'],
    temporaryRoles: [],
    createdAt: '2024-01-01T00:00:00Z',
  };

  beforeEach(() => {
    // Reset store state
    useAuthStore.setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(true);
    });
  });

  describe('setUser', () => {
    it('should set user and isAuthenticated to true when user is provided', () => {
      const { setUser } = useAuthStore.getState();
      setUser(mockUser);

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });

    it('should set user to null and isAuthenticated to false when null is provided', () => {
      const { setUser } = useAuthStore.getState();
      setUser(mockUser);
      setUser(null);

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe('setTokens', () => {
    it('should call storage.setTokens and update state', () => {
      const { setTokens } = useAuthStore.getState();
      const accessToken = 'access-token-123';
      const refreshToken = 'refresh-token-456';

      setTokens(accessToken, refreshToken);

      expect(storage.setTokens).toHaveBeenCalledWith(accessToken, refreshToken);
      const state = useAuthStore.getState();
      expect(state.accessToken).toBe(accessToken);
      expect(state.refreshToken).toBe(refreshToken);
    });
  });

  describe('clearTokens', () => {
    it('should call storage.clearTokens and reset tokens in state', () => {
      const { setTokens, clearTokens } = useAuthStore.getState();
      setTokens('access-123', 'refresh-456');
      clearTokens();

      expect(storage.clearTokens).toHaveBeenCalled();
      const state = useAuthStore.getState();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
    });
  });

  describe('login', () => {
    it('should set user, tokens, isAuthenticated, and isLoading correctly', () => {
      const { login } = useAuthStore.getState();
      const accessToken = 'access-token-789';
      const refreshToken = 'refresh-token-012';

      login(mockUser, accessToken, refreshToken);

      expect(storage.setTokens).toHaveBeenCalledWith(accessToken, refreshToken);
      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.accessToken).toBe(accessToken);
      expect(state.refreshToken).toBe(refreshToken);
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
    });
  });

  describe('logout', () => {
    it('should clear all auth state and call storage.clearTokens', () => {
      const { login, logout } = useAuthStore.getState();
      login(mockUser, 'access-123', 'refresh-456');
      logout();

      expect(storage.clearTokens).toHaveBeenCalled();
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
    });
  });

  describe('setLoading', () => {
    it('should set isLoading to true', () => {
      const { setLoading } = useAuthStore.getState();
      setLoading(true);
      expect(useAuthStore.getState().isLoading).toBe(true);
    });

    it('should set isLoading to false', () => {
      const { setLoading } = useAuthStore.getState();
      setLoading(false);
      expect(useAuthStore.getState().isLoading).toBe(false);
    });
  });

  describe('hasPermission', () => {
    it('should return false when user is null', () => {
      const { hasPermission } = useAuthStore.getState();
      expect(hasPermission('nodes:read')).toBe(false);
    });

    it('should return true for wildcard *:* permission', () => {
      const { setUser, hasPermission } = useAuthStore.getState();
      setUser({ ...mockUser, permissions: ['*:*'] });
      expect(hasPermission('nodes:read')).toBe(true);
      expect(hasPermission('anything:delete')).toBe(true);
    });

    it('should return true for exact permission match', () => {
      const { setUser, hasPermission } = useAuthStore.getState();
      setUser({ ...mockUser, permissions: ['nodes:read', 'users:write'] });
      expect(hasPermission('nodes:read')).toBe(true);
      expect(hasPermission('users:write')).toBe(true);
    });

    it('should return true for resource wildcard permission', () => {
      const { setUser, hasPermission } = useAuthStore.getState();
      setUser({ ...mockUser, permissions: ['users:*'] });
      expect(hasPermission('users:read')).toBe(true);
      expect(hasPermission('users:write')).toBe(true);
      expect(hasPermission('users:delete')).toBe(true);
    });

    it('should return true for action wildcard permission', () => {
      const { setUser, hasPermission } = useAuthStore.getState();
      setUser({ ...mockUser, permissions: ['*:delete'] });
      expect(hasPermission('nodes:delete')).toBe(true);
      expect(hasPermission('users:delete')).toBe(true);
      expect(hasPermission('services:delete')).toBe(true);
    });

    it('should return false when permission does not match', () => {
      const { setUser, hasPermission } = useAuthStore.getState();
      setUser({ ...mockUser, permissions: ['nodes:read'] });
      expect(hasPermission('nodes:write')).toBe(false);
      expect(hasPermission('users:read')).toBe(false);
    });

    it('should handle missing permissions field gracefully', () => {
      const { setUser, hasPermission } = useAuthStore.getState();
      const userWithoutPermissions = { ...mockUser };
      delete (userWithoutPermissions as any).permissions;
      setUser(userWithoutPermissions);
      expect(hasPermission('nodes:read')).toBe(false);
    });
  });

  describe('hasRole', () => {
    it('should return false when user is null', () => {
      const { hasRole } = useAuthStore.getState();
      expect(hasRole('admin')).toBe(false);
    });

    it('should return true when user has the specified role', () => {
      const { setUser, hasRole } = useAuthStore.getState();
      setUser({ ...mockUser, role: 'admin' });
      expect(hasRole('admin')).toBe(true);
    });

    it('should return false when user does not have the specified role', () => {
      const { setUser, hasRole } = useAuthStore.getState();
      setUser({ ...mockUser, role: 'viewer' });
      expect(hasRole('admin')).toBe(false);
    });
  });

  describe('hasAnyRole', () => {
    it('should return false when user is null', () => {
      const { hasAnyRole } = useAuthStore.getState();
      expect(hasAnyRole(['admin', 'operator'])).toBe(false);
    });

    it('should return true when user has one of the specified roles', () => {
      const { setUser, hasAnyRole } = useAuthStore.getState();
      setUser({ ...mockUser, role: 'operator' });
      expect(hasAnyRole(['admin', 'operator', 'viewer'])).toBe(true);
    });

    it('should return false when user does not have any of the specified roles', () => {
      const { setUser, hasAnyRole } = useAuthStore.getState();
      setUser({ ...mockUser, role: 'viewer' });
      expect(hasAnyRole(['admin', 'operator'])).toBe(false);
    });
  });

  describe('Persistence', () => {
    it('should persist user, tokens, and isAuthenticated to localStorage', () => {
      const { login } = useAuthStore.getState();
      login(mockUser, 'access-token', 'refresh-token');

      // Verify localStorage contains persisted data
      const stored = localStorage.getItem('hydra-auth-storage');
      expect(stored).toBeTruthy();

      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.user).toEqual(mockUser);
        expect(parsed.state.accessToken).toBe('access-token');
        expect(parsed.state.refreshToken).toBe('refresh-token');
        expect(parsed.state.isAuthenticated).toBe(true);
      }
    });

    it('should not persist isLoading to localStorage', () => {
      const { setLoading } = useAuthStore.getState();
      setLoading(true);

      const stored = localStorage.getItem('hydra-auth-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.isLoading).toBeUndefined();
      }
    });
  });
});
