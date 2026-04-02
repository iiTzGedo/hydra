import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '@/stores/auth-store';
import type { Role, User } from '@/types/auth';

const mockUser: User = {
  userId: 'user-123',
  username: 'testuser',
  email: 'test@example.com',
  role: 'admin' as Role,
  permissions: ['nodes:read', 'users:*', '*:delete'],
  temporaryRoles: [],
  createdAt: '2024-01-01T00:00:00Z',
};

describe('auth-store', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: true,
    });
    document.cookie = 'hydra_csrf=test-csrf; path=/';
    fetchMock.mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = 'hydra_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
  });

  it('starts unauthenticated', () => {
    const state = useAuthStore.getState();

    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(true);
  });

  it('marks the user authenticated on login', () => {
    useAuthStore.getState().login(mockUser);

    const state = useAuthStore.getState();
    expect(state.user).toEqual(mockUser);
    expect(state.isAuthenticated).toBe(true);
    expect(state.isLoading).toBe(false);
  });

  it('clears auth state without making a network call', () => {
    useAuthStore.getState().login(mockUser);

    useAuthStore.getState().clearAuth();

    const state = useAuthStore.getState();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
  });

  it('logs out through the session endpoint and clears local auth state', () => {
    useAuthStore.getState().login(mockUser);

    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/auth/session/logout'),
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': 'test-csrf' },
      })
    );
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
  });

  it('supports wildcard permission checks', () => {
    useAuthStore.getState().setUser(mockUser);

    const state = useAuthStore.getState();
    expect(state.hasPermission('nodes:read')).toBe(true);
    expect(state.hasPermission('users:read')).toBe(true);
    expect(state.hasPermission('services:delete')).toBe(true);
    expect(state.hasPermission('services:write')).toBe(false);
  });

  it('checks direct and grouped roles', () => {
    useAuthStore.getState().setUser({ ...mockUser, role: 'operator' });

    const state = useAuthStore.getState();
    expect(state.hasRole('operator')).toBe(true);
    expect(state.hasRole('admin')).toBe(false);
    expect(state.hasAnyRole(['viewer', 'operator'])).toBe(true);
    expect(state.hasAnyRole(['viewer', 'family'])).toBe(false);
  });
});
