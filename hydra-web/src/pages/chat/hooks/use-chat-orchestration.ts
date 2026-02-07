import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useQueries } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import { useMCPChat, type ModelConfig, type SessionUsage } from '@/hooks/use-mcp-chat';
import {
  useChatProjects,
  useChatSessions,
  useChatMessages,
  useSessionContext,
  useCreateChatProject,
  useUpdateChatProject,
  useDeleteChatProject,
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
  type MCPServerResponse,
  type MCPToolInfo,
  type MCPToolsResponse,
  type MCPResourcesResponse,
  type MCPPromptsResponse,
} from '@/api/mcp';
import { useToast } from '@/components/ui/use-toast';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';
import { useNotificationStats } from '@/api/notifications';
import type { ReasoningLevel } from '../components';

// ─── Infrastructure Context ────────────────────────────────────────────

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

// ─── MCP Server Queries ────────────────────────────────────────────────

function useMCPServerData(servers: MCPServerResponse[], activeServerIds: string[]) {
  const externalServers = useMemo(
    () => servers.filter((s) => s.serverId !== 'hydra-mcp'),
    [servers]
  );

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

  return { externalServers, toolsByServerId, resourcesByServerId, promptsByServerId, serversWithTools };
}

// ─── Main Orchestration Hook ───────────────────────────────────────────

