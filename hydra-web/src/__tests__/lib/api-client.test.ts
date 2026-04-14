import axios, { AxiosError } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: {
    getState: vi.fn(() => ({
      clearAuth: vi.fn(),
    })),
  },
}));

import { apiClient, getErrorCode, getErrorMessage } from '@/lib/api-client';

describe('apiClient', () => {
  beforeEach(() => {
    document.cookie = 'hydra_csrf=test-csrf; path=/';
    vi.clearAllMocks();
  });

  it('uses the resolved API base URL and cookie credentials', () => {
    expect(apiClient.defaults.baseURL).toBe(process.env.NEXT_PUBLIC_API_URL || '/api/v1');
    expect(apiClient.defaults.withCredentials).toBe(true);
    expect(apiClient.defaults.timeout).toBe(30000);
    expect(apiClient.defaults.headers['Content-Type']).toBe('application/json');
  });

  it('adds the CSRF header to mutating requests', async () => {
    const requestInterceptor = apiClient.interceptors.request.handlers?.[0]?.fulfilled;
    if (!requestInterceptor) {
      throw new Error('Request interceptor was not registered');
    }

    const config = await requestInterceptor({
      method: 'post',
      headers: {},
    } as any);

    expect(config.headers['X-CSRF-Token']).toBe('test-csrf');
  });

  it('does not add the CSRF header to GET requests', async () => {
    const requestInterceptor = apiClient.interceptors.request.handlers?.[0]?.fulfilled;
    if (!requestInterceptor) {
      throw new Error('Request interceptor was not registered');
    }

    const config = await requestInterceptor({
      method: 'get',
      headers: {},
    } as any);

    expect(config.headers['X-CSRF-Token']).toBeUndefined();
  });
});

describe('apiClient error helpers', () => {
  it('extracts user-facing messages from Hydra error payloads', () => {
    const axiosError = {
      isAxiosError: true,
      response: {
        status: 400,
        data: {
          error: {
            code: 'INVALID_INPUT',
            message: 'Invalid node ID format',
          },
        },
      },
    } as AxiosError;

    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);

    expect(getErrorMessage(axiosError)).toBe('Invalid node ID format');
    expect(getErrorCode(axiosError)).toBe('INVALID_INPUT');
  });

  it('falls back to HTTP status messages for Axios errors without payload messages', () => {
    const axiosError = {
      isAxiosError: true,
      response: {
        status: 401,
        data: {},
      },
    } as AxiosError;

    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);

    expect(getErrorMessage(axiosError)).toBe('Your session has expired. Please log in again.');
    expect(getErrorCode(axiosError)).toBeNull();
  });

  it('returns generic messages for non-Axios failures', () => {
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(false);

    expect(getErrorMessage(new Error('Boom'))).toBe('Boom');
    expect(getErrorMessage(null)).toBe('An unexpected error occurred.');
    expect(getErrorCode(new Error('Boom'))).toBeNull();
  });
});
