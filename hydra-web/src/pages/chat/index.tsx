import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import {
  MessageSquare,
  Loader2,
  Bot,
  Sparkles,
  Zap,
  Server,
  Plus,
  AlertCircle,
  FolderOpen,
  Store,
  Globe,
  Terminal,
  Network,
  AlertTriangle,
  Boxes,
  Wrench,
  Menu,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import { useMCPChat } from '@/hooks/use-mcp-chat';
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
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/use-toast';

import {
  ChatHeader,
  ChatInput,
  MessageBubble,
  ChatListItem,
  ProjectFolder,
  UnorganizedDropTarget,
} from './components';
import type { ReasoningLevel } from './components';
import { NewProjectModal, MCPConfigModal, LLMConfigModal } from './modals';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';

const suggestedPrompts = [
  { icon: Server, text: 'List all compute nodes', category: 'nodes' },
  { icon: Boxes, text: 'Show services with health issues', category: 'services' },
  { icon: Network, text: 'What networks are configured?', category: 'networks' },
  { icon: AlertTriangle, text: 'Show unacknowledged alerts', category: 'alerts' },
];

const useInfrastructureContext = () => {
  const { data: nodesData } = useNodes({ limit: 1 });
  const { data: servicesData } = useServices({ limit: 1 });
  const { data: networksData } = useNetworks({ limit: 1 });

  return useMemo(
    () => ({
      nodes: nodesData?.total ?? 0,
      services: servicesData?.total ?? 0,
      networks: networksData?.total ?? 0,
      alerts: 0, // TODO: Wire to alerts API when ready
    }),
    [nodesData, servicesData, networksData]
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
  const [sidebarTab, setSidebarTab] = useState<'chats' | 'tools'>('chats');
  const [expandedProjects, setExpandedProjects] = useState<string[]>([]);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [showMCPConfigModal, setShowMCPConfigModal] = useState(false);
  const [showLLMConfigModal, setShowLLMConfigModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [streamingContent, setStreamingContent] = useState('');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [reasoningLevel, setReasoningLevel] = useState<ReasoningLevel>('none');
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [showAllTools, setShowAllTools] = useState(false);
  const [showAllPrompts, setShowAllPrompts] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const infraContext = useInfrastructureContext();

  const messages = messagesData?.messages || [];
  const { data: sessionContextData } = useSessionContext(currentSessionId);
  const sessionContext = sessionContextData?.context ?? null;
  const llmConfigLocked = currentSession?.llmConfigLocked ?? false;
  const { invalidateMessages } = useChatCacheStore();

  // Stable callbacks for WebSocket hook - uses the actual message data
  const handleWSMessage = useCallback(
    (message: { id: string; role: string; content: string; toolCalls?: unknown[] }) => {
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

  const getProjectSessions = (projectId: string) =>
    sessions.filter((session) => session.projectId === projectId);

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
    connect: wsConnect,
    disconnect: wsDisconnect,
  } = useMCPChat({
    sessionId: currentSessionId,
    providerId: activeLLMProviderId,
    reasoningLevel,
    webSearchEnabled,
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

  return (
    <TooltipProvider>
      <div className="h-[calc(100vh-3.5rem)] flex gap-4 p-4 bg-background relative">
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

        <div
          className={cn(
            'flex flex-col bg-card border border-border rounded-lg overflow-hidden min-h-0',
            'fixed inset-y-0 left-0 z-40 w-72 m-4 transition-transform duration-200 ease-in-out',
            'md:static md:translate-x-0 md:shrink-0',
            mobileSidebarOpen ? 'translate-x-0' : '-translate-x-[calc(100%+2rem)]'
          )}
        >
          <Tabs
            value={sidebarTab}
            onValueChange={(v) => setSidebarTab(v as 'chats' | 'tools')}
            className="flex flex-col h-full min-h-0"
          >
            <TabsList className="w-full rounded-none border-b border-border bg-transparent h-auto p-0 shrink-0">
              <TabsTrigger
                value="chats"
                className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-blue-500 data-[state=active]:bg-transparent py-3 text-muted-foreground data-[state=active]:text-foreground"
              >
                <MessageSquare className="h-4 w-4 mr-2" />
                Chats
              </TabsTrigger>
              <TabsTrigger
                value="tools"
                className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-blue-500 data-[state=active]:bg-transparent py-3 text-muted-foreground data-[state=active]:text-foreground"
              >
                <Wrench className="h-4 w-4 mr-2" />
                Tools
              </TabsTrigger>
            </TabsList>

            <TabsContent value="chats" className="data-[state=inactive]:hidden flex-1 m-0 overflow-hidden flex flex-col">
              <div className="p-2 border-b border-border shrink-0 flex gap-2">
                <Button
                  onClick={() => handleNewChat()}
                  variant="outline"
                  className="flex-1 border-border text-foreground hover:bg-muted bg-transparent"
                  size="sm"
                >
                  <Plus className="h-4 w-4 mr-1" />
                  New Chat
                </Button>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      onClick={() => setShowNewProjectModal(true)}
                      variant="ghost"
                      size="sm"
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <FolderOpen className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="bg-popover text-popover-foreground border-border">
                    New Project
                  </TooltipContent>
                </Tooltip>
              </div>

              <ScrollArea className="flex-1">
                <DndProvider backend={HTML5Backend}>
                  <div className="p-2">
                    {projects.length > 0 && (
                      <div className="mb-3">
                        <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-2 mb-1">
                          Projects
                        </h4>
                        <div className="space-y-0.5">
                          {projects.map((project) => {
                            const projectSessions = getProjectSessions(project.projectId);
                            return (
                              <ProjectFolder
                                key={project.projectId}
                                project={project}
                                sessionCount={projectSessions.length}
                                isOpen={expandedProjects.includes(project.projectId)}
                                onOpenChange={() => toggleProjectExpand(project.projectId)}
                                onDrop={(sessionId) =>
                                  handleMoveSessionToProject(sessionId, project.projectId)
                                }
                              >
                                {projectSessions.map((session) => (
                                  <ChatListItem
                                    key={session.sessionId}
                                    session={session}
                                    isActive={currentSessionId === session.sessionId}
                                    onSelect={() => handleSelectSession(session.sessionId)}
                                    onRename={(newTitle) =>
                                      handleRenameSession(session.sessionId, newTitle)
                                    }
                                    onMoveToProject={(projectId) =>
                                      handleMoveSessionToProject(session.sessionId, projectId)
                                    }
                                    onDuplicate={() => handleDuplicateSession(session.sessionId)}
                                    onExport={() => handleExportSession(session.sessionId)}
                                    onDelete={() => handleDeleteSession(session.sessionId)}
                                    projects={projects}
                                  />
                                ))}
                                <button
                                  onClick={() => handleNewChat(project.projectId)}
                                  className="w-full flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                                >
                                  <Plus className="h-3 w-3" />
                                  New Chat
                                </button>
                              </ProjectFolder>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    <UnorganizedDropTarget
                      onDrop={(sessionId) => handleMoveSessionToProject(sessionId, null)}
                    >
                      <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-2 mb-1">
                        Recent Chats
                      </h4>
                      <div className="space-y-0.5">
                        {standaloneSessions.map((session) => (
                          <ChatListItem
                            key={session.sessionId}
                            session={session}
                            isActive={currentSessionId === session.sessionId}
                            onSelect={() => handleSelectSession(session.sessionId)}
                            onRename={(newTitle) =>
                              handleRenameSession(session.sessionId, newTitle)
                            }
                            onMoveToProject={(projectId) =>
                              handleMoveSessionToProject(session.sessionId, projectId)
                            }
                            onDuplicate={() => handleDuplicateSession(session.sessionId)}
                            onExport={() => handleExportSession(session.sessionId)}
                            onDelete={() => handleDeleteSession(session.sessionId)}
                            projects={projects}
                          />
                        ))}
                        {standaloneSessions.length === 0 && sessions.length === 0 && (
                          <p className="text-[11px] text-muted-foreground/70 px-2 py-2">No chats yet</p>
                        )}
                      </div>
                    </UnorganizedDropTarget>
                  </div>
                </DndProvider>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="tools" className="flex-1 min-h-0 m-0 p-0 overflow-hidden flex flex-col">
              <div className="flex-1 min-h-0 overflow-y-auto">
                <div className="p-3 space-y-4">
                  {/* Dedicated Hydra MCP Section */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                        <Terminal className="h-3.5 w-3.5 text-violet-500" />
                        Hydra MCP
                        <Badge
                          variant="secondary"
                          className="text-[8px] px-1 h-3.5 bg-violet-500/20 text-violet-400 border-0"
                        >
                          Built-in
                        </Badge>
                      </h4>
                    </div>
                    <div
                      className={cn(
                        'rounded-lg p-3 transition-colors cursor-pointer border',
                        isHydraMcpInSession && isHydraMcpHealthy
                          ? 'bg-emerald-500/5 border-emerald-500/20 hover:bg-emerald-500/10'
                          : isHydraMcpInSession && !isHydraMcpHealthy
                            ? 'bg-red-500/5 border-red-500/20 hover:bg-red-500/10'
                            : 'bg-muted/30 border-border hover:bg-muted/60'
                      )}
                      onClick={() =>
                        isHydraMcpInSession
                          ? handleDisconnectServer('hydra-mcp')
                          : handleConnectServer('hydra-mcp')
                      }
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={cn(
                            'h-10 w-10 rounded-md flex items-center justify-center shrink-0',
                            isHydraMcpInSession && isHydraMcpHealthy
                              ? 'bg-emerald-500/20'
                              : isHydraMcpInSession && !isHydraMcpHealthy
                                ? 'bg-red-500/20'
                                : 'bg-muted'
                          )}
                        >
                          <Terminal className="h-5 w-5 text-violet-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium text-foreground">
                              {hydraMcpHealth?.serverName || 'Hydra MCP Server'}
                            </span>
                            <div
                              className={cn(
                                'h-2 w-2 rounded-full shrink-0',
                                isHydraMcpHealthy
                                  ? 'bg-emerald-500'
                                  : isHydraMcpInSession
                                    ? 'bg-red-500'
                                    : 'bg-muted-foreground'
                              )}
                              title={
                                isHydraMcpHealthy
                                  ? 'healthy'
                                  : isHydraMcpInSession
                                    ? 'unhealthy'
                                    : 'not connected'
                              }
                            />
                          </div>
                          <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">
                            {isHydraMcpHealthy
                              ? 'Part of Hydra ecosystem — access infrastructure tools'
                              : isHydraMcpInSession
                                ? hydraMcpHealth?.message || 'Server unreachable'
                                : 'Connect to access infrastructure tools'}
                          </p>
                          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                            {isHydraMcpHealthy && (
                              <>
                                <Badge
                                  variant="secondary"
                                  className="text-[9px] px-1.5 h-4 bg-blue-500/20 text-blue-400 border-0"
                                >
                                  {hydraMcpHealth?.toolsCount || hydraMcpTools.length} tools
                                </Badge>
                                <Badge
                                  variant="secondary"
                                  className="text-[9px] px-1.5 h-4 bg-amber-500/20 text-amber-400 border-0"
                                >
                                  {hydraMcpHealth?.promptsCount || hydraMcpPrompts.length} prompts
                                </Badge>
                              </>
                            )}
                            <span className="text-[9px] text-muted-foreground/70">
                              {isHydraMcpInSession ? 'Click to disconnect' : 'Click to connect'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* External MCP Servers Section */}
                  {serversWithTools.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                          <Server className="h-3.5 w-3.5 text-cyan-500" />
                          External MCP Servers
                        </h4>
                        <Link to={ROUTES.MCP_MARKETPLACE}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 text-[10px] px-2 text-muted-foreground hover:text-foreground"
                          >
                            <Store className="h-3 w-3 mr-1" />
                            Add More
                          </Button>
                        </Link>
                      </div>
                      <div className="space-y-2">
                        {serversWithTools.map((mcp) => {
                          const statusColor = mcp.isActive
                            ? 'bg-emerald-500'
                            : mcp.status === 'unhealthy'
                              ? 'bg-red-500'
                              : 'bg-muted-foreground';

                          return (
                            <div
                              key={mcp.serverId}
                              className={cn(
                                'rounded-lg p-3 transition-colors cursor-pointer border',
                                mcp.isActive
                                  ? 'bg-emerald-500/5 border-emerald-500/20 hover:bg-emerald-500/10'
                                  : 'bg-muted/30 border-border hover:bg-muted/60'
                              )}
                              onClick={() =>
                                mcp.isActive
                                  ? handleDisconnectServer(mcp.serverId)
                                  : handleConnectServer(mcp.serverId)
                              }
                            >
                              <div className="flex items-start gap-3">
                                <div
                                  className={cn(
                                    'h-9 w-9 rounded-md flex items-center justify-center shrink-0',
                                    mcp.isActive ? 'bg-emerald-500/20' : 'bg-muted'
                                  )}
                                >
                                  <Globe className="h-4 w-4 text-cyan-400" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs font-medium text-foreground">
                                      {mcp.name}
                                    </span>
                                    <div
                                      className={cn('h-2 w-2 rounded-full shrink-0', statusColor)}
                                      title={mcp.isActive ? 'active' : mcp.status}
                                    />
                                  </div>
                                  <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2 leading-relaxed">
                                    {mcp.description || mcp.category}
                                  </p>
                                  <div className="flex items-center gap-2 mt-1.5">
                                    <Badge
                                      variant="secondary"
                                      className="text-[9px] px-1.5 h-4 bg-muted/80 text-muted-foreground"
                                    >
                                      {mcp.tools.length} tools
                                    </Badge>
                                    <span className="text-[9px] text-muted-foreground/70">
                                      {mcp.isActive ? 'Click to disconnect' : 'Click to connect'}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {serversWithTools.length === 0 && (
                    <div className="flex items-center justify-center py-2">
                      <Link to={ROUTES.MCP_MARKETPLACE}>
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-[10px] text-muted-foreground hover:text-foreground"
                        >
                          <Store className="h-3 w-3 mr-1" />
                          Browse MCP Marketplace
                        </Button>
                      </Link>
                    </div>
                  )}

                  {/* Dynamic Available Tools Section */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <Wrench className="h-3.5 w-3.5 text-blue-500" />
                      Available Tools
                      <Badge variant="secondary" className="text-[9px] px-1.5 h-4 bg-muted text-muted-foreground ml-1">
                        {activeTools.length}
                      </Badge>
                    </h4>
                    <div className="grid grid-cols-2 gap-1.5">
                      {(showAllTools ? activeTools : activeTools.slice(0, 12)).map((tool, idx) => (
                        <Tooltip key={`${tool.serverId}-${tool.name}-${idx}`}>
                          <TooltipTrigger asChild>
                            <button
                              onClick={() => handleSend(`Use the ${tool.name} tool`)}
                              className="px-2 py-1.5 rounded bg-blue-500/10 border border-blue-500/20 text-[10px] font-mono text-blue-400 truncate hover:bg-blue-500/20 transition-colors text-left"
                            >
                              {tool.name}
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="bg-popover text-popover-foreground border-border">
                            <p className="text-xs">
                              {tool.serverName}
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      ))}
                    </div>
                    {activeTools.length > 12 && (
                      <button
                        onClick={() => setShowAllTools(!showAllTools)}
                        className="w-full text-[10px] text-muted-foreground hover:text-foreground py-1 hover:bg-muted/50 rounded transition-colors"
                      >
                        {showAllTools ? 'Show less' : `+${activeTools.length - 12} more tools`}
                      </button>
                    )}
                    {activeTools.length === 0 && (
                      <p className="text-[11px] text-muted-foreground/70 text-center py-2">
                        Connect an MCP service to see available tools
                      </p>
                    )}
                  </div>

                  {/* Dynamic Available Prompts Section */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                      Available Prompts
                      <Badge variant="secondary" className="text-[9px] px-1.5 h-4 bg-muted text-muted-foreground ml-1">
                        {activePrompts.length}
                      </Badge>
                    </h4>
                    <div className="space-y-1.5">
                      {activePrompts.length > 0 ? (
                        (showAllPrompts ? activePrompts : activePrompts.slice(0, 6)).map((prompt, idx) => (
                          <button
                            key={`${prompt.serverId}-${prompt.name}-${idx}`}
                            onClick={() => handleSend(`Run the ${prompt.name} prompt`)}
                            className="w-full text-left px-2.5 py-2 rounded bg-amber-500/10 border border-amber-500/20 text-[10px] text-amber-400 hover:bg-amber-500/15 transition-colors"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono">{prompt.name}</span>
                              <span className="text-[8px] text-muted-foreground">{prompt.serverName}</span>
                            </div>
                            {prompt.description && (
                              <p className="text-[9px] text-muted-foreground mt-0.5 line-clamp-2">
                                {prompt.description}
                              </p>
                            )}
                          </button>
                        ))
                      ) : (
                        <p className="text-[11px] text-muted-foreground/70 text-center py-2">
                          Connect an MCP service to see available prompts
                        </p>
                      )}
                      {activePrompts.length > 6 && (
                        <button
                          onClick={() => setShowAllPrompts(!showAllPrompts)}
                          className="w-full text-[10px] text-muted-foreground hover:text-foreground py-1 hover:bg-muted/50 rounded transition-colors"
                        >
                          {showAllPrompts ? 'Show less' : `+${activePrompts.length - 6} more prompts`}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="border-t border-border p-3 space-y-3 shrink-0">
                <div className="space-y-2">
                  <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <Zap className="h-3 w-3 text-cyan-500" />
                    Quick Actions
                  </h4>
                  <div className="grid grid-cols-2 gap-1">
                    {[
                      { icon: Server, text: 'List nodes' },
                      { icon: Boxes, text: 'Unhealthy services' },
                      { icon: Network, text: 'Show networks' },
                      { icon: AlertTriangle, text: 'Active alerts' },
                      { icon: Globe, text: 'Topology overview' },
                      { icon: Terminal, text: 'Recent changes' },
                    ].map((prompt, i) => (
                      <button
                        key={i}
                        onClick={() => handleSend(prompt.text)}
                        className="flex items-center gap-1.5 px-2 py-1.5 rounded text-[10px] text-muted-foreground hover:bg-cyan-500/10 hover:text-cyan-400 transition-colors text-left border border-border hover:border-cyan-500/30"
                      >
                        <prompt.icon className="h-3 w-3 shrink-0" />
                        <span className="truncate">{prompt.text}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                    Context
                  </h4>
                  <div className="grid grid-cols-4 gap-1">
                    <div className="p-1.5 rounded bg-muted/60 text-center">
                      <div className="text-sm font-bold text-foreground">{infraContext.nodes}</div>
                      <div className="text-[9px] text-muted-foreground">Nodes</div>
                    </div>
                    <div className="p-1.5 rounded bg-muted/60 text-center">
                      <div className="text-sm font-bold text-foreground">{infraContext.services}</div>
                      <div className="text-[9px] text-muted-foreground">Svcs</div>
                    </div>
                    <div className="p-1.5 rounded bg-muted/60 text-center">
                      <div className="text-sm font-bold text-foreground">{infraContext.networks}</div>
                      <div className="text-[9px] text-muted-foreground">Nets</div>
                    </div>
                    <div className="p-1.5 rounded bg-muted/60 text-center">
                      <div className="text-sm font-bold text-foreground">{infraContext.alerts}</div>
                      <div className="text-[9px] text-muted-foreground">Alerts</div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 p-2 rounded-md bg-blue-500/5 border border-blue-500/20">
                  <Sparkles className="h-4 w-4 text-blue-500 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-foreground truncate">
                      {activeLLMProvider?.name || 'No LLM Selected'}
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      {activeLLMProvider?.type || 'Configure in settings'}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[10px] px-2 shrink-0 text-muted-foreground hover:text-foreground"
                    onClick={() => setShowLLMConfigModal(true)}
                  >
                    Switch
                  </Button>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        <div className="flex-1 flex flex-col bg-card border border-border rounded-lg overflow-hidden min-w-0">
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

          <div className="flex-1 overflow-y-auto">
            <div className="p-4 space-y-4 max-w-4xl mx-auto">
              {allMessages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center py-12">
                  <div className="rounded-full bg-blue-600/10 p-4">
                    <Bot className="h-8 w-8 text-blue-500" />
                  </div>
                  <h2 className="mt-4 text-xl font-semibold text-foreground">
                    How can I help you today?
                  </h2>
                  <p className="mt-2 text-muted-foreground max-w-md">
                    Ask me about your infrastructure. I can help you find nodes, services, analyze
                    topology, and answer questions about your setup.
                  </p>

                  <div className="mt-8 max-w-2xl">
                    <div className="flex items-center gap-2 mb-3 justify-center">
                      <Sparkles className="h-4 w-4 text-amber-500" />
                      <span className="text-xs text-muted-foreground">Suggested prompts</span>
                    </div>
                    <div className="flex flex-wrap gap-2 justify-center">
                      {suggestedPrompts.map((prompt, index) => (
                        <Button
                          key={index}
                          variant="outline"
                          size="sm"
                          onClick={() => handleSend(prompt.text)}
                          className="h-auto py-1.5 text-xs border-border text-foreground hover:bg-muted bg-transparent"
                          disabled={isStreaming}
                        >
                          <prompt.icon className="h-3 w-3 mr-2" />
                          {prompt.text}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  {allMessages.map((message) => (
                    <MessageBubble key={message.messageId} message={message} />
                  ))}
                  {isStreaming && (
                    <div className="flex gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                        <Bot className="h-4 w-4 text-muted-foreground animate-pulse" />
                      </div>
                      <div className="flex-1 max-w-[80%]">
                        <div className="rounded-lg p-4 bg-muted">
                          {streamingContent ? (
                            <p className="text-sm text-foreground whitespace-pre-wrap">{streamingContent}</p>
                          ) : (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              <span>Thinking...</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          <ChatInput
            value={input}
            onChange={setInput}
            onSend={() => handleSend()}
            isStreaming={isStreaming}
            reasoningLevel={reasoningLevel}
            webSearchEnabled={webSearchEnabled}
            supportsReasoning={supportsReasoning}
            supportsWebSearch={supportsWebSearch}
            onReasoningLevelChange={setReasoningLevel}
            onWebSearchToggle={setWebSearchEnabled}
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
