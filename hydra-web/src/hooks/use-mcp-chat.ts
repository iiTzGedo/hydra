/**
 * WebSocket hook for MCP chat with streaming support.
 *
 * Connects to the Hydra API WebSocket endpoint for real-time chat with LLM streaming.
 * Handles connection management, message streaming, tool calls, and automatic reconnection.
 *
 * Uses refs for callbacks to avoid closure bugs where WebSocket handlers capture stale values.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { STORAGE_KEYS } from '@/lib/constants';

// Enable debug logging for WebSocket connections
const WS_DEBUG = import.meta.env.DEV;

// WebSocket message types from backend
const WSMessageType = {
  // Client -> Server
  CHAT_REQUEST: 'chat_request',
  CANCEL: 'cancel',
  PING: 'ping',

  // Server -> Client
  TEXT_DELTA: 'text_delta',
  TOOL_CALL_START: 'tool_call_start',
  TOOL_CALL_RESULT: 'tool_call_result',
  MESSAGE_COMPLETE: 'message_complete',
  ERROR: 'error',
  PONG: 'pong',
} as const;

// Reconnection configuration
const RECONNECT_BASE_DELAY = 1000; // 1 second
const RECONNECT_MAX_DELAY = 30000; // 30 seconds
const RECONNECT_MAX_ATTEMPTS = 10;

// API URL for token refresh
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

/**
 * Refresh the access token using the refresh token.
 * Returns the new access token or null if refresh failed.
 */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
  if (!refreshToken) {
    if (WS_DEBUG) console.log('[WebSocket] No refresh token available');
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
      if (WS_DEBUG) console.log('[WebSocket] Token refresh failed:', response.status);
      return null;
    }

    const data = await response.json();
    const { accessToken, refreshToken: newRefreshToken } = data;

    // Update localStorage
    localStorage.setItem(STORAGE_KEYS.accessToken, accessToken);
    localStorage.setItem(STORAGE_KEYS.refreshToken, newRefreshToken);

    // Update Zustand store
    useAuthStore.getState().setTokens(accessToken, newRefreshToken);

    if (WS_DEBUG) console.log('[WebSocket] Token refreshed successfully');
    return accessToken;
  } catch (error) {
    if (WS_DEBUG) console.error('[WebSocket] Token refresh error:', error);
    return null;
  }
}

export interface MCPToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: string;
  error?: string;
  status: 'pending' | 'success' | 'error';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: MCPToolCall[];
  isStreaming?: boolean;
  error?: boolean;
}

// Reasoning level type - matches chat-input.tsx
export type ReasoningLevel = 'none' | 'low' | 'medium' | 'high';

interface UseMCPChatOptions {
  sessionId: string | null;
  providerId: string | null;
  reasoningLevel?: ReasoningLevel;
  webSearchEnabled?: boolean;
  onMessage?: (message: ChatMessage) => void;
  onToolCallStart?: (toolCall: MCPToolCall) => void;
  onToolCallResult?: (toolCall: MCPToolCall) => void;
  onError?: (error: string) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
}

interface UseMCPChatReturn {
  isConnected: boolean;
  isStreaming: boolean;
  currentResponse: string;
  currentToolCalls: MCPToolCall[];
  hasPendingRefetch: boolean;
  clearPendingRefetch: () => void;
  sendMessage: (content: string) => void;
  cancelStream: () => void;
  connect: () => void;
  disconnect: () => void;
}

