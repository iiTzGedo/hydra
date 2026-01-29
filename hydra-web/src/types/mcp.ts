export interface MCPServer {
  id: string;
  name: string;
  description: string;
  type: 'builtin' | 'remote' | 'custom';
  status: 'connected' | 'disconnected' | 'error';
  endpoint?: string;
  wsEndpoint?: string;
  category: MCPServerCategory;
  icon?: string;
  docsUrl?: string;
  tools?: (MCPTool | string)[];
  resources?: (MCPResource | string)[];
  lastConnected?: Date;
  error?: string;
}

export type MCPServerCategory =
  | 'infrastructure'
  | 'monitoring'
  | 'version-control'
  | 'databases'
  | 'cloud'
  | 'development'
  | 'other';

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface MCPResource {
  uri: string;
  name: string;
  description?: string;
  mimeType?: string;
}

export interface LLMProvider {
  id: string;
  name: string;
  type: 'openai' | 'anthropic' | 'ollama' | 'custom';
  apiKey?: string;
  baseUrl?: string;
  model: string;
  isConfigured: boolean;
}

export interface MCPChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  toolCalls?: MCPToolCall[];
  error?: boolean;
  pending?: boolean;
}

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

export interface ChatProject {
  id: string;
  name: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface MCPChatSession {
  id: string;
  name: string;
  projectId?: string;
  messages: MCPChatMessage[];
  connectedServers: string[];
  llmProvider: string;
  createdAt: Date;
  updatedAt: Date;
}

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

export interface MCPClientState {
  servers: MCPServer[];
  activeSessions: MCPChatSession[];
  currentSessionId: string | null;
  llmProviders: LLMProvider[];
  activeLLMProvider: string | null;
  isConnecting: boolean;
  error: string | null;
}

export interface SendMessageRequest {
  sessionId: string;
  content: string;
  serverIds?: string[];
}

export interface SendMessageResponse {
  message: MCPChatMessage;
  toolCalls?: MCPToolCall[];
}

// Model configuration for per-request overrides
export interface ModelConfig {
  maxTokens?: number;
  temperature?: number;
  topP?: number;
  topK?: number;
  frequencyPenalty?: number;
  presencePenalty?: number;
}

// Session token usage info returned from message_complete
export interface SessionUsage {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  contextWindow: number;
}
