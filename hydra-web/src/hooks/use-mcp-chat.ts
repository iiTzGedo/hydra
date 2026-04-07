/**
 * MCP Chat hook with streaming support.
 *
 * Builds on useWebSocket for connection lifecycle, adding chat-specific
 * message handling, streaming state, tool calls, and send/retry/cancel actions.
 *
 * Uses refs for callbacks to avoid closure bugs where WebSocket handlers capture stale values.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useWebSocket, wsDebug } from '@/hooks/use-websocket';
import { useNotificationStore } from '@/stores/notification-store';
import type { Notification } from '@/types/notification';

// WebSocket message types from backend
const WSMessageType = {
  // Client -> Server
  CHAT_REQUEST: 'chat_request',
  RETRY_MESSAGE: 'retry_message',
  CANCEL: 'cancel',
  PING: 'ping',

  // Server -> Client
  TEXT_DELTA: 'text_delta',
  TOOL_CALL_START: 'tool_call_start',
  TOOL_CALL_RESULT: 'tool_call_result',
  MESSAGE_COMPLETE: 'message_complete',
  NOTIFICATION: 'notification',
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

// Reasoning level type - matches chat-input.tsx
export type ReasoningLevel = 'none' | 'low' | 'medium' | 'high';

// Model configuration for per-request overrides
export interface ModelConfig {
  maxTokens?: number;
  temperature?: number;
  topP?: number;
  topK?: number;
  frequencyPenalty?: number;
  presencePenalty?: number;
}

// Session token usage info returned from message_complete
export interface SessionUsage {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  contextWindow: number;
}

interface UseMCPChatOptions {
  sessionId: string | null;
  providerId: string | null;
  reasoningLevel?: ReasoningLevel;
  webSearchEnabled?: boolean;
  modelConfig?: ModelConfig;
  onMessage?: (message: ChatMessage, usage?: SessionUsage) => void;
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
  retryMessage: (messageId: string) => void;
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
    modelConfig,
    onMessage,
    onToolCallStart,
    onToolCallResult,
    onError,
    onConnected,
    onDisconnected,
  } = options;

  const pendingRefetchRef = useRef(false);

  // Callback refs for chat-specific handlers
  const onMessageRef = useRef(onMessage);
  const onToolCallStartRef = useRef(onToolCallStart);
  const onToolCallResultRef = useRef(onToolCallResult);

  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onToolCallStartRef.current = onToolCallStart; }, [onToolCallStart]);
  useEffect(() => { onToolCallResultRef.current = onToolCallResult; }, [onToolCallResult]);

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [currentToolCalls, setCurrentToolCalls] = useState<MCPToolCall[]>([]);

  // Refs for streaming state so handlers can access current values
  const currentResponseRef = useRef('');
  const currentToolCallsRef = useRef<MCPToolCall[]>([]);

  useEffect(() => { currentResponseRef.current = currentResponse; }, [currentResponse]);
  useEffect(() => { currentToolCallsRef.current = currentToolCalls; }, [currentToolCalls]);

  /**
   * Handle incoming WebSocket messages (chat-specific dispatch).
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
        const existing = currentToolCallsRef.current.find((tc) => tc.id === result.id);
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
          name: existing?.name ?? '',
          arguments: existing?.arguments ?? {},
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
          content: data.content as string || currentResponseRef.current,
          toolCalls: data.toolCalls as MCPToolCall[] || currentToolCallsRef.current,
        };

        const usageData = data.usage as SessionUsage | undefined;
        const usage: SessionUsage | undefined = usageData ? {
          inputTokens: usageData.inputTokens || 0,
          outputTokens: usageData.outputTokens || 0,
          totalTokens: usageData.totalTokens || 0,
          contextWindow: usageData.contextWindow || 0,
        } : undefined;

        onMessageRef.current?.(message, usage);

        if (document.hidden) {
          pendingRefetchRef.current = true;
          wsDebug.log('Message completed while tab in background, will refetch on return');
        }

        setCurrentResponse('');
        setCurrentToolCalls([]);
        break;
      }

      case WSMessageType.ERROR:
        setIsStreaming(false);
        // Access onError via the websocket's onError callback
        break;

      case WSMessageType.NOTIFICATION: {
        const notifData = data.data as Partial<Notification>;
        if (notifData?.notificationId) {
          useNotificationStore.getState().addNotification(notifData as Notification);
        }
        break;
      }

      case WSMessageType.PONG:
        break;

      default:
        wsDebug.log('Unknown WebSocket message type:', type);
    }
  }, []);

  // Error ref for the websocket layer
  const onErrorRef = useRef(onError);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  // Combined message handler that also handles errors from chat messages
  const handleWsMessage = useCallback((data: Record<string, unknown>) => {
    if (data.type === WSMessageType.ERROR) {
      setIsStreaming(false);
      onErrorRef.current?.(data.error as string || 'Unknown error');
      return;
    }
    handleMessage(data);
  }, [handleMessage]);

  // Use the WebSocket hook for connection lifecycle
  const {
    isConnected,
    wsRef,
    connect,
    disconnect,
  } = useWebSocket({
    path: '/chat/ws',
    pingType: WSMessageType.PING,
    onMessage: handleWsMessage,
    onError: onError,
    onConnected: () => {
      onConnected?.();
    },
    onDisconnected: () => {
      setIsStreaming(false);
      onDisconnected?.();
    },
  });

  // Refs for send parameters to avoid recreating callbacks
  const sessionIdRef = useRef(sessionId);
  const providerIdRef = useRef(providerId);
  const reasoningLevelRef = useRef(reasoningLevel);
  const webSearchEnabledRef = useRef(webSearchEnabled);
  const modelConfigRef = useRef(modelConfig);

  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { providerIdRef.current = providerId; }, [providerId]);
  useEffect(() => { reasoningLevelRef.current = reasoningLevel; }, [reasoningLevel]);
  useEffect(() => { webSearchEnabledRef.current = webSearchEnabled; }, [webSearchEnabled]);
  useEffect(() => { modelConfigRef.current = modelConfig; }, [modelConfig]);

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      onErrorRef.current?.('Not connected to chat server');
      return;
    }

    if (!sessionIdRef.current) {
      onErrorRef.current?.('No session selected');
      return;
    }

    setCurrentResponse('');
    setCurrentToolCalls([]);
    setIsStreaming(true);

    const config = modelConfigRef.current;
    wsRef.current.send(JSON.stringify({
      type: WSMessageType.CHAT_REQUEST,
      sessionId: sessionIdRef.current,
      content,
      providerId: providerIdRef.current,
      reasoningLevel: reasoningLevelRef.current ?? 'none',
      webSearchEnabled: webSearchEnabledRef.current ?? false,
      modelConfig: config ? {
        maxTokens: config.maxTokens,
        temperature: config.temperature,
        topP: config.topP,
        topK: config.topK,
        frequencyPenalty: config.frequencyPenalty,
        presencePenalty: config.presencePenalty,
      } : undefined,
    }));
  }, [wsRef]);

  const retryMessage = useCallback((messageId: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      onErrorRef.current?.('Not connected to chat server');
      return;
    }

    if (!sessionIdRef.current) {
      onErrorRef.current?.('No session selected');
      return;
    }

    if (!messageId) {
      onErrorRef.current?.('Message ID is required for retry');
      return;
    }

    setCurrentResponse('');
    setCurrentToolCalls([]);
    setIsStreaming(true);

    const config = modelConfigRef.current;
    wsRef.current.send(JSON.stringify({
      type: WSMessageType.RETRY_MESSAGE,
      sessionId: sessionIdRef.current,
      messageId,
      providerId: providerIdRef.current,
      reasoningLevel: reasoningLevelRef.current ?? 'none',
      webSearchEnabled: webSearchEnabledRef.current ?? false,
      modelConfig: config ? {
        maxTokens: config.maxTokens,
        temperature: config.temperature,
        topP: config.topP,
        topK: config.topK,
        frequencyPenalty: config.frequencyPenalty,
        presencePenalty: config.presencePenalty,
      } : undefined,
    }));
  }, [wsRef]);

  const cancelStream = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: WSMessageType.CANCEL }));
    }
    setIsStreaming(false);
  }, [wsRef]);

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
        wsDebug.log('Tab visible again, pending refetch detected');
        setHasPendingRefetch(true);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  return {
    isConnected,
    isStreaming,
    currentResponse,
    currentToolCalls,
    hasPendingRefetch,
    clearPendingRefetch,
    sendMessage,
    retryMessage,
    cancelStream,
    connect,
    disconnect,
  };
}
