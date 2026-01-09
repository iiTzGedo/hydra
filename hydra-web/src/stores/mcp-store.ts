/**
 * MCP Client Store
 * Manages MCP server connections, chat sessions, and LLM provider configuration
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { generateId } from '@/lib/utils';
import type {
  MCPServer,
  MCPChatSession,
  MCPChatMessage,
  MCPToolCall,
  LLMProvider,
  ChatProject,
} from '@/types/mcp';

const HYDRA_MCP_URL = import.meta.env.VITE_MCP_URL as string | undefined;
const HYDRA_MCP_WS_URL = import.meta.env.VITE_MCP_WS_URL as string | undefined;

interface MCPHealthResponse {
  status: string;
  transport: string;
  server: string;
  version: string;
  tools: string[];
  resources: string[];
}

/**
 * Probe MCP server via HTTP health endpoint
 */
const probeHttpHealth = async (endpoint: string, timeoutMs = 5000): Promise<MCPHealthResponse> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${endpoint}/health`, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return data as MCPHealthResponse;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Connection timed out');
    }
    throw error;
  }
};

interface MCPStore {
  // Server management
  servers: MCPServer[];
  addServer: (server: Omit<MCPServer, 'id' | 'status'>) => void;
  removeServer: (serverId: string) => void;
  updateServerStatus: (serverId: string, status: MCPServer['status'], error?: string) => void;
  connectServer: (serverId: string) => Promise<void>;
  disconnectServer: (serverId: string) => void;

  // LLM Provider management
  llmProviders: LLMProvider[];
  activeLLMProviderId: string | null;
  addLLMProvider: (provider: Omit<LLMProvider, 'id' | 'isConfigured'>) => void;
  updateLLMProvider: (providerId: string, updates: Partial<LLMProvider>) => void;
  removeLLMProvider: (providerId: string) => void;
  setActiveLLMProvider: (providerId: string | null) => void;

  // Project management
  projects: ChatProject[];
  createProject: (name: string) => string;
  deleteProject: (projectId: string) => void;
  renameProject: (projectId: string, name: string) => void;

  // Chat session management
  sessions: MCPChatSession[];
  currentSessionId: string | null;
  createSession: (name?: string, projectId?: string) => string;
  deleteSession: (sessionId: string) => void;
  setCurrentSession: (sessionId: string | null) => void;
  renameSession: (sessionId: string, name: string) => void;
  addMessage: (sessionId: string, message: Omit<MCPChatMessage, 'id' | 'timestamp'>) => void;
  updateMessage: (sessionId: string, messageId: string, updates: Partial<MCPChatMessage>) => void;
  addToolCall: (sessionId: string, messageId: string, toolCall: MCPToolCall) => void;
  updateToolCall: (
    sessionId: string,
    messageId: string,
    toolCallId: string,
    updates: Partial<MCPToolCall>
  ) => void;

  // Connection state
  isConnecting: boolean;
  setConnecting: (connecting: boolean) => void;
  globalError: string | null;
  setGlobalError: (error: string | null) => void;

  // Helpers
  getActiveServers: () => MCPServer[];
  getActiveLLMProvider: () => LLMProvider | null;
  getCurrentSession: () => MCPChatSession | null;
  getProjectSessions: (projectId: string) => MCPChatSession[];
  getStandaloneSessions: () => MCPChatSession[];
}

// Default Hydra MCP server (built-in)
const HYDRA_MCP_SERVER: MCPServer = {
  id: 'hydra-mcp',
  name: 'Hydra MCP',
  description: 'Built-in MCP server for Hydra infrastructure management',
  type: 'builtin',
  status: 'disconnected',
  category: 'infrastructure',
  endpoint: HYDRA_MCP_URL,
  wsEndpoint: HYDRA_MCP_WS_URL,
  docsUrl: '/docs/mcp',
  tools: [],
  resources: [],
};

// Default LLM providers
const DEFAULT_LLM_PROVIDERS: LLMProvider[] = [
  {
    id: 'anthropic',
    name: 'Anthropic Claude',
    type: 'anthropic',
    model: 'claude-3-5-sonnet-20241022',
    isConfigured: false,
  },
  {
    id: 'openai',
    name: 'OpenAI GPT',
    type: 'openai',
    model: 'gpt-4-turbo-preview',
    isConfigured: false,
  },
  {
    id: 'ollama',
    name: 'Ollama (Local)',
    type: 'ollama',
    baseUrl: 'http://localhost:11434',
    model: 'llama3.2',
    isConfigured: false,
  },
];

export const useMCPStore = create<MCPStore>()(
  persist(
    (set, get) => ({
      // Initial state
      servers: [HYDRA_MCP_SERVER],
      llmProviders: DEFAULT_LLM_PROVIDERS,
      activeLLMProviderId: null,
      projects: [],
      sessions: [],
      currentSessionId: null,
      isConnecting: false,
      globalError: null,

      // Server management
      addServer: (server) => {
        const newServer: MCPServer = {
          ...server,
          id: generateId(),
          status: 'disconnected',
        };
        set((state) => ({
          servers: [...state.servers, newServer],
        }));
      },

      removeServer: (serverId) => {
        if (serverId === 'hydra-mcp') return; // Cannot remove built-in server
        set((state) => ({
          servers: state.servers.filter((s) => s.id !== serverId),
        }));
      },

      updateServerStatus: (serverId, status, error) => {
        set((state) => ({
          servers: state.servers.map((s) =>
            s.id === serverId
              ? { ...s, status, error, lastConnected: status === 'connected' ? new Date() : s.lastConnected }
              : s
          ),
        }));
      },

      connectServer: async (serverId) => {
        const server = get().servers.find((s) => s.id === serverId);
        if (!server) return;

        set({ isConnecting: true });
        get().updateServerStatus(serverId, 'disconnected');

        try {
          const endpoint = server.endpoint || (serverId === 'hydra-mcp' ? HYDRA_MCP_URL : undefined);
          if (!endpoint) {
            throw new Error('MCP endpoint is not configured. Set VITE_MCP_URL in your .env file.');
          }

          // Use HTTP health check for MCP servers
          const health = await probeHttpHealth(endpoint);

          // Update server with tools from health response
          set((state) => ({
            servers: state.servers.map((s) =>
              s.id === serverId
                ? {
                    ...s,
                    status: 'connected' as const,
                    error: undefined,
                    lastConnected: new Date(),
                    tools: health.tools || [],
                    resources: health.resources || [],
                  }
                : s
            ),
          }));
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Connection failed';
          get().updateServerStatus(serverId, 'error', errorMessage);
        } finally {
          set({ isConnecting: false });
        }
      },

      disconnectServer: (serverId) => {
        get().updateServerStatus(serverId, 'disconnected');
      },

      // LLM Provider management
      addLLMProvider: (provider) => {
        const newProvider: LLMProvider = {
          ...provider,
          id: generateId(),
          isConfigured: !!(provider.apiKey || provider.type === 'ollama'),
        };
        set((state) => ({
          llmProviders: [...state.llmProviders, newProvider],
        }));
      },

      updateLLMProvider: (providerId, updates) => {
        set((state) => ({
          llmProviders: state.llmProviders.map((p) =>
            p.id === providerId
              ? {
                  ...p,
                  ...updates,
                  isConfigured: !!(updates.apiKey ?? p.apiKey) || p.type === 'ollama',
                }
              : p
          ),
        }));
      },

      removeLLMProvider: (providerId) => {
        set((state) => ({
          llmProviders: state.llmProviders.filter((p) => p.id !== providerId),
          activeLLMProviderId:
            state.activeLLMProviderId === providerId ? null : state.activeLLMProviderId,
        }));
      },

      setActiveLLMProvider: (providerId) => {
        set({ activeLLMProviderId: providerId });
      },

      // Project management
      createProject: (name) => {
        const projectId = generateId();
        const newProject: ChatProject = {
          id: projectId,
          name,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({
          projects: [newProject, ...state.projects],
        }));
        return projectId;
      },

      deleteProject: (projectId) => {
        set((state) => ({
          projects: state.projects.filter((p) => p.id !== projectId),
          // Also delete or orphan sessions in this project
          sessions: state.sessions.map((s) =>
            s.projectId === projectId ? { ...s, projectId: undefined } : s
          ),
        }));
      },

      renameProject: (projectId, name) => {
        set((state) => ({
          projects: state.projects.map((p) =>
            p.id === projectId ? { ...p, name, updatedAt: new Date() } : p
          ),
        }));
      },

      // Chat session management
      createSession: (name, projectId) => {
        const sessionId = generateId();
        const newSession: MCPChatSession = {
          id: sessionId,
          name: name || `Chat ${new Date().toLocaleDateString()}`,
          projectId,
          messages: [],
          connectedServers: get()
            .servers.filter((s) => s.status === 'connected')
            .map((s) => s.id),
          llmProvider: get().activeLLMProviderId || '',
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({
          sessions: [newSession, ...state.sessions],
          currentSessionId: sessionId,
        }));
        return sessionId;
      },

      deleteSession: (sessionId) => {
        set((state) => ({
          sessions: state.sessions.filter((s) => s.id !== sessionId),
          currentSessionId:
            state.currentSessionId === sessionId ? null : state.currentSessionId,
        }));
      },

      setCurrentSession: (sessionId) => {
        set({ currentSessionId: sessionId });
      },

      renameSession: (sessionId, name) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId ? { ...s, name, updatedAt: new Date() } : s
          ),
        }));
      },

      addMessage: (sessionId, message) => {
        const newMessage: MCPChatMessage = {
          ...message,
          id: generateId(),
          timestamp: new Date(),
        };
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? { ...s, messages: [...s.messages, newMessage], updatedAt: new Date() }
              : s
          ),
        }));
      },

      updateMessage: (sessionId, messageId, updates) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? {
                  ...s,
                  messages: s.messages.map((m) =>
                    m.id === messageId ? { ...m, ...updates } : m
                  ),
                  updatedAt: new Date(),
                }
              : s
          ),
        }));
      },

      addToolCall: (sessionId, messageId, toolCall) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? {
                  ...s,
                  messages: s.messages.map((m) =>
                    m.id === messageId
                      ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
                      : m
                  ),
                  updatedAt: new Date(),
                }
              : s
          ),
        }));
      },

      updateToolCall: (sessionId, messageId, toolCallId, updates) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? {
                  ...s,
                  messages: s.messages.map((m) =>
                    m.id === messageId
                      ? {
                          ...m,
                          toolCalls: m.toolCalls?.map((tc) =>
                            tc.id === toolCallId ? { ...tc, ...updates } : tc
                          ),
                        }
                      : m
                  ),
                  updatedAt: new Date(),
                }
              : s
          ),
        }));
      },

      // Connection state
      setConnecting: (connecting) => {
        set({ isConnecting: connecting });
      },

      setGlobalError: (error) => {
        set({ globalError: error });
      },

      // Helpers
      getActiveServers: () => {
        return get().servers.filter((s) => s.status === 'connected');
      },

      getActiveLLMProvider: () => {
        const { llmProviders, activeLLMProviderId } = get();
        return llmProviders.find((p) => p.id === activeLLMProviderId) || null;
      },

      getCurrentSession: () => {
        const { sessions, currentSessionId } = get();
        return sessions.find((s) => s.id === currentSessionId) || null;
      },

      getProjectSessions: (projectId) => {
        return get().sessions.filter((s) => s.projectId === projectId);
      },

      getStandaloneSessions: () => {
        return get().sessions.filter((s) => !s.projectId);
      },
    }),
    {
      name: 'hydra-mcp-storage',
      partialize: (state) => ({
        servers: state.servers.map((s) => ({ ...s, status: 'disconnected' as const })),
        llmProviders: state.llmProviders,
        activeLLMProviderId: state.activeLLMProviderId,
        projects: state.projects,
        sessions: state.sessions.slice(0, 50), // Persist last 50 sessions
      }),
    }
  )
);
