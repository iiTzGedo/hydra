/**
 * WebSocket hook for MCP chat with streaming support.
 *
 * Connects to the Hydra API WebSocket endpoint for real-time chat with LLM streaming.
 * Handles connection management, message streaming, tool calls, and automatic reconnection.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthStore } from '@/stores/auth-store';

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

interface UseMCPChatOptions {
  sessionId: string | null;
  providerId: string | null;
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
    onMessage,
    onToolCallStart,
    onToolCallResult,
    onError,
    onConnected,
    onDisconnected,
  } = options;

  const { accessToken } = useAuthStore();
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const pendingRefetchRef = useRef(false);

  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [currentToolCalls, setCurrentToolCalls] = useState<MCPToolCall[]>([]);

  /**
   * Build WebSocket URL from API URL configuration.
   * The chat WebSocket endpoint is at /chat/ws relative to the API base path.
   */
  const getWsUrl = useCallback(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

    try {
      // Parse the URL properly to handle all edge cases
      const url = new URL(apiUrl);
      const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';

      // Ensure pathname doesn't have trailing slash before appending
      const basePath = url.pathname.replace(/\/$/, '');
      const wsUrl = `${wsProtocol}//${url.host}${basePath}/chat/ws?token=${accessToken}`;

      if (WS_DEBUG) {
        console.log('[WebSocket] Constructed URL:', wsUrl.replace(/token=[^&]+/, 'token=***'));
      }

      return wsUrl;
    } catch {
      // Fallback for malformed URLs - use current window location
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/chat/ws?token=${accessToken}`;

      if (WS_DEBUG) {
        console.warn('[WebSocket] URL parsing failed, using fallback:', wsUrl.replace(/token=[^&]+/, 'token=***'));
      }

      return wsUrl;
    }
  }, [accessToken]);

  const connect = useCallback(() => {
    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      if (WS_DEBUG) console.log('[WebSocket] Already connected');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      if (WS_DEBUG) console.log('[WebSocket] Connection in progress');
      return;
    }

    if (!accessToken) {
      if (WS_DEBUG) console.warn('[WebSocket] No access token available');
      onError?.('Not authenticated');
      return;
    }

    const wsUrl = getWsUrl();

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
        onConnected?.();

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
        onDisconnected?.();

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Handle specific close codes
        if (event.code === 4001) {
          onError?.('Authentication failed - please log in again');
          return;
        }

        if (event.code === 4003) {
          onError?.('Access denied - agents cannot use chat');
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
          onError?.('Connection lost - maximum reconnection attempts reached');
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
      onError?.(`Failed to connect: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, [accessToken, getWsUrl, onConnected, onDisconnected, onError]);

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
        onToolCallStart?.(newToolCall);
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
        onToolCallResult?.(updatedToolCall);
        break;
      }

      case WSMessageType.MESSAGE_COMPLETE: {
        setIsStreaming(false);
        const message: ChatMessage = {
          id: data.messageId as string || crypto.randomUUID(),
          role: 'assistant',
          content: data.content as string || currentResponse,
          toolCalls: data.toolCalls as MCPToolCall[] || currentToolCalls,
        };
        onMessage?.(message);

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
        onError?.(data.error as string || 'Unknown error');
        break;

      case WSMessageType.PONG:
        // Heartbeat response, no action needed
        break;

      default:
        console.warn('Unknown WebSocket message type:', type);
    }
  }, [currentResponse, currentToolCalls, onMessage, onToolCallStart, onToolCallResult, onError]);

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      onError?.('Not connected to chat server');
      return;
    }

    if (!sessionId) {
      onError?.('No session selected');
      return;
    }

    // Reset streaming state
    setCurrentResponse('');
    setCurrentToolCalls([]);
    setIsStreaming(true);

    // Send chat request
    wsRef.current.send(JSON.stringify({
      type: WSMessageType.CHAT_REQUEST,
      sessionId,
      content,
      providerId,
    }));
  }, [sessionId, providerId, onError]);

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
