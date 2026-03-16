import type {
  ChatMessageResponse,
  ChatProjectResponse,
  ChatSessionResponse,
  SessionContextResponse,
} from '@/api/chat';
import type {
  GlobalAPIKey,
  LLMModel,
  LLMProviderResponse,
  LLMProviderType,
} from '@/api/ai';
import type {
  HydraMCPHealthResponse,
  MCPHealthResponse,
  MCPPromptInfo,
  MCPResourceInfo,
  MCPServerResponse,
  MCPToolInfo,
} from '@/api/mcp';
import type { GroupMembersResponse } from '@/types/group';
import type { Profile, ProfileDiff, ProfileSummary } from '@/types/profile';
import type { SystemSettingsResponse, UserSettingsResponse } from '@/types/settings';
import type { Topology, TopologyDiffResponse, SubgraphResponse } from '@/types/topology';
import type { UserSummary } from '@/types/user';

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

const ISO_NOW = '2026-03-09T12:00:00Z';
const ISO_LATER = '2026-03-09T12:30:00Z';

export interface MockState {
  chatProjects: ChatProjectResponse[];
  chatSessions: ChatSessionResponse[];
  chatMessages: Record<string, ChatMessageResponse[]>;
  sessionContexts: Record<string, SessionContextResponse>;
  mcpServers: MCPServerResponse[];
  mcpHealth: Record<string, MCPHealthResponse>;
  mcpTools: Record<string, MCPToolInfo[]>;
  mcpResources: Record<string, MCPResourceInfo[]>;
  mcpPrompts: Record<string, MCPPromptInfo[]>;
  hydraMcpHealth: HydraMCPHealthResponse;
  hydraMcpTools: MCPToolInfo[];
  hydraMcpPrompts: MCPPromptInfo[];
  groupMembers: Record<string, GroupMembersResponse>;
  profileSummaries: Record<string, ProfileSummary[]>;
  profiles: Record<string, Profile>;
  profileDiffs: Record<string, ProfileDiff>;
  topologies: Topology[];
  topologyDiff: TopologyDiffResponse;
  subgraphs: Record<string, SubgraphResponse>;
  users: UserSummary[];
  userSettings: UserSettingsResponse;
  systemSettings: SystemSettingsResponse;
  llmProviders: LLMProviderResponse[];
  globalKeys: GlobalAPIKey[];
  providerModels: Record<LLMProviderType, LLMModel[]>;
}

function createUsers(): UserSummary[] {
  return [
    {
      userId: 'user-001',
      username: 'system_admin',
      email: 'admin@example.com',
      role: 'admin',
      status: 'active',
      createdAt: '2026-01-01T08:00:00Z',
      lastLogin: '2026-03-09T08:00:00Z',
    },
    {
      userId: 'user-002',
      username: 'ops_lead',
      email: 'ops@example.com',
      role: 'operator',
      status: 'active',
      createdAt: '2026-01-03T08:00:00Z',
      lastLogin: '2026-03-08T08:00:00Z',
    },
    {
      userId: 'user-003',
      username: 'viewer_one',
      email: 'viewer1@example.com',
      role: 'viewer',
      status: 'active',
      createdAt: '2026-01-05T08:00:00Z',
      lastLogin: '2026-03-07T08:00:00Z',
    },
    {
      userId: 'user-004',
      username: 'viewer_two',
      email: 'viewer2@example.com',
      role: 'viewer',
      status: 'active',
      createdAt: '2026-01-06T08:00:00Z',
      lastLogin: '2026-03-06T08:00:00Z',
    },
    {
      userId: 'user-005',
      username: 'family_room',
      email: 'family@example.com',
      role: 'family',
      status: 'active',
      createdAt: '2026-01-07T08:00:00Z',
      lastLogin: '2026-03-05T08:00:00Z',
    },
    {
      userId: 'user-006',
      username: 'staging_user',
      email: 'staging@example.com',
      role: 'viewer',
      status: 'inactive',
      createdAt: '2026-01-08T08:00:00Z',
      lastLogin: '2026-02-28T08:00:00Z',
    },
    {
      userId: 'user-007',
      username: 'auditor',
      email: 'auditor@example.com',
      role: 'viewer',
      status: 'active',
      createdAt: '2026-01-10T08:00:00Z',
      lastLogin: '2026-03-04T08:00:00Z',
    },
    {
      userId: 'user-008',
      username: 'docs_admin',
      email: 'docs@example.com',
      role: 'admin',
      status: 'active',
      createdAt: '2026-01-12T08:00:00Z',
      lastLogin: '2026-03-03T08:00:00Z',
    },
    {
      userId: 'user-009',
      username: 'night_shift',
      email: 'night@example.com',
      role: 'operator',
      status: 'active',
      createdAt: '2026-01-14T08:00:00Z',
      lastLogin: '2026-03-02T08:00:00Z',
    },
    {
      userId: 'user-010',
      username: 'guest_reader',
      email: 'guest@example.com',
      role: 'viewer',
      status: 'active',
      createdAt: '2026-01-16T08:00:00Z',
      lastLogin: '2026-03-01T08:00:00Z',
    },
    {
      userId: 'user-011',
      username: 'archived_user',
      email: 'archived@example.com',
      role: 'viewer',
      status: 'archived',
      createdAt: '2026-01-18T08:00:00Z',
      lastLogin: '2026-02-20T08:00:00Z',
    },
    {
      userId: 'user-012',
      username: 'search_match',
      email: 'search@example.com',
      role: 'viewer',
      status: 'active',
      createdAt: '2026-01-20T08:00:00Z',
      lastLogin: '2026-03-09T07:30:00Z',
    },
  ];
}

