/**
 * Reusable WebSocket hook with automatic reconnection, ping/pong, and token refresh.
 *
 * Manages WebSocket connection lifecycle independently of message-handling logic.
 * Consumers provide an `onMessage` callback to handle incoming messages.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { storage } from '@/lib/storage';

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

// API URL for token refresh
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

/**
 * Refresh the access token using the refresh token.
 * Returns the new access token or null if refresh failed.
 */
export async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = storage.getRefreshToken();
  if (!refreshToken) {
    wsDebug.log('No refresh token available');
    return null;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refreshToken }),
    });

    if (!response.ok) {
      wsDebug.log('Token refresh failed:', response.status);
      return null;
    }

    const data = await response.json();
    const { accessToken, refreshToken: newRefreshToken } = data;

    // Update storage and Zustand store
    storage.setTokens(accessToken, newRefreshToken);
    useAuthStore.getState().setTokens(accessToken, newRefreshToken);

    wsDebug.log('Token refreshed successfully');
    return accessToken;
  } catch (error) {
    wsDebug.error('Token refresh error:', error);
    return null;
  }
}

/**
 * Build WebSocket URL from API URL configuration.
 * @param path - WebSocket path relative to API base (e.g., '/chat/ws')
 * @param token - Authentication token
 */
export function buildWsUrl(path: string, token: string): string {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

  try {
    const url = new URL(apiUrl);
    const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const basePath = url.pathname.replace(/\/$/, '');
    const wsUrl = `${wsProtocol}//${url.host}${basePath}${path}?token=${token}`;

    wsDebug.log('Constructed URL:', wsUrl.replace(/token=[^&]+/, 'token=***'));
    return wsUrl;
  } catch {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1${path}?token=${token}`;

    wsDebug.warn('URL parsing failed, using fallback:', wsUrl.replace(/token=[^&]+/, 'token=***'));
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
  const reconnectAttemptRef = useRef(0);

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

  const connect = useCallback(async () => {
    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsDebug.log('Already connected');
      return;
    }
    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      wsDebug.log('Connection in progress');
      return;
    }

    // Proactively refresh token before connecting
    wsDebug.log('Refreshing token before connection...');
    let tokenToUse = await refreshAccessToken();

    if (!tokenToUse) {
      tokenToUse = useAuthStore.getState().accessToken;
      wsDebug.log('Using existing token from store');
    }

    if (!tokenToUse) {
      wsDebug.warn('No access token available');
      onErrorRef.current?.('Not authenticated');
      return;
    }

    const wsUrl = buildWsUrl(path, tokenToUse);

    try {
      wsDebug.log('Attempting connection...', {
        attempt: reconnectAttemptRef.current + 1,
        maxAttempts: RECONNECT_MAX_ATTEMPTS,
      });

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        wsDebug.log('Connected successfully');
        reconnectAttemptRef.current = 0;
        setIsConnected(true);
        onConnectedRef.current?.();

        // Start ping interval
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: pingType }));
          }
        }, PING_INTERVAL);
      };

      ws.onclose = (event) => {
        wsDebug.log('Connection closed', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
        });

        setIsConnected(false);
        onDisconnectedRef.current?.();

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Handle specific close codes
        if (event.code === 4001) {
          onErrorRef.current?.('Authentication failed - please log in again');
          return;
        }
        if (event.code === 4003) {
          onErrorRef.current?.('Access denied - agents cannot use chat');
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
            connect();
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
          onMessageRef.current?.(data);
        } catch (e) {
          console.error('[WebSocket] Failed to parse message:', e);
        }
      };
    } catch (error) {
      wsDebug.error('Failed to create WebSocket:', error);
      onErrorRef.current?.(`Failed to connect: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, [path, pingType]); // Minimal dependencies - callbacks accessed via refs

  const disconnect = useCallback(() => {
    wsDebug.log('Disconnecting...');

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
