/**
 * WebSocket hook for MCP chat with streaming support.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthStore } from '@/stores/auth-store';

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

  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [currentToolCalls, setCurrentToolCalls] = useState<MCPToolCall[]>([]);

  // Build WebSocket URL
  const getWsUrl = useCallback(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';
    // Convert http(s) to ws(s)
    const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
    const wsBase = apiUrl.replace(/^https?/, wsProtocol);
    return `${wsBase}/chat/ws?accessToken=${accessToken}`;
  }, [accessToken]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    if (!accessToken) {
      onError?.('Not authenticated');
      return;
    }

    try {
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
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
        setIsConnected(false);
        setIsStreaming(false);
        onDisconnected?.();

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Auto-reconnect on unexpected close (but not on auth errors)
        if (event.code !== 4001 && event.code !== 4003 && event.code !== 1000) {
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, 3000);
        }
      };

      ws.onerror = () => {
        onError?.('WebSocket connection error');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
    } catch (error) {
      onError?.(`Failed to connect: ${error}`);
    }
  }, [accessToken, getWsUrl, onConnected, onDisconnected, onError]);

  const disconnect = useCallback(() => {
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
    sendMessage,
    cancelStream,
    connect,
    disconnect,
  };
}
