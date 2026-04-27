import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/auth-store';
import { CSRF_HEADER_NAME, getApiBaseUrl, getCsrfToken, isMutationMethod } from '@/lib/auth-session';
import type { SessionRefreshResponse } from '@/types/auth';

const API_BASE_URL = getApiBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (error?: unknown) => void;
}> = [];

const processQueue = (error: unknown | null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else {
      promise.resolve();
    }
  });
  failedQueue = [];
};

function syncRefreshedSessionUser(payload: SessionRefreshResponse) {
  if (!payload.user) {
    return;
  }

  useAuthStore.getState().setUser(payload.user);
}

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (config.headers && isMutationMethod(config.method)) {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        config.headers[CSRF_HEADER_NAME] = csrfToken;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };
    const requestUrl = originalRequest?.url || '';
    const skipRefresh =
      requestUrl.includes('/auth/session/login') ||
      requestUrl.includes('/auth/session/refresh') ||
      requestUrl.includes('/auth/login') ||
      requestUrl.includes('/auth/refresh') ||
      // Kiosk endpoints authenticate via ?token=... query param, not a session.
      // A 401 here means the kiosk token is invalid/revoked — the page should
      // render its Deauthorized fallback, not trigger a session-refresh/logout
      // chain that would redirect the kiosk display to the login page.
      requestUrl.includes('/dashboards/kiosk/');

    if (error.response?.status === 401 && !originalRequest._retry && !skipRefresh) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => apiClient(originalRequest))
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const csrfToken = getCsrfToken();
        const refreshResponse = await axios.post<SessionRefreshResponse>(
          `${API_BASE_URL}/auth/session/refresh`,
          undefined,
          {
            withCredentials: true,
            headers: csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : undefined,
          }
        );
        syncRefreshedSessionUser(refreshResponse.data);
        processQueue(null);

        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError as Error);
        handleLogout();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

function handleLogout() {
  useAuthStore.getState().clearAuth();

  if (typeof window === 'undefined') {
    return;
  }

  const pathname = window.location.pathname;
  // Skip the redirect on the login page itself, and on kiosk routes — kiosk
  // pages authenticate via ?token= and can legitimately trigger 401s from
  // widget data fetches without needing a session. Kiosk pages render their
  // own Deauthorized fallback when the kiosk token itself is invalid.
  if (pathname.includes('/login') || pathname.startsWith('/kiosk/')) {
    return;
  }

  window.location.href = '/login';
}

/**
 * Unified API error response type covering all formats returned by hydra-api.
 *
 * Format 1 - HydraError / ValidationError / General exception handlers:
 *   { error: { code: "...", message: "...", details: {...} }, requestId: "..." }
 *
 * Format 2 - FastAPI HTTPException (string detail):
 *   { detail: "string message" }
 *
 * Format 3 - FastAPI HTTPException (structured detail):
 *   { detail: { error: { code: "...", message: "...", details: {...} } } }
 */
interface ApiErrorData {
  // Format 1: HydraError handler response
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
  requestId?: string;
  // Format 2/3: FastAPI HTTPException detail
  detail?:
    | string
    | {
        error?: {
          code?: string;
          message?: string;
          details?: Record<string, unknown>;
        };
      };
}

/**
 * Parse an API error into a user-friendly message string.
 *
 * Handles all error formats from hydra-api:
 * - HydraError responses (error.message)
 * - HTTPException with string detail
 * - HTTPException with nested error object
 * - Network errors (no response)
 * - Timeout errors
 * - Generic JS errors
 *
 * @param error - The caught error (usually from a try/catch around an API call)
 * @param fallback - Optional fallback message if no meaningful message can be extracted
 * @returns A user-friendly error message string
 */
export function getErrorMessage(error: unknown, fallback?: string): string {
  const defaultFallback = fallback || 'An unexpected error occurred.';

  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorData>;

    // Handle network errors (no response received)
    if (!axiosError.response) {
      if (axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout')) {
        return 'Request timed out. Please check your connection and try again.';
      }
      if (axiosError.code === 'ERR_NETWORK') {
        return 'Unable to reach the server. Please check your connection.';
      }
      return 'Unable to reach the server. Please check your connection.';
    }

    const data = axiosError.response.data;

    if (data) {
      // Format 1: HydraError handler - { error: { code, message, details } }
      if (data.error && typeof data.error === 'object' && data.error.message) {
        return data.error.message;
      }

      // Format 2: HTTPException with string detail - { detail: "message" }
      if (typeof data.detail === 'string' && data.detail) {
        return data.detail;
      }

      // Format 3: HTTPException with nested error - { detail: { error: { message } } }
      if (
        typeof data.detail === 'object' &&
        data.detail !== null &&
        data.detail.error?.message
      ) {
        return data.detail.error.message;
      }
    }

    // Fall back to HTTP status code messages
    switch (axiosError.response.status) {
      case 400:
        return 'Invalid request. Please check your input.';
      case 401:
        return 'Your session has expired. Please log in again.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return 'The requested resource was not found.';
      case 409:
        return 'A conflict occurred. The resource may already exist.';
      case 422:
        return 'Validation failed. Please check your input.';
      case 429:
        return 'Too many requests. Please try again later.';
      case 500:
        return 'An internal server error occurred. Please try again later.';
      case 502:
        return 'The server is temporarily unavailable. Please try again later.';
      case 503:
        return 'The service is temporarily unavailable. Please try again later.';
      default:
        return defaultFallback;
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return defaultFallback;
}

/**
 * Extract the error code from an API error response.
 *
 * Handles all error formats from hydra-api:
 * - HydraError responses (error.code)
 * - HTTPException with nested error object (detail.error.code)
 *
 * @param error - The caught error
 * @returns The error code string, or null if not available
 */
export function getErrorCode(error: unknown): string | null {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorData>;
    const data = axiosError.response?.data;

    if (!data) return null;

    // Format 1: HydraError handler
    if (data.error && typeof data.error === 'object' && data.error.code) {
      return data.error.code;
    }

    // Format 3: HTTPException with nested error
    if (
      typeof data.detail === 'object' &&
      data.detail !== null &&
      data.detail.error?.code
    ) {
      return data.detail.error.code;
    }
  }
  return null;
}

export default apiClient;