function createInitialState(): MockState {
  const chatProjects: ChatProjectResponse[] = [
    {
      projectId: 'proj-homelab',
      name: 'Homelab Ops',
      description: 'Main infrastructure conversations',
      sessionCount: 1,
      ownerId: 'user-001',
      createdAt: '2026-03-01T08:00:00Z',
      updatedAt: '2026-03-08T08:00:00Z',
    },
    {
      projectId: 'proj-research',
      name: 'Research',
      description: 'Experimentation',
      sessionCount: 1,
      ownerId: 'user-001',
      createdAt: '2026-03-02T08:00:00Z',
      updatedAt: '2026-03-09T08:00:00Z',
    },
  ];

  const chatSessions: ChatSessionResponse[] = [
    {
      sessionId: 'sess-alpha',
      projectId: 'proj-homelab',
      title: 'Weekly review',
      status: 'active',
      messageCount: 2,
      llmProviderId: 'llm-anthropic',
      mcpServerIds: ['hydra-mcp'],
      llmConfigLocked: true,
      sessionContext: null,
      ownerId: 'user-001',
      createdAt: '2026-03-08T08:00:00Z',
      updatedAt: ISO_NOW,
      lastMessageAt: ISO_NOW,
    },
    {
      sessionId: 'sess-standalone',
      projectId: null,
      title: 'Standalone chat',
      status: 'active',
      messageCount: 1,
      llmProviderId: 'llm-ollama',
      mcpServerIds: [],
      llmConfigLocked: false,
      sessionContext: null,
      ownerId: 'user-001',
      createdAt: '2026-03-07T08:00:00Z',
      updatedAt: '2026-03-07T08:05:00Z',
      lastMessageAt: '2026-03-07T08:05:00Z',
    },
  ];

  const chatMessages: Record<string, ChatMessageResponse[]> = {
    'sess-alpha': [
      {
        messageId: 'msg-001',
        sessionId: 'sess-alpha',
        role: 'user',
        content: 'Show my infrastructure summary',
        order: 1,
        createdAt: '2026-03-08T08:00:00Z',
      },
      {
        messageId: 'msg-002',
        sessionId: 'sess-alpha',
        role: 'assistant',
        content: 'Your homelab includes two nodes and one network.',
        order: 2,
        createdAt: ISO_NOW,
      },
    ],
    'sess-standalone': [
      {
        messageId: 'msg-003',
        sessionId: 'sess-standalone',
        role: 'user',
        content: 'Hello',
        order: 1,
        createdAt: '2026-03-07T08:05:00Z',
      },
    ],
  };

  const sessionContexts: Record<string, SessionContextResponse> = {
    'sess-alpha': {
      sessionId: 'sess-alpha',
      context: {
        totalTokens: 512,
        inputTokens: 288,
        outputTokens: 224,
        estimatedCost: 0.02,
        toolCallsCount: 1,
        messageCount: 2,
        modelUsed: 'claude-3-5-sonnet',
        providerType: 'anthropic',
        thread: ['msg-001', 'msg-002'],
      },
      llmConfigLocked: true,
      lastUpdated: ISO_NOW,
    },
  };

  const mcpServers: MCPServerResponse[] = [
    {
      serverId: 'hydra-mcp',
      name: 'Hydra MCP',
      endpoint: 'http://hydra-mcp.local',
      description: 'Built-in infrastructure MCP server',
      category: 'infrastructure',
      authType: 'bearer',
      authConfigured: true,
      enabled: true,
      status: 'healthy',
      lastHealthCheck: ISO_NOW,
      docsUrl: 'https://docs.example.com/hydra-mcp',
      ownerId: 'user-001',
      createdAt: '2026-02-01T08:00:00Z',
      updatedAt: ISO_NOW,
    },
    {
      serverId: 'docker-mcp',
      name: 'Docker MCP',
      endpoint: 'http://docker-mcp.local',
      description: 'Container management server',
      category: 'development',
      authType: 'api_key',
      authConfigured: true,
      enabled: false,
      status: 'unknown',
      lastHealthCheck: null,
      docsUrl: null,
      ownerId: 'user-001',
      createdAt: '2026-02-15T08:00:00Z',
      updatedAt: '2026-03-01T08:00:00Z',
    },
  ];

  const mcpTools: Record<string, MCPToolInfo[]> = {
    'hydra-mcp': [
      { name: 'nodes.list', description: 'List nodes' },
      { name: 'services.list', description: 'List services' },
    ],
    'docker-mcp': [{ name: 'containers.ps', description: 'List containers' }],
  };

  const mcpResources: Record<string, MCPResourceInfo[]> = {
    'hydra-mcp': [
      {
        uri: 'hydra://nodes/proxmox-01',
        name: 'Proxmox Node',
        description: 'Node profile resource',
        mimeType: 'application/json',
      },
    ],
    'docker-mcp': [],
  };

  const mcpPrompts: Record<string, MCPPromptInfo[]> = {
    'hydra-mcp': [
      {
        name: 'summarize_homelab',
        description: 'Summarize the homelab',
        arguments: [{ name: 'scope', description: 'Summary scope', required: false }],
      },
    ],
    'docker-mcp': [
      {
        name: 'inspect_container',
        description: 'Inspect a container',
        arguments: [{ name: 'container', description: 'Container name', required: true }],
      },
    ],
  };

  const mcpHealth: Record<string, MCPHealthResponse> = {
    'hydra-mcp': {
      serverId: 'hydra-mcp',
      status: 'healthy',
      message: 'Hydra MCP is healthy',
      checkedAt: ISO_NOW,
      tools: mcpTools['hydra-mcp'].map((tool) => tool.name),
      resources: mcpResources['hydra-mcp'].map((resource) => resource.uri),
    },
    'docker-mcp': {
      serverId: 'docker-mcp',
      status: 'healthy',
      message: 'Docker MCP responded successfully',
      checkedAt: ISO_LATER,
      tools: mcpTools['docker-mcp'].map((tool) => tool.name),
      resources: [],
    },
  };

  const profileSummaries: Record<string, ProfileSummary[]> = {
    'proxmox-01': [
      {
        profileId: 'profile-001',
        nodeId: 'proxmox-01',
        version: 'E0-0.0.1.0',
        collectedAt: '2026-03-07T08:00:00Z',
        submittedAt: '2026-03-07T08:01:00Z',
        collectionLevel: 'neutral',
        serviceCount: 2,
      },
      {
        profileId: 'profile-002',
        nodeId: 'proxmox-01',
        version: 'E0-0.0.1.1',
        collectedAt: '2026-03-09T08:00:00Z',
        submittedAt: '2026-03-09T08:01:00Z',
        collectionLevel: 'deep',
        serviceCount: 3,
      },
    ],
  };

  const profiles: Record<string, Profile> = {
    'profile-001': {
      ...profileSummaries['proxmox-01'][0],
      agentVersion: '0.5.0',
      serviceIds: ['svc-nginx-a1b2', 'svc-mongodb-c3d4'],
      hardware: {
        cpu: { model: 'Intel Xeon', coresPhysical: 8, coresLogical: 16 },
        memory: { totalBytes: 64 * 1024 * 1024 * 1024, usedBytes: 32 * 1024 * 1024 * 1024 },
      },
      network: {
        hostname: 'proxmox-01.local',
        defaultGateway: '192.168.1.1',
        interfaces: [
          {
            name: 'eth0',
            macAddress: '00:11:22:33:44:55',
            ipv4Addresses: ['192.168.1.10'],
            state: 'up',
          },
        ],
      },
      storage: {
        totalCapacityBytes: 2 * 1024 * 1024 * 1024 * 1024,
        filesystems: [
          {
            mountPoint: '/',
            device: '/dev/nvme0n1p2',
            fsType: 'ext4',
            sizeBytes: 500 * 1024 * 1024 * 1024,
            usedBytes: 220 * 1024 * 1024 * 1024,
          },
        ],
      },
      software: {
        os: { name: 'Proxmox VE', version: '8.3', family: 'Linux' },
        packageCount: 128,
      },
      users: {
        users: [
          {
            username: 'root',
            uid: 0,
            shell: '/bin/bash',
          },
        ],
      },
    },
    'profile-002': {
      ...profileSummaries['proxmox-01'][1],
      agentVersion: '0.5.0',
      serviceIds: ['svc-nginx-a1b2', 'svc-mongodb-c3d4', 'svc-api-gateway-e5f6'],
      hardware: {
        cpu: { model: 'Intel Xeon', coresPhysical: 8, coresLogical: 16 },
        memory: { totalBytes: 64 * 1024 * 1024 * 1024, usedBytes: 36 * 1024 * 1024 * 1024 },
      },
      network: {
        hostname: 'proxmox-01.local',
        defaultGateway: '192.168.1.1',
        interfaces: [
          {
            name: 'eth0',
            macAddress: '00:11:22:33:44:55',
            ipv4Addresses: ['192.168.1.10'],
            state: 'up',
          },
        ],
      },
      storage: {
        totalCapacityBytes: 2 * 1024 * 1024 * 1024 * 1024,
        filesystems: [
          {
            mountPoint: '/',
            device: '/dev/nvme0n1p2',
            fsType: 'ext4',
            sizeBytes: 500 * 1024 * 1024 * 1024,
            usedBytes: 260 * 1024 * 1024 * 1024,
          },
        ],
      },
      software: {
        os: { name: 'Proxmox VE', version: '8.3', family: 'Linux' },
        packageCount: 140,
      },
      users: {
        users: [
          {
            username: 'root',
            uid: 0,
            shell: '/bin/bash',
          },
          {
            username: 'deploy',
            uid: 1001,
            shell: '/bin/bash',
          },
        ],
      },
    },
  };

  const profileDiff: ProfileDiff = {
    fromVersion: 'E0-0.0.1.0',
    toVersion: 'E0-0.0.1.1',
    fromProfileId: 'profile-001',
    toProfileId: 'profile-002',
    changedSections: ['storage', 'software', 'services', 'users'],
    changeSummary: {
      storage: { changed: 1 },
      software: { changed: 1 },
      services: { added: 1 },
      users: { added: 1 },
    },
    diffPercentage: 31.5,
  };

  const infrastructureTopologyLatest: Topology = {
    topologyId: 'topology-infra-002',
    mode: 'infrastructure',
    version: 2,
    generatedAt: ISO_NOW,
    validFrom: ISO_NOW,
    stats: {
      nodeCount: 3,
      edgeCount: 2,
      networkCount: 1,
      serviceCount: 0,
      computeTimeMs: 42,
    },
    graph: {
      nodes: [
        {
          id: 'node-proxmox-01',
          type: 'node',
          label: 'Proxmox Server 01',
          data: { nodeId: 'proxmox-01', class: 'compute', kind: 'host', status: 'active' },
          position: { x: 0, y: 0 },
        },
        {
          id: 'node-opnsense-gw',
          type: 'node',
          label: 'OPNsense Gateway',
          data: { nodeId: 'opnsense-gw', class: 'networking', kind: 'appliance', status: 'active' },
          position: { x: 200, y: 0 },
        },
        {
          id: 'node-sensor',
          type: 'node',
          label: 'Basement Sensor',
          data: { nodeId: 'basement-sensor', class: 'iot', kind: 'sensor', status: 'active' },
          position: { x: 400, y: 0 },
        },
      ],
      edges: [
        {
          id: 'edge-001',
          source: 'node-opnsense-gw',
          target: 'node-proxmox-01',
          type: 'network-gateway',
          label: 'gateway',
          data: {},
        },
        {
          id: 'edge-002',
          source: 'node-opnsense-gw',
          target: 'node-sensor',
          type: 'network-connection',
          label: 'wifi',
          data: {},
        },
      ],
    },
  };

  const topologies: Topology[] = [
    {
      topologyId: 'topology-infra-001',
      mode: 'infrastructure',
      version: 1,
      generatedAt: '2026-03-07T08:00:00Z',
      validFrom: '2026-03-07T08:00:00Z',
      stats: {
        nodeCount: 2,
        edgeCount: 1,
        networkCount: 1,
        serviceCount: 0,
        computeTimeMs: 40,
      },
      graph: infrastructureTopologyLatest.graph,
    },
    infrastructureTopologyLatest,
    {
      topologyId: 'topology-network-001',
      mode: 'network',
      version: 1,
      generatedAt: ISO_NOW,
      validFrom: ISO_NOW,
      stats: {
        nodeCount: 3,
        edgeCount: 2,
        networkCount: 1,
        serviceCount: 0,
        computeTimeMs: 35,
      },
      graph: {
        nodes: [
          {
            id: 'network-lan',
            type: 'network',
            label: 'LAN Network',
            data: { networkId: 'net-lan-192-168-0', class: 'network' },
            position: { x: 0, y: 0 },
          },
          {
            id: 'node-proxmox-01',
            type: 'node',
            label: 'Proxmox Server 01',
            data: { nodeId: 'proxmox-01', class: 'compute' },
            position: { x: 160, y: 0 },
          },
          {
            id: 'node-opnsense-gw',
            type: 'node',
            label: 'OPNsense Gateway',
            data: { nodeId: 'opnsense-gw', class: 'networking' },
            position: { x: 320, y: 0 },
          },
        ],
        edges: [
          {
            id: 'edge-network-001',
            source: 'network-lan',
            target: 'node-proxmox-01',
            type: 'network-connection',
            data: {},
          },
          {
            id: 'edge-network-002',
            source: 'network-lan',
            target: 'node-opnsense-gw',
            type: 'network-gateway',
            data: {},
          },
        ],
      },
    },
    {
      topologyId: 'topology-service-001',
      mode: 'service',
      version: 1,
      generatedAt: ISO_NOW,
      validFrom: ISO_NOW,
      stats: {
        nodeCount: 3,
        edgeCount: 2,
        networkCount: 0,
        serviceCount: 2,
        computeTimeMs: 33,
      },
      graph: {
        nodes: [
          {
            id: 'svc-nginx-a1b2',
            type: 'service',
            label: 'nginx',
            data: { serviceId: 'svc-nginx-a1b2', class: 'service', runtime: 'systemd' },
            position: { x: 0, y: 0 },
          },
          {
            id: 'svc-mongodb-c3d4',
            type: 'service',
            label: 'mongodb',
            data: { serviceId: 'svc-mongodb-c3d4', class: 'service', runtime: 'systemd' },
            position: { x: 160, y: 0 },
          },
          {
            id: 'node-proxmox-01',
            type: 'node',
            label: 'Proxmox Server 01',
            data: { nodeId: 'proxmox-01', class: 'compute' },
            position: { x: 320, y: 0 },
          },
        ],
        edges: [
          {
            id: 'edge-service-001',
            source: 'svc-nginx-a1b2',
            target: 'node-proxmox-01',
            type: 'service-host',
            data: {},
          },
          {
            id: 'edge-service-002',
            source: 'svc-mongodb-c3d4',
            target: 'node-proxmox-01',
            type: 'service-host',
            data: {},
          },
        ],
      },
    },
  ];

  const topologyDiff: TopologyDiffResponse = {
    from: {
      topologyId: 'topology-infra-001',
      mode: 'infrastructure',
      version: 1,
      generatedAt: '2026-03-07T08:00:00Z',
      validFrom: '2026-03-07T08:00:00Z',
      stats: {
        nodeCount: 2,
        edgeCount: 1,
        networkCount: 1,
        serviceCount: 0,
        computeTimeMs: 40,
      },
    },
    to: {
      topologyId: 'topology-infra-002',
      mode: 'infrastructure',
      version: 2,
      generatedAt: ISO_NOW,
      validFrom: ISO_NOW,
      stats: {
        nodeCount: 3,
        edgeCount: 2,
        networkCount: 1,
        serviceCount: 0,
        computeTimeMs: 42,
      },
    },
    diff: {
      nodesAdded: ['basement-sensor'],
      nodesRemoved: [],
      nodesModified: ['proxmox-01'],
      edgesAdded: ['edge-002'],
      edgesRemoved: [],
    },
    summary: {
      nodesAdded: 1,
      nodesModified: 1,
      edgesAdded: 1,
    },
  };

  const subgraphs: Record<string, SubgraphResponse> = {
    'proxmox-01': {
      centerNodeId: 'proxmox-01',
      depth: 1,
      graph: {
        nodes: [
          {
            id: 'node-proxmox-01',
            type: 'node',
            label: 'Proxmox Server 01',
            data: { nodeId: 'proxmox-01', class: 'compute' },
            position: { x: 0, y: 0 },
          },
          {
            id: 'svc-nginx-a1b2',
            type: 'service',
            label: 'nginx',
            data: { serviceId: 'svc-nginx-a1b2', class: 'service' },
            position: { x: 160, y: 0 },
          },
        ],
        edges: [
          {
            id: 'edge-subgraph-001',
            source: 'svc-nginx-a1b2',
            target: 'node-proxmox-01',
            type: 'service-host',
            data: {},
          },
        ],
      },
      stats: {
        nodeCount: 2,
        edgeCount: 1,
        serviceCount: 1,
        networkCount: 0,
      },
    },
  };

  const userSettings: UserSettingsResponse = {
    userId: 'user-001',
    ui: {
      theme: 'system',
      sidebarCollapsed: false,
      animationsEnabled: true,
    },
    views: {
      nodes: { layout: 'list', sortField: 'displayName', sortOrder: 'asc', pageSize: 20, filters: {} },
      services: { layout: 'list', sortField: 'displayName', sortOrder: 'asc', pageSize: 20, filters: {} },
      networks: { layout: 'list', sortField: 'displayName', sortOrder: 'asc', pageSize: 20, filters: {} },
      groups: { layout: 'list', sortField: 'displayName', sortOrder: 'asc', pageSize: 20, filters: {} },
      topology: { layout: 'grid', sortField: 'displayName', sortOrder: 'asc', pageSize: 20, filters: {} },
    },
    notifications: {
      emailEnabled: false,
      browserEnabled: true,
      browserMinTier: 2,
      emailMinTier: 4,
      nodeNotifications: true,
      serviceNotifications: true,
      profileNotifications: true,
      securityNotifications: true,
      systemNotifications: true,
      commandNotifications: true,
      quietHoursEnabled: false,
      quietHoursStart: null,
      quietHoursEnd: null,
      quietHoursMinTier: 5,
    },
    updatedAt: ISO_NOW,
  };

  const systemSettings: SystemSettingsResponse = {
    smtp: {
      enabled: false,
      host: null,
      port: 587,
      username: null,
      fromAddress: null,
      fromName: 'Hydra',
      useTls: true,
    },
    objectStorage: {
      enabled: true,
      endpoint: 'https://garage.local',
      bucket: 'hydra-bucket',
      region: 'garage',
    },
    defaults: {
      nodeStatus: 'active',
      profileRetentionDays: 30,
      sessionTimeoutMinutes: 60,
    },
    updatedAt: ISO_NOW,
    updatedBy: 'user-001',
  };

  const llmProviders: LLMProviderResponse[] = [
    {
      configId: 'llm-anthropic',
      name: 'Anthropic Primary',
      type: 'anthropic',
      apiKeyLast4: '1234',
      apiKeySet: true,
      baseUrl: null,
      model: 'claude-3-5-sonnet',
      isDefault: true,
      isValid: true,
      lastValidatedAt: ISO_NOW,
      createdBy: 'user-001',
      createdAt: '2026-02-20T08:00:00Z',
      updatedAt: ISO_NOW,
    },
    {
      configId: 'llm-ollama',
      name: 'Local Ollama',
      type: 'ollama',
      apiKeyLast4: null,
      apiKeySet: false,
      baseUrl: 'http://ollama.local:11434',
      model: 'llama3.2',
      isDefault: false,
      isValid: true,
      lastValidatedAt: ISO_NOW,
      createdBy: 'user-001',
      createdAt: '2026-02-25T08:00:00Z',
      updatedAt: ISO_NOW,
    },
  ];

  return {
    chatProjects,
    chatSessions,
    chatMessages,
    sessionContexts,
    mcpServers,
    mcpHealth,
    mcpTools,
    mcpResources,
    mcpPrompts,
    hydraMcpHealth: {
      status: 'healthy',
      message: 'Hydra MCP is healthy',
      checkedAt: ISO_NOW,
      serverName: 'Hydra MCP',
      version: '0.5.0',
      toolsCount: mcpTools['hydra-mcp'].length,
      promptsCount: mcpPrompts['hydra-mcp'].length,
      resourcesCount: mcpResources['hydra-mcp'].length,
      endpoint: 'http://hydra-mcp.local',
    },
    hydraMcpTools: mcpTools['hydra-mcp'],
    hydraMcpPrompts: mcpPrompts['hydra-mcp'],
    groupMembers: {
      'grp-production': {
        nodes: [
          {
            nodeId: 'proxmox-01',
            displayName: 'Proxmox Server 01',
            matchedSelectors: ['tags:production'],
          },
        ],
        services: [],
      },
      'grp-web-services': {
        nodes: [],
        services: [
          {
            serviceId: 'svc-nginx-a1b2',
            name: 'nginx',
            nodeId: 'proxmox-01',
            matchedSelectors: ['tags:web'],
          },
        ],
      },
    },
    profileSummaries,
    profiles,
    profileDiffs: {
      'proxmox-01::': profileDiff,
      'proxmox-01:E0-0.0.1.0:E0-0.0.1.1': profileDiff,
    },
    topologies,
    topologyDiff,
    subgraphs,
    users: createUsers(),
    userSettings,
    systemSettings,
    llmProviders,
    globalKeys: [
      {
        providerType: 'anthropic',
        apiKeyLast4: '1234',
        apiKeySet: true,
        scopes: ['chat', 'meta'],
        isValid: true,
        lastValidatedAt: ISO_NOW,
        createdAt: '2026-02-20T08:00:00Z',
        updatedAt: ISO_NOW,
      },
    ],
    providerModels: {
      anthropic: [
        {
          id: 'claude-3-5-sonnet',
          name: 'Claude 3.5 Sonnet',
          contextWindow: 200000,
          supportsTools: true,
          supportsVision: true,
          supportsReasoning: true,
          costPer1kInput: 0.003,
          costPer1kOutput: 0.015,
        },
      ],
      openai: [
        {
          id: 'gpt-4.1',
          name: 'GPT-4.1',
          contextWindow: 128000,
          supportsTools: true,
          supportsVision: true,
          supportsReasoning: true,
          costPer1kInput: 0.01,
          costPer1kOutput: 0.03,
        },
      ],
      ollama: [
        {
          id: 'llama3.2',
          name: 'Llama 3.2',
          contextWindow: 8192,
          supportsTools: false,
          supportsVision: false,
          supportsReasoning: false,
          costPer1kInput: null,
          costPer1kOutput: null,
        },
      ],
      openrouter: [
        {
          id: 'anthropic/claude-3.5-sonnet',
          name: 'Claude 3.5 Sonnet via OpenRouter',
          contextWindow: 200000,
          supportsTools: true,
          supportsVision: true,
          supportsReasoning: true,
          costPer1kInput: 0.004,
          costPer1kOutput: 0.016,
        },
      ],
    },
  };
}

export const mockState: MockState = createInitialState();

export function resetMockState() {
  Object.assign(mockState, clone(createInitialState()));
}

