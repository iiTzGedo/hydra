/**
 * MCP (Model Context Protocol) types for Hydra Web
 */

/**
 * MCP Server configuration
 */
export interface MCPServer {
  id: string;
  name: string;
  description: string;
  type: 'builtin' | 'remote' | 'custom';
  status: 'connected' | 'disconnected' | 'error';
  endpoint?: string; // HTTP endpoint URL for health/tools/resources
  wsEndpoint?: string; // WebSocket endpoint URL for streaming
  category: MCPServerCategory;
  icon?: string;
  docsUrl?: string;
  tools?: (MCPTool | string)[]; // Can be full tool objects or just names from health check
  resources?: (MCPResource | string)[]; // Can be full resource objects or just URIs from health check
  lastConnected?: Date;
  error?: string;
}

/**
 * MCP Server category for grouping in the marketplace
 */
export type MCPServerCategory =
  | 'infrastructure'
  | 'monitoring'
  | 'version-control'
  | 'databases'
  | 'cloud'
  | 'development'
  | 'other';

/**
 * MCP Tool definition
 */
export interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

/**
 * MCP Resource definition
 */
export interface MCPResource {
  uri: string;
  name: string;
  description?: string;
  mimeType?: string;
}

/**
 * LLM Provider configuration
 */
export interface LLMProvider {
  id: string;
  name: string;
  type: 'openai' | 'anthropic' | 'ollama' | 'custom';
  apiKey?: string;
  baseUrl?: string;
  model: string;
  isConfigured: boolean;
}

/**
 * Chat message in the MCP chat interface
 */
export interface MCPChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  toolCalls?: MCPToolCall[];
  error?: boolean;
  pending?: boolean;
}

/**
 * Tool call made by the LLM
 */
export interface MCPToolCall {
  id: string;
  serverId: string;
  serverName: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  error?: string;
  status: 'pending' | 'success' | 'error';
}

/**
 * Chat project for organizing conversations
 */
export interface ChatProject {
  id: string;
  name: string;
  createdAt: Date;
  updatedAt: Date;
}

/**
 * MCP Chat session
 */
export interface MCPChatSession {
  id: string;
  name: string;
  projectId?: string; // Optional: if set, belongs to a project; otherwise standalone
  messages: MCPChatMessage[];
  connectedServers: string[];
  llmProvider: string;
  createdAt: Date;
  updatedAt: Date;
}

/**
 * Suggested MCP servers for the marketplace
 */
export interface SuggestedMCPServer {
  id: string;
  name: string;
  description: string;
  category: MCPServerCategory;
  icon: string;
  docsUrl: string;
  repoUrl?: string;
  installCommand?: string;
  features: string[];
  useCases: string[];
  isPopular?: boolean;
}

/**
 * MCP Client state
 */
export interface MCPClientState {
  servers: MCPServer[];
  activeSessions: MCPChatSession[];
  currentSessionId: string | null;
  llmProviders: LLMProvider[];
  activeLLMProvider: string | null;
  isConnecting: boolean;
  error: string | null;
}

/**
 * Send message request
 */
export interface SendMessageRequest {
  sessionId: string;
  content: string;
  serverIds?: string[];
}

/**
 * Send message response
 */
export interface SendMessageResponse {
  message: MCPChatMessage;
  toolCalls?: MCPToolCall[];
}
