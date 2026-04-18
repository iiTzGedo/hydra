/**
 * Subscribes to live scan progress events for API-direct scans.
 *
 * Per spec §2.7.2 the WebSocket endpoint is exposed only for scans the
 * API runs itself. Agent-delegated scans (`delegateToNodeId` set) keep
 * polling — the API has no event stream for those.
 *
 * On every `progress`, `device_found`, `scan_complete` and `scan_failed`
 * message we invalidate the scan and discoveries query keys so the
 * existing TanStack Query polling layer renders the latest data.
 *
 * Gating is strict on purpose: we only open the socket when we have
 * fully-loaded scan details confirming (a) the scan is API-direct and
 * (b) the scan is still running. Anything else keeps the hook inert
 * so we don't blast `console.error` through the shared WS debug helper
 * — transient connection errors fire the Next.js dev overlay.
 */

import { useCallback, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { useWebSocket } from '@/hooks/use-websocket';
import { useAuthStore } from '@/stores/auth-store';
import { queryKeys } from '@/lib/query-client';

export interface UseDiscoveryScanStreamOptions {
  scanId: string | null | undefined;
  /**
   * Node ID the scan was delegated to. ``null`` means API-direct,
   * ``undefined`` means the scan document hasn't loaded yet. The hook
   * treats ``undefined`` as "unknown — stay inert" so it never connects
   * before the scan's execution mode is confirmed.
   */
  delegateToNodeId: string | null | undefined;
  /** Current scan status — hook stays inert until this is defined. */
  status?: string | null;
}

export interface UseDiscoveryScanStreamReturn {
  isConnected: boolean;
  /** True when the scan qualifies for WS streaming (API-direct + active). */
  isStreaming: boolean;
}

const TERMINAL_STATES = new Set(['completed', 'failed', 'cancelled']);
// Path used when the hook stays inert. Never connected — the effect gate
// below makes sure `connect()` only fires when there's a real scanId.
const INACTIVE_PATH = '/discovery/scan/__inactive__/stream';

export function useDiscoveryScanStream(
  options: UseDiscoveryScanStreamOptions,
): UseDiscoveryScanStreamReturn {
  const { scanId, delegateToNodeId, status } = options;
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Only flip `isStreaming` to true once we have authoritative scan data.
  // Before that `delegateToNodeId` and `status` are both `undefined` and
  // we deliberately keep the socket closed.
  const hasScanDetails = delegateToNodeId !== undefined && status !== undefined;
  const isApiDirect = Boolean(scanId) && delegateToNodeId === null;
  const isActive = status !== null && status !== undefined
    && !TERMINAL_STATES.has(status);
  const isStreaming = isAuthenticated
    && hasScanDetails
    && isApiDirect
    && isActive;

  const handleMessage = useCallback(
    (data: Record<string, unknown>) => {
      if (!scanId) return;
      const messageType = data.type;
      if (
        messageType === 'progress' ||
        messageType === 'device_found' ||
        messageType === 'scan_complete' ||
        messageType === 'scan_failed'
      ) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.discovery.scan(scanId),
        });
      }
      if (messageType === 'device_found' || messageType === 'scan_complete') {
        queryClient.invalidateQueries({ queryKey: queryKeys.discovery.devices() });
      }
    },
    [queryClient, scanId],
  );

  // Swallow connection errors. Scan streaming is a "best-effort" enhancement
  // on top of the 3s polling in `useDiscoveryScan`, so an unreachable
  // WebSocket should not surface as a dev overlay — polling continues.
  const handleError = useCallback(() => {
    /* intentionally empty */
  }, []);

  const { isConnected, connect, disconnect } = useWebSocket({
    path: isStreaming && scanId
      ? `/discovery/scan/${scanId}/stream`
      : INACTIVE_PATH,
    onMessage: handleMessage,
    onError: handleError,
  });

  useEffect(() => {
    if (isStreaming) {
      void connect();
      return () => {
        disconnect();
      };
    }
    disconnect();
    return undefined;
  }, [isStreaming, connect, disconnect]);

  return { isConnected, isStreaming };
}
