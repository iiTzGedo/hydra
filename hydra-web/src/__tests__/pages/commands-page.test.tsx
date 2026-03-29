import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const createCommandMock = vi.fn();
const useCommandCatalogMock = vi.fn();
const useCommandQueueMock = vi.fn();
const useCommandsMock = vi.fn();
const useCancelCommandMock = vi.fn();

vi.mock('@/api/commands', async () => {
  const actual = await vi.importActual<typeof import('@/api/commands')>('@/api/commands');
  return {
    ...actual,
    useCommandCatalog: () => useCommandCatalogMock(),
    useCommandQueue: () => useCommandQueueMock(),
    useCommands: () => useCommandsMock(),
    useCancelCommand: () => useCancelCommandMock(),
    useCreateCommand: () => ({
      mutateAsync: createCommandMock,
      isPending: false,
    }),
  };
});

import CommandsPage from '@/pages/commands';
import { renderWithRoute } from '../page-test-utils';

describe('Commands Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createCommandMock.mockResolvedValue({ commandId: 'cmd-new-001' });
    useCommandCatalogMock.mockReturnValue({
      data: [
        {
          registryId: 'reg::service::restart',
          category: 'service',
          action: 'restart',
          displayName: 'Restart Service',
          description: 'Restart a service',
          minimumRole: 'operator',
          requiresConfirmation: false,
          timeout: 60,
          deliveryMode: 'poll_only',
          builtIn: true,
          deprecated: false,
        },
      ],
      isLoading: false,
      error: null,
    });
    useCommandQueueMock.mockReturnValue({
      data: {
        queue: [],
        stats: {
          totalQueued: 0,
          totalExecuting: 0,
          oldestQueuedAt: null,
        },
      },
      isLoading: false,
      error: null,
    });
    useCommandsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });
    useCancelCommandMock.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    });
  });

  it('opens the execute dialog from the catalog and submits the command', async () => {
    const user = userEvent.setup();

    renderWithRoute(<CommandsPage />, {
      path: '/commands',
      route: '/commands',
    });

    await user.click(screen.getByText('Restart Service'));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    const nodeIdInput = screen.getByLabelText('Node ID *');
    await user.clear(nodeIdInput);
    await user.type(nodeIdInput, 'server-01');
    await user.type(screen.getByLabelText('Service ID'), 'svc-nginx-a1b2');
    await user.click(screen.getByRole('button', { name: 'Execute' }));

    await waitFor(() => expect(createCommandMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    expect(createCommandMock).toHaveBeenCalledWith({
      registryId: 'reg::service::restart',
      target: {
        nodeId: 'server-01',
        serviceId: 'svc-nginx-a1b2',
      },
      parameters: undefined,
      timeoutSeconds: 60,
    });
  });
});
