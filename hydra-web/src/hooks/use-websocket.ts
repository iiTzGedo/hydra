/**
 * Reusable WebSocket hook with automatic reconnection, ping/pong, and session refresh.
 *
 * Manages WebSocket connection lifecycle independently of message-handling logic.
 * Consumers provide an `onMessage` callback to handle incoming messages.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { CSRF_HEADER_NAME, getApiBaseUrl, getCsrfToken } from '@/lib/auth-session';

// Enable debug logging for WebSocket connections
const WS_DEBUG = import.meta.env.DEV;

// Consolidated debug logging utility
export const wsDebug = {
  log: WS_DEBUG ? (...args: unknown[]) => console.log('[WebSocket]', ...args) : () => {},
  warn: WS_DEBUG ? (...args: unknown[]) => console.warn('[WebSocket]', ...args) : () => {},
  error: WS_DEBUG ? (...args: unknown[]) => console.error('[WebSocket]', ...args) : () => {},
};

// Reconnection configuration
const RECONNECT_BASE_DELAY = 1000; // 1 second
const RECONNECT_MAX_DELAY = 30000; // 30 seconds
const RECONNECT_MAX_ATTEMPTS = 10;

// Ping interval
const PING_INTERVAL = 30000; // 30 seconds

const API_BASE_URL = getApiBaseUrl();
let sessionRefreshPromise: Promise<string | null> | null = null;

/**
 * Refresh the cookie-backed browser session.
 * Returns the CSRF bootstrap token or null if refresh failed.
 */
export async function refreshSession(): Promise<string | null> {
  const csrfToken = getCsrfToken();
  if (!csrfToken) {
    wsDebug.log('No CSRF token available');
    return null;
  }

  if (sessionRefreshPromise) {
    wsDebug.log('Session refresh already in progress');
    return sessionRefreshPromise;
  }

  const refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/session/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          [CSRF_HEADER_NAME]: csrfToken,
        },
      });

      if (!response.ok) {
        // Avoid logging the user out on a transient background refresh race.
        wsDebug.log('Session refresh failed:', response.status);
        return null;
      }

      wsDebug.log('Session refreshed successfully');
      return getCsrfToken() || csrfToken;
    } catch (error) {
      wsDebug.error('Session refresh error:', error);
      return null;
    }
  })();

  sessionRefreshPromise = refreshPromise;
  const clearRefreshPromise = () => {
    if (sessionRefreshPromise === refreshPromise) {
      sessionRefreshPromise = null;
    }
  };
  refreshPromise.then(clearRefreshPromise, clearRefreshPromise);

  return refreshPromise;
}

/**
 * Build WebSocket URL from API URL configuration.
 * Token is NOT included in the URL — authentication happens via message after connection.
 * @param path - WebSocket path relative to API base (e.g., '/chat/ws')
 */
export function buildWsUrl(path: string): string {
  const apiUrl = getApiBaseUrl();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  try {
    if (/^https?:\/\//.test(apiUrl)) {
      const url = new URL(apiUrl);
      const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      const basePath = url.pathname.replace(/\/$/, '');
      const wsUrl = `${wsProtocol}//${url.host}${basePath}${normalizedPath}`;

      wsDebug.log('Constructed URL:', wsUrl);
      return wsUrl;
    }

    const basePath = apiUrl.startsWith('/') ? apiUrl : `/${apiUrl}`;
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}${basePath.replace(/\/$/, '')}${normalizedPath}`;

    wsDebug.log('Constructed URL:', wsUrl);
    return wsUrl;
  } catch {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1${normalizedPath}`;

    wsDebug.warn('URL parsing failed, using fallback:', wsUrl);
    return wsUrl;
  }
}

