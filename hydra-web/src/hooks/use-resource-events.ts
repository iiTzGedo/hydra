import { useCallback, useEffect, useRef } from 'react';

import { useWebSocket } from '@/hooks/use-websocket';
import { useAuthStore } from '@/stores/auth-store';

/** A real-time event forwarded from the `/events/stream` WebSocket. */
export interface ResourceEvent {
  topic?: string;
  eventType?: string;
  data?: Record<string, unknown>;
}

export interface UseResourceEventsOptions {
  /**
   * Topics to subscribe to, e.g. `['commands:*']` or
   * `['dashboards:board:board_1']`. The subscription set is fixed per
   * connection — when this list changes the socket reconnects and re-subscribes.
   */
  topics: string[];
  /** Called for each forwarded event. */
  onEvent: (event: ResourceEvent) => void;
  /** When false, the socket stays disconnected (default true). */
  enabled?: boolean;
}

/**
 * Subscribe to real-time resource events over the shared `/events/stream`
 * WebSocket. Backs command execution tracking (P2G-T03) and dashboard
 * real-time updates (P2DASH-T029).
 *
 * The server authorizes each topic against the caller's permissions; topics
 * the user cannot see are silently dropped server-side.
 */
export function useResourceEvents({
  topics,
  onEvent,
  enabled = true,
}: UseResourceEventsOptions): { isConnected: boolean } {
  const { isAuthenticated } = useAuthStore();
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  // Stable key so the subscription resets when the topic set changes.
  const topicsKey = topics.join('|');

  const handleMessage = useCallback((data: Record<string, unknown>) => {
    if (data.type === 'event') {
      onEventRef.current({
        topic: data.topic as string | undefined,
        eventType: data.eventType as string | undefined,
        data: data.data as Record<string, unknown> | undefined,
      });
    }
  }, []);

  const { isConnected, connect, disconnect, wsRef } = useWebSocket({
    path: '/events/stream',
    pingType: 'ping',
    onMessage: handleMessage,
  });

  // Open/close the socket; reconnect when topics change or auth flips.
  useEffect(() => {
    if (isAuthenticated && enabled && topics.length > 0) {
      void connect();
      return () => disconnect();
    }
    disconnect();
    return undefined;
    // topicsKey drives reconnection when the subscription set changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, enabled, topicsKey, connect, disconnect]);

  // Send the subscribe message once authenticated (the server expects it as the
  // first message after `authenticated`).
  useEffect(() => {
    const ws = wsRef.current;
    if (isConnected && ws?.readyState === WebSocket.OPEN && topics.length > 0) {
      ws.send(JSON.stringify({ type: 'subscribe', topics }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, topicsKey]);

  return { isConnected };
}
