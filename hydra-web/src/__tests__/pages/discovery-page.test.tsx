import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const useDiscoveryScansMock = vi.fn();
const useDiscoveryScanMock = vi.fn();
const useDiscoveryDevicesMock = vi.fn();
const useDiscoveryDeviceMock = vi.fn();
const startDiscoveryScanMock = vi.fn();
const approveDiscoveryMock = vi.fn();
const registerDiscoveryMock = vi.fn();
const rejectDiscoveryMock = vi.fn();
const dismissDiscoveryMock = vi.fn();
const useNodesMock = vi.fn();
let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

vi.mock('@/api/discovery', () => ({
  useDiscoveryScans: () => useDiscoveryScansMock(),
  useDiscoveryScan: (scanId: string | null | undefined) => useDiscoveryScanMock(scanId),
  useDiscoveryDevices: () => useDiscoveryDevicesMock(),
  useDiscoveryDevice: (discoveryId: string | null | undefined) => useDiscoveryDeviceMock(discoveryId),
  useStartDiscoveryScan: () => ({
    mutateAsync: startDiscoveryScanMock,
    isPending: false,
  }),
  useApproveDiscovery: () => ({
    mutateAsync: approveDiscoveryMock,
    isPending: false,
  }),
  useRegisterDiscovery: () => ({
    mutateAsync: registerDiscoveryMock,
    isPending: false,
  }),
  useRejectDiscovery: () => ({
    mutateAsync: rejectDiscoveryMock,
    isPending: false,
  }),
  useDismissDiscovery: () => ({
    mutateAsync: dismissDiscoveryMock,
    isPending: false,
  }),
  useInstallations: () => ({ data: undefined, isLoading: false }),
  useInstallation: () => ({ data: undefined, isLoading: false }),
  useStartInstallation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCancelInstallation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRetryInstallation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock('@/api/nodes', () => ({
  useNodes: () => useNodesMock(),
}));

vi.mock('@/api/networks', () => ({
  useNetworks: () => ({
    data: { items: [], total: 0, limit: 200, offset: 0 },
    isLoading: false,
    error: null,
  }),
}));

import DiscoveryPage from '@/views/discovery';
import { ROUTES } from '@/lib/constants';
import { renderWithRoute } from '../page-test-utils';

const scanSummary = {
  scanId: 'scan-001',
  status: 'running',
  targetCount: 1,
  resultCount: 2,
  progress: {
    phase: 'running',
    hostsTotal: 254,
    hostsScanned: 128,
    hostsAlive: 8,
    percentComplete: 50,
  },
  startedAt: '2026-04-06T08:00:00Z',
  createdAt: '2026-04-06T07:58:00Z',
};

const scanDetail = {
  ...scanSummary,
  targets: [{ subnet: '192.168.1.0/24', delegateToNodeId: 'node-scanner-01' }],
  options: {
    methods: ['arp', 'tcp_port', 'mdns', 'ssdp', 'snmp'],
    portTier: 'tier1',
    timeoutSeconds: 60,
    includeIoTProtocols: false,
  },
  delegateToNodeId: 'node-scanner-01',
  summary: {
    hostsScanned: 254,
    hostsAlive: 8,
    newDiscoveries: 2,
    returningDevices: 1,
    errors: [],
  },
  delegation: {
    delegatedTo: 'node-scanner-01',
    commandId: 'cmd-001',
    executionMethod: 'agent-poll',
    commandStatus: 'executing',
    notes: ['Delegated network scan queued for agent execution.'],
  },
  error: null,
  completedAt: null,
  updatedAt: '2026-04-06T08:05:00Z',
};

const discoveryDevice = {
  discoveryId: 'disc-001',
  identity: {
    primaryMac: 'aa:bb:cc:dd:ee:ff',
    currentIp: '192.168.1.44',
    hostname: 'edge-switch',
  },
  networkId: 'net-lan',
  probe: {
    scannedBy: 'node-scanner-01',
    method: 'arp',
    scannedAt: '2026-04-06T08:03:00Z',
    sourceSubnet: '192.168.1.0/24',
    delegatedByScanId: 'scan-001',
    scanMethods: ['arp', 'tcp_port'],
  },
  status: 'pending',
  firstSeen: '2026-04-06T08:03:00Z',
  lastSeen: '2026-04-06T08:04:00Z',
  seenCount: 1,
  openPorts: [22, 443],
  protocols: ['ssh', 'https'],
  rawEvidence: {
    vendor: 'Cisco',
    macOui: 'AABBCC',
    dnsNames: ['edge-switch.local'],
    banners: { '443': 'nginx' },
    protocolDetails: { ssh: { versions: ['OpenSSH_9.7'] } },
    signals: ['ssh', 'https'],
  },
  fingerprint: {
    openPorts: [22, 443],
    serviceHints: ['ssh', 'https'],
    protocols: ['ssh', 'https'],
    osHint: 'linux',
    vendor: 'Cisco',
    macOui: 'AABBCC',
    deviceFamily: 'switch',
  },
  classification: {
    suggestedClass: 'networking',
    suggestedType: 'switch',
    confidence: 0.92,
    signals: ['ssh', 'https', 'vendor:cisco'],
    explanation: 'Ports and vendor evidence indicate a managed switch.',
    eligibleForRegistration: true,
  },
  dismissedAt: null,
  dismissedBy: null,
  dismissReason: null,
  approvedAt: null,
  approvedBy: null,
  rejectedAt: null,
  rejectedBy: null,
  rejectReason: null,
  matchedNodeId: null,
};

function setupPage() {
  useNodesMock.mockReturnValue({
    data: {
      items: [
        {
          nodeId: 'node-scanner-01',
          displayName: 'Scanner Node',
          class: 'compute',
          type: 'physical',
          status: 'active',
          tags: [],
          agentTier: 'max',
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    },
  });
  useDiscoveryScansMock.mockReturnValue({
    data: {
      items: [scanSummary],
      total: 1,
      limit: 12,
      offset: 0,
    },
    isLoading: false,
  });
  useDiscoveryScanMock.mockReturnValue({ data: scanDetail });
  useDiscoveryDevicesMock.mockReturnValue({
    data: {
      items: [discoveryDevice],
      total: 1,
      limit: 25,
      offset: 0,
    },
    isLoading: false,
  });
  useDiscoveryDeviceMock.mockReturnValue({ data: discoveryDevice });
}

describe('Discovery Page', () => {
  beforeAll(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation((message) => {
      const text = typeof message === 'string' ? message : String(message);
      if (text.includes('not wrapped in act')) {
        return;
      }
      return;
    });
  });

  afterAll(() => {
    consoleErrorSpy.mockRestore();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    startDiscoveryScanMock.mockResolvedValue({
      ...scanDetail,
      scanId: 'scan-new',
    });
    approveDiscoveryMock.mockResolvedValue({
      discoveryId: 'disc-001',
      status: 'approved',
      matchedNodeId: null,
    });
    registerDiscoveryMock.mockResolvedValue({
      nodeId: 'edge-switch',
      registeredBy: 'user-001',
      registeredAt: '2026-04-06T08:05:00Z',
      status: 'registered',
      fromDiscovery: 'disc-001',
    });
    rejectDiscoveryMock.mockResolvedValue({
      discoveryId: 'disc-001',
      status: 'rejected',
      matchedNodeId: null,
    });
    dismissDiscoveryMock.mockResolvedValue({
      ...discoveryDevice,
      status: 'dismissed',
    });
    setupPage();
  });

  it('queues a delegated scan from the dialog', async () => {
    const user = userEvent.setup();
    renderWithRoute(<DiscoveryPage />, {
      path: ROUTES.DISCOVERY,
      route: ROUTES.DISCOVERY,
    });

    await user.click(screen.getByRole('button', { name: /start scan/i }));

    await user.click(screen.getByRole('button', { name: /agent delegated/i }));

    // Target subnet — combobox with free text entry
    const subnetCombobox = screen.getByRole('combobox', { name: /target subnet/i });
    await user.click(subnetCombobox);
    const subnetInput = screen.getByPlaceholderText(/search/i);
    await user.type(subnetInput, '192.168.50.0/24');
    await user.click(await screen.findByText('192.168.50.0/24'));

    // Delegated scanner — select dropdown
    await user.click(screen.getByRole('combobox', { name: /delegated scanner/i }));
    await user.click(await screen.findByText(/scanner node/i));
    await user.click(screen.getByRole('button', { name: /queue scan/i }));

    await waitFor(() => expect(startDiscoveryScanMock).toHaveBeenCalledTimes(1));
    expect(startDiscoveryScanMock).toHaveBeenCalledWith({
      targets: [
        {
          subnet: '192.168.50.0/24',
          delegateToNodeId: 'node-scanner-01',
        },
      ],
      delegateToNodeId: 'node-scanner-01',
      options: {
        methods: ['arp', 'tcp_port', 'mdns', 'ssdp', 'snmp'],
        portTier: 'tier1',
        timeoutSeconds: 60,
        includeIoTProtocols: false,
      },
    });
  });

  it('registers a pending discovery as a node', async () => {
    const user = userEvent.setup();
    renderWithRoute(<DiscoveryPage />, {
      path: ROUTES.DISCOVERY,
      route: ROUTES.DISCOVERY,
    });

    await user.click(screen.getByRole('tab', { name: /discoveries/i }));
    expect((await screen.findAllByText('edge-switch')).length).toBeGreaterThan(0);

    await user.type(screen.getByLabelText(/tags/i), 'edge, switching');
    await user.click(screen.getByRole('button', { name: /register node/i }));

    await waitFor(() => expect(registerDiscoveryMock).toHaveBeenCalledTimes(1));
    expect(registerDiscoveryMock).toHaveBeenCalledWith({
      nodeId: 'edge-switch',
      class: undefined,
      tags: ['edge', 'switching'],
      overrideClassification: false,
    });
  });
});
