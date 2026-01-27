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
  useCreateChatProject,
  useCreateChatSession,
  useUpdateChatSession,
  useDeleteChatSession,
  useBulkUpsertMessages,
  type ChatMessageResponse,
  type ChatMessageRole,
} from '@/api/chat';
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
  type MCPToolInfo,
  type MCPToolsResponse,
  type MCPResourcesResponse,
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
  const llmProviders = llmProvidersData?.providers || [];
  const servers = mcpServersData?.servers || [];

  const currentSession =
    sessions.find((session) => session.sessionId === currentSessionId) || null;

  const defaultProvider = llmProviders.find((provider) => provider.isDefault);
  const activeLLMProviderId =
    currentSession?.llmProviderId || defaultProvider?.providerId || null;
  const activeLLMProvider = llmProviders.find(
    (provider) => provider.providerId === activeLLMProviderId
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

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const infraContext = useInfrastructureContext();

  const messages = messagesData?.messages || [];
  const standaloneSessions = useMemo(
    () => sessions.filter((session) => !session.projectId),
    [sessions]
  );

  const getProjectSessions = (projectId: string) =>
    sessions.filter((session) => session.projectId === projectId);

  const isHydraMcpConnected = activeServerIds.includes('hydra-mcp');

  const toolsQueries = useQueries({
    queries: servers.map((server) => ({
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
    queries: servers.map((server) => ({
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

  const toolsByServerId = useMemo(() => {
    const toolMap = new Map<string, MCPToolInfo[]>();
    servers.forEach((server, index) => {
      const tools = toolsQueries[index]?.data?.tools || [];
      toolMap.set(server.serverId, tools);
    });
    return toolMap;
  }, [servers, toolsQueries]);

  const resourcesByServerId = useMemo(() => {
    const resourceMap = new Map<string, MCPResourcesResponse['resources']>();
    servers.forEach((server, index) => {
      const resources = resourcesQueries[index]?.data?.resources || [];
      resourceMap.set(server.serverId, resources);
    });
    return resourceMap;
  }, [servers, resourcesQueries]);

  const serversWithTools = useMemo(
    () =>
      servers.map((server) => ({
        ...server,
        isActive: activeServerIds.includes(server.serverId),
        tools: toolsByServerId.get(server.serverId) || [],
        resources: resourcesByServerId.get(server.serverId) || [],
      })),
    [servers, activeServerIds, toolsByServerId, resourcesByServerId]
  );

  const activeTools = useMemo(() => {
    return activeServerIds.flatMap((serverId) =>
      (toolsByServerId.get(serverId) || []).map((tool) => tool.name)
    );
  }, [activeServerIds, toolsByServerId]);

  const allMessages = useMemo(() => {
    const combined = [...messages, ...localMessages];
    return combined.sort((a, b) => a.order - b.order);
  }, [messages, localMessages]);

  const appendLocalMessage = (
    payload: Pick<ChatMessageResponse, 'role' | 'content' | 'toolCalls'> & { error?: boolean }
  ) => {
    setLocalMessages((prev) => [
      ...prev,
      {
        messageId: `local_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        sessionId: currentSessionId || 'local',
        role: payload.role as ChatMessageRole,
        content: payload.content,
        toolCalls: payload.toolCalls,
        order: messages.length + prev.length,
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
    onMessage: () => {
      setStreamingContent('');
      setLocalMessages([]);
      if (currentSessionId) {
        refetchMessages();
      }
    },
    onError: (error) => {
      appendLocalMessage({
        role: 'assistant',
        content: `Error: ${error}`,
        error: true,
      });
      setStreamingContent('');
    },
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

    const sessionExists = sessions.some(
      (session) => session.sessionId === currentSessionId
    );
    if (!sessionExists && sessions.length > 0) {
      setCurrentSessionId(sessions[0].sessionId);
    }
  }, [currentSessionId, sessions]);

  useEffect(() => {
    if (!currentSession || !defaultProvider) {
      return;
    }
    if (!currentSession.llmProviderId) {
      updateSessionMutation.mutate({
        sessionId: currentSession.sessionId,
        data: { llmProviderId: defaultProvider.providerId },
      });
    }
  }, [currentSession, defaultProvider, updateSessionMutation]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [allMessages, isStreaming]);

  useEffect(() => {
    setLocalMessages([]);
    setStreamingContent('');
  }, [currentSessionId]);

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
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                        <Server className="h-3.5 w-3.5 text-violet-500" />
                        MCP Services
                      </h4>
                      <Link to={ROUTES.MCP_MARKETPLACE}>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-[10px] px-2 text-muted-foreground hover:text-foreground"
                        >
                          <Store className="h-3 w-3 mr-1" />
                          Marketplace
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
                                {mcp.serverId === 'hydra-mcp' ? (
                                  <Terminal className="h-4 w-4 text-violet-400" />
                                ) : (
                                  <Globe className="h-4 w-4 text-cyan-400" />
                                )}
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

                  <div className="space-y-3">
                    <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <Wrench className="h-3.5 w-3.5 text-blue-500" />
                      Available Tools
                      <Badge variant="secondary" className="text-[9px] px-1.5 h-4 bg-muted text-muted-foreground ml-1">
                        {activeTools.length}
                      </Badge>
                    </h4>
                    <div className="grid grid-cols-2 gap-1.5">
                      {activeTools.slice(0, 12).map((tool) => (
                        <button
                          key={tool}
                          onClick={() => handleSend(`Use the ${tool} tool`)}
                          className="px-2 py-1.5 rounded bg-blue-500/10 border border-blue-500/20 text-[10px] font-mono text-blue-400 truncate hover:bg-blue-500/20 transition-colors text-left"
                          title={`Execute ${tool} via LLM`}
                        >
                          {tool}
                        </button>
                      ))}
                    </div>
                    {activeTools.length > 12 && (
                      <button className="w-full text-[10px] text-muted-foreground hover:text-foreground py-1">
                        +{activeTools.length - 12} more tools
                      </button>
                    )}
                    {activeTools.length === 0 && (
                      <p className="text-[11px] text-muted-foreground/70 text-center py-2">
                        Connect an MCP service to see available tools
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                      Available Prompts
                    </h4>
                    <div className="space-y-1.5">
                      {[
                        { name: 'infrastructure_summary', desc: 'Get a summary of your infrastructure', message: 'Give me a comprehensive summary of my entire infrastructure including all nodes, services, networks, and their current status' },
                        { name: 'health_check', desc: 'Check health of all services', message: 'Run a health check on all services and report any issues or warnings' },
                        { name: 'node_diagnostics', desc: 'Run diagnostics on a specific node', message: 'Run comprehensive diagnostics on my infrastructure nodes' },
                      ].map((prompt) => (
                        <button
                          key={prompt.name}
                          onClick={() => handleSend(prompt.message)}
                          className="w-full text-left px-2.5 py-2 rounded bg-amber-500/10 border border-amber-500/20 text-[10px] text-amber-400 hover:bg-amber-500/15 transition-colors"
                        >
                          <span className="font-mono">{prompt.name}</span>
                          <p className="text-[9px] text-muted-foreground mt-0.5">{prompt.desc}</p>
                        </button>
                      ))}
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
            onLLMProviderChange={handleSetActiveProvider}
            onOpenLLMConfig={() => setShowLLMConfigModal(true)}
            onRenameSession={(newTitle) =>
              currentSession && handleRenameSession(currentSession.sessionId, newTitle)
            }
            onDuplicateSession={() => handleDuplicateSession()}
            onExportSession={() => handleExportSession()}
            onDeleteSession={() => handleDeleteSession()}
          />

          {!isHydraMcpConnected && (
            <div className="mx-4 mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-foreground">
                MCP is offline. Start{' '}
                <code className="bg-muted px-1 rounded text-foreground">hydra-mcp</code> and
                connect it in the Tools tab.
              </span>
            </div>
          )}

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