export function useChatOrchestration() {
  const { toast } = useToast();

  // ── Core state ──────────────────────────────────────────────────────
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [localMessages, setLocalMessages] = useState<
    Array<ChatMessageResponse & { error?: boolean }>
  >([]);
  const [input, setInput] = useState('');
  const [streamingContent, setStreamingContent] = useState('');
  const [reasoningLevel, setReasoningLevel] = useState<ReasoningLevel>('none');
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [modelConfig, setModelConfig] = useState<ModelConfig>({});
  const [sessionUsage, setSessionUsage] = useState<SessionUsage | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Data queries ────────────────────────────────────────────────────
  const { data: projectsData } = useChatProjects();
  const { data: sessionsData } = useChatSessions();
  const {
    data: messagesData,
    refetch: refetchMessages,
  } = useChatMessages(currentSessionId || '', { order: 'asc' });

  const { data: llmProvidersData } = useLLMProviders();
  const { data: mcpServersData } = useMCPServers();
  const { data: hydraMcpHealth } = useHydraMCPHealth();
  const { data: hydraMcpToolsData } = useHydraMCPTools();
  const { data: hydraMcpPromptsData } = useHydraMCPPrompts();

  const { data: sessionContextData } = useSessionContext(currentSessionId);

  // ── Mutations ───────────────────────────────────────────────────────
  const createProjectMutation = useCreateChatProject();
  const updateProjectMutation = useUpdateChatProject();
  const deleteProjectMutation = useDeleteChatProject();
  const createSessionMutation = useCreateChatSession();
  const updateSessionMutation = useUpdateChatSession();
  const deleteSessionMutation = useDeleteChatSession();
  const bulkUpsertMessagesMutation = useBulkUpsertMessages();

  const createProviderMutation = useCreateLLMProvider();
  const updateProviderMutation = useUpdateLLMProvider();
  const deleteProviderMutation = useDeleteLLMProvider();
  const validateProviderMutation = useValidateLLMProvider();

  // ── Derived data ────────────────────────────────────────────────────
  const projects = projectsData?.projects || [];
  const sessions = sessionsData?.sessions || [];
  const llmProviders = llmProvidersData?.configs || [];
  const servers = mcpServersData?.servers || [];
  const messages = messagesData?.messages || [];
  const sessionContext = sessionContextData?.context ?? null;

  const currentSession =
    sessions.find((session) => session.sessionId === currentSessionId) || null;
  const llmConfigLocked = currentSession?.llmConfigLocked ?? false;

  const defaultProvider = llmProviders.find((provider) => provider.isDefault);
  const activeLLMProviderId =
    currentSession?.llmProviderId || defaultProvider?.configId || null;
  const activeLLMProvider = llmProviders.find(
    (provider) => provider.configId === activeLLMProviderId
  );

  const activeServerIds = currentSession?.mcpServerIds || [];
  const standaloneSessions = useMemo(
    () => sessions.filter((session) => !session.projectId),
    [sessions]
  );

  // ── Hydra MCP status ───────────────────────────────────────────────
  const isHydraMcpInSession = activeServerIds.includes('hydra-mcp');
  const isHydraMcpHealthy = hydraMcpHealth?.status === 'healthy';
  const hydraMcpTools = hydraMcpToolsData?.tools || [];
  const hydraMcpPrompts = hydraMcpPromptsData?.prompts || [];

  // ── External server data (tools/resources/prompts) ─────────────────
  const { externalServers, toolsByServerId, promptsByServerId, serversWithTools } =
    useMCPServerData(servers, activeServerIds);

  // ── Active tools/prompts aggregation ───────────────────────────────
  const activeTools = useMemo(() => {
    const tools: Array<{ name: string; serverId: string; serverName: string }> = [];

    if (isHydraMcpInSession && isHydraMcpHealthy) {
      hydraMcpTools.forEach((tool) => {
        tools.push({ name: tool.name, serverId: 'hydra-mcp', serverName: 'Hydra MCP' });
      });
    }

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

  const activePrompts = useMemo(() => {
    const prompts: Array<{ name: string; description?: string | null; serverId: string; serverName: string }> = [];

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

  // ── Model capability detection ─────────────────────────────────────
  const supportsReasoning = useMemo(() => {
    if (!activeLLMProvider) return false;
    const model = activeLLMProvider.model.toLowerCase();
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
    return activeLLMProvider.type === 'openrouter';
  }, [activeLLMProvider]);

  // ── Infrastructure context ─────────────────────────────────────────
  const infraContext = useInfrastructureContext();

  // ── Cache store ────────────────────────────────────────────────────
  const { invalidateMessages } = useChatCacheStore();

  // ── Message deduplication ──────────────────────────────────────────
  const allMessages = useMemo(() => {
    const serverMessageIds = new Set(messages.map((m) => m.messageId));
    const serverContentSignatures = new Set(
      messages.map((m) => `${m.role}:${m.content}`)
    );

    const uniqueLocalMessages = localMessages.filter((local) => {
      if (serverMessageIds.has(local.messageId)) return false;
      if (local.role !== 'user' && serverContentSignatures.has(`${local.role}:${local.content}`)) {
        return false;
      }
      return true;
    });

    const combined = [...messages, ...uniqueLocalMessages];
    return combined.sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
    });
  }, [messages, localMessages]);

  const appendLocalMessage = useCallback(
    (payload: Pick<ChatMessageResponse, 'role' | 'content' | 'toolCalls'> & { error?: boolean }) => {
      const now = Date.now();
      setLocalMessages((prev) => [
        ...prev,
        {
          messageId: `local_${now}_${Math.random().toString(36).slice(2, 8)}`,
          sessionId: currentSessionId || 'local',
          role: payload.role as ChatMessageRole,
          content: payload.content,
          toolCalls: payload.toolCalls,
          order: 1000000 + prev.length,
          createdAt: new Date().toISOString(),
          error: payload.error,
        },
      ]);
    },
    [currentSessionId]
  );

  // ── WebSocket callbacks ────────────────────────────────────────────
  const handleWSMessage = useCallback(
    (message: { id: string; role: string; content: string; toolCalls?: unknown[] }, usage?: SessionUsage) => {
      if (usage) {
        setSessionUsage(usage);
      }
      setStreamingContent('');

      const localMessageId = message.id || `local_assistant_${Date.now()}`;

      setLocalMessages((prev) => {
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
            order: 1000000 + prev.length,
            createdAt: new Date().toISOString(),
          },
        ];
      });

      if (currentSessionId) {
        invalidateMessages(currentSessionId);
        refetchMessages();
      }
    },
    [currentSessionId, invalidateMessages, refetchMessages]
  );

  const handleWSError = useCallback((error: string) => {
    setLocalMessages((prev) => [
      ...prev,
      {
        messageId: `local_error_${Date.now()}`,
        sessionId: currentSessionId || 'local',
        role: 'assistant' as ChatMessageRole,
        content: `Error: ${error}`,
        order: 1000000 + prev.length,
        createdAt: new Date().toISOString(),
        error: true,
      },
    ]);
    setStreamingContent('');
  }, [currentSessionId]);

  // ── WebSocket connection ───────────────────────────────────────────
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

  // ── Session bootstrap & lifecycle ──────────────────────────────────
  const hasBootstrappedRef = useRef(false);

  useEffect(() => {
    if (!sessionsData) return;

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
    if (!currentSessionId || isStreaming) return;

    const sessionExists = sessions.some(
      (session) => session.sessionId === currentSessionId
    );
    if (!sessionExists && sessions.length > 0) {
      setCurrentSessionId(sessions[0].sessionId);
    }
  }, [currentSessionId, sessions, isStreaming]);

  useEffect(() => {
    if (!currentSession || !defaultProvider) return;
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
    if (prevSessionIdRef.current !== currentSessionId) {
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

  // ── Event handlers ─────────────────────────────────────────────────

  const handleSend = useCallback(
    async (text?: string) => {
      const messageText = text || input.trim();
      if (!messageText || isStreaming || !currentSessionId) return;

      const providerReady =
        activeLLMProvider?.apiKeySet || activeLLMProvider?.type === 'ollama';
      if (!providerReady) {
        return { needsLLMConfig: true };
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
      appendLocalMessage({ role: 'user', content: messageText });
      wsSendMessage(messageText);
    },
    [input, isStreaming, currentSessionId, activeLLMProvider, wsConnected, wsConnect, appendLocalMessage, wsSendMessage]
  );

  const handleCreateProject = useCallback(
    (name: string, onSuccess?: () => void) => {
      if (!name.trim()) return;
      createProjectMutation.mutate(
        { name: name.trim() },
        {
          onSuccess: (project) => {
            onSuccess?.();
            return project;
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
    },
    [createProjectMutation, toast]
  );

  const handleRenameProject = useCallback(
    (projectId: string, newName: string) => {
      if (!newName.trim()) return;
      updateProjectMutation.mutate(
        { projectId, data: { name: newName.trim() } },
        {
          onError: () => {
            toast({
              title: 'Failed to rename project',
              description: 'Please try again.',
              variant: 'destructive',
            });
          },
        }
      );
    },
    [updateProjectMutation, toast]
  );

  const handleDeleteProject = useCallback(
    (projectId: string) => {
      const sessionsInProject = sessions.filter((s) => s.projectId === projectId);
      const currentInProject = sessionsInProject.some((s) => s.sessionId === currentSessionId);

      deleteProjectMutation.mutate(
        { projectId, cascade: true },
        {
          onSuccess: () => {
            if (currentInProject) {
              setCurrentSessionId(null);
            }
          },
          onError: () => {
            toast({
              title: 'Failed to delete project',
              description: 'Please try again.',
              variant: 'destructive',
            });
          },
        }
      );
    },
    [sessions, currentSessionId, deleteProjectMutation, toast]
  );

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      setCurrentSessionId(sessionId);
      setLocalMessages([]);
    },
    []
  );

  const handleNewChat = useCallback(
    (projectId?: string, onSuccess?: () => void) => {
      createSessionMutation.mutate(
        { title: 'New Chat', projectId },
        {
          onSuccess: (session) => {
            setCurrentSessionId(session.sessionId);
            onSuccess?.();
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
    },
    [createSessionMutation, toast]
  );

  const handleSetActiveProvider = useCallback(
    (providerId: string) => {
      if (!currentSession) return;
      updateSessionMutation.mutate({
        sessionId: currentSession.sessionId,
        data: { llmProviderId: providerId },
      });
    },
    [currentSession, updateSessionMutation]
  );

  const handleConnectServer = useCallback(
    (serverId: string) => {
      if (!currentSession) return;
      const nextServerIds = Array.from(
        new Set([...(currentSession.mcpServerIds || []), serverId])
      );
      updateSessionMutation.mutate({
        sessionId: currentSession.sessionId,
        data: { mcpServerIds: nextServerIds },
      });
    },
    [currentSession, updateSessionMutation]
  );

  const handleDisconnectServer = useCallback(
    (serverId: string) => {
      if (!currentSession) return;
      const nextServerIds = (currentSession.mcpServerIds || []).filter(
        (id) => id !== serverId
      );
      updateSessionMutation.mutate({
        sessionId: currentSession.sessionId,
        data: { mcpServerIds: nextServerIds },
      });
    },
    [currentSession, updateSessionMutation]
  );

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
        data: { projectId: projectId ?? undefined },
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
      } catch {
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

  const handleCreateProvider = useCallback(
    (data: LLMProviderCreate) => {
      createProviderMutation.mutate(data, {
        onError: () => {
          toast({
            title: 'Failed to add provider',
            description: 'Please check the configuration and try again.',
            variant: 'destructive',
          });
        },
      });
    },
    [createProviderMutation, toast]
  );

  const handleUpdateProvider = useCallback(
    (providerId: string, updates: { apiKey?: string }) => {
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
    },
    [updateProviderMutation, toast]
  );

  const handleDeleteProvider = useCallback(
    (providerId: string) => {
      deleteProviderMutation.mutate(providerId, {
        onError: () => {
          toast({
            title: 'Failed to remove provider',
            description: 'Please try again.',
            variant: 'destructive',
          });
        },
      });
    },
    [deleteProviderMutation, toast]
  );

  const handleValidateProvider = useCallback(
    (providerId: string) => {
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
    },
    [validateProviderMutation, toast]
  );

  return {
    // Core state
    currentSessionId,
    input,
    setInput,
    streamingContent,
    reasoningLevel,
    setReasoningLevel,
    webSearchEnabled,
    setWebSearchEnabled,
    modelConfig,
    setModelConfig,
    sessionUsage,
    messagesEndRef,

    // Derived data
    projects,
    sessions,
    standaloneSessions,
    currentSession,
    llmProviders,
    activeLLMProviderId,
    activeLLMProvider,
    llmConfigLocked,
    sessionContext,
    allMessages,
    infraContext,

    // MCP state
    isHydraMcpInSession,
    isHydraMcpHealthy,
    hydraMcpHealth,
    hydraMcpTools,
    hydraMcpPrompts,
    serversWithTools,
    activeTools,
    activePrompts,

    // Model capabilities
    supportsReasoning,
    supportsWebSearch,

    // WebSocket state
    wsConnected,
    isStreaming,

    // Session handlers
    handleSelectSession,
    handleNewChat,
    handleDeleteSession,
    handleRenameSession,
    handleMoveSessionToProject,
    handleDuplicateSession,
    handleExportSession,
    handleCreateProject,
    handleRenameProject,
    handleDeleteProject,
    handleSend,

    // LLM provider handlers
    handleSetActiveProvider,
    handleCreateProvider,
    handleUpdateProvider,
    handleDeleteProvider,
    handleValidateProvider,

    // MCP server handlers
    handleConnectServer,
    handleDisconnectServer,

    // Retry
    retryMessage: wsRetryMessage,
  };
}
