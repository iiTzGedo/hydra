import { http, HttpResponse } from 'msw';
import type { ChatMessageResponse, ChatToolCall } from '@/api/chat';
import type { MCPServerResponse, MCPServerStatus } from '@/api/mcp';
import type { KioskTokenSummary } from '@/types/dashboard';
import { mockState } from './mock-state';

// Must match NEXT_PUBLIC_API_URL set in vitest.config.ts test env block.
// Using 'localhost' here would cause MSW to miss all requests since axios sends them to
// 127.0.0.1, silently falling through to the real server instead of the mock.
const BASE_URL = 'http://127.0.0.1:8080/api/v1';

// ── Wave 4 in-memory state (resets via resetWave4MockState) ───────────────

/** Per-board kiosk token lists (Wave 4). */
const kioskTokensByBoard = new Map<string, KioskTokenSummary[]>();

/** Per-user entity-panel overrides keyed as "userId:entityType" (Wave 4). */
const panelOverrides = new Map<string, Record<string, unknown>>();

/** Resets Wave 4 mock state — call this in beforeEach alongside resetMockState(). */
export function resetWave4MockState() {
  kioskTokensByBoard.clear();
  panelOverrides.clear();
}

const mockNodes = [
  {
    nodeId: 'proxmox-01',
    displayName: 'Proxmox Server 01',
    class: 'compute',
    type: 'bare-metal',
    kind: 'host',
    status: 'active',
    agent: {
      tier: 'max',
      serverConfig: {
        enabled: true,
        advertiseAddress: '192.168.1.10',
        port: 9100,
        tlsEnabled: true,
      },
      serverStatus: { isReachable: true, failedDirectAttempts: 0 },
    },
    tags: ['production', 'hypervisor'],
    ipAddresses: ['192.168.1.10'],
    macAddresses: ['00:11:22:33:44:55'],
    hostname: 'proxmox-01.local',
    osInfo: {
      family: 'Linux',
      name: 'Proxmox VE',
      version: '8.0',
    },
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-15T12:00:00Z',
  },
  {
    nodeId: 'opnsense-gw',
    displayName: 'OPNsense Gateway',
    class: 'networking',
    type: 'router',
    kind: 'appliance',
    status: 'active',
    agent: { tier: 'normal' },
    tags: ['gateway', 'firewall'],
    ipAddresses: ['192.168.1.1'],
    macAddresses: ['AA:BB:CC:DD:EE:FF'],
    hostname: 'opnsense.local',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-10T10:00:00Z',
  },
];

const mockNodeDetail = {
  ...mockNodes[0],
  metadata: {
    location: 'Rack 1',
    environment: 'production',
  },
  hardwareInfo: {
    cpu: {
      model: 'Intel Xeon',
      cores: 16,
      threads: 32,
    },
    memory: {
      total: 65536,
      available: 32768,
    },
  },
};

const mockServices = [
  {
    serviceId: 'svc-nginx-a1b2',
    name: 'nginx',
    displayName: 'NGINX Web Server',
    runtime: 'systemd',
    status: 'running',
    nodeId: 'proxmox-01',
    ports: [80, 443],
    tags: ['web', 'proxy'],
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-15T12:00:00Z',
  },
  {
    serviceId: 'svc-mongodb-c3d4',
    name: 'mongodb',
    displayName: 'MongoDB Database',
    runtime: 'systemd',
    status: 'running',
    nodeId: 'proxmox-01',
    ports: [27017],
    tags: ['database'],
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-15T12:00:00Z',
  },
];

const mockServiceDetail = {
  ...mockServices[0],
  config: {
    autoStart: true,
    restartPolicy: 'always',
  },
  environment: {
    NODE_ENV: 'production',
  },
};

const mockNetworks = [
  {
    networkId: 'net-lan-192-168-0',
    name: 'LAN Network',
    cidr: '192.168.1.0/24',
    type: 'lan',
    vlanId: 1,
    gateway: '192.168.1.1',
    tags: ['primary'],
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-10T10:00:00Z',
  },
  {
    networkId: 'net-iot-10-0-1',
    name: 'IoT Network',
    cidr: '10.0.1.0/24',
    type: 'isolated',
    vlanId: 10,
    gateway: '10.0.1.1',
    tags: ['iot', 'isolated'],
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-05T08:00:00Z',
  },
];

const mockNetworkDetail = {
  ...mockNetworks[0],
  dhcpRange: {
    start: '192.168.1.100',
    end: '192.168.1.200',
  },
  dnsServers: ['1.1.1.1', '8.8.8.8'],
};

const mockGroups = [
  {
    groupId: 'grp-production',
    name: 'Production Servers',
    description: 'All production infrastructure',
    types: ['node'],
    tags: ['environment:production'],
    memberCount: {
      nodes: 1,
      services: 0,
      lastComputed: '2026-03-09T12:00:00Z',
    },
  },
  {
    groupId: 'grp-web-services',
    name: 'Web Services',
    description: 'All web-related services',
    types: ['service'],
    tags: ['category:web'],
    memberCount: {
      nodes: 0,
      services: 1,
      lastComputed: '2026-03-09T12:00:00Z',
    },
  },
];

const mockGroupDetail = {
  ...mockGroups[0],
  selectors: {
    tags: {
      isAny: ['production'],
    },
  },
  parentGroupIds: [],
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-10T10:00:00Z',
};

const mockUser = {
  userId: 'user-123',
  username: 'system_admin',
  email: 'admin@example.com',
  role: 'admin' as const,
  permissions: ['*:*'],
  temporaryRoles: [],
};

const mockAccessToken = 'mock-access-token-abc123';
const mockRefreshToken = 'mock-refresh-token-xyz789';

const mockPendingUsers = [
  {
    userId: 'pending-user-1',
    username: 'pending_user',
    email: 'pending@example.com',
    role: 'viewer' as const,
    requestedAt: '2024-01-15T10:00:00Z',
  },
];

const mockApiKeys = [
  {
    keyId: 'key-123',
    name: 'Test API Key',
    type: 'user',
    ownerId: 'user-123',
    permissions: ['nodes:read', 'services:read'],
    createdAt: '2024-01-01T00:00:00Z',
    lastUsedAt: '2024-01-15T12:00:00Z',
    usageCount: 42,
  },
];

function apiResponse<T>(data: T, meta?: Record<string, unknown>) {
  return { data, ...(meta ? { meta } : {}) };
}

function errorResponse(code: string, message: string, status: number) {
  return HttpResponse.json(
    {
      error: {
        code,
        message,
      },
    },
    { status }
  );
}

function paginate<T>(items: T[], request: Request, defaultLimit = 20) {
  const url = new URL(request.url);
  const limit = Number(url.searchParams.get('limit') || defaultLimit);
  const offset = Number(url.searchParams.get('offset') || 0);
  return {
    items: items.slice(offset, offset + limit),
    total: items.length,
    limit,
    offset,
  };
}

function nextId(prefix: string, currentLength: number) {
  return `${prefix}-${String(currentLength + 1).padStart(3, '0')}`;
}

