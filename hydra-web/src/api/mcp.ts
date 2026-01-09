/**
 * MCP (Model Context Protocol) API hooks
 * Manages MCP server connections and tool execution
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';

// Types based on backend models
export interface MCPServer {
  serverId: string;
  name: string;
  url: string;
  category: string;
  enabled: boolean;
  status?: string;
  lastConnectedAt?: string;
  tools?: MCPTool[];
  createdAt: string;
  updatedAt?: string;
}

export interface MCPTool {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

export interface MCPServerCreate {
  name: string;
  url: string;
  category: string;
  enabled?: boolean;
  config?: Record<string, unknown>;
}

export interface MCPServerUpdate {
  name?: string;
  url?: string;
  enabled?: boolean;
  config?: Record<string, unknown>;
}

export interface MCPHealthResponse {
  status: 'healthy' | 'unhealthy' | 'unknown';
  latencyMs?: number;
  error?: string;
  checkedAt: string;
}

export interface MCPToolsResponse {
  serverId: string;
  tools: MCPTool[];
  fetchedAt: string;
}

export interface MCPServerListResponse {
  servers: MCPServer[];
  total: number;
}

// List MCP servers
export function useMCPServers(params?: { category?: string; enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.mcp.servers(),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<MCPServerListResponse>>('/mcp/servers', {
        params: {
          category: params?.category,
          enabled: params?.enabled,
        },
      });
      return response.data.data;
    },
  });
}

// Get single MCP server
export function useMCPServer(serverId: string) {
  return useQuery({
    queryKey: queryKeys.mcp.serverStatus(serverId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<MCPServer>>(`/mcp/servers/${serverId}`);
      return response.data.data;
    },
    enabled: !!serverId,
  });
}

// Create MCP server
export function useCreateMCPServer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: MCPServerCreate) => {
      const response = await apiClient.post<ApiResponse<MCPServer>>('/mcp/servers', data);
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.servers() });
    },
  });
}

// Update MCP server
export function useUpdateMCPServer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ serverId, data }: { serverId: string; data: MCPServerUpdate }) => {
      const response = await apiClient.put<ApiResponse<MCPServer>>(
        `/mcp/servers/${serverId}`,
        data
      );
      return response.data.data;
    },
    onSuccess: (_data, { serverId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.serverStatus(serverId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.servers() });
    },
  });
}

// Delete MCP server
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

// Check MCP server health
export function useMCPServerHealth(serverId: string) {
  return useQuery({
    queryKey: [...queryKeys.mcp.serverStatus(serverId), 'health'],
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<MCPHealthResponse>>(
        `/mcp/servers/${serverId}/health`
      );
      return response.data.data;
    },
    enabled: !!serverId,
    refetchInterval: 30000, // Refetch every 30 seconds
  });
}

// Check health mutation (for manual refresh)
export function useCheckMCPServerHealth() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (serverId: string) => {
      const response = await apiClient.get<ApiResponse<MCPHealthResponse>>(
        `/mcp/servers/${serverId}/health`
      );
      return response.data.data;
    },
    onSuccess: (_data, serverId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mcp.serverStatus(serverId) });
    },
  });
}

// List MCP server tools
export function useMCPServerTools(serverId: string) {
  return useQuery({
    queryKey: queryKeys.mcp.tools(serverId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<MCPToolsResponse>>(
        `/mcp/servers/${serverId}/tools`
      );
      return response.data.data;
    },
    enabled: !!serverId,
  });
}

// List MCP server resources
export function useMCPServerResources(serverId: string) {
  return useQuery({
    queryKey: queryKeys.mcp.resources(serverId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<{ resources: unknown[] }>>(
        `/mcp/servers/${serverId}/resources`
      );
      return response.data.data;
    },
    enabled: !!serverId,
  });
}

// MCP Chat - Send message with tool support
export interface MCPChatRequest {
  message: string;
  sessionId?: string;
  connectedServers: string[];
  llmProvider: {
    type: 'anthropic' | 'openai' | 'ollama' | 'custom';
    model: string;
    apiKey?: string;
    baseUrl?: string;
  };
}

export interface MCPChatToolCall {
  id: string;
  serverId: string;
  serverName: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  error?: string;
  status: 'pending' | 'success' | 'error';
}

export interface MCPChatResponse {
  message: string;
  role: 'assistant';
  toolCalls?: MCPChatToolCall[];
}

export function useSendMCPMessage() {
  return useMutation({
    mutationFn: async (data: MCPChatRequest) => {
      const response = await apiClient.post<ApiResponse<MCPChatResponse>>('/mcp/chat', data);
      return response.data.data;
    },
  });
}
