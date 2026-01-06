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
} from '@/types/mcp';

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

  // Chat session management
  sessions: MCPChatSession[];
  currentSessionId: string | null;
  createSession: (name?: string) => string;
  deleteSession: (sessionId: string) => void;
  setCurrentSession: (sessionId: string | null) => void;
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
}

// Default Hydra MCP server (built-in)
const HYDRA_MCP_SERVER: MCPServer = {
  id: 'hydra-mcp',
  name: 'Hydra MCP',
  description: 'Built-in MCP server for Hydra infrastructure management',
  type: 'builtin',
  status: 'disconnected',
  category: 'infrastructure',
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
        get().updateServerStatus(serverId, 'connected');

        try {
          // For built-in Hydra MCP, connect via API
          if (server.type === 'builtin' && serverId === 'hydra-mcp') {
            // TODO: Implement actual connection to Hydra MCP
            // This would involve fetching available tools and resources
            get().updateServerStatus(serverId, 'connected');
          } else if (server.endpoint) {
            // For remote servers, attempt connection
            // TODO: Implement remote server connection
            get().updateServerStatus(serverId, 'connected');
          }
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

      // Chat session management
      createSession: (name) => {
        const sessionId = generateId();
        const newSession: MCPChatSession = {
          id: sessionId,
          name: name || `Chat ${new Date().toLocaleDateString()}`,
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
    }),
    {
      name: 'hydra-mcp-storage',
      partialize: (state) => ({
        servers: state.servers.map((s) => ({ ...s, status: 'disconnected' as const })),
        llmProviders: state.llmProviders,
        activeLLMProviderId: state.activeLLMProviderId,
        sessions: state.sessions.slice(0, 10), // Only persist last 10 sessions
      }),
    }
  )
);
