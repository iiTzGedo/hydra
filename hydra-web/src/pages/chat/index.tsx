/**
 * Chat Page with MCP Integration - Redesigned with Left Sidebar
 * Allows users to interact with their infrastructure through AI
 */

import { useState, useRef, useEffect, useMemo } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { Link } from 'react-router-dom';
import {
  MessageSquare,
  Loader2,
  Bot,
  Sparkles,
  Zap,
  Server,
  Plus,
  AlertCircle,
  ChevronDown,
  ChevronRight,
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
import { useMCPStore } from '@/stores/mcp-store';
import { ROUTES } from '@/lib/constants';
import { useMCPChat } from '@/hooks/use-mcp-chat';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

import { ChatHeader, ChatInput, MessageBubble } from './components';
import { NewProjectModal, MCPConfigModal, LLMConfigModal } from './modals';

// Suggested queries for users
const suggestedPrompts = [
  { icon: Server, text: 'List all compute nodes', category: 'nodes' },
  { icon: Boxes, text: 'Show services with health issues', category: 'services' },
  { icon: Network, text: 'What networks are configured?', category: 'networks' },
  { icon: AlertTriangle, text: 'Show unacknowledged alerts', category: 'alerts' },
];

// Mock infrastructure context (replace with real data)
const useInfrastructureContext = () => {
  return useMemo(
    () => ({
      nodes: 12,
      services: 48,
      networks: 5,
      alerts: 3,
    }),
    []
  );
};

export default function ChatPage() {
  useDocumentTitle('Chat');

  const {
    servers,
    sessions,
    projects,
    currentSessionId,
    llmProviders,
    activeLLMProviderId,
    createSession,
    deleteSession,
    setCurrentSession,
    createProject,
    addMessage,
    getCurrentSession,
    getActiveServers,
    getActiveLLMProvider,
    getProjectSessions,
    getStandaloneSessions,
    connectServer,
    disconnectServer,
    setActiveLLMProvider,
    updateLLMProvider,
  } = useMCPStore();

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

  // Get current session data
  const currentSession = getCurrentSession();
  const messages = currentSession?.messages || [];
  const activeServers = getActiveServers();
  const activeLLMProvider = getActiveLLMProvider();
  const standaloneSessions = getStandaloneSessions();

  const hydraMcp = servers.find((server) => server.id === 'hydra-mcp');
  const isHydraMcpConnected = hydraMcp?.status === 'connected';

  // WebSocket chat hook
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
    onMessage: (message) => {
      if (currentSessionId) {
        addMessage(currentSessionId, {
          role: message.role,
          content: message.content,
          toolCalls: message.toolCalls?.map(tc => ({
            id: tc.id,
            serverId: '',
            serverName: '',
            name: tc.name,
            arguments: tc.arguments,
            result: tc.result,
            error: tc.error,
            status: tc.status,
          })),
        });
        setStreamingContent('');
      }
    },
    onError: (error) => {
      if (currentSessionId) {
        addMessage(currentSessionId, {
          role: 'assistant',
          content: `Error: ${error}`,
          error: true,
        });
        setStreamingContent('');
      }
    },
  });

  // Update streaming content display
  useEffect(() => {
    setStreamingContent(currentResponse);
  }, [currentResponse]);

  // Get active tools from connected servers
  const activeTools = useMemo(() => {
    return activeServers.flatMap((s) =>
      (s.tools || []).map((t) => (typeof t === 'string' ? t : t.name))
    );
  }, [activeServers]);

  // Auto-create session if none exists
  useEffect(() => {
    if (!currentSessionId && sessions.length === 0) {
      createSession('New Chat');
    }
  }, [currentSessionId, sessions.length, createSession]);

  // Auto-connect to Hydra MCP on mount (run once)
  useEffect(() => {
    const hydraMCP = servers.find((s) => s.id === 'hydra-mcp');
    if (hydraMCP && hydraMCP.status === 'disconnected') {
      connectServer('hydra-mcp');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Connect WebSocket when session and provider are ready
  useEffect(() => {
    if (currentSessionId && activeLLMProvider?.isConfigured && !wsConnected) {
      wsConnect();
    }
  }, [currentSessionId, activeLLMProvider?.isConfigured, wsConnected, wsConnect]);

  // Disconnect WebSocket when component unmounts
  useEffect(() => {
    return () => {
      wsDisconnect();
    };
  }, [wsDisconnect]);

  const handleSend = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText || isStreaming || !currentSessionId) return;

    // Check if LLM provider is configured
    if (!activeLLMProvider?.isConfigured) {
      setShowLLMConfigModal(true);
      return;
    }

    if (!wsConnected) {
      // Try to connect if not connected
      wsConnect();
      addMessage(currentSessionId, {
        role: 'assistant',
        content: 'Connecting to chat server... Please try again in a moment.',
        error: true,
      });
      return;
    }

    setInput('');

    // Add user message
    addMessage(currentSessionId, {
      role: 'user',
      content: messageText,
    });

    // Send message via WebSocket
    wsSendMessage(messageText);
  };

  const toggleProjectExpand = (projectId: string) => {
    setExpandedProjects((prev) =>
      prev.includes(projectId) ? prev.filter((p) => p !== projectId) : [...prev, projectId]
    );
  };

  const handleCreateProject = () => {
    if (!newProjectName.trim()) return;
    const projectId = createProject(newProjectName.trim());
    setExpandedProjects((prev) => [...prev, projectId]);
    setNewProjectName('');
    setShowNewProjectModal(false);
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSession(sessionId);
    setMobileSidebarOpen(false);
  };

  const handleNewChat = (projectId?: string) => {
    createSession('New Chat', projectId);
    setMobileSidebarOpen(false);
  };

  return (
    <TooltipProvider>
      <div className="h-[calc(100vh-3.5rem)] flex gap-4 p-4 bg-background relative">
        {/* Mobile sidebar toggle */}
        <Button
          variant="outline"
          size="icon"
          className="fixed bottom-4 left-4 z-50 md:hidden shadow-lg"
          onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
          aria-label={mobileSidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        >
          {mobileSidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>

        {/* Mobile overlay */}
        {mobileSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-30 md:hidden"
            onClick={() => setMobileSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Left Sidebar - Chats & Tools */}
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

            {/* Chats Tab */}
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
                <div className="p-2">
                  {/* Projects Section */}
                  {projects.length > 0 && (
                    <div className="mb-3">
                      <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-2 mb-1">
                        Projects
                      </h4>
                      <div className="space-y-0.5">
                        {projects.map((project) => {
                          const projectSessions = getProjectSessions(project.id);
                          return (
                            <Collapsible
                              key={project.id}
                              open={expandedProjects.includes(project.id)}
                              onOpenChange={() => toggleProjectExpand(project.id)}
                            >
                              <CollapsibleTrigger asChild>
                                <button
                                  className={cn(
                                    'w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs transition-colors',
                                    'hover:bg-muted text-muted-foreground hover:text-foreground'
                                  )}
                                >
                                  {expandedProjects.includes(project.id) ? (
                                    <ChevronDown className="h-3 w-3 shrink-0" />
                                  ) : (
                                    <ChevronRight className="h-3 w-3 shrink-0" />
                                  )}
                                  <FolderOpen className="h-3 w-3 shrink-0" />
                                  <span className="truncate flex-1 text-left">{project.name}</span>
                                  <Badge
                                    variant="secondary"
                                    className="text-[9px] h-4 px-1 shrink-0 bg-muted text-muted-foreground"
                                  >
                                    {projectSessions.length}
                                  </Badge>
                                </button>
                              </CollapsibleTrigger>
                              <CollapsibleContent>
                                <div className="ml-5 mt-0.5 space-y-0.5">
                                  {projectSessions.map((session) => (
                                    <button
                                      key={session.id}
                                      onClick={() => handleSelectSession(session.id)}
                                      className={cn(
                                        'w-full flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] transition-colors',
                                        'hover:bg-muted text-muted-foreground hover:text-foreground',
                                        currentSessionId === session.id && 'bg-muted text-foreground'
                                      )}
                                    >
                                      <MessageSquare className="h-3 w-3 shrink-0" />
                                      <span className="truncate">{session.name}</span>
                                    </button>
                                  ))}
                                  <button
                                    onClick={() => handleNewChat(project.id)}
                                    className="w-full flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                                  >
                                    <Plus className="h-3 w-3" />
                                    New Chat
                                  </button>
                                </div>
                              </CollapsibleContent>
                            </Collapsible>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Standalone/Recent Chats Section */}
                  <div>
                    <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-2 mb-1">
                      Recent Chats
                    </h4>
                    <div className="space-y-0.5">
                      {standaloneSessions.map((session) => (
                        <button
                          key={session.id}
                          onClick={() => handleSelectSession(session.id)}
                          className={cn(
                            'w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs transition-colors',
                            'hover:bg-muted text-muted-foreground hover:text-foreground',
                            currentSessionId === session.id && 'bg-muted text-foreground'
                          )}
                        >
                          <MessageSquare className="h-3 w-3 shrink-0" />
                          <span className="truncate flex-1 text-left">{session.name}</span>
                        </button>
                      ))}
                      {standaloneSessions.length === 0 && sessions.length === 0 && (
                        <p className="text-[11px] text-muted-foreground/70 px-2 py-2">No chats yet</p>
                      )}
                    </div>
                  </div>
                </div>
              </ScrollArea>
            </TabsContent>

            {/* Tools Tab */}
            <TabsContent value="tools" className="flex-1 min-h-0 m-0 p-0 overflow-hidden flex flex-col">
              <div className="flex-1 min-h-0 overflow-y-auto">
                <div className="p-3 space-y-4">
                  {/* MCP Services Section */}
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
                      {servers.map((mcp) => {
                        const statusColor = mcp.status === 'connected'
                          ? 'bg-emerald-500'
                          : mcp.status === 'error'
                            ? 'bg-red-500'
                            : 'bg-muted-foreground';

                        return (
                          <div
                            key={mcp.id}
                            className={cn(
                              'rounded-lg p-3 transition-colors cursor-pointer border',
                              mcp.status === 'connected'
                                ? 'bg-emerald-500/5 border-emerald-500/20 hover:bg-emerald-500/10'
                                : 'bg-muted/30 border-border hover:bg-muted/60'
                            )}
                            onClick={() =>
                              mcp.status === 'connected'
                                ? disconnectServer(mcp.id)
                                : connectServer(mcp.id)
                            }
                          >
                            <div className="flex items-start gap-3">
                              <div
                                className={cn(
                                  'h-9 w-9 rounded-md flex items-center justify-center shrink-0',
                                  mcp.status === 'connected' ? 'bg-emerald-500/20' : 'bg-muted'
                                )}
                              >
                                {mcp.type === 'builtin' ? (
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
                                    title={mcp.status}
                                  />
                                </div>
                                <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2 leading-relaxed">
                                  {mcp.description || mcp.type}
                                </p>
                                <div className="flex items-center gap-2 mt-1.5">
                                  <Badge
                                    variant="secondary"
                                    className="text-[9px] px-1.5 h-4 bg-muted/80 text-muted-foreground"
                                  >
                                    {(mcp.tools || []).length} tools
                                  </Badge>
                                  <span className="text-[9px] text-muted-foreground/70">
                                    {mcp.status === 'connected' ? 'Click to disconnect' : 'Click to connect'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Available Tools Section */}
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

                  {/* Available Prompts Section */}
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

              {/* Fixed bottom section - Quick Actions, Context, LLM */}
              <div className="border-t border-border p-3 space-y-3 shrink-0">
                {/* Quick Actions Section */}
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
                {/* Infrastructure Context */}
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

                {/* Active Model */}
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

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col bg-card border border-border rounded-lg overflow-hidden min-w-0">
          {/* Chat Header */}
          <ChatHeader
            currentSession={currentSession}
            activeLLMProvider={activeLLMProvider}
            activeLLMProviderId={activeLLMProviderId}
            llmProviders={llmProviders}
            activeToolsCount={activeTools.length}
            onLLMProviderChange={setActiveLLMProvider}
            onOpenLLMConfig={() => setShowLLMConfigModal(true)}
            onDeleteSession={() => currentSessionId && deleteSession(currentSessionId)}
          />

          {/* MCP Warning */}
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

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 space-y-4 max-w-4xl mx-auto">
              {messages.length === 0 ? (
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

                  {/* Suggested prompts */}
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
                  {messages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
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

          {/* Input Area */}
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={() => handleSend()}
            isStreaming={isStreaming}
          />
        </div>

        {/* Modals */}
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
          servers={servers}
          onConnectServer={connectServer}
          onDisconnectServer={disconnectServer}
        />

        <LLMConfigModal
          open={showLLMConfigModal}
          onOpenChange={setShowLLMConfigModal}
          llmProviders={llmProviders}
          activeLLMProviderId={activeLLMProviderId}
          onSetActiveProvider={setActiveLLMProvider}
          onUpdateProvider={updateLLMProvider}
        />
      </div>
    </TooltipProvider>
  );
}
