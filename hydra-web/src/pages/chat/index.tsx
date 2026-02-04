import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useQueries } from '@tanstack/react-query';
import {
  AlertCircle,
  Menu,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import { useMCPChat, type ModelConfig, type SessionUsage } from '@/hooks/use-mcp-chat';
import {
  useChatProjects,
  useChatSessions,
  useChatMessages,
  useSessionContext,
  useCreateChatProject,
  useCreateChatSession,
  useUpdateChatSession,
  useDeleteChatSession,
  useBulkUpsertMessages,
  type ChatMessageResponse,
  type ChatMessageRole,
} from '@/api/chat';
import { useChatCacheStore } from '@/stores/chat-cache-store';
import {
  useLLMProviders,
  useCreateLLMProvider,
  useUpdateLLMProvider,
  useDeleteLLMProvider,
  useValidateLLMProvider,
  type LLMProviderCreate,
} from '@/api/ai';
import {
  useMCPServers,
  useHydraMCPHealth,
  useHydraMCPTools,
  useHydraMCPPrompts,
  type MCPToolInfo,
  type MCPToolsResponse,
  type MCPResourcesResponse,
  type MCPPromptsResponse,
} from '@/api/mcp';
import { Button } from '@/components/ui/button';
import {
  TooltipProvider,
} from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/use-toast';

import {
  ChatHeader,
  ChatInput,
  ChatSidebar,
  ChatSettingsPanel,
  ChatMessageList,
} from './components';
import type { ReasoningLevel } from './components';
import { NewProjectModal, MCPConfigModal, LLMConfigModal } from './modals';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';
import { useNotificationStats } from '@/api/notifications';

const useInfrastructureContext = () => {
  const { data: nodesData } = useNodes({ limit: 1 });
  const { data: servicesData } = useServices({ limit: 1 });
  const { data: networksData } = useNetworks({ limit: 1 });
  const { data: notifStats } = useNotificationStats();

  return useMemo(
    () => ({
      nodes: nodesData?.total ?? 0,
      services: servicesData?.total ?? 0,
      networks: networksData?.total ?? 0,
      notifications: notifStats?.total ?? 0,
    }),
    [nodesData, servicesData, networksData, notifStats]
  );
};

export default function ChatPage() {
  useDocumentTitle('Chat');

  const { toast } = useToast();

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [localMessages, setLocalMessages] = useState<
    Array<ChatMessageResponse & { error?: boolean }>
  >([]);

  const { data: projectsData } = useChatProjects();
  const { data: sessionsData } = useChatSessions();
  const {
    data: messagesData,
    refetch: refetchMessages,
  } = useChatMessages(currentSessionId || '', { order: 'asc' });

  const { data: llmProvidersData } = useLLMProviders();
  const { data: mcpServersData } = useMCPServers();

  // Dedicated Hydra MCP hooks for first-class integration
  const { data: hydraMcpHealth } = useHydraMCPHealth();
  const { data: hydraMcpToolsData } = useHydraMCPTools();
  const { data: hydraMcpPromptsData } = useHydraMCPPrompts();

  const createProjectMutation = useCreateChatProject();
  const createSessionMutation = useCreateChatSession();
  const updateSessionMutation = useUpdateChatSession();
  const deleteSessionMutation = useDeleteChatSession();
  const bulkUpsertMessagesMutation = useBulkUpsertMessages();

  const createProviderMutation = useCreateLLMProvider();
  const updateProviderMutation = useUpdateLLMProvider();
  const deleteProviderMutation = useDeleteLLMProvider();
  const validateProviderMutation = useValidateLLMProvider();

  const projects = projectsData?.projects || [];
  const sessions = sessionsData?.sessions || [];
  const llmProviders = llmProvidersData?.configs || [];
  const servers = mcpServersData?.servers || [];

  const currentSession =
    sessions.find((session) => session.sessionId === currentSessionId) || null;

  const defaultProvider = llmProviders.find((provider) => provider.isDefault);
  const activeLLMProviderId =
    currentSession?.llmProviderId || defaultProvider?.configId || null;
  const activeLLMProvider = llmProviders.find(
    (provider) => provider.configId === activeLLMProviderId
  );

  const activeServerIds = currentSession?.mcpServerIds || [];

  const [input, setInput] = useState('');
  const [sidebarTab, setSidebarTab] = useState<'chats' | 'tools' | 'configs'>('chats');
  const [expandedProjects, setExpandedProjects] = useState<string[]>([]);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [showMCPConfigModal, setShowMCPConfigModal] = useState(false);
  const [showLLMConfigModal, setShowLLMConfigModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [streamingContent, setStreamingContent] = useState('');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [reasoningLevel, setReasoningLevel] = useState<ReasoningLevel>('none');
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  // Model configuration state for per-request overrides
  const [modelConfig, setModelConfig] = useState<ModelConfig>({});
  const [sessionUsage, setSessionUsage] = useState<SessionUsage | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const infraContext = useInfrastructureContext();

  const messages = messagesData?.messages || [];
  const { data: sessionContextData } = useSessionContext(currentSessionId);
  const sessionContext = sessionContextData?.context ?? null;
  const llmConfigLocked = currentSession?.llmConfigLocked ?? false;
  const { invalidateMessages } = useChatCacheStore();

  // Stable callbacks for WebSocket hook - uses the actual message data
  const handleWSMessage = useCallback(
    (message: { id: string; role: string; content: string; toolCalls?: unknown[] }, usage?: SessionUsage) => {
      // Update session usage if provided
      if (usage) {
        setSessionUsage(usage);
      }
      // Clear streaming content since message is complete
      setStreamingContent('');

      // Generate a stable local ID for this message
      const localMessageId = message.id || `local_assistant_${Date.now()}`;

      // Add the completed message to local messages immediately for display
      // This ensures the message is visible even before refetch completes
      setLocalMessages((prev) => {
        // Check by messageId to avoid duplicates
        const hasMessage = prev.some((m) => m.messageId === localMessageId);
        if (hasMessage) return prev;

        return [
          ...prev,
          {
            messageId: localMessageId,
            sessionId: currentSessionId || 'local',
            role: 'assistant' as ChatMessageRole,
            content: message.content,
            toolCalls: message.toolCalls as ChatMessageResponse['toolCalls'],
            order: 1000000 + prev.length, // High order to appear at end until synced
            createdAt: new Date().toISOString(),
          },
        ];
      });

      // Invalidate cache and refetch to sync with backend
      // Don't clear local messages here - let allMessages deduplication handle it
      if (currentSessionId) {
        invalidateMessages(currentSessionId);
        refetchMessages();
      }
    },
    [currentSessionId, invalidateMessages, refetchMessages]
  );

  const handleWSError = useCallback((error: string) => {
    // Add error message to local messages - keep any existing messages
    setLocalMessages((prev) => [
      ...prev,
      {
        messageId: `local_error_${Date.now()}`,
        sessionId: currentSessionId || 'local',
        role: 'assistant' as ChatMessageRole,
        content: `Error: ${error}`,
        order: 1000000 + prev.length, // High order to appear at end
        createdAt: new Date().toISOString(),
        error: true,
      },
    ]);
    setStreamingContent('');
  }, [currentSessionId]);

  // Derive model capabilities from active provider
  const supportsReasoning = useMemo(() => {
    if (!activeLLMProvider) return false;
    const model = activeLLMProvider.model.toLowerCase();
    // Claude 3.5+ models, Claude 4.0+, and OpenAI o1/o3 support extended thinking
    return (
      model.includes('claude-3-5') ||
      model.includes('claude-3.5') ||
      model.includes('claude-4') ||
      model.includes('o1') ||
      model.includes('o3')
    );
  }, [activeLLMProvider]);

  const supportsWebSearch = useMemo(() => {
    if (!activeLLMProvider) return false;
    // OpenRouter provides web search capability
    return activeLLMProvider.type === 'openrouter';
  }, [activeLLMProvider]);

  const standaloneSessions = useMemo(
    () => sessions.filter((session) => !session.projectId),
    [sessions]
  );

  // Hydra MCP status: check both session state and actual health
  const isHydraMcpInSession = activeServerIds.includes('hydra-mcp');
  const isHydraMcpHealthy = hydraMcpHealth?.status === 'healthy';
  const hydraMcpTools = hydraMcpToolsData?.tools || [];
  const hydraMcpPrompts = hydraMcpPromptsData?.prompts || [];

  // External servers (exclude hydra-mcp from generic list)
  const externalServers = useMemo(
    () => servers.filter((s) => s.serverId !== 'hydra-mcp'),
    [servers]
  );

  // Fetch tools/resources/prompts for external servers only (Hydra MCP fetched separately)
  const toolsQueries = useQueries({
    queries: externalServers.map((server) => ({
      queryKey: queryKeys.mcp.tools(server.serverId),
      queryFn: async () => {
        const response = await apiClient.get<MCPToolsResponse>(
          `/mcp/servers/${server.serverId}/tools`
        );
        return response.data;
      },
      enabled: !!server.serverId,
    })),
  });

  const resourcesQueries = useQueries({
    queries: externalServers.map((server) => ({
      queryKey: queryKeys.mcp.resources(server.serverId),
      queryFn: async () => {
        const response = await apiClient.get<MCPResourcesResponse>(
          `/mcp/servers/${server.serverId}/resources`
        );
        return response.data;
      },
      enabled: !!server.serverId,
    })),
  });

  const promptsQueries = useQueries({
    queries: externalServers.map((server) => ({
      queryKey: queryKeys.mcp.prompts(server.serverId),
      queryFn: async () => {
        const response = await apiClient.get<MCPPromptsResponse>(
          `/mcp/servers/${server.serverId}/prompts`
        );
        return response.data;
      },
      enabled: !!server.serverId,
    })),
  });

  const toolsByServerId = useMemo(() => {
    const toolMap = new Map<string, MCPToolInfo[]>();
    externalServers.forEach((server, index) => {
      const tools = toolsQueries[index]?.data?.tools || [];
      toolMap.set(server.serverId, tools);
    });
    return toolMap;
  }, [externalServers, toolsQueries]);

  const resourcesByServerId = useMemo(() => {
    const resourceMap = new Map<string, MCPResourcesResponse['resources']>();
    externalServers.forEach((server, index) => {
      const resources = resourcesQueries[index]?.data?.resources || [];
      resourceMap.set(server.serverId, resources);
    });
    return resourceMap;
  }, [externalServers, resourcesQueries]);

  const promptsByServerId = useMemo(() => {
    const promptMap = new Map<string, MCPPromptsResponse['prompts']>();
    externalServers.forEach((server, index) => {
      const prompts = promptsQueries[index]?.data?.prompts || [];
      promptMap.set(server.serverId, prompts);
    });
    return promptMap;
  }, [externalServers, promptsQueries]);

  const serversWithTools = useMemo(
    () =>
      externalServers.map((server) => ({
        ...server,
        isActive: activeServerIds.includes(server.serverId),
        tools: toolsByServerId.get(server.serverId) || [],
        resources: resourcesByServerId.get(server.serverId) || [],
        prompts: promptsByServerId.get(server.serverId) || [],
      })),
    [externalServers, activeServerIds, toolsByServerId, resourcesByServerId, promptsByServerId]
  );

  // Aggregate tools from all connected servers (including Hydra MCP)
  const activeTools = useMemo(() => {
    const tools: Array<{ name: string; serverId: string; serverName: string }> = [];

    // Add Hydra MCP tools if connected
    if (isHydraMcpInSession && isHydraMcpHealthy) {
      hydraMcpTools.forEach((tool) => {
        tools.push({ name: tool.name, serverId: 'hydra-mcp', serverName: 'Hydra MCP' });
      });
    }

    // Add external server tools
    activeServerIds
      .filter((id) => id !== 'hydra-mcp')
      .forEach((serverId) => {
        const server = externalServers.find((s) => s.serverId === serverId);
        const serverTools = toolsByServerId.get(serverId) || [];
        serverTools.forEach((tool) => {
          tools.push({
            name: tool.name,
            serverId,
            serverName: server?.name || serverId,
          });
        });
      });

    return tools;
  }, [activeServerIds, isHydraMcpInSession, isHydraMcpHealthy, hydraMcpTools, externalServers, toolsByServerId]);

  // Aggregate prompts from all connected servers (including Hydra MCP)
  const activePrompts = useMemo(() => {
    const prompts: Array<{ name: string; description?: string | null; serverId: string; serverName: string }> = [];

    // Add Hydra MCP prompts if connected
    if (isHydraMcpInSession && isHydraMcpHealthy) {
      hydraMcpPrompts.forEach((prompt) => {
        prompts.push({
          name: prompt.name,
          description: prompt.description,
          serverId: 'hydra-mcp',
          serverName: 'Hydra MCP',
        });
      });
    }

    // Add external server prompts
    activeServerIds
      .filter((id) => id !== 'hydra-mcp')
      .forEach((serverId) => {
        const server = externalServers.find((s) => s.serverId === serverId);
        const serverPrompts = promptsByServerId.get(serverId) || [];
        serverPrompts.forEach((prompt) => {
          prompts.push({
            name: prompt.name,
            description: prompt.description,
            serverId,
            serverName: server?.name || serverId,
          });
        });
      });

    return prompts;
  }, [activeServerIds, isHydraMcpInSession, isHydraMcpHealthy, hydraMcpPrompts, externalServers, promptsByServerId]);

  // Combine server messages with local messages, avoiding duplicates
  // Server messages are the source of truth; local messages are optimistic UI
  const allMessages = useMemo(() => {
    // Build a set of server message IDs for quick lookup
    const serverMessageIds = new Set(messages.map((m) => m.messageId));

    // Also build content signatures for deduplicating local messages
    // that have been synced but have different temporary IDs
    const serverContentSignatures = new Set(
      messages.map((m) => `${m.role}:${m.content}`)
    );

    // Filter local messages that aren't yet in server messages
    // A local message is unique if:
    // 1. Its ID doesn't exist in server messages (not yet synced)
    // 2. Its content+role combo doesn't exist (for optimistic messages)
    const uniqueLocalMessages = localMessages.filter((local) => {
      // Skip if this exact message ID exists on server
      if (serverMessageIds.has(local.messageId)) return false;
      // Skip if content matches a server message (local optimistic was synced)
      if (serverContentSignatures.has(`${local.role}:${local.content}`)) return false;
      return true;
    });

    // Combine and sort by order, then by createdAt for tiebreaking
    const combined = [...messages, ...uniqueLocalMessages];
    return combined.sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
    });
  }, [messages, localMessages]);

  const appendLocalMessage = (
    payload: Pick<ChatMessageResponse, 'role' | 'content' | 'toolCalls'> & { error?: boolean }
  ) => {
    // Use a very high order number for local messages so they appear at the end
    // until they're synced from the server with correct order values
    const now = Date.now();
    setLocalMessages((prev) => [
      ...prev,
      {
        messageId: `local_${now}_${Math.random().toString(36).slice(2, 8)}`,
        sessionId: currentSessionId || 'local',
        role: payload.role as ChatMessageRole,
        content: payload.content,
        toolCalls: payload.toolCalls,
        order: 1000000 + prev.length, // High order to appear at end until synced
        createdAt: new Date().toISOString(),
        error: payload.error,
      },
    ]);
  };

  const {
    isConnected: wsConnected,
    isStreaming,
    currentResponse,
    sendMessage: wsSendMessage,
    retryMessage: wsRetryMessage,
    connect: wsConnect,
    disconnect: wsDisconnect,
  } = useMCPChat({
    sessionId: currentSessionId,
    providerId: activeLLMProviderId,
    reasoningLevel,
    webSearchEnabled,
    modelConfig,
    onMessage: handleWSMessage,
    onError: handleWSError,
  });

  useEffect(() => {
    setStreamingContent(currentResponse);
  }, [currentResponse]);

  const hasBootstrappedRef = useRef(false);

  useEffect(() => {
    if (!sessionsData) {
      return;
    }

    if (!currentSessionId && sessions.length > 0) {
      setCurrentSessionId(sessions[0].sessionId);
      return;
    }

    if (sessions.length === 0 && !hasBootstrappedRef.current) {
      hasBootstrappedRef.current = true;
      createSessionMutation.mutate(
        { title: 'New Chat' },
        {
          onSuccess: (session) => {
            setCurrentSessionId(session.sessionId);
          },
          onError: () => {
            hasBootstrappedRef.current = false;
          },
        }
      );
    }
  }, [sessionsData, sessions.length, currentSessionId, createSessionMutation]);

  useEffect(() => {
    if (!currentSessionId) {
      return;
    }

    // Don't change session while streaming - this would clear the chat
    if (isStreaming) {
      return;
    }

    const sessionExists = sessions.some(
      (session) => session.sessionId === currentSessionId
    );
    if (!sessionExists && sessions.length > 0) {
      setCurrentSessionId(sessions[0].sessionId);
    }
  }, [currentSessionId, sessions, isStreaming]);

  useEffect(() => {
    if (!currentSession || !defaultProvider) {
      return;
    }
    if (!currentSession.llmProviderId) {
      updateSessionMutation.mutate({
        sessionId: currentSession.sessionId,
        data: { llmProviderId: defaultProvider.configId },
      });
    }
  }, [currentSession, defaultProvider, updateSessionMutation]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [allMessages, isStreaming]);

  // Track previous session to detect actual session changes
  const prevSessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    // Only clear when session actually changes, not when isStreaming changes
    if (prevSessionIdRef.current !== currentSessionId) {
      // Session changed - clear local state only if not streaming
      if (!isStreaming) {
        setLocalMessages([]);
        setStreamingContent('');
      }
      prevSessionIdRef.current = currentSessionId;
    }
  }, [currentSessionId, isStreaming]);

  useEffect(() => {
    const isProviderReady =
      activeLLMProvider?.apiKeySet || activeLLMProvider?.type === 'ollama';
    if (currentSessionId && isProviderReady && !wsConnected) {
      wsConnect();
    }
  }, [currentSessionId, activeLLMProvider, wsConnected, wsConnect]);

  useEffect(() => {
    return () => {
      wsDisconnect();
    };
  }, [wsDisconnect]);

  const handleSend = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText || isStreaming || !currentSessionId) return;

    const providerReady =
      activeLLMProvider?.apiKeySet || activeLLMProvider?.type === 'ollama';
    if (!providerReady) {
      setShowLLMConfigModal(true);
      return;
    }

    if (!wsConnected) {
      wsConnect();
      appendLocalMessage({
        role: 'assistant',
        content: 'Connecting to chat server... Please try again in a moment.',
        error: true,
      });
      return;
    }

    setInput('');

    appendLocalMessage({
      role: 'user',
      content: messageText,
    });

    wsSendMessage(messageText);
  };

  const toggleProjectExpand = (projectId: string) => {
    setExpandedProjects((prev) =>
      prev.includes(projectId) ? prev.filter((p) => p !== projectId) : [...prev, projectId]
    );
  };

  const handleCreateProject = () => {
    if (!newProjectName.trim()) return;
    createProjectMutation.mutate(
      { name: newProjectName.trim() },
      {
        onSuccess: (project) => {
          setExpandedProjects((prev) => [...prev, project.projectId]);
          setNewProjectName('');
          setShowNewProjectModal(false);
        },
        onError: () => {
          toast({
            title: 'Failed to create project',
            description: 'Please try again.',
            variant: 'destructive',
          });
        },
      }
    );
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setLocalMessages([]);
    setMobileSidebarOpen(false);
  };

  const handleNewChat = (projectId?: string) => {
    createSessionMutation.mutate(
      { title: 'New Chat', projectId },
      {
        onSuccess: (session) => {
          setCurrentSessionId(session.sessionId);
          setMobileSidebarOpen(false);
        },
        onError: () => {
          toast({
            title: 'Failed to create chat',
            description: 'Please try again.',
            variant: 'destructive',
          });
        },
      }
    );
  };

  const handleSetActiveProvider = (providerId: string) => {
    if (!currentSession) return;
    updateSessionMutation.mutate({
      sessionId: currentSession.sessionId,
      data: { llmProviderId: providerId },
    });
  };

  const handleConnectServer = (serverId: string) => {
    if (!currentSession) return;
    const nextServerIds = Array.from(
      new Set([...(currentSession.mcpServerIds || []), serverId])
    );
    updateSessionMutation.mutate({
      sessionId: currentSession.sessionId,
      data: { mcpServerIds: nextServerIds },
    });
  };

  const handleDisconnectServer = (serverId: string) => {
    if (!currentSession) return;
    const nextServerIds = (currentSession.mcpServerIds || []).filter(
      (id) => id !== serverId
    );
    updateSessionMutation.mutate({
      sessionId: currentSession.sessionId,
      data: { mcpServerIds: nextServerIds },
    });
  };

  const handleDeleteSession = useCallback(
    (sessionId?: string) => {
      const targetSessionId = sessionId || currentSessionId;
      if (!targetSessionId) return;

      deleteSessionMutation.mutate(targetSessionId, {
        onSuccess: () => {
          if (targetSessionId === currentSessionId) {
            setCurrentSessionId(null);
          }
        },
        onError: () => {
          toast({
            title: 'Failed to delete chat',
            description: 'Please try again.',
            variant: 'destructive',
          });
        },
      });
    },
    [currentSessionId, deleteSessionMutation, toast]
  );

  const handleRenameSession = useCallback(
    (sessionId: string, newTitle: string) => {
      if (!newTitle.trim()) return;
      updateSessionMutation.mutate({
        sessionId,
        data: { title: newTitle.trim() },
      });
    },
    [updateSessionMutation]
  );

  const handleMoveSessionToProject = useCallback(
    (sessionId: string, projectId: string | null) => {
      updateSessionMutation.mutate({
        sessionId,
        data: { projectId: projectId || null },
      });
    },
    [updateSessionMutation]
  );

  const handleDuplicateSession = useCallback(
    async (sessionId?: string) => {
      const targetSession = sessionId
        ? sessions.find((s) => s.sessionId === sessionId)
        : currentSession;
      if (!targetSession) return;

      try {
        const newSession = await createSessionMutation.mutateAsync({
          title: `${targetSession.title || 'Chat'} (copy)`,
          projectId: targetSession.projectId || undefined,
          llmProviderId: targetSession.llmProviderId || undefined,
          mcpServerIds: targetSession.mcpServerIds || [],
        });

        // Only copy messages if duplicating the current session
        if (!sessionId && messages.length > 0) {
          await bulkUpsertMessagesMutation.mutateAsync({
            sessionId: newSession.sessionId,
            messages: messages.map((message) => ({
              role: message.role,
              content: message.content,
              toolCalls: message.toolCalls,
              order: message.order,
            })),
          });
        }

        setCurrentSessionId(newSession.sessionId);
      } catch (error) {
        toast({
          title: 'Failed to duplicate chat',
          description: 'Please try again.',
          variant: 'destructive',
        });
      }
    },
    [sessions, currentSession, messages, createSessionMutation, bulkUpsertMessagesMutation, toast]
  );

  const handleExportSession = useCallback(
    (sessionId?: string) => {
      const targetSession = sessionId
        ? sessions.find((s) => s.sessionId === sessionId)
        : currentSession;
      if (!targetSession) return;

      const exportData = {
        session: targetSession,
        messages: sessionId === currentSessionId || !sessionId ? messages : [],
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${targetSession.title || 'chat'}-${targetSession.sessionId}.json`;
      link.click();
      URL.revokeObjectURL(url);
    },
    [sessions, currentSession, currentSessionId, messages]
  );

  const handleCreateProvider = (data: LLMProviderCreate) => {
    createProviderMutation.mutate(data, {
      onError: () => {
        toast({
          title: 'Failed to add provider',
          description: 'Please check the configuration and try again.',
          variant: 'destructive',
        });
      },
    });
  };

  const handleUpdateProvider = (providerId: string, updates: { apiKey?: string }) => {
    updateProviderMutation.mutate(
      { providerId, data: updates },
      {
        onError: () => {
          toast({
            title: 'Failed to update provider',
            description: 'Please try again.',
            variant: 'destructive',
          });
        },
      }
    );
  };

  const handleDeleteProvider = (providerId: string) => {
    deleteProviderMutation.mutate(providerId, {
      onError: () => {
        toast({
          title: 'Failed to remove provider',
          description: 'Please try again.',
          variant: 'destructive',
        });
      },
    });
  };

  const handleValidateProvider = (providerId: string) => {
    validateProviderMutation.mutate(providerId, {
      onSuccess: (result) => {
        toast({
          title: result.isValid ? 'Provider validated' : 'Validation failed',
          description: result.message,
          variant: result.isValid ? 'default' : 'destructive',
        });
      },
      onError: () => {
        toast({
          title: 'Validation failed',
          description: 'Please try again.',
          variant: 'destructive',
        });
      },
    });
  };

  const settingsPanel = (
    <ChatSettingsPanel
      modelConfig={modelConfig}
      onModelConfigChange={setModelConfig}
      reasoningLevel={reasoningLevel}
      onReasoningLevelChange={setReasoningLevel}
      webSearchEnabled={webSearchEnabled}
      onWebSearchEnabledChange={setWebSearchEnabled}
      supportsReasoning={supportsReasoning}
      supportsWebSearch={supportsWebSearch}
      isStreaming={isStreaming}
      sessionUsage={sessionUsage}
      sessionContext={sessionContext}
      activeLLMProvider={activeLLMProvider ?? null}
      onOpenLLMConfig={() => setShowLLMConfigModal(true)}
    />
  );

  return (
    <TooltipProvider>
      <div className="h-[calc(100vh-3.5rem)] flex items-stretch gap-4 p-4 bg-background relative">
        <Button
          variant="outline"
          size="icon"
          className="fixed bottom-4 left-4 z-50 md:hidden shadow-lg"
          onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
          aria-label={mobileSidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        >
          {mobileSidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>

        {mobileSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-30 md:hidden"
            onClick={() => setMobileSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        <ChatSidebar
          sidebarTab={sidebarTab}
          onSidebarTabChange={(tab) => setSidebarTab(tab)}
          mobileSidebarOpen={mobileSidebarOpen}
          projects={projects}
          standaloneSessions={standaloneSessions}
          sessions={sessions}
          currentSessionId={currentSessionId}
          expandedProjects={expandedProjects}
          onToggleProjectExpand={toggleProjectExpand}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onNewProject={() => setShowNewProjectModal(true)}
          onRenameSession={handleRenameSession}
          onMoveSessionToProject={handleMoveSessionToProject}
          onDuplicateSession={handleDuplicateSession}
          onExportSession={handleExportSession}
          onDeleteSession={handleDeleteSession}
          isHydraMcpInSession={isHydraMcpInSession}
          isHydraMcpHealthy={isHydraMcpHealthy}
          hydraMcpHealth={hydraMcpHealth}
          hydraMcpTools={hydraMcpTools}
          hydraMcpPrompts={hydraMcpPrompts}
          serversWithTools={serversWithTools}
          activeTools={activeTools}
          activePrompts={activePrompts}
          onConnectServer={handleConnectServer}
          onDisconnectServer={handleDisconnectServer}
          onSend={handleSend}
          infraContext={infraContext}
          activeLLMProvider={activeLLMProvider}
          onOpenLLMConfig={() => setShowLLMConfigModal(true)}
          configTabContent={settingsPanel}
        />

        <div className="flex-1 h-full flex flex-col bg-card border border-border rounded-lg overflow-hidden min-w-0">
          <ChatHeader
            currentSession={currentSession}
            activeLLMProvider={activeLLMProvider}
            activeLLMProviderId={activeLLMProviderId}
            llmProviders={llmProviders}
            activeToolsCount={activeTools.length}
            sessionContext={sessionContext}
            llmConfigLocked={llmConfigLocked}
            onLLMProviderChange={handleSetActiveProvider}
            onOpenLLMConfig={() => setShowLLMConfigModal(true)}
            onRenameSession={(newTitle) =>
              currentSession && handleRenameSession(currentSession.sessionId, newTitle)
            }
            onDuplicateSession={() => handleDuplicateSession()}
            onExportSession={() => handleExportSession()}
            onDeleteSession={() => handleDeleteSession()}
          />

          {/* Hydra MCP Status Banner */}
          {!isHydraMcpInSession ? (
            <div className="mx-4 mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-foreground">
                Connect <code className="bg-muted px-1 rounded text-foreground">Hydra MCP</code> in
                the Tools tab to access infrastructure tools.
              </span>
            </div>
          ) : !isHydraMcpHealthy ? (
            <div className="mx-4 mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-red-500" />
              <span className="text-sm text-foreground">
                <code className="bg-muted px-1 rounded text-foreground">Hydra MCP</code> is
                unreachable — check if the hydra-mcp service is running.
              </span>
            </div>
          ) : null}

          <ChatMessageList
            messages={allMessages}
            isStreaming={isStreaming}
            streamingContent={streamingContent}
            onSend={handleSend}
            onRetryMessage={wsRetryMessage}
            messagesEndRef={messagesEndRef}
          />

          <ChatInput
            value={input}
            onChange={setInput}
            onSend={() => handleSend()}
            isStreaming={isStreaming}
          />
        </div>

        <NewProjectModal
          open={showNewProjectModal}
          onOpenChange={setShowNewProjectModal}
          projectName={newProjectName}
          onProjectNameChange={setNewProjectName}
          onCreateProject={handleCreateProject}
        />

        <MCPConfigModal
          open={showMCPConfigModal}
          onOpenChange={setShowMCPConfigModal}
          servers={serversWithTools}
          onConnectServer={handleConnectServer}
          onDisconnectServer={handleDisconnectServer}
        />

        <LLMConfigModal
          open={showLLMConfigModal}
          onOpenChange={setShowLLMConfigModal}
          llmProviders={llmProviders}
          activeLLMProviderId={activeLLMProviderId}
          onSetActiveProvider={handleSetActiveProvider}
          onUpdateProvider={handleUpdateProvider}
          onCreateProvider={handleCreateProvider}
          onDeleteProvider={handleDeleteProvider}
          onValidateProvider={handleValidateProvider}
        />
      </div>
    </TooltipProvider>
  );
}