export interface UseWebSocketOptions {
  /** WebSocket path relative to API base (e.g., '/chat/ws') */
  path: string;
  /** Message type string to use for ping messages */
  pingType?: string;
  /** Callback when a parsed JSON message is received */
  onMessage?: (data: Record<string, unknown>) => void;
  /** Callback on connection error */
  onError?: (error: string) => void;
  /** Callback when connected */
  onConnected?: () => void;
  /** Callback when disconnected */
  onDisconnected?: () => void;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  wsRef: React.MutableRefObject<WebSocket | null>;
  connect: () => Promise<void>;
  disconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    path,
    pingType = 'ping',
    onMessage,
    onError,
    onConnected,
    onDisconnected,
  } = options;

  // Refs for WebSocket and timers
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const connectPromiseRef = useRef<Promise<void> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const authFailedRef = useRef(false);
  const connectCycleRef = useRef(0);

  // Callback refs to avoid stale closures
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onConnectedRef = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);

  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);
  useEffect(() => { onConnectedRef.current = onConnected; }, [onConnected]);
  useEffect(() => { onDisconnectedRef.current = onDisconnected; }, [onDisconnected]);

  const [isConnected, setIsConnected] = useState(false);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (isAuthenticated) {
      authFailedRef.current = false;
    }
  }, [isAuthenticated]);

  const connect = useCallback(async () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (authFailedRef.current) {
      wsDebug.warn('Auth failure latched, skipping reconnect');
      return;
    }

    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsDebug.log('Already connected');
      return;
    }
    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      wsDebug.log('Connection in progress');
      return;
    }

    if (connectPromiseRef.current) {
      wsDebug.log('Connection setup already in progress');
      return connectPromiseRef.current;
    }

    const connectCycle = ++connectCycleRef.current;
    const connectPromise: Promise<void> = (async () => {
      const csrfToken = getCsrfToken();
      if (!csrfToken) {
        wsDebug.warn('No CSRF token available');
        onErrorRef.current?.('Not authenticated');
        return;
      }

      wsDebug.log('Refreshing session before connection...');
      const refreshedCsrfToken = await refreshSession();
      const bootstrapToken = refreshedCsrfToken || getCsrfToken() || csrfToken;

      if (connectCycle !== connectCycleRef.current) {
        wsDebug.log('Connection attempt superseded before WebSocket creation');
        return;
      }

      if (!bootstrapToken) {
        wsDebug.warn('No CSRF bootstrap token available');
        onErrorRef.current?.('Not authenticated');
        return;
      }

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsDebug.log('Already connected');
        return;
      }
      if (wsRef.current?.readyState === WebSocket.CONNECTING) {
        wsDebug.log('Connection in progress');
        return;
      }

      const wsUrl = buildWsUrl(path);

      try {
        wsDebug.log('Attempting connection...', {
          attempt: reconnectAttemptRef.current + 1,
          maxAttempts: RECONNECT_MAX_ATTEMPTS,
        });

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          wsDebug.log('Connected, sending authentication message...');

          ws.send(JSON.stringify({ type: 'authenticate', csrfToken: bootstrapToken }));
        };

        ws.onclose = (event) => {
          wsDebug.log('Connection closed', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
          });

          if (wsRef.current === ws) {
            wsRef.current = null;
          }

          setIsConnected(false);
          onDisconnectedRef.current?.();

          // Clear ping interval
          if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
          }

          // Handle specific close codes
          if (event.code === 4001) {
            authFailedRef.current = true;
            useAuthStore.getState().clearAuth();
            onErrorRef.current?.('Authentication failed - please log in again');
            return;
          }
          if (event.code === 4003) {
            authFailedRef.current = true;
            onErrorRef.current?.('Access denied');
            return;
          }
          // Normal closure - don't reconnect
          if (event.code === 1000) {
            return;
          }

          // Unexpected close - attempt reconnection with exponential backoff
          if (reconnectAttemptRef.current < RECONNECT_MAX_ATTEMPTS) {
            const delay = Math.min(
              RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttemptRef.current),
              RECONNECT_MAX_DELAY
            );
            reconnectAttemptRef.current++;

            wsDebug.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current}/${RECONNECT_MAX_ATTEMPTS})`);

            reconnectTimeoutRef.current = window.setTimeout(() => {
              void connect();
            }, delay);
          } else {
            onErrorRef.current?.('Connection lost - maximum reconnection attempts reached');
          }
        };

        ws.onerror = (event) => {
          wsDebug.error('Connection error', event);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            // Handle authentication response from server
            if (data.type === 'authenticated') {
              wsDebug.log('Authenticated successfully');
              reconnectAttemptRef.current = 0;
              setIsConnected(true);
              onConnectedRef.current?.();

              // Start ping interval after successful auth
              pingIntervalRef.current = window.setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                  ws.send(JSON.stringify({ type: pingType }));
                }
              }, PING_INTERVAL);
              return;
            }

            onMessageRef.current?.(data);
          } catch (e) {
            wsDebug.error('Failed to parse message:', e);
          }
        };
      } catch (error) {
        wsDebug.error('Failed to create WebSocket:', error);
        onErrorRef.current?.(`Failed to connect: ${error instanceof Error ? error.message : String(error)}`);
      }
    })().finally(() => {
      if (connectPromiseRef.current === connectPromise) {
        connectPromiseRef.current = null;
      }
    });

    connectPromiseRef.current = connectPromise;
    return connectPromise;
  }, [path, pingType]); // Minimal dependencies - callbacks accessed via refs

  const disconnect = useCallback(() => {
    wsDebug.log('Disconnecting...');
    connectCycleRef.current += 1;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }

    reconnectAttemptRef.current = 0;
    setIsConnected(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    wsRef,
    connect,
    disconnect,
  };
}