function sanitizeId(input: string) {
  return input.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

function toDashboardSummary(board: (typeof mockState.dashboards)[number]) {
  return {
    boardId: board.boardId,
    name: board.name,
    description: board.description,
    icon: board.icon,
    ownerId: board.ownerId,
    ownerType: (board as { ownerType?: string }).ownerType ?? 'user',
    boardType: board.boardType,
    visibility: board.visibility,
    widgetCount: board.widgets.length,
    tags: board.tags,
    isHome: board.isHome,
    version: board.version,
    createdAt: board.createdAt,
    updatedAt: board.updatedAt,
    layoutMode: board.layoutMode,
    scope: board.scope,
    entityTypeFilter: board.entityTypeFilter,
    isSystemDefault: board.isSystemDefault,
  };
}

function stripGraphIfNeeded(topology: (typeof mockState.topologies)[number], includeGraph: boolean) {
  if (includeGraph) {
    return topology;
  }
  const { graph: _graph, ...rest } = topology;
  return rest;
}

function getLatestTopology(mode: string) {
  return [...mockState.topologies]
    .filter((topology) => topology.mode === mode)
    .sort((a, b) => b.version - a.version)[0];
}

function buildProfileDiffKey(nodeId: string, fromVersion?: string | null, toVersion?: string | null) {
  return `${nodeId}:${fromVersion || ''}:${toVersion || ''}`;
}

export const handlers = [
  http.post(`${BASE_URL}/auth/session/login`, async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string };

    if (body.username === 'system_admin' && body.password === 'system12345') {
      return HttpResponse.json({
        user: mockUser,
        expiresIn: 3600,
      });
    }

    return errorResponse('INVALID_CREDENTIALS', 'Invalid username or password', 401);
  }),

  http.post(`${BASE_URL}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string };

    if (body.username === 'system_admin' && body.password === 'system12345') {
      return HttpResponse.json({
        accessToken: mockAccessToken,
        refreshToken: mockRefreshToken,
        expiresIn: 3600,
        tokenType: 'Bearer',
        user: mockUser,
      });
    }

    return errorResponse('INVALID_CREDENTIALS', 'Invalid username or password', 401);
  }),

  http.post(`${BASE_URL}/auth/register`, async ({ request }) => {
    const body = (await request.json()) as {
      username: string;
      email: string;
      password: string;
      role?: string;
      registrationToken?: string;
    };

    if (body.username === 'existing_user') {
      return errorResponse('USER_ALREADY_EXISTS', 'Username already exists', 409);
    }

    return HttpResponse.json({
      userId: 'new-user-123',
      username: body.username,
      email: body.email,
      role: body.role || 'viewer',
      status: 'active',
      createdAt: new Date().toISOString(),
    });
  }),

  http.get(`${BASE_URL}/auth/me`, () =>
    HttpResponse.json({
      type: 'user',
      userId: mockUser.userId,
      username: mockUser.username,
      email: mockUser.email,
      role: mockUser.role,
      permissions: mockUser.permissions,
    })
  ),

  http.post(`${BASE_URL}/auth/session/refresh`, () =>
    HttpResponse.json({
      user: mockUser,
      expiresIn: 3600,
    })
  ),

  http.post(`${BASE_URL}/auth/refresh`, async ({ request }) => {
    const body = (await request.json()) as { refreshToken: string };

    if (body.refreshToken === mockRefreshToken) {
      return HttpResponse.json({
        accessToken: 'new-access-token-def456',
        refreshToken: 'new-refresh-token-def456',
        expiresIn: 3600,
        tokenType: 'Bearer',
      });
    }

    return errorResponse('INVALID_REFRESH_TOKEN', 'Invalid or expired refresh token', 401);
  }),

  http.post(`${BASE_URL}/auth/logout`, () =>
    HttpResponse.json({
      message: 'Successfully logged out',
    })
  ),

  http.post(`${BASE_URL}/auth/session/logout`, () =>
    HttpResponse.json({
      loggedOut: true,
    })
  ),

  http.post(`${BASE_URL}/auth/password/forgot`, async ({ request }) => {
    const body = (await request.json()) as { email: string };
    return HttpResponse.json({
      message: `Password reset email sent to ${body.email}`,
    });
  }),

  http.post(`${BASE_URL}/auth/password/reset`, async ({ request }) => {
    const body = (await request.json()) as { token: string; newPassword: string };

    if (body.token === 'valid-reset-token') {
      return HttpResponse.json({
        message: 'Password successfully reset',
      });
    }

    return errorResponse('INVALID_RESET_TOKEN', 'Invalid or expired reset token', 400);
  }),

  http.post(`${BASE_URL}/auth/password/change`, async ({ request }) => {
    const body = (await request.json()) as { currentPassword: string; newPassword: string };

    if (body.currentPassword === 'wrong-password') {
      return errorResponse('INVALID_CURRENT_PASSWORD', 'Current password is incorrect', 400);
    }

    return HttpResponse.json({
      message: 'Password successfully changed',
    });
  }),

  http.get(`${BASE_URL}/auth/approvals`, ({ request }) => {
    const { items, total, limit, offset } = paginate(mockPendingUsers, request);
    return HttpResponse.json({
      pendingUsers: items,
      total,
      limit,
      offset,
    });
  }),

  http.post(`${BASE_URL}/auth/approvals`, async ({ request }) => {
    const body = (await request.json()) as { userId?: string; username?: string };
    return HttpResponse.json({
      message: `User ${body.userId || body.username} approved successfully`,
    });
  }),

  http.delete(`${BASE_URL}/auth/approvals/:userId`, ({ params }) =>
    HttpResponse.json({
      message: `User ${params.userId} rejected successfully`,
    })
  ),

  http.post(`${BASE_URL}/auth/tokens`, async ({ request }) => {
    const body = (await request.json()) as {
      description?: string;
      expiresIn?: number;
      maxUses?: number;
      allowedRoles?: string[];
      scope?: string;
    };

    return HttpResponse.json({
      token: 'reg_abc123def456',
      tokenId: 'token-123',
      description: body.description,
      expiresAt: new Date(Date.now() + (body.expiresIn || 86400) * 1000).toISOString(),
      maxUses: body.maxUses,
      usedCount: 0,
      usedBy: [],
      allowedRoles: body.allowedRoles || ['viewer'],
      scope: body.scope || 'user',
      createdBy: mockUser.userId,
      createdAt: new Date().toISOString(),
      isActive: true,
    });
  }),

  http.post(`${BASE_URL}/auth/apikeys`, async ({ request }) => {
    const body = (await request.json()) as {
      name: string;
      roles?: string[];
      permissions?: string[];
      expiresAt?: string;
    };

    return HttpResponse.json({
      keyId: 'new-key-456',
      key: 'hak_abc123def456ghi789',
      name: body.name,
      type: 'user',
      ownerId: mockUser.userId,
      roles: body.roles,
      permissions: body.permissions || [],
      expiresAt: body.expiresAt,
      createdAt: new Date().toISOString(),
    });
  }),

  http.get(`${BASE_URL}/auth/apikeys`, () =>
    HttpResponse.json({
      apiKeys: mockApiKeys,
      total: mockApiKeys.length,
    })
  ),

  http.delete(`${BASE_URL}/auth/apikeys/:keyId`, ({ params }) =>
    HttpResponse.json({
      keyId: params.keyId,
      revoked: true,
      revokedAt: new Date().toISOString(),
    })
  ),

  http.get(`${BASE_URL}/nodes`, ({ request }) => {
    const { items, total, limit, offset } = paginate(mockNodes, request);
    return HttpResponse.json(apiResponse(items, { total, limit, offset }));
  }),

  http.get(`${BASE_URL}/nodes/:nodeId`, ({ params }) => {
    const node = params.nodeId === 'proxmox-01' ? mockNodeDetail : null;
    if (!node) {
      return errorResponse('NODE_NOT_FOUND', 'Node not found', 404);
    }
    return HttpResponse.json(apiResponse(node));
  }),

  http.patch(`${BASE_URL}/nodes/:nodeId`, async ({ request, params }) => {
    const updates = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      apiResponse({
        ...mockNodeDetail,
        nodeId: params.nodeId as string,
        ...updates,
        updatedAt: new Date().toISOString(),
      })
    );
  }),

  http.delete(`${BASE_URL}/nodes/:nodeId`, ({ params }) =>
    HttpResponse.json(
      apiResponse({
        ...mockNodeDetail,
        nodeId: params.nodeId as string,
        status: 'archived',
        archivedAt: new Date().toISOString(),
      })
    )
  ),

  http.get(`${BASE_URL}/services`, ({ request }) => {
    const { items, total, limit, offset } = paginate(mockServices, request);
    return HttpResponse.json(apiResponse(items, { total, limit, offset }));
  }),

  http.get(`${BASE_URL}/services/:serviceId`, ({ params }) => {
    const service = params.serviceId === 'svc-nginx-a1b2' ? mockServiceDetail : null;
    if (!service) {
      return errorResponse('SERVICE_NOT_FOUND', 'Service not found', 404);
    }
    return HttpResponse.json(apiResponse(service));
  }),

  http.get(`${BASE_URL}/dashboards`, ({ request }) => {
    const summaries = mockState.dashboards.map(toDashboardSummary);
    const { items, total, limit, offset } = paginate(summaries, request, 50);
    return HttpResponse.json(apiResponse(items, { total, limit, offset }));
  }),

  http.get(`${BASE_URL}/dashboards/widgets/registry`, ({ request }) => {
    const url = new URL(request.url);
    const category = url.searchParams.get('category');

    const sharedConfigSchema = [
      { key: 'title', label: 'Title', type: 'string', description: 'Optional display title override for the widget header.' },
      { key: 'subtitle', label: 'Subtitle', type: 'string', description: 'Short supporting text shown under the title.' },
      { key: 'collapsible', label: 'Collapsible', type: 'boolean', description: 'Allow the widget body to be collapsed from the header.' },
      { key: 'defaultCollapsed', label: 'Start collapsed', type: 'boolean', description: 'Collapse the widget body when the board first loads.' },
    ];

    const allWidgets = [
      { widgetType: 'hydra::stats-cards', displayName: 'Stats Overview', description: 'Key infrastructure metrics at a glance.', category: 'data-display', icon: 'bar-chart-3', source: 'hydra', defaultSize: { w: 12, h: 2 }, minSize: { w: 6, h: 2 }, maxSize: { w: 12, h: 4 }, configSchema: sharedConfigSchema, capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false }, kioskMode: 'render', isAvailable: true },
      { widgetType: 'hydra::capacity-overview', displayName: 'Capacity Overview', description: 'Resource utilization and capacity planning for your fleet.', category: 'infrastructure', icon: 'hard-drive', source: 'hydra', defaultSize: { w: 12, h: 4 }, minSize: { w: 6, h: 3 }, maxSize: { w: 12, h: 6 }, configSchema: sharedConfigSchema, capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false }, kioskMode: 'render', isAvailable: true },
      { widgetType: 'hydra::service-summary', displayName: 'Service Summary', description: 'Overview of service health and operational status.', category: 'status', icon: 'activity', source: 'hydra', defaultSize: { w: 6, h: 4 }, minSize: { w: 4, h: 3 }, maxSize: { w: 12, h: 6 }, configSchema: sharedConfigSchema, capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false }, kioskMode: 'render', isAvailable: true },
      { widgetType: 'hydra::recent-activity', displayName: 'Recent Activity', description: 'Latest infrastructure events and state changes.', category: 'activity', icon: 'clock', source: 'hydra', defaultSize: { w: 6, h: 4 }, minSize: { w: 4, h: 3 }, maxSize: { w: 12, h: 6 }, configSchema: sharedConfigSchema, capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false }, kioskMode: 'render', isAvailable: true },
      { widgetType: 'hydra::mini-topology', displayName: 'Infrastructure Topology', description: 'Visual map of the current topology snapshot.', category: 'infrastructure', icon: 'network', source: 'hydra', defaultSize: { w: 12, h: 4 }, minSize: { w: 6, h: 3 }, maxSize: { w: 12, h: 8 }, configSchema: sharedConfigSchema, capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false }, kioskMode: 'render', isAvailable: true },
      { widgetType: 'hydra::node-status-grid', displayName: 'Node Status Grid', description: 'Grid view of node health, reachability, and role.', category: 'status', icon: 'server', source: 'hydra', defaultSize: { w: 12, h: 4 }, minSize: { w: 6, h: 3 }, maxSize: { w: 12, h: 6 }, configSchema: sharedConfigSchema, capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false }, kioskMode: 'render', isAvailable: true },
    ];

    const widgets = category ? allWidgets.filter((w) => w.category === category) : allWidgets;

    const catCounts: Record<string, number> = {};
    for (const w of allWidgets) {
      catCounts[w.category] = (catCounts[w.category] ?? 0) + 1;
    }
    const categories = Object.entries(catCounts)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([id, count]) => ({ id, name: id.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()), count }));

    return HttpResponse.json(apiResponse({ widgets, categories, total: widgets.length }));
  }),

  http.get(`${BASE_URL}/dashboards/:dashboardId`, ({ params }) => {
    const board = mockState.dashboards.find((item) => item.boardId === params.dashboardId);
    if (!board) {
      return errorResponse('DASHBOARD_NOT_FOUND', 'Dashboard not found', 404);
    }
    return HttpResponse.json(apiResponse(board));
  }),

  http.post(`${BASE_URL}/dashboards`, async ({ request }) => {
    const payload = (await request.json()) as Partial<(typeof mockState.dashboards)[number]>;
    const now = new Date().toISOString();
    const boardId = nextId('board', mockState.dashboards.length);
    const widgets = payload.widgets ?? [];
    const board = {
      boardId,
      name: payload.name || 'New Dashboard',
      description: payload.description ?? null,
      icon: payload.icon ?? null,
      ownerId: 'user-001',
      ownerType: 'user' as const,
      boardType: payload.boardType ?? 'user',
      visibility: payload.visibility ?? {
        scope: 'private' as const,
        sharedWith: { roles: [], users: [] },
      },
      widgetCount: widgets.length,
      tags: payload.tags ?? [],
      isHome: payload.isHome ?? false,
      version: 1,
      createdAt: now,
      updatedAt: now,
      layout: payload.layout ?? {
        mode: 'grid' as const,
        grid: {
          columns: 12,
          rowHeight: 80,
          breakpoints: {
            xl: { columns: 12, width: 1536 },
            lg: { columns: 12, width: 1200 },
            md: { columns: 8, width: 996 },
            sm: { columns: 4, width: 480 },
            xs: { columns: 2, width: 0 },
          },
          compaction: 'vertical' as const,
          margin: [16, 16] as [number, number],
          padding: [0, 0] as [number, number],
        },
      },
      widgets,
      settings: payload.settings ?? {
        theme: 'inherit',
        autoRefresh: true,
        refreshInterval: 30,
        showHeader: true,
        kioskMode: false,
        kioskAutoScroll: false,
        kioskScrollSpeed: 30,
        backgroundImage: null,
        customCss: null,
      },
      clonedFrom: null,
      archivedAt: null,
      layoutMode: payload.layoutMode ?? 'grid' as const,
      scope: payload.scope ?? 'standalone' as const,
      entityTypeFilter: payload.entityTypeFilter ?? null,
      isSystemDefault: payload.isSystemDefault ?? false,
    };
    mockState.dashboards.unshift(board);
    return HttpResponse.json(apiResponse(board), { status: 201 });
  }),

  http.put(`${BASE_URL}/dashboards/:dashboardId`, async ({ request, params }) => {
    const updates = (await request.json()) as Partial<(typeof mockState.dashboards)[number]>;
    const index = mockState.dashboards.findIndex((item) => item.boardId === params.dashboardId);
    if (index === -1) {
      return errorResponse('DASHBOARD_NOT_FOUND', 'Dashboard not found', 404);
    }

    const current = mockState.dashboards[index];
    const updatedBoard = {
      ...current,
      ...updates,
      widgetCount: updates.widgets?.length ?? current.widgets.length,
      updatedAt: new Date().toISOString(),
      version: current.version + 1,
    };
    mockState.dashboards[index] = updatedBoard;
    return HttpResponse.json(apiResponse(updatedBoard));
  }),

  http.delete(`${BASE_URL}/dashboards/:dashboardId`, ({ params }) => {
    const index = mockState.dashboards.findIndex((item) => item.boardId === params.dashboardId);
    if (index === -1) {
      return errorResponse('DASHBOARD_NOT_FOUND', 'Dashboard not found', 404);
    }
    mockState.dashboards.splice(index, 1);
    return HttpResponse.json(apiResponse({ deleted: true }));
  }),

  http.post(`${BASE_URL}/dashboards/:dashboardId/clone`, ({ params }) => {
    const source = mockState.dashboards.find((item) => item.boardId === params.dashboardId);
    if (!source) {
      return errorResponse('DASHBOARD_NOT_FOUND', 'Dashboard not found', 404);
    }
    const now = new Date().toISOString();
    const boardId = nextId('board', mockState.dashboards.length);
    const cloned = {
      ...source,
      boardId,
      name: `${source.name} (Copy)`,
      version: 1,
      createdAt: now,
      updatedAt: now,
      clonedFrom: source.boardId,
      isHome: false,
    };
    mockState.dashboards.unshift(cloned);
    return HttpResponse.json(apiResponse(cloned), { status: 201 });
  }),

  http.post(`${BASE_URL}/dashboards/:dashboardId/widgets`, async ({ request, params }) => {
    const payload = (await request.json()) as {
      widgetType: string;
      position: { x: number; y: number; w: number; h: number };
      config?: Record<string, unknown>;
      dataBinding?: unknown;
    };
    const index = mockState.dashboards.findIndex((item) => item.boardId === params.dashboardId);
    if (index === -1) {
      return errorResponse('DASHBOARD_NOT_FOUND', 'Dashboard not found', 404);
    }
    const board = mockState.dashboards[index];
    const newWidget = {
      instanceId: `wi_${Date.now()}`,
      widgetType: payload.widgetType,
      position: payload.position,
      config: payload.config ?? {},
      dataBinding: (payload.dataBinding as { source: string; query: Record<string, unknown> } | null) ?? null,
    };
    const updatedBoard = {
      ...board,
      widgets: [...board.widgets, newWidget],
      widgetCount: board.widgets.length + 1,
      updatedAt: new Date().toISOString(),
      version: board.version + 1,
    };
    mockState.dashboards[index] = updatedBoard;
    return HttpResponse.json(apiResponse(updatedBoard), { status: 201 });
  }),

  http.put(`${BASE_URL}/dashboards/:dashboardId/widgets/:widgetId`, async ({ request, params }) => {
    const updates = (await request.json()) as Record<string, unknown>;
    const boardIndex = mockState.dashboards.findIndex((item) => item.boardId === params.dashboardId);
    if (boardIndex === -1) {
      return errorResponse('DASHBOARD_NOT_FOUND', 'Dashboard not found', 404);
    }
    const board = mockState.dashboards[boardIndex];
    const widgetIndex = board.widgets.findIndex((w) => w.instanceId === params.widgetId);
    if (widgetIndex === -1) {
      return errorResponse('WIDGET_NOT_FOUND', 'Widget not found', 404);
    }
    const updatedWidgets = [...board.widgets];
    const current = updatedWidgets[widgetIndex];
    updatedWidgets[widgetIndex] = {
      ...current,
      widgetType: (updates.widgetType as string) ?? current.widgetType,
      position: (updates.position as typeof current.position) ?? current.position,
      config: (updates.config as typeof current.config) ?? current.config,
      dataBinding: updates.dataBinding !== undefined
        ? (updates.dataBinding as typeof current.dataBinding)
        : current.dataBinding,
    };
    const updatedBoard = {
      ...board,
      widgets: updatedWidgets,
      updatedAt: new Date().toISOString(),
      version: board.version + 1,
    };
    mockState.dashboards[boardIndex] = updatedBoard;
    return HttpResponse.json(apiResponse(updatedBoard));
  }),

  http.delete(`${BASE_URL}/dashboards/:dashboardId/widgets/:widgetId`, ({ params }) => {
    const boardIndex = mockState.dashboards.findIndex((item) => item.boardId === params.dashboardId);
    if (boardIndex === -1) {
      return errorResponse('DASHBOARD_NOT_FOUND', 'Dashboard not found', 404);
    }
    const board = mockState.dashboards[boardIndex];
    const filtered = board.widgets.filter((w) => w.instanceId !== params.widgetId);
    if (filtered.length === board.widgets.length) {
      return errorResponse('WIDGET_NOT_FOUND', 'Widget not found', 404);
    }
    const updatedBoard = {
      ...board,
      widgets: filtered,
      widgetCount: filtered.length,
      updatedAt: new Date().toISOString(),
      version: board.version + 1,
    };
    mockState.dashboards[boardIndex] = updatedBoard;
    return HttpResponse.json(apiResponse(updatedBoard));
  }),

  // ── Wave 4: Kiosk tokens ────────────────────────────────────────────────

  http.get(`${BASE_URL}/dashboards/:boardId/kiosk-tokens`, ({ params }) => {
    const tokens = kioskTokensByBoard.get(params.boardId as string) ?? [];
    return HttpResponse.json(apiResponse(tokens, { total: tokens.length }));
  }),

  http.post(`${BASE_URL}/dashboards/:boardId/kiosk-tokens`, async ({ params, request }) => {
    const body = (await request.json()) as { label: string; ttlHours: number | null };
    const boardId = params.boardId as string;
    const tokenId = `kt_${Math.random().toString(16).slice(2, 10)}`;
    const now = new Date().toISOString();
    const expiresAt =
      body.ttlHours === null
        ? null
        : new Date(Date.now() + body.ttlHours * 3_600_000).toISOString();
    const created: KioskTokenSummary & { token: string } = {
      tokenId,
      boardId,
      label: body.label,
      createdBy: 'user-001',
      createdAt: now,
      expiresAt,
      revokedAt: null,
      lastUsedAt: null,
      token: `MOCK_RAW_${tokenId}`,
    };
    const list = kioskTokensByBoard.get(boardId) ?? [];
    const { token: _token, ...summary } = created;
    list.unshift(summary);
    kioskTokensByBoard.set(boardId, list);
    return HttpResponse.json(apiResponse(created), { status: 201 });
  }),

  http.delete(`${BASE_URL}/dashboards/:boardId/kiosk-tokens/:tokenId`, ({ params }) => {
    const boardId = params.boardId as string;
    const tokenId = params.tokenId as string;
    const list = kioskTokensByBoard.get(boardId) ?? [];
    const idx = list.findIndex((t) => t.tokenId === tokenId);
    if (idx === -1) {
      return errorResponse('KIOSK_TOKEN_NOT_FOUND', 'Kiosk token not found', 404);
    }
    list[idx] = { ...list[idx], revokedAt: new Date().toISOString() };
    return new HttpResponse(null, { status: 204 });
  }),

  // ── Wave 4: Kiosk board read (unauthenticated, token-gated) ────────────

  http.get(`${BASE_URL}/dashboards/kiosk/:boardId`, ({ request, params }) => {
    const url = new URL(request.url);
    const token = url.searchParams.get('token');
    if (!token || token === 'invalid') {
      return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const boardId = params.boardId as string;
    const source = mockState.dashboards.find((b) => b.boardId === boardId);
    const board = source ?? {
      boardId,
      name: 'Kiosk Board',
      description: null,
      icon: null,
      ownerId: 'user-001',
      ownerType: 'user' as const,
      boardType: 'kiosk' as const,
      visibility: { scope: 'public' as const, sharedWith: { roles: [], users: [] } },
      widgetCount: 0,
      tags: [],
      isHome: false,
      version: 1,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      layoutMode: 'grid' as const,
      scope: 'standalone' as const,
      entityTypeFilter: null,
      isSystemDefault: false,
      layout: {
        mode: 'grid' as const,
        grid: {
          columns: 12,
          rowHeight: 80,
          breakpoints: {},
          compaction: 'vertical' as const,
          margin: [16, 16] as [number, number],
          padding: [0, 0] as [number, number],
        },
      },
      widgets: [],
      settings: {
        theme: 'inherit',
        autoRefresh: true,
        refreshInterval: 30,
        showHeader: false,
        kioskMode: true,
        kioskAutoScroll: false,
        kioskScrollSpeed: 30,
        backgroundImage: null,
        customCss: null,
      },
      clonedFrom: null,
      archivedAt: null,
    };
    return HttpResponse.json(apiResponse(board));
  }),

  // ── Wave 4: Entity panels ───────────────────────────────────────────────

  http.get(`${BASE_URL}/dashboards/panel/:entityType`, ({ params }) => {
    const entityType = params.entityType as string;
    const key = `user-001:${entityType}`;
    const override = panelOverrides.get(key);
    if (override) {
      return HttpResponse.json(apiResponse(override));
    }
    return HttpResponse.json(
      apiResponse({
        boardId: `panel-default-${entityType}`,
        name: `Default ${entityType} Panel`,
        description: null,
        icon: null,
        ownerId: 'system',
        ownerType: 'system' as const,
        boardType: 'user' as const,
        visibility: { scope: 'public' as const, sharedWith: { roles: [], users: [] } },
        widgetCount: 0,
        tags: [],
        isHome: false,
        version: 1,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        layoutMode: 'grid' as const,
        scope: 'entity-panel' as const,
        entityTypeFilter: entityType,
        isSystemDefault: true,
        layout: {
          mode: 'grid' as const,
          grid: {
            columns: 12,
            rowHeight: 80,
            breakpoints: {},
            compaction: 'vertical' as const,
            margin: [16, 16] as [number, number],
            padding: [0, 0] as [number, number],
          },
        },
        widgets: [],
        settings: {
          theme: 'inherit',
          autoRefresh: true,
          refreshInterval: 30,
          showHeader: true,
          kioskMode: false,
          kioskAutoScroll: false,
          kioskScrollSpeed: 30,
          backgroundImage: null,
          customCss: null,
        },
        clonedFrom: null,
        archivedAt: null,
      }),
    );
  }),

  http.post(`${BASE_URL}/dashboards/panel/:entityType/customize`, ({ params }) => {
    const entityType = params.entityType as string;
    const key = `user-001:${entityType}`;
    const boardId = `panel-${entityType}-user-001-${Math.random().toString(16).slice(2, 10)}`;
    const override = {
      boardId,
      name: `My ${entityType} Panel`,
      description: null,
      icon: null,
      ownerId: 'user-001',
      ownerType: 'user' as const,
      boardType: 'user' as const,
      visibility: { scope: 'private' as const, sharedWith: { roles: [], users: [] } },
      widgetCount: 0,
      tags: [],
      isHome: false,
      version: 1,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      layoutMode: 'grid' as const,
      scope: 'entity-panel' as const,
      entityTypeFilter: entityType,
      isSystemDefault: false,
      layout: {
        mode: 'grid' as const,
        grid: {
          columns: 12,
          rowHeight: 80,
          breakpoints: {},
          compaction: 'vertical' as const,
          margin: [16, 16] as [number, number],
          padding: [0, 0] as [number, number],
        },
      },
      widgets: [],
      settings: {
        theme: 'inherit',
        autoRefresh: true,
        refreshInterval: 30,
        showHeader: true,
        kioskMode: false,
        kioskAutoScroll: false,
        kioskScrollSpeed: 30,
        backgroundImage: null,
        customCss: null,
      },
      clonedFrom: null,
      archivedAt: null,
    };
    panelOverrides.set(key, override);
    return HttpResponse.json(apiResponse(override), { status: 201 });
  }),

  http.delete(`${BASE_URL}/dashboards/panel/:entityType/override`, ({ params }) => {
    const entityType = params.entityType as string;
    const key = `user-001:${entityType}`;
    if (!panelOverrides.has(key)) {
      return errorResponse('PANEL_OVERRIDE_NOT_FOUND', 'Panel override not found', 404);
    }
    panelOverrides.delete(key);
    return new HttpResponse(null, { status: 204 });
  }),

  // ── Networks ─────────────────────────────────────────────────────────────

  http.get(`${BASE_URL}/networks`, ({ request }) => {
    const { items, total, limit, offset } = paginate(mockNetworks, request);
    return HttpResponse.json(apiResponse(items, { total, limit, offset }));
  }),

  http.get(`${BASE_URL}/networks/:networkId`, ({ params }) => {
    const network = params.networkId === 'net-lan-192-168-0' ? mockNetworkDetail : null;
    if (!network) {
      return errorResponse('NETWORK_NOT_FOUND', 'Network not found', 404);
    }
    return HttpResponse.json(apiResponse(network));
  }),

  http.get(`${BASE_URL}/groups`, ({ request }) => {
    const { items, total, limit, offset } = paginate(mockGroups, request);
    return HttpResponse.json(apiResponse(items, { total, limit, offset }));
  }),

  http.get(`${BASE_URL}/groups/:groupId`, ({ params }) => {
    const group = params.groupId === 'grp-production' ? mockGroupDetail : null;
    if (!group) {
      return errorResponse('GROUP_NOT_FOUND', 'Group not found', 404);
    }
    return HttpResponse.json(apiResponse(group));
  }),

  http.get(`${BASE_URL}/groups/:groupId/members`, ({ params, request }) => {
    const groupId = params.groupId as string;
    const members = mockState.groupMembers[groupId];
    if (!members) {
      return errorResponse('GROUP_NOT_FOUND', 'Group not found', 404);
    }

    const entityType = new URL(request.url).searchParams.get('entityType');
    const filtered =
      entityType === 'node'
        ? { nodes: members.nodes, services: [] }
        : entityType === 'service'
          ? { nodes: [], services: members.services }
          : members;

    return HttpResponse.json(
      apiResponse(filtered, {
        total: filtered.nodes.length + filtered.services.length,
        limit: 50,
        offset: 0,
      })
    );
  }),

  http.get(`${BASE_URL}/profiles/:profileId`, ({ params }) => {
    const profile = mockState.profiles[params.profileId as string];
    if (!profile) {
      return errorResponse('PROFILE_NOT_FOUND', 'Profile not found', 404);
    }
    return HttpResponse.json(apiResponse(profile));
  }),

  http.get(`${BASE_URL}/nodes/:nodeId/profiles`, ({ params, request }) => {
    const nodeId = params.nodeId as string;
    const profiles = mockState.profileSummaries[nodeId] || [];
    const { items, total, limit, offset } = paginate(profiles, request, 50);
    return HttpResponse.json(apiResponse(items, { total, limit, offset }));
  }),

  http.get(`${BASE_URL}/nodes/:nodeId/profiles/latest`, ({ params }) => {
    const nodeId = params.nodeId as string;
    const latest = (mockState.profileSummaries[nodeId] || []).slice(-1)[0];
    if (!latest) {
      return errorResponse('PROFILE_NOT_FOUND', 'Latest profile not found', 404);
    }
    return HttpResponse.json(apiResponse(mockState.profiles[latest.profileId]));
  }),

  http.get(`${BASE_URL}/nodes/:nodeId/profiles/diff`, ({ params, request }) => {
    const nodeId = params.nodeId as string;
    const url = new URL(request.url);
    const fromVersion = url.searchParams.get('fromVersion');
    const toVersion = url.searchParams.get('toVersion');
    const diff = mockState.profileDiffs[buildProfileDiffKey(nodeId, fromVersion, toVersion)];
    if (!diff) {
      return errorResponse('PROFILE_DIFF_NOT_FOUND', 'Profile diff not found', 404);
    }
    return HttpResponse.json(apiResponse(diff));
  }),

  http.get(`${BASE_URL}/topologies`, ({ request }) => {
    const url = new URL(request.url);
    const mode = url.searchParams.get('mode');
    const items = mode
      ? mockState.topologies.filter((topology) => topology.mode === mode)
      : mockState.topologies;
    const paginated = paginate(items, request);
    const summaries = paginated.items.map(({ graph: _graph, diff: _diff, scope: _scope, previousTopologyId: _previousTopologyId, ...summary }) => summary);
    return HttpResponse.json(apiResponse(summaries, {
      total: paginated.total,
      limit: paginated.limit,
      offset: paginated.offset,
    }));
  }),

  http.get(`${BASE_URL}/topologies/latest`, ({ request }) => {
    const url = new URL(request.url);
    const mode = url.searchParams.get('mode') || 'infrastructure';
    const includeGraph = url.searchParams.get('includeGraph') !== 'false';
    const topology = getLatestTopology(mode);

    if (!topology) {
      return errorResponse('TOPOLOGY_NOT_FOUND', 'Topology not found', 404);
    }

    return HttpResponse.json(apiResponse(stripGraphIfNeeded(topology, includeGraph)));
  }),

  http.get(`${BASE_URL}/topologies/diff`, () => HttpResponse.json(apiResponse(mockState.topologyDiff))),

  http.get(`${BASE_URL}/topologies/subgraph`, ({ request }) => {
    const url = new URL(request.url);
    const nodeId = url.searchParams.get('nodeId') || '';
    const subgraph = mockState.subgraphs[nodeId];
    if (!subgraph) {
      return errorResponse('SUBGRAPH_NOT_FOUND', 'Subgraph not found', 404);
    }
    return HttpResponse.json(apiResponse(subgraph));
  }),

  http.get(`${BASE_URL}/topologies/:topologyId`, ({ params, request }) => {
    const topologyId = params.topologyId as string;
    const includeGraph = new URL(request.url).searchParams.get('includeGraph') !== 'false';
    const topology = mockState.topologies.find((item) => item.topologyId === topologyId);

    if (!topology) {
      return errorResponse('TOPOLOGY_NOT_FOUND', 'Topology not found', 404);
    }

    return HttpResponse.json(apiResponse(stripGraphIfNeeded(topology, includeGraph)));
  }),

  http.post(`${BASE_URL}/topologies/generate`, async ({ request }) => {
    const body = (await request.json()) as { mode: string };
    const latest = getLatestTopology(body.mode);
    if (!latest) {
      return errorResponse('TOPOLOGY_NOT_FOUND', 'Topology not found', 404);
    }

    const next = {
      ...latest,
      topologyId: `${latest.mode}-${nextId('topology', mockState.topologies.length)}`,
      version: latest.version + 1,
      generatedAt: new Date().toISOString(),
      validFrom: new Date().toISOString(),
    };
    mockState.topologies.push(next);
    return HttpResponse.json(apiResponse(next));
  }),

  http.get(`${BASE_URL}/users`, ({ request }) => {
    const url = new URL(request.url);
    const role = url.searchParams.get('role');
    const status = url.searchParams.get('status');
    const search = (url.searchParams.get('search') || '').toLowerCase();
    const sortBy = url.searchParams.get('sortBy');
    const sortOrder = url.searchParams.get('sortOrder') || 'asc';

    let users = [...mockState.users];

    if (role) {
      users = users.filter((user) => user.role === role);
    }
    if (status) {
      users = users.filter((user) => user.status === status);
    }
    if (search) {
      users = users.filter(
        (user) =>
          user.username.toLowerCase().includes(search) ||
          user.email.toLowerCase().includes(search)
      );
    }

    if (sortBy === 'createdAt' || sortBy === 'username') {
      users.sort((a, b) => {
        const left = String(a[sortBy]);
        const right = String(b[sortBy]);
        return sortOrder === 'desc' ? right.localeCompare(left) : left.localeCompare(right);
      });
    }

    const { items, total, limit, offset } = paginate(users, request);
    return HttpResponse.json({
      users: items,
      total,
      limit,
      offset,
    });
  }),

  http.delete(`${BASE_URL}/users/:userId`, ({ params }) => {
    const userId = params.userId as string;
    const user = mockState.users.find((item) => item.userId === userId);
    if (!user) {
      return errorResponse('USER_NOT_FOUND', 'User not found', 404);
    }
    user.status = 'archived';
    return HttpResponse.json({
      userId,
      status: user.status,
      archived: true,
    });
  }),

  http.post(`${BASE_URL}/users/:userId/roles/elevate`, async ({ params, request }) => {
    const userId = params.userId as string;
    const body = (await request.json()) as { newRole: typeof mockState.users[number]['role'] };
    const user = mockState.users.find((item) => item.userId === userId);
    if (!user) {
      return errorResponse('USER_NOT_FOUND', 'User not found', 404);
    }
    user.role = body.newRole;
    return HttpResponse.json({
      userId,
      role: user.role,
    });
  }),

  http.post(`${BASE_URL}/users/:userId/roles/grant-temporary`, async ({ params, request }) => {
    const userId = params.userId as string;
    const body = (await request.json()) as { role: string; durationHours: number };
    return HttpResponse.json({
      userId,
      role: body.role,
      durationHours: body.durationHours,
      granted: true,
    });
  }),

  http.delete(`${BASE_URL}/users/:userId/roles/temporary/:role`, ({ params }) =>
    HttpResponse.json({
      userId: params.userId,
      role: params.role,
      revoked: true,
    })
  ),

  http.get(`${BASE_URL}/chat/projects`, ({ request }) => {
    const { items, total } = paginate(mockState.chatProjects, request);
    return HttpResponse.json({
      projects: items,
      total,
    });
  }),

  http.get(`${BASE_URL}/chat/projects/:projectId`, ({ params }) => {
    const project = mockState.chatProjects.find((item) => item.projectId === params.projectId);
    if (!project) {
      return errorResponse('CHAT_PROJECT_NOT_FOUND', 'Chat project not found', 404);
    }
    return HttpResponse.json(project);
  }),

  http.post(`${BASE_URL}/chat/projects`, async ({ request }) => {
    const body = (await request.json()) as { name: string; description?: string };
    const project = {
      projectId: nextId('proj', mockState.chatProjects.length),
      name: body.name,
      description: body.description,
      sessionCount: 0,
      ownerId: 'user-001',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    mockState.chatProjects.push(project);
    return HttpResponse.json(project);
  }),

  http.put(`${BASE_URL}/chat/projects/:projectId`, async ({ params, request }) => {
    const project = mockState.chatProjects.find((item) => item.projectId === params.projectId);
    if (!project) {
      return errorResponse('CHAT_PROJECT_NOT_FOUND', 'Chat project not found', 404);
    }
    const body = (await request.json()) as { name?: string; description?: string };
    Object.assign(project, body, { updatedAt: new Date().toISOString() });
    return HttpResponse.json(project);
  }),

  http.delete(`${BASE_URL}/chat/projects/:projectId`, ({ params, request }) => {
    const projectId = params.projectId as string;
    const url = new URL(request.url);
    const cascade = url.searchParams.get('cascade') === 'true';

    mockState.chatProjects = mockState.chatProjects.filter((project) => project.projectId !== projectId);
    if (cascade) {
      const sessionIds = mockState.chatSessions
        .filter((session) => session.projectId === projectId)
        .map((session) => session.sessionId);
      mockState.chatSessions = mockState.chatSessions.filter((session) => session.projectId !== projectId);
      sessionIds.forEach((sessionId) => {
        delete mockState.chatMessages[sessionId];
        delete mockState.sessionContexts[sessionId];
      });
    }
    return HttpResponse.json({ deleted: true, projectId });
  }),

  http.get(`${BASE_URL}/chat/sessions`, ({ request }) => {
    const url = new URL(request.url);
    const projectId = url.searchParams.get('projectId');
    const sessions = projectId
      ? mockState.chatSessions.filter((session) => session.projectId === projectId)
      : mockState.chatSessions;
    const { items, total } = paginate(sessions, request);
    return HttpResponse.json({
      sessions: items,
      total,
    });
  }),

  http.get(`${BASE_URL}/chat/sessions/:sessionId`, ({ params }) => {
    const session = mockState.chatSessions.find((item) => item.sessionId === params.sessionId);
    if (!session) {
      return errorResponse('CHAT_SESSION_NOT_FOUND', 'Chat session not found', 404);
    }
    return HttpResponse.json(session);
  }),

  http.post(`${BASE_URL}/chat/sessions`, async ({ request }) => {
    const body = (await request.json()) as {
      projectId?: string;
      title?: string;
      llmProviderId?: string;
      mcpServerIds?: string[];
    };
    const session = {
      sessionId: nextId('sess', mockState.chatSessions.length),
      projectId: body.projectId || null,
      title: body.title || 'New Chat',
      status: 'active' as const,
      messageCount: 0,
      llmProviderId: body.llmProviderId || null,
      mcpServerIds: body.mcpServerIds || [],
      llmConfigLocked: false,
      sessionContext: null,
      ownerId: 'user-001',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      lastMessageAt: null,
    };
    mockState.chatSessions.push(session);
    if (session.projectId) {
      const project = mockState.chatProjects.find((item) => item.projectId === session.projectId);
      if (project) {
        project.sessionCount += 1;
      }
    }
    return HttpResponse.json(session);
  }),

  http.put(`${BASE_URL}/chat/sessions/:sessionId`, async ({ params, request }) => {
    const session = mockState.chatSessions.find((item) => item.sessionId === params.sessionId);
    if (!session) {
      return errorResponse('CHAT_SESSION_NOT_FOUND', 'Chat session not found', 404);
    }
    const body = (await request.json()) as Partial<typeof session>;
    Object.assign(session, body, { updatedAt: new Date().toISOString() });
    return HttpResponse.json(session);
  }),

  http.delete(`${BASE_URL}/chat/sessions/:sessionId`, ({ params }) => {
    const sessionId = params.sessionId as string;
    mockState.chatSessions = mockState.chatSessions.filter((session) => session.sessionId !== sessionId);
    delete mockState.chatMessages[sessionId];
    delete mockState.sessionContexts[sessionId];
    return HttpResponse.json({ deleted: true, sessionId });
  }),

  http.get(`${BASE_URL}/chat/sessions/:sessionId/messages`, ({ params, request }) => {
    const sessionId = params.sessionId as string;
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get('limit') || 100);
    const offset = Number(url.searchParams.get('offset') || 0);
    const order = url.searchParams.get('order') || 'asc';
    const source = [...(mockState.chatMessages[sessionId] || [])];
    const messages = order === 'desc' ? source.reverse() : source;
    const items = messages.slice(offset, offset + limit);
    return HttpResponse.json({
      messages: items,
      total: messages.length,
      hasMore: offset + limit < messages.length,
    });
  }),

  http.post(`${BASE_URL}/chat/sessions/:sessionId/messages`, async ({ params, request }) => {
    const sessionId = params.sessionId as string;
    const body = (await request.json()) as {
      role: ChatMessage['role'];
      content: string;
      toolCalls?: ChatToolCall[];
    };
    const messages = mockState.chatMessages[sessionId] || [];
    const message: ChatMessageResponse = {
      messageId: nextId('msg', messages.length),
      sessionId,
      role: body.role,
      content: body.content,
      toolCalls: body.toolCalls,
      order: messages.length + 1,
      createdAt: new Date().toISOString(),
    };
    mockState.chatMessages[sessionId] = [...messages, message];
    const session = mockState.chatSessions.find((item) => item.sessionId === sessionId);
    if (session) {
      session.messageCount = mockState.chatMessages[sessionId].length;
      session.lastMessageAt = message.createdAt;
      session.updatedAt = message.createdAt;
    }
    return HttpResponse.json(message);
  }),

  http.post(`${BASE_URL}/chat/sessions/:sessionId/messages/bulk`, async ({ params, request }) => {
    const sessionId = params.sessionId as string;
    const body = (await request.json()) as {
      messages: Array<{
        messageId?: string;
        role: ChatMessage['role'];
        content: string;
        order?: number;
      }>;
    };
    const existing = mockState.chatMessages[sessionId] || [];
    const appended = body.messages.map((message, index) => ({
      messageId: message.messageId || nextId('msg', existing.length + index),
      sessionId,
      role: message.role,
      content: message.content,
      order: message.order ?? existing.length + index + 1,
      createdAt: new Date().toISOString(),
    }));
    mockState.chatMessages[sessionId] = [...existing, ...appended];
    return HttpResponse.json({
      upsertedCount: appended.length,
      sessionId,
    });
  }),

  http.get(`${BASE_URL}/chat/sessions/:sessionId/context`, ({ params }) => {
    const sessionId = params.sessionId as string;
    const context = mockState.sessionContexts[sessionId];
    if (!context) {
      return errorResponse('SESSION_CONTEXT_NOT_FOUND', 'Session context not found', 404);
    }
    return HttpResponse.json(context);
  }),

  http.get(`${BASE_URL}/mcp/servers`, ({ request }) => {
    const url = new URL(request.url);
    const category = url.searchParams.get('category');
    const enabledParam = url.searchParams.get('enabled');
    const enabled = enabledParam === null ? null : enabledParam === 'true';

    let servers = [...mockState.mcpServers];
    if (category) {
      servers = servers.filter((server) => server.category === category);
    }
    if (enabled !== null) {
      servers = servers.filter((server) => server.enabled === enabled);
    }

    return HttpResponse.json({
      servers,
      total: servers.length,
    });
  }),

  http.get(`${BASE_URL}/mcp/servers/:serverId`, ({ params }) => {
    const server = mockState.mcpServers.find((item) => item.serverId === params.serverId);
    if (!server) {
      return errorResponse('MCP_SERVER_NOT_FOUND', 'MCP server not found', 404);
    }
    return HttpResponse.json(server);
  }),

  http.post(`${BASE_URL}/mcp/servers`, async ({ request }) => {
    const body = (await request.json()) as {
      name: string;
      endpoint: string;
      description?: string;
      category?: string;
      authType?: string;
      enabled?: boolean;
      docsUrl?: string;
    };
    const serverId = sanitizeId(body.name);
    const status: MCPServerStatus = body.enabled === false ? 'unknown' : 'healthy';
    const server: MCPServerResponse = {
      serverId,
      name: body.name,
      endpoint: body.endpoint,
      description: body.description,
      category: (body.category || 'other') as MCPServer['category'],
      authType: (body.authType || 'none') as MCPServer['authType'],
      authConfigured: Boolean(body.authType && body.authType !== 'none'),
      enabled: body.enabled ?? true,
      status,
      lastHealthCheck: body.enabled === false ? null : new Date().toISOString(),
      docsUrl: body.docsUrl || null,
      ownerId: 'user-001',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    mockState.mcpServers.push(server);
    mockState.mcpTools[serverId] = [];
    mockState.mcpResources[serverId] = [];
    mockState.mcpPrompts[serverId] = [];
    mockState.mcpHealth[serverId] = {
      serverId,
      status: server.status,
      message: `${server.name} responded successfully`,
      checkedAt: new Date().toISOString(),
      tools: [],
      resources: [],
    };
    return HttpResponse.json(server);
  }),

  http.put(`${BASE_URL}/mcp/servers/:serverId`, async ({ params, request }) => {
    const server = mockState.mcpServers.find((item) => item.serverId === params.serverId);
    if (!server) {
      return errorResponse('MCP_SERVER_NOT_FOUND', 'MCP server not found', 404);
    }
    const body = (await request.json()) as Partial<MCPServerResponse>;
    Object.assign(server, body, {
      updatedAt: new Date().toISOString(),
      status: (
        body.enabled === false ? 'unknown' : body.enabled === true ? 'healthy' : server.status
      ) as MCPServerStatus,
    });
    return HttpResponse.json(server);
  }),

  http.delete(`${BASE_URL}/mcp/servers/:serverId`, ({ params }) => {
    const serverId = params.serverId as string;
    mockState.mcpServers = mockState.mcpServers.filter((server) => server.serverId !== serverId);
    delete mockState.mcpTools[serverId];
    delete mockState.mcpResources[serverId];
    delete mockState.mcpPrompts[serverId];
    delete mockState.mcpHealth[serverId];
    return HttpResponse.json({ deleted: true, serverId });
  }),

  http.get(`${BASE_URL}/mcp/servers/:serverId/health`, ({ params }) => {
    const serverId = params.serverId as string;
    const health = mockState.mcpHealth[serverId];
    const server = mockState.mcpServers.find((item) => item.serverId === serverId);
    if (!health || !server) {
      return errorResponse('MCP_SERVER_NOT_FOUND', 'MCP server not found', 404);
    }
    server.status = health.status;
    server.lastHealthCheck = health.checkedAt;
    return HttpResponse.json(health);
  }),

  http.get(`${BASE_URL}/mcp/servers/:serverId/tools`, ({ params }) => {
    const serverId = params.serverId as string;
    return HttpResponse.json({
      serverId,
      tools: mockState.mcpTools[serverId] || [],
    });
  }),

  http.get(`${BASE_URL}/mcp/servers/:serverId/resources`, ({ params }) => {
    const serverId = params.serverId as string;
    return HttpResponse.json({
      serverId,
      resources: mockState.mcpResources[serverId] || [],
    });
  }),

  http.get(`${BASE_URL}/mcp/servers/:serverId/prompts`, ({ params }) => {
    const serverId = params.serverId as string;
    return HttpResponse.json({
      serverId,
      prompts: mockState.mcpPrompts[serverId] || [],
    });
  }),

  http.get(`${BASE_URL}/mcp/hydra/health`, () => HttpResponse.json(mockState.hydraMcpHealth)),

  http.get(`${BASE_URL}/mcp/hydra/tools`, () =>
    HttpResponse.json({
      serverId: 'hydra-mcp',
      tools: mockState.hydraMcpTools,
    })
  ),

  http.get(`${BASE_URL}/mcp/hydra/prompts`, () =>
    HttpResponse.json({
      serverId: 'hydra-mcp',
      prompts: mockState.hydraMcpPrompts,
    })
  ),

  http.get(`${BASE_URL}/settings`, () => HttpResponse.json(mockState.userSettings)),

  http.put(`${BASE_URL}/settings`, async ({ request }) => {
    const body = (await request.json()) as Partial<typeof mockState.userSettings>;
    mockState.userSettings = {
      ...mockState.userSettings,
      ...body,
      ui: {
        ...mockState.userSettings.ui,
        ...(body.ui || {}),
      },
      views: {
        ...mockState.userSettings.views,
        ...(body.views || {}),
      },
      notifications: {
        ...mockState.userSettings.notifications,
        ...(body.notifications || {}),
      },
      updatedAt: new Date().toISOString(),
    };
    return HttpResponse.json(mockState.userSettings);
  }),

  http.get(`${BASE_URL}/settings/system`, () => HttpResponse.json(mockState.systemSettings)),

  http.put(`${BASE_URL}/settings/system`, async ({ request }) => {
    const body = (await request.json()) as Partial<typeof mockState.systemSettings>;
    mockState.systemSettings = {
      ...mockState.systemSettings,
      ...body,
      smtp: {
        ...mockState.systemSettings.smtp,
        ...(body.smtp || {}),
      },
      objectStorage: {
        ...mockState.systemSettings.objectStorage,
        ...(body.objectStorage || {}),
      },
      defaults: {
        ...mockState.systemSettings.defaults,
        ...(body.defaults || {}),
      },
      updatedAt: new Date().toISOString(),
    };
    return HttpResponse.json(mockState.systemSettings);
  }),

  http.get(`${BASE_URL}/ai/global-keys`, () =>
    HttpResponse.json({
      keys: mockState.globalKeys,
    })
  ),

  http.get(`${BASE_URL}/ai/global-keys/:providerType`, ({ params }) => {
    const key = mockState.globalKeys.find((item) => item.providerType === params.providerType);
    if (!key) {
      return errorResponse('GLOBAL_KEY_NOT_FOUND', 'Global key not found', 404);
    }
    return HttpResponse.json(key);
  }),

  http.put(`${BASE_URL}/ai/global-keys/:providerType`, async ({ params, request }) => {
    const providerType = params.providerType as keyof typeof mockState.providerModels;
    const body = (await request.json()) as { scopes?: string[] };
    const existing = mockState.globalKeys.find((item) => item.providerType === providerType);
    if (existing) {
      existing.apiKeySet = true;
      existing.scopes = (body.scopes || existing.scopes) as typeof existing.scopes;
      existing.updatedAt = new Date().toISOString();
      return HttpResponse.json(existing);
    }
    const created = {
      providerType,
      apiKeyLast4: '9999',
      apiKeySet: true,
      scopes: (body.scopes || ['chat']) as typeof mockState.globalKeys[number]['scopes'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      isValid: true,
      lastValidatedAt: new Date().toISOString(),
    };
    mockState.globalKeys.push(created);
    return HttpResponse.json(created);
  }),

  http.delete(`${BASE_URL}/ai/global-keys/:providerType`, ({ params }) => {
    mockState.globalKeys = mockState.globalKeys.filter(
      (item) => item.providerType !== params.providerType
    );
    return HttpResponse.json({ deleted: true, providerType: params.providerType });
  }),

  http.post(`${BASE_URL}/ai/global-keys/:providerType/validate`, ({ params }) =>
    HttpResponse.json({
      providerType: params.providerType,
      isValid: true,
      message: 'Global key validated successfully',
      validatedAt: new Date().toISOString(),
    })
  ),

  http.get(`${BASE_URL}/ai/providers/:providerType/models`, ({ params }) => {
    const providerType = params.providerType as keyof typeof mockState.providerModels;
    return HttpResponse.json({
      models: mockState.providerModels[providerType] || [],
      provider: providerType,
      fetchedAt: new Date().toISOString(),
      cached: true,
    });
  }),
];

type ChatMessage = {
  role: 'user' | 'assistant' | 'system' | 'tool';
};

type MCPServer = (typeof mockState.mcpServers)[number];
