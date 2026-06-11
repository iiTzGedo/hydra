/**
 * Tests for useResourceEvents — subscribes to the shared /events/stream socket
 * and forwards `event` messages to the consumer.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

// Capture the options passed to useWebSocket so we can drive onMessage and
// assert subscribe behaviour.
type WsOptions = {
  path: string;
  onMessage?: (data: Record<string, unknown>) => void;
};
let capturedOptions: WsOptions | null = null;
const connectMock = vi.fn(() => Promise.resolve());
const disconnectMock = vi.fn();
const fakeWs = { readyState: 1 /* OPEN */, send: vi.fn() };

vi.mock('@/hooks/use-websocket', () => ({
  useWebSocket: (options: WsOptions) => {
    capturedOptions = options;
    return {
      isConnected: true,
      connect: connectMock,
      disconnect: disconnectMock,
      wsRef: { current: fakeWs },
    };
  },
}));

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}));

import { useResourceEvents } from '@/hooks/use-resource-events';

describe('useResourceEvents', () => {
  beforeEach(() => {
    capturedOptions = null;
    connectMock.mockClear();
    disconnectMock.mockClear();
    fakeWs.send.mockClear();
  });

  it('connects and sends a subscribe message with the requested topics', () => {
    renderHook(() =>
      useResourceEvents({ topics: ['commands:*'], onEvent: vi.fn() })
    );

    expect(connectMock).toHaveBeenCalled();
    expect(fakeWs.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'subscribe', topics: ['commands:*'] })
    );
  });

  it('forwards `event` messages to onEvent and ignores others', () => {
    const onEvent = vi.fn();
    renderHook(() =>
      useResourceEvents({ topics: ['command:cmd-1'], onEvent })
    );

    capturedOptions?.onMessage?.({
      type: 'event',
      topic: 'command:cmd-1',
      eventType: 'command.completed',
      data: { commandId: 'cmd-1', status: 'completed' },
    });
    capturedOptions?.onMessage?.({ type: 'subscribed', topics: ['command:cmd-1'] });

    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({
      topic: 'command:cmd-1',
      eventType: 'command.completed',
      data: { commandId: 'cmd-1', status: 'completed' },
    });
  });

  it('does not connect when there are no topics', () => {
    renderHook(() => useResourceEvents({ topics: [], onEvent: vi.fn() }));
    expect(connectMock).not.toHaveBeenCalled();
    expect(fakeWs.send).not.toHaveBeenCalled();
  });
});
