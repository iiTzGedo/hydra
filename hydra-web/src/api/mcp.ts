/**
 * MCP API hooks for interacting with MCP servers
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import type { MCPTool, MCPResource, MCPToolCall } from '@/types/mcp';

interface MCPServerInfo {
  name: string;
  version: string;
  tools: MCPTool[];
  resources: MCPResource[];
}

interface MCPToolCallRequest {
  toolName: string;
  arguments: Record<string, unknown>;
}

interface MCPToolCallResponse {
  result: unknown;
  error?: string;
}

interface MCPResourceReadRequest {
  uri: string;
}

interface MCPResourceReadResponse {
  contents: Array<{
    uri: string;
    mimeType?: string;
    text?: string;
    blob?: string;
  }>;
}

interface MCPChatRequest {
  messages: Array<{
    role: 'user' | 'assistant' | 'system';
    content: string;
  }>;
  tools?: MCPTool[];
  model?: string;
}

interface MCPChatResponse {
  content: string;
  toolCalls?: MCPToolCall[];
  usage?: {
    inputTokens: number;
    outputTokens: number;
  };
}

/**
 * Get Hydra MCP server info (tools and resources)
 */
export function useHydraMCPInfo() {
  return useQuery({
    queryKey: queryKeys.mcp.servers(),
    queryFn: async () => {
      // Connect to Hydra MCP via the API
      // The API proxies to the MCP server
      const response = await apiClient.get<ApiResponse<MCPServerInfo>>('/mcp/info');
      return response.data.data;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * Get available tools from Hydra MCP
 */
export function useHydraMCPTools() {
  return useQuery({
    queryKey: queryKeys.mcp.tools('hydra-mcp'),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<MCPTool[]>>('/mcp/tools');
      return response.data.data;
    },
    staleTime: 1000 * 60 * 5,
  });
}

/**
 * Get available resources from Hydra MCP
 */
export function useHydraMCPResources() {
  return useQuery({
    queryKey: queryKeys.mcp.resources('hydra-mcp'),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<MCPResource[]>>('/mcp/resources');
      return response.data.data;
    },
    staleTime: 1000 * 60 * 5,
  });
}

/**
 * Call a tool on Hydra MCP
 */
export function useHydraMCPToolCall() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: MCPToolCallRequest) => {
      const response = await apiClient.post<ApiResponse<MCPToolCallResponse>>(
        '/mcp/tools/call',
        request
      );
      return response.data.data;
    },
    onSuccess: () => {
      // Invalidate relevant queries based on the tool called
      queryClient.invalidateQueries({ queryKey: queryKeys.nodes.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.services.all });
    },
  });
}

/**
 * Read a resource from Hydra MCP
 */
export function useHydraMCPResourceRead() {
  return useMutation({
    mutationFn: async (request: MCPResourceReadRequest) => {
      const response = await apiClient.post<ApiResponse<MCPResourceReadResponse>>(
        '/mcp/resources/read',
        request
      );
      return response.data.data;
    },
  });
}

/**
 * Send a chat message with MCP tool support
 * This uses the backend to:
 * 1. Forward the message to the configured LLM
 * 2. Handle tool calls from the LLM
 * 3. Execute tools via MCP
 * 4. Return the final response
 */
export function useMCPChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: MCPChatRequest) => {
      const response = await apiClient.post<ApiResponse<MCPChatResponse>>('/mcp/chat', request);
      return response.data.data;
    },
    onSuccess: () => {
      // Invalidate data that might have been modified by tool calls
      queryClient.invalidateQueries({ queryKey: queryKeys.nodes.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.services.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.networks.all });
    },
  });
}

/**
 * Check MCP server status
 */
export function useMCPServerStatus(serverId: string) {
  return useQuery({
    queryKey: queryKeys.mcp.serverStatus(serverId),
    queryFn: async () => {
      if (serverId === 'hydra-mcp') {
        // For built-in server, check via API health endpoint
        try {
          await apiClient.get('/mcp/health');
          return { connected: true };
        } catch {
          return { connected: false };
        }
      }
      // For external servers, we'd need different logic
      return { connected: false };
    },
    refetchInterval: 30000, // Check every 30 seconds
  });
}
