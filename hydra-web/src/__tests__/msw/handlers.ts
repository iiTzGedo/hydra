import { http, HttpResponse } from 'msw';

const BASE_URL = 'http://localhost:8080/api/v1';

// Mock data
const mockNodes = [
  {
    nodeId: 'proxmox-01',
    displayName: 'Proxmox Server 01',
    class: 'compute',
    type: 'bare-metal',
    kind: 'host',
    status: 'active',
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
    selectors: [
      {
        field: 'tags',
        operator: 'contains',
        value: 'production',
      },
    ],
    tags: ['environment:production'],
    memberCount: 5,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-10T10:00:00Z',
  },
  {
    groupId: 'grp-web-services',
    name: 'Web Services',
    description: 'All web-related services',
    types: ['service'],
    selectors: [
      {
        field: 'tags',
        operator: 'contains',
        value: 'web',
      },
    ],
    tags: ['category:web'],
    memberCount: 3,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-12T14:00:00Z',
  },
];

const mockGroupDetail = {
  ...mockGroups[0],
  parentGroupId: null,
  metadata: {
    owner: 'ops-team',
  },
};

// Mock auth data
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

export const handlers = [
  // Auth endpoints
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

    return HttpResponse.json(
      {
        error: {
          code: 'INVALID_CREDENTIALS',
          message: 'Invalid username or password',
        },
      },
      { status: 401 }
    );
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
      return HttpResponse.json(
        {
          error: {
            code: 'USER_ALREADY_EXISTS',
            message: 'Username already exists',
          },
        },
        { status: 409 }
      );
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

  http.get(`${BASE_URL}/auth/me`, () => {
    return HttpResponse.json({
      type: 'user',
      userId: mockUser.userId,
      username: mockUser.username,
      email: mockUser.email,
      role: mockUser.role,
      permissions: mockUser.permissions,
    });
  }),

  http.post(`${BASE_URL}/auth/refresh`, async ({ request }) => {
    const body = (await request.json()) as { refreshToken: string };

    if (body.refreshToken === mockRefreshToken) {
      return HttpResponse.json({
        accessToken: 'new-access-token-def456',
        expiresIn: 3600,
        tokenType: 'Bearer',
      });
    }

    return HttpResponse.json(
      {
        error: {
          code: 'INVALID_REFRESH_TOKEN',
          message: 'Invalid or expired refresh token',
        },
      },
      { status: 401 }
    );
  }),

  http.post(`${BASE_URL}/auth/logout`, () => {
    return HttpResponse.json({
      message: 'Successfully logged out',
    });
  }),

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

    return HttpResponse.json(
      {
        error: {
          code: 'INVALID_RESET_TOKEN',
          message: 'Invalid or expired reset token',
        },
      },
      { status: 400 }
    );
  }),

  http.post(`${BASE_URL}/auth/password/change`, async ({ request }) => {
    const body = (await request.json()) as { currentPassword: string; newPassword: string };

    if (body.currentPassword === 'wrong-password') {
      return HttpResponse.json(
        {
          error: {
            code: 'INVALID_CURRENT_PASSWORD',
            message: 'Current password is incorrect',
          },
        },
        { status: 400 }
      );
    }

    return HttpResponse.json({
      message: 'Password successfully changed',
    });
  }),

  http.get(`${BASE_URL}/auth/approvals`, ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '20', 10);
    const offset = parseInt(url.searchParams.get('offset') || '0', 10);

    return HttpResponse.json({
      pendingUsers: mockPendingUsers.slice(offset, offset + limit),
      total: mockPendingUsers.length,
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

  http.delete(`${BASE_URL}/auth/approvals/:userId`, ({ params }) => {
    return HttpResponse.json({
      message: `User ${params.userId} rejected successfully`,
    });
  }),

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

  http.get(`${BASE_URL}/auth/apikeys`, () => {
    return HttpResponse.json({
      apiKeys: mockApiKeys,
      total: mockApiKeys.length,
    });
  }),

  http.delete(`${BASE_URL}/auth/apikeys/:keyId`, ({ params }) => {
    return HttpResponse.json({
      keyId: params.keyId,
      revoked: true,
      revokedAt: new Date().toISOString(),
    });
  }),

  // Nodes endpoints
  http.get(`${BASE_URL}/nodes`, ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '20', 10);
    const offset = parseInt(url.searchParams.get('offset') || '0', 10);

    return HttpResponse.json({
      data: mockNodes.slice(offset, offset + limit),
      meta: {
        total: mockNodes.length,
        limit,
        offset,
      },
    });
  }),

  http.get(`${BASE_URL}/nodes/:nodeId`, ({ params }) => {
    const { nodeId } = params;
    const node = nodeId === 'proxmox-01' ? mockNodeDetail : null;

    if (!node) {
      return HttpResponse.json(
        {
          error: {
            code: 'NODE_NOT_FOUND',
            message: 'Node not found',
          },
        },
        { status: 404 }
      );
    }

    return HttpResponse.json({ data: node });
  }),

  http.patch(`${BASE_URL}/nodes/:nodeId`, async ({ request, params }) => {
    const { nodeId } = params;
    const updates = (await request.json()) as Record<string, unknown>;

    return HttpResponse.json({
      data: {
        ...mockNodeDetail,
        nodeId: nodeId as string,
        ...updates,
        updatedAt: new Date().toISOString(),
      },
    });
  }),

  http.delete(`${BASE_URL}/nodes/:nodeId`, ({ params }) => {
    const { nodeId } = params;

    return HttpResponse.json({
      data: {
        ...mockNodeDetail,
        nodeId: nodeId as string,
        status: 'archived',
        archivedAt: new Date().toISOString(),
      },
    });
  }),

  // Services endpoints
  http.get(`${BASE_URL}/services`, ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '20', 10);
    const offset = parseInt(url.searchParams.get('offset') || '0', 10);

    return HttpResponse.json({
      data: mockServices.slice(offset, offset + limit),
      meta: {
        total: mockServices.length,
        limit,
        offset,
      },
    });
  }),

  http.get(`${BASE_URL}/services/:serviceId`, ({ params }) => {
    const { serviceId } = params;
    const service = serviceId === 'svc-nginx-a1b2' ? mockServiceDetail : null;

    if (!service) {
      return HttpResponse.json(
        {
          error: {
            code: 'SERVICE_NOT_FOUND',
            message: 'Service not found',
          },
        },
        { status: 404 }
      );
    }

    return HttpResponse.json({ data: service });
  }),

  // Networks endpoints
  http.get(`${BASE_URL}/networks`, ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '20', 10);
    const offset = parseInt(url.searchParams.get('offset') || '0', 10);

    return HttpResponse.json({
      data: mockNetworks.slice(offset, offset + limit),
      meta: {
        total: mockNetworks.length,
        limit,
        offset,
      },
    });
  }),

  http.get(`${BASE_URL}/networks/:networkId`, ({ params }) => {
    const { networkId } = params;
    const network = networkId === 'net-lan-192-168-0' ? mockNetworkDetail : null;

    if (!network) {
      return HttpResponse.json(
        {
          error: {
            code: 'NETWORK_NOT_FOUND',
            message: 'Network not found',
          },
        },
        { status: 404 }
      );
    }

    return HttpResponse.json({ data: network });
  }),

  // Groups endpoints
  http.get(`${BASE_URL}/groups`, ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '20', 10);
    const offset = parseInt(url.searchParams.get('offset') || '0', 10);

    return HttpResponse.json({
      data: mockGroups.slice(offset, offset + limit),
      meta: {
        total: mockGroups.length,
        limit,
        offset,
      },
    });
  }),

  http.get(`${BASE_URL}/groups/:groupId`, ({ params }) => {
    const { groupId } = params;
    const group = groupId === 'grp-production' ? mockGroupDetail : null;

    if (!group) {
      return HttpResponse.json(
        {
          error: {
            code: 'GROUP_NOT_FOUND',
            message: 'Group not found',
          },
        },
        { status: 404 }
      );
    }

    return HttpResponse.json({ data: group });
  }),
];
