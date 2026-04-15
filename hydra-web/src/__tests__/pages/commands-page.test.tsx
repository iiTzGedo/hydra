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

vi.mock('@/api/nodes', () => ({
  useNodes: () => ({
    data: {
      items: [
        { nodeId: 'server-01', displayName: 'Server 01', class: 'compute', type: 'physical', status: 'active', tags: [] },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    },
    isLoading: false,
    error: null,
  }),
}));

vi.mock('@/api/services', () => ({
  useServices: () => ({
    data: {
      items: [
        { serviceId: 'svc-nginx-a1b2', name: 'nginx', displayName: 'Nginx', nodeId: 'server-01', runtime: 'docker', status: 'running', lastSeen: '2026-01-01' },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    },
    isLoading: false,
    error: null,
  }),
}));

vi.mock('@/api/workflows', () => ({
  useWorkflows: () => ({
    data: { items: [] },
    isLoading: false,
    error: null,
  }),
  useExecuteWorkflow: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateWorkflow: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useDeleteWorkflow: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

import CommandsPage from '@/views/commands';
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

    // Select node from combobox
    const comboboxes = screen.getAllByRole('combobox');
    await user.click(comboboxes[0]); // Node combobox
    await user.click(await screen.findByText('Server 01'));

    // Select service from combobox
    await user.click(comboboxes[1]); // Service combobox
    await user.click(await screen.findByText('Nginx'));

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
