import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';

export type MCPServerCategory =
  | 'infrastructure'
  | 'monitoring'
  | 'version-control'
  | 'databases'
  | 'cloud'
  | 'development'
  | 'other';

export type MCPAuthType = 'none' | 'api_key' | 'bearer';
export type MCPServerStatus = 'unknown' | 'healthy' | 'unhealthy';

export interface MCPServerResponse {
  serverId: string;
  name: string;
  endpoint: string;
  description?: string;
  category: MCPServerCategory;
  authType: MCPAuthType;
  authConfigured: boolean;
  enabled: boolean;
  status: MCPServerStatus;
  lastHealthCheck?: string | null;
  docsUrl?: string | null;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
}

export interface MCPServerListResponse {
  servers: MCPServerResponse[];
  total: number;
}

export interface MCPServerCreate {
  name: string;
  endpoint: string;
  description?: string;
  category?: MCPServerCategory;
  authType?: MCPAuthType;
  authValue?: string;
  enabled?: boolean;
  docsUrl?: string;
}

export interface MCPServerUpdate {
  name?: string;
  endpoint?: string;
  description?: string;
  category?: MCPServerCategory;
  authType?: MCPAuthType;
  authValue?: string;
  enabled?: boolean;
  docsUrl?: string;
}

export interface MCPHealthResponse {
  serverId: string;
  status: MCPServerStatus;
  message: string;
  checkedAt: string;
  tools?: string[];
  resources?: string[];
}

export interface MCPToolInfo {
  name: string;
  description?: string | null;
}

export interface MCPToolsResponse {
  serverId: string;
  tools: MCPToolInfo[];
}

export interface MCPResourceInfo {
  uri: string;
  name?: string | null;
  description?: string | null;
  mimeType?: string | null;
}

export interface MCPResourcesResponse {
  serverId: string;
  resources: MCPResourceInfo[];
}

export function useMCPServers(params?: { category?: MCPServerCategory; enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.mcp.servers(),
    queryFn: async () => {
      const response = await apiClient.get<MCPServerListResponse>('/mcp/servers', {
        params: {
          category: params?.category,
          enabled: params?.enabled,
        },
      });
      return response.data;
    },
  });
}

export function useMCPServer(serverId: string) {
  return useQuery({
    queryKey: queryKeys.mcp.serverStatus(serverId),
    queryFn: async () => {
      const response = await apiClient.get<MCPServerResponse>(`/mcp/servers/${serverId}`);
      return response.data;
    },
    enabled: !!serverId,
  });
}

export function useCreateMCPServer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: MCPServerCreate) => {
      const response = await apiClient.post<MCPServerResponse>('/mcp/servers', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.servers() });
    },
  });
}

export function useUpdateMCPServer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ serverId, data }: { serverId: string; data: MCPServerUpdate }) => {
      const response = await apiClient.put<MCPServerResponse>(
        `/mcp/servers/${serverId}`,
        data
      );
      return response.data;
    },
    onSuccess: (_data, { serverId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.serverStatus(serverId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.servers() });
    },
  });
}

export function useDeleteMCPServer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (serverId: string) => {
      const response = await apiClient.delete(`/mcp/servers/${serverId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.servers() });
    },
  });
}

export function useMCPServerHealth(serverId: string) {
  return useQuery({
    queryKey: [...queryKeys.mcp.serverStatus(serverId), 'health'],
    queryFn: async () => {
      const response = await apiClient.get<MCPHealthResponse>(
        `/mcp/servers/${serverId}/health`
      );
      return response.data;
    },
    enabled: !!serverId,
    refetchInterval: 30000,
  });
}

export function useCheckMCPServerHealth() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (serverId: string) => {
      const response = await apiClient.get<MCPHealthResponse>(
        `/mcp/servers/${serverId}/health`
      );
      return response.data;
    },
    onSuccess: (_data, serverId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.serverStatus(serverId) });
    },
  });
}

export function useMCPServerTools(serverId: string) {
  return useQuery({
    queryKey: queryKeys.mcp.tools(serverId),
    queryFn: async () => {
      const response = await apiClient.get<MCPToolsResponse>(
        `/mcp/servers/${serverId}/tools`
      );
      return response.data;
    },
    enabled: !!serverId,
  });
}

export function useMCPServerResources(serverId: string) {
  return useQuery({
    queryKey: queryKeys.mcp.resources(serverId),
    queryFn: async () => {
      const response = await apiClient.get<MCPResourcesResponse>(
        `/mcp/servers/${serverId}/resources`
      );
      return response.data;
    },
    enabled: !!serverId,
  });
}
