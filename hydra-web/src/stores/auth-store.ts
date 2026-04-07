import { create } from 'zustand';

import { CSRF_HEADER_NAME, getApiBaseUrl, getCsrfToken } from '@/lib/auth-session';
import { queryClient } from '@/lib/query-client';
import { useChatCacheStore } from '@/stores/chat-cache-store';
import { useDashboardStore } from '@/stores/dashboard-store';
import type { User, Role } from '@/types/auth';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setUser: (user: User | null) => void;
  clearAuth: () => void;
  login: (user: User) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;

  hasPermission: (permission: string) => boolean;
  hasRole: (role: Role) => boolean;
  hasAnyRole: (roles: Role[]) => boolean;
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  setUser: (user) => set({ user, isAuthenticated: !!user }),

  clearAuth: () =>
    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    }),

  login: (user) =>
    set({
      user,
      isAuthenticated: true,
      isLoading: false,
    }),

  logout: () => {
    const csrfToken = getCsrfToken();
    fetch(`${getApiBaseUrl()}/auth/session/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : undefined,
    }).catch(() => {});

    // Clear all client-side state to prevent data leaking between sessions
    queryClient.clear();
    useChatCacheStore.getState().clearAllCache();
    useDashboardStore.getState().reset();

    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  setLoading: (isLoading) => set({ isLoading }),

  hasPermission: (permission) => {
    const { user } = get();
    if (!user) return false;

    const permissions = user.permissions ?? [];

    if (permissions.includes('*:*')) return true;
    if (permissions.includes(permission)) return true;

    // Split on first colon only to support multi-level permissions
    // e.g. "services:control:restart" → resource="services", action="control:restart"
    const colonIdx = permission.indexOf(':');
    if (colonIdx === -1) return false;
    const resource = permission.substring(0, colonIdx);
    const action = permission.substring(colonIdx + 1);

    if (permissions.includes(`${resource}:*`)) return true;
    if (permissions.includes(`*:${action}`)) return true;

    return false;
  },

  hasRole: (role) => {
    const { user } = get();
    if (!user) return false;
    return user.role === role;
  },

  hasAnyRole: (roles) => {
    const { user } = get();
    if (!user) return false;
    return roles.includes(user.role);
  },
}));
