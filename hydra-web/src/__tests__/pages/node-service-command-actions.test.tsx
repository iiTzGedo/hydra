import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const createCommandMock = vi.fn();
const confirmCommandMock = vi.fn();
const useServiceMock = vi.fn();
const useNodeMock = vi.fn();
const useCommandsMock = vi.fn();
const useCommandCatalogMock = vi.fn();

vi.mock('@/api/commands', async () => {
  const actual = await vi.importActual<typeof import('@/api/commands')>('@/api/commands');
  return {
    ...actual,
    useCreateCommand: () => ({
      mutateAsync: createCommandMock,
      isPending: false,
    }),
    useConfirmCommand: () => ({
      mutateAsync: confirmCommandMock,
      isPending: false,
    }),
    useCommands: (params?: unknown) => useCommandsMock(params),
    useCommandCatalog: (params?: unknown) => useCommandCatalogMock(params),
  };
});

vi.mock('@/api/services', async () => {
  const actual = await vi.importActual<typeof import('@/api/services')>('@/api/services');
  return {
    ...actual,
    useService: () => useServiceMock(),
  };
});

vi.mock('@/api/nodes', async () => {
  const actual = await vi.importActual<typeof import('@/api/nodes')>('@/api/nodes');
  return {
    ...actual,
    useNode: () => useNodeMock(),
    useUpdateNode: () => ({
      mutateAsync: vi.fn(),
      isPending: false,
    }),
    useArchiveNode: () => ({
      mutateAsync: vi.fn(),
      isPending: false,
    }),
  };
});

vi.mock('@/pages/nodes/[nodeId]/tabs', () => ({
  OverviewTab: () => <div>Overview tab</div>,
  ProfileTab: () => <div>Profile tab</div>,
  ServicesTab: () => <div>Services tab</div>,
  TopologyTab: () => <div>Topology tab</div>,
  NetworksTab: () => <div>Networks tab</div>,
  GroupsTab: () => <div>Groups tab</div>,
}));

import NodeDetailPage from '@/pages/nodes/[nodeId]';
import ServiceDetailPage from '@/pages/services/[serviceId]';
import { renderWithRoute } from '../page-test-utils';

describe('Node and Service Command Actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createCommandMock.mockResolvedValue({ commandId: 'cmd-queued-001' });
    confirmCommandMock.mockResolvedValue({ commandId: 'cmd-queued-001', status: 'queued' });
    useCommandsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });
    useCommandCatalogMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });
    useServiceMock.mockReturnValue({
      data: {
        id: 'svc-nginx-a1b2',
        serviceId: 'svc-nginx-a1b2',
        nodeId: 'server-01',
        displayName: 'NGINX Web Server',
        name: 'nginx',
        runtime: 'systemd',
        status: 'running',
        health: { status: 'healthy', lastCheck: '2026-03-23T10:00:00Z' },
        lastSeen: '2026-03-23T10:00:00Z',
        firstSeen: '2026-03-20T10:00:00Z',
        tags: ['production'],
        exposure: { ports: [], endpoints: [] },
      },
      isLoading: false,
      error: null,
    });
    useNodeMock.mockReturnValue({
      data: {
        id: 'server-01',
        nodeId: 'server-01',
        displayName: 'Server 01',
        class: 'compute',
        type: 'physical',
        kind: null,
        status: 'active',
        description: null,
        tags: [],
        parentNodeId: null,
      },
      isLoading: false,
      error: null,
    });
    vi.stubGlobal('confirm', vi.fn(() => true));
  });

  it('queues service commands using only the stable service target contract', async () => {
    const user = userEvent.setup();

    renderWithRoute(<ServiceDetailPage />, {
      path: '/services/:serviceId',
      route: '/services/svc-nginx-a1b2',
    });

    await user.click(screen.getByRole('button', { name: 'Restart' }));

    await waitFor(() => expect(createCommandMock).toHaveBeenCalledTimes(1));

    const payload = createCommandMock.mock.calls[0][0];
    expect(payload.registryId).toBe('reg::service::restart');
    expect(payload.target).toEqual({
      nodeId: 'server-01',
      serviceId: 'svc-nginx-a1b2',
    });
    expect(payload).not.toHaveProperty('parameters');
    expect(useCommandsMock).toHaveBeenCalledWith({
      nodeId: 'server-01',
      serviceId: 'svc-nginx-a1b2',
    });
  });

  it('queues node actions from the node detail entry point', async () => {
    const user = userEvent.setup();

    renderWithRoute(<NodeDetailPage />, {
      path: '/nodes/:nodeId',
      route: '/nodes/server-01',
    });

    await user.click(screen.getByRole('tab', { name: 'Controls' }));
    await user.click(screen.getByRole('button', { name: 'Reboot' }));

    await waitFor(() => expect(createCommandMock).toHaveBeenCalledTimes(1));

    expect(createCommandMock).toHaveBeenCalledWith({
      registryId: 'reg::node::reboot',
      target: {
        nodeId: 'server-01',
      },
    });
  });

  it('requires a hostname before submitting the set-hostname control', async () => {
    const user = userEvent.setup();

    renderWithRoute(<NodeDetailPage />, {
      path: '/nodes/:nodeId',
      route: '/nodes/server-01',
    });

    await user.click(screen.getByRole('tab', { name: 'Controls' }));
    await user.click(screen.getByRole('button', { name: 'Set Hostname' }));
    await user.click(screen.getByRole('button', { name: 'Send Command' }));

    expect(await screen.findByText('Hostname is required.')).toBeInTheDocument();
    expect(createCommandMock).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText('Hostname'), 'hydra-node-01');
    await user.click(screen.getByRole('button', { name: 'Send Command' }));

    await waitFor(() => expect(createCommandMock).toHaveBeenCalledTimes(1));
    expect(createCommandMock).toHaveBeenCalledWith({
      registryId: 'reg::node::set-hostname',
      target: {
        nodeId: 'server-01',
      },
      parameters: {
        hostname: 'hydra-node-01',
      },
    });
  });

  it('requires a CIDR subnet before submitting probe-network', async () => {
    const user = userEvent.setup();

    renderWithRoute(<NodeDetailPage />, {
      path: '/nodes/:nodeId',
      route: '/nodes/server-01',
    });

    await user.click(screen.getByRole('tab', { name: 'Controls' }));
    await user.click(screen.getByRole('button', { name: 'Probe Network' }));
    await user.click(screen.getByRole('button', { name: 'Send Command' }));

    expect(
      await screen.findByText('Subnet is required.')
    ).toBeInTheDocument();
    expect(createCommandMock).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText('Subnet'), '192.168.1.0/24');
    await user.click(screen.getByRole('button', { name: 'Send Command' }));

    await waitFor(() => expect(createCommandMock).toHaveBeenCalledTimes(1));
    expect(createCommandMock).toHaveBeenCalledWith({
      registryId: 'reg::agent::probe-network',
      target: {
        nodeId: 'server-01',
      },
      parameters: {
        subnet: '192.168.1.0/24',
      },
    });
  });
});
