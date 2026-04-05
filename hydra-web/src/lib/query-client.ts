import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      gcTime: 1000 * 60 * 30,
      retry: (failureCount, error) => {
        if (error && typeof error === 'object' && 'response' in error) {
          const status = (error as { response?: { status?: number } }).response?.status;
          if (status && status >= 400 && status < 500 && status !== 429) {
            return false;
          }
        }
        return failureCount < 3;
      },
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: false,
    },
  },
});

export const queryKeys = {
  auth: {
    all: ['auth'] as const,
    me: () => [...queryKeys.auth.all, 'me'] as const,
    approvals: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.auth.all, 'approvals', params] as const;
      }
      return [...queryKeys.auth.all, 'approvals'] as const;
    },
    tokens: () => [...queryKeys.auth.all, 'tokens'] as const,
    apiKeys: () => [...queryKeys.auth.all, 'apiKeys'] as const,
  },

  nodes: {
    all: ['nodes'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.nodes.all, 'list', params] as const;
      }
      return [...queryKeys.nodes.all, 'list'] as const;
    },
    detail: (nodeId: string) => [...queryKeys.nodes.all, 'detail', nodeId] as const,
    children: (nodeId: string) => [...queryKeys.nodes.all, 'children', nodeId] as const,
    services: (nodeId: string) => [...queryKeys.nodes.all, 'services', nodeId] as const,
    profiles: (nodeId: string) => [...queryKeys.nodes.all, 'profiles', nodeId] as const,
  },

  services: {
    all: ['services'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.services.all, 'list', params] as const;
      }
      return [...queryKeys.services.all, 'list'] as const;
    },
    detail: (serviceId: string) => [...queryKeys.services.all, 'detail', serviceId] as const,
    byNode: <T extends object = Record<string, unknown>>(nodeId: string, params?: T) => {
      if (params) {
        return [...queryKeys.services.all, 'byNode', nodeId, params] as const;
      }
      return [...queryKeys.services.all, 'byNode', nodeId] as const;
    },
  },

  networks: {
    all: ['networks'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.networks.all, 'list', params] as const;
      }
      return [...queryKeys.networks.all, 'list'] as const;
    },
    detail: (networkId: string) => [...queryKeys.networks.all, 'detail', networkId] as const,
    nodes: (networkId: string) => [...queryKeys.networks.all, 'nodes', networkId] as const,
  },

  groups: {
    all: ['groups'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.groups.all, 'list', params] as const;
      }
      return [...queryKeys.groups.all, 'list'] as const;
    },
    detail: (groupId: string) => [...queryKeys.groups.all, 'detail', groupId] as const,
    members: <T extends object = Record<string, unknown>>(groupId: string, params?: T) => {
      if (params) {
        return [...queryKeys.groups.all, 'members', groupId, params] as const;
      }
      return [...queryKeys.groups.all, 'members', groupId] as const;
    },
  },

  profiles: {
    all: ['profiles'] as const,
    detail: (profileId: string) => [...queryKeys.profiles.all, 'detail', profileId] as const,
    byNode: <T extends object = Record<string, unknown>>(nodeId: string, params?: T) => {
      if (params) {
        return [...queryKeys.profiles.all, 'byNode', nodeId, params] as const;
      }
      return [...queryKeys.profiles.all, 'byNode', nodeId] as const;
    },
    latest: (nodeId: string) => [...queryKeys.profiles.all, 'latest', nodeId] as const,
    diff: (nodeId: string, fromId?: string, toId?: string) =>
      [...queryKeys.profiles.all, 'diff', nodeId, fromId, toId] as const,
  },

  topologies: {
    all: ['topologies'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.topologies.all, 'list', params] as const;
      }
      return [...queryKeys.topologies.all, 'list'] as const;
    },
    detail: (topologyId: string) => [...queryKeys.topologies.all, 'detail', topologyId] as const,
    latest: (mode?: string) => {
      if (mode) {
        return [...queryKeys.topologies.all, 'latest', mode] as const;
      }
      return [...queryKeys.topologies.all, 'latest'] as const;
    },
    diff: (topologyId1?: string, topologyId2?: string, mode?: string) =>
      [...queryKeys.topologies.all, 'diff', topologyId1, topologyId2, mode] as const,
    subgraph: <T extends object = Record<string, unknown>>(nodeId: string, options?: T) => {
      if (options) {
        return [...queryKeys.topologies.all, 'subgraph', nodeId, options] as const;
      }
      return [...queryKeys.topologies.all, 'subgraph', nodeId] as const;
    },
  },

  timemachine: {
    all: ['timemachine'] as const,
    nodeState: (nodeId: string, timestamp: string) =>
      [...queryKeys.timemachine.all, 'nodeState', nodeId, timestamp] as const,
    topology: (timestamp: string, mode?: string) => {
      if (mode) {
        return [...queryKeys.timemachine.all, 'topology', timestamp, mode] as const;
      }
      return [...queryKeys.timemachine.all, 'topology', timestamp] as const;
    },
    timeline: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.timemachine.all, 'timeline', params] as const;
      }
      return [...queryKeys.timemachine.all, 'timeline'] as const;
    },
  },

  users: {
    all: ['users'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.users.all, 'list', params] as const;
      }
      return [...queryKeys.users.all, 'list'] as const;
    },
    detail: (userId: string) => [...queryKeys.users.all, 'detail', userId] as const,
  },

  query: {
    all: ['query'] as const,
    capacity: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.query.all, 'capacity', params] as const;
      }
      return [...queryKeys.query.all, 'capacity'] as const;
    },
    audit: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.query.all, 'audit', params] as const;
      }
      return [...queryKeys.query.all, 'audit'] as const;
    },
  },

  commands: {
    all: ['commands'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.commands.all, 'list', params] as const;
      }
      return [...queryKeys.commands.all, 'list'] as const;
    },
    detail: (commandId: string) => [...queryKeys.commands.all, 'detail', commandId] as const,
    queue: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.commands.all, 'queue', params] as const;
      }
      return [...queryKeys.commands.all, 'queue'] as const;
    },
  },

  commandCatalog: {
    all: ['commandCatalog'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.commandCatalog.all, 'list', params] as const;
      }
      return [...queryKeys.commandCatalog.all, 'list'] as const;
    },
    detail: (id: string) => [...queryKeys.commandCatalog.all, 'detail', id] as const,
  },

  health: {
    all: ['health'] as const,
    status: () => [...queryKeys.health.all, 'status'] as const,
    info: () => [...queryKeys.health.all, 'info'] as const,
  },

  settings: {
    all: ['settings'] as const,
    user: () => [...queryKeys.settings.all, 'user'] as const,
    system: () => [...queryKeys.settings.all, 'system'] as const,
  },

  mcp: {
    all: ['mcp'] as const,
    servers: () => [...queryKeys.mcp.all, 'servers'] as const,
    serverStatus: (serverId: string) => [...queryKeys.mcp.all, 'serverStatus', serverId] as const,
    tools: (serverId: string) => [...queryKeys.mcp.all, 'tools', serverId] as const,
    resources: (serverId: string) => [...queryKeys.mcp.all, 'resources', serverId] as const,
    prompts: (serverId: string) => [...queryKeys.mcp.all, 'prompts', serverId] as const,
    // Dedicated Hydra MCP keys
    hydra: {
      all: ['mcp', 'hydra'] as const,
      health: () => [...queryKeys.mcp.hydra.all, 'health'] as const,
      tools: () => [...queryKeys.mcp.hydra.all, 'tools'] as const,
      prompts: () => [...queryKeys.mcp.hydra.all, 'prompts'] as const,
    },
  },

  notifications: {
    all: ['notifications'] as const,
    list: <T extends object = Record<string, unknown>>(params?: T) => {
      if (params) {
        return [...queryKeys.notifications.all, 'list', params] as const;
      }
      return [...queryKeys.notifications.all, 'list'] as const;
    },
    stats: () => [...queryKeys.notifications.all, 'stats'] as const,
    detail: (notificationId: string) =>
      [...queryKeys.notifications.all, 'detail', notificationId] as const,
  },

  ai: {
    all: ['ai'] as const,
    models: () => [...queryKeys.ai.all, 'models'] as const,
    model: (providerId: string) => [...queryKeys.ai.all, 'model', providerId] as const,
    providerModels: (providerType: string) =>
      [...queryKeys.ai.all, 'providerModels', providerType] as const,
    globalKeys: () => [...queryKeys.ai.all, 'globalKeys'] as const,
    globalKey: (providerType: string) =>
      [...queryKeys.ai.all, 'globalKey', providerType] as const,
  },
};

export default queryClient;
