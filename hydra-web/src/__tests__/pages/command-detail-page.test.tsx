import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const cancelCommandMock = vi.fn();
const useCommandMock = vi.fn();

vi.mock('@/api/commands', async () => {
  const actual = await vi.importActual<typeof import('@/api/commands')>('@/api/commands');
  return {
    ...actual,
    useCommand: () => useCommandMock(),
    useCancelCommand: () => ({
      mutateAsync: cancelCommandMock,
      isPending: false,
    }),
  };
});

import CommandDetailPage from '@/pages/commands/[commandId]';
import { renderWithRoute } from '../page-test-utils';

describe('Command Detail Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cancelCommandMock.mockResolvedValue({ commandId: 'cmd-abc123', status: 'cancelled' });
    useCommandMock.mockReturnValue({
      data: {
        commandId: 'cmd-abc123',
        registryId: 'reg::agent::probe-network',
        type: 'agent',
        action: 'probe-network',
        target: {
          nodeId: 'server-01',
          serviceId: null,
        },
        parameters: {
          subnet: '192.168.1.0/30',
        },
        status: 'queued',
        executionMethod: 'agent-poll',
        result: {
          success: true,
          output: 'Probe completed',
          exitCode: 0,
          error: null,
        },
        error: null,
        timeoutSeconds: 120,
        retryCount: 0,
        queuePosition: 1,
        createdAt: '2026-03-23T10:00:00Z',
        queuedAt: '2026-03-23T10:00:01Z',
        startedAt: null,
        completedAt: null,
        cancelledAt: null,
        cancelledBy: null,
      },
      isLoading: false,
      error: null,
    });
  });

  it('shows command details and allows cancelling queued commands', async () => {
    const user = userEvent.setup();

    renderWithRoute(<CommandDetailPage />, {
      path: '/commands/:commandId',
      route: '/commands/cmd-abc123',
    });

    expect(screen.getByText('Command cmd-abc123')).toBeInTheDocument();
    expect(screen.getByText('Probe completed')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Cancel Command' }));

    await waitFor(() => expect(cancelCommandMock).toHaveBeenCalledWith('cmd-abc123'));
  });
});
