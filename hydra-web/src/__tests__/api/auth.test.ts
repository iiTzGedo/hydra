import { waitFor } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { renderWithQuery } from '../msw/test-utils';
import { server } from '../msw/server';
import {
  useLogin,
  useLogout,
  useMe,
  useRefreshToken,
  useRegister,
} from '@/api/auth';
import { useAuthStore } from '@/stores/auth-store';
import type { LoginRequest, RegisterRequest } from '@/types/auth';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

describe('auth hooks', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: true,
    });
    document.cookie = 'hydra_csrf=test-csrf; path=/';
  });

  it('logs in through the browser session endpoint and updates the auth store', async () => {
    const { result } = renderWithQuery(() => useLogin());
    const loginData: LoginRequest = {
      username: 'system_admin',
      password: 'system12345',
    };

    result.current.mutate(loginData);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.expiresIn).toBe(3600);
    expect(result.current.data?.user.username).toBe('system_admin');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().user?.role).toBe('admin');
  });

  it('surfaces login failures without authenticating the store', async () => {
    const { result } = renderWithQuery(() => useLogin());

    result.current.mutate({
      username: 'wrong_user',
      password: 'wrong_password',
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('bootstraps auth state from /auth/me', async () => {
    const { result } = renderWithQuery(() => useMe());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.type).toBe('user');
    expect(useAuthStore.getState().user?.username).toBe('system_admin');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it('clears auth state when /auth/me reports an agent identity', async () => {
    useAuthStore.getState().login({
      userId: 'user-123',
      username: 'system_admin',
      email: 'admin@example.com',
      role: 'admin',
      permissions: ['*:*'],
      temporaryRoles: [],
    });

    server.use(
      http.get(`${BASE_URL}/auth/me`, () =>
        HttpResponse.json({
          type: 'agent',
          nodeId: 'node-123',
          permissions: [],
        })
      )
    );

    const { result } = renderWithQuery(() => useMe());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('logs out by clearing the session-backed auth store state', async () => {
    useAuthStore.getState().login({
      userId: 'user-123',
      username: 'system_admin',
      email: 'admin@example.com',
      role: 'admin',
      permissions: ['*:*'],
      temporaryRoles: [],
    });

    const { result } = renderWithQuery(() => useLogout());

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('refreshes the browser session through the session refresh endpoint', async () => {
    const { result } = renderWithQuery(() => useRefreshToken());

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.expiresIn).toBe(3600);
  });

  it('registers a user without returning a password field', async () => {
    const { result } = renderWithQuery(() => useRegister());
    const registerData: RegisterRequest = {
      username: 'new_user',
      email: 'newuser@example.com',
      password: 'SecurePass123!',
      role: 'viewer',
    };

    result.current.mutate(registerData);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.username).toBe('new_user');
    expect(result.current.data?.role).toBe('viewer');
    expect(result.current.data).not.toHaveProperty('password');
  });
});