export function useMCPChat(options: UseMCPChatOptions): UseMCPChatReturn {
  const {
    sessionId,
    providerId,
    reasoningLevel = 'none',
    webSearchEnabled,
    onMessage,
    onToolCallStart,
    onToolCallResult,
    onError,
    onConnected,
    onDisconnected,
  } = options;

  // Refs for WebSocket and timers
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const pendingRefetchRef = useRef(false);

  // Refs for callbacks - these allow WebSocket handlers to always use latest callbacks
  // without needing to recreate the handlers when callbacks change
  const onMessageRef = useRef(onMessage);
  const onToolCallStartRef = useRef(onToolCallStart);
  const onToolCallResultRef = useRef(onToolCallResult);
  const onErrorRef = useRef(onError);
  const onConnectedRef = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);

  // Refs for streaming state - allows handlers to access current values without closure issues
  const currentResponseRef = useRef('');
  const currentToolCallsRef = useRef<MCPToolCall[]>([]);

  // Update callback refs when they change
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onToolCallStartRef.current = onToolCallStart;
  }, [onToolCallStart]);

  useEffect(() => {
    onToolCallResultRef.current = onToolCallResult;
  }, [onToolCallResult]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    onConnectedRef.current = onConnected;
  }, [onConnected]);

  useEffect(() => {
    onDisconnectedRef.current = onDisconnected;
  }, [onDisconnected]);

  // State for UI
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [currentToolCalls, setCurrentToolCalls] = useState<MCPToolCall[]>([]);

  // Sync state to refs for access in handlers
  useEffect(() => {
    currentResponseRef.current = currentResponse;
  }, [currentResponse]);

  useEffect(() => {
    currentToolCallsRef.current = currentToolCalls;
  }, [currentToolCalls]);

  /**
   * Build WebSocket URL from API URL configuration.
   * The chat WebSocket endpoint is at /chat/ws relative to the API base path.
   */
  const getWsUrl = useCallback((token: string) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

    try {
      // Parse the URL properly to handle all edge cases
      const url = new URL(apiUrl);
      const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';

      // Ensure pathname doesn't have trailing slash before appending
      const basePath = url.pathname.replace(/\/$/, '');
      const wsUrl = `${wsProtocol}//${url.host}${basePath}/chat/ws?token=${token}`;

      if (WS_DEBUG) {
        console.log('[WebSocket] Constructed URL:', wsUrl.replace(/token=[^&]+/, 'token=***'));
      }

      return wsUrl;
    } catch {
      // Fallback for malformed URLs - use current window location
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/chat/ws?token=${token}`;

      if (WS_DEBUG) {
        console.warn('[WebSocket] URL parsing failed, using fallback:', wsUrl.replace(/token=[^&]+/, 'token=***'));
      }

      return wsUrl;
    }
  }, []);

  /**
   * Handle incoming WebSocket messages.
   * Uses refs to access current callbacks and state to avoid closure bugs.
   */
  const handleMessage = useCallback((data: Record<string, unknown>) => {
    const type = data.type as string;

    switch (type) {
      case WSMessageType.TEXT_DELTA:
        setCurrentResponse(prev => prev + (data.text as string || ''));
        break;

      case WSMessageType.TOOL_CALL_START: {
        const toolCall = data.toolCall as MCPToolCall;
        const newToolCall: MCPToolCall = {
          id: toolCall.id,
          name: toolCall.name,
          arguments: toolCall.arguments || {},
          status: 'pending',
        };
        setCurrentToolCalls(prev => [...prev, newToolCall]);
        onToolCallStartRef.current?.(newToolCall);
        break;
      }

      case WSMessageType.TOOL_CALL_RESULT: {
        const result = data.toolCall as { id: string; result: string; isError: boolean };
        setCurrentToolCalls(prev =>
          prev.map(tc =>
            tc.id === result.id
              ? {
                  ...tc,
                  result: result.result,
                  status: result.isError ? 'error' : 'success',
                  error: result.isError ? result.result : undefined,
                }
              : tc
          )
        );
        const updatedToolCall: MCPToolCall = {
          id: result.id,
          name: '',
          arguments: {},
          result: result.result,
          status: result.isError ? 'error' : 'success',
          error: result.isError ? result.result : undefined,
        };
        onToolCallResultRef.current?.(updatedToolCall);
        break;
      }

      case WSMessageType.MESSAGE_COMPLETE: {
        setIsStreaming(false);
        const message: ChatMessage = {
          id: data.messageId as string || crypto.randomUUID(),
          role: 'assistant',
          // Use refs to get current values, not stale closure values
          content: data.content as string || currentResponseRef.current,
          toolCalls: data.toolCalls as MCPToolCall[] || currentToolCallsRef.current,
        };
        onMessageRef.current?.(message);

        // If tab was in background, mark for refetch when user returns
        if (document.hidden) {
          pendingRefetchRef.current = true;
          if (WS_DEBUG) console.log('[WebSocket] Message completed while tab in background, will refetch on return');
        }

        // Reset state for next message
        setCurrentResponse('');
        setCurrentToolCalls([]);
        break;
      }

      case WSMessageType.ERROR:
        setIsStreaming(false);
        onErrorRef.current?.(data.error as string || 'Unknown error');
        break;

      case WSMessageType.PONG:
        // Heartbeat response, no action needed
        break;

      default:
        console.warn('Unknown WebSocket message type:', type);
    }
  }, []); // No dependencies - uses refs for everything

  const connect = useCallback(async () => {
    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      if (WS_DEBUG) console.log('[WebSocket] Already connected');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      if (WS_DEBUG) console.log('[WebSocket] Connection in progress');
      return;
    }

    // Proactively refresh token before connecting to ensure it's not expired
    if (WS_DEBUG) console.log('[WebSocket] Refreshing token before connection...');
    let tokenToUse = await refreshAccessToken();

    // If refresh failed, try using current token from store as fallback
    if (!tokenToUse) {
      tokenToUse = useAuthStore.getState().accessToken;
      if (WS_DEBUG) console.log('[WebSocket] Using existing token from store');
    }

    if (!tokenToUse) {
      if (WS_DEBUG) console.warn('[WebSocket] No access token available');
      onErrorRef.current?.('Not authenticated');
      return;
    }

    const wsUrl = getWsUrl(tokenToUse);

    try {
      if (WS_DEBUG) {
        console.log('[WebSocket] Attempting connection...', {
          attempt: reconnectAttemptRef.current + 1,
          maxAttempts: RECONNECT_MAX_ATTEMPTS,
        });
      }

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (WS_DEBUG) console.log('[WebSocket] Connected successfully');

        // Reset reconnection counter on successful connection
        reconnectAttemptRef.current = 0;

        setIsConnected(true);
        onConnectedRef.current?.();

        // Start ping interval to keep connection alive
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: WSMessageType.PING }));
          }
        }, 30000);
      };

      ws.onclose = (event) => {
        if (WS_DEBUG) {
          console.log('[WebSocket] Connection closed', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
          });
        }

        setIsConnected(false);
        setIsStreaming(false);
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

          if (WS_DEBUG) {
            console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current}/${RECONNECT_MAX_ATTEMPTS})`);
          }

          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, delay);
        } else {
          onErrorRef.current?.('Connection lost - maximum reconnection attempts reached');
        }
      };

      ws.onerror = (event) => {
        if (WS_DEBUG) {
          console.error('[WebSocket] Connection error', event);
        }
        // Don't call onError here - onclose will be called after onerror
        // and we handle the error there with proper context
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (e) {
          console.error('[WebSocket] Failed to parse message:', e);
        }
      };
    } catch (error) {
      if (WS_DEBUG) {
        console.error('[WebSocket] Failed to create WebSocket:', error);
      }
      onErrorRef.current?.(`Failed to connect: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, [getWsUrl, handleMessage]); // Minimal dependencies - callbacks accessed via refs

  const disconnect = useCallback(() => {
    if (WS_DEBUG) console.log('[WebSocket] Disconnecting...');

    // Clear reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Clear ping interval
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    // Close WebSocket connection
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }

    // Reset state
    reconnectAttemptRef.current = 0;
    setIsConnected(false);
    setIsStreaming(false);
  }, []);

  // Refs for sendMessage to avoid recreating it when these change
  const sessionIdRef = useRef(sessionId);
  const providerIdRef = useRef(providerId);
  const reasoningLevelRef = useRef(reasoningLevel);
  const webSearchEnabledRef = useRef(webSearchEnabled);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    providerIdRef.current = providerId;
  }, [providerId]);

  useEffect(() => {
    reasoningLevelRef.current = reasoningLevel;
  }, [reasoningLevel]);

  useEffect(() => {
    webSearchEnabledRef.current = webSearchEnabled;
  }, [webSearchEnabled]);

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      onErrorRef.current?.('Not connected to chat server');
      return;
    }

    if (!sessionIdRef.current) {
      onErrorRef.current?.('No session selected');
      return;
    }

    // Reset streaming state
    setCurrentResponse('');
    setCurrentToolCalls([]);
    setIsStreaming(true);

    // Send chat request with feature flags
    wsRef.current.send(JSON.stringify({
      type: WSMessageType.CHAT_REQUEST,
      sessionId: sessionIdRef.current,
      content,
      providerId: providerIdRef.current,
      reasoningLevel: reasoningLevelRef.current ?? 'none',
      webSearchEnabled: webSearchEnabledRef.current ?? false,
    }));
  }, []); // No dependencies - uses refs for everything

  const cancelStream = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: WSMessageType.CANCEL }));
    }
    setIsStreaming(false);
  }, []);

  // Track pending refetch state
  const [hasPendingRefetch, setHasPendingRefetch] = useState(false);

  const clearPendingRefetch = useCallback(() => {
    pendingRefetchRef.current = false;
    setHasPendingRefetch(false);
  }, []);

  // Handle visibility change for background message handling
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden && pendingRefetchRef.current) {
        if (WS_DEBUG) console.log('[WebSocket] Tab visible again, pending refetch detected');
        setHasPendingRefetch(true);
        // Note: The actual refetch is handled by the chat page via the hasPendingRefetch flag
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isStreaming,
    currentResponse,
    currentToolCalls,
    hasPendingRefetch,
    clearPendingRefetch,
    sendMessage,
    cancelStream,
    connect,
    disconnect,
  };
}
