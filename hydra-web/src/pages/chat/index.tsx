/**
 * Chat Page with MCP Integration - Redesigned with Left Sidebar
 * Allows users to interact with their infrastructure through AI
 */

import { useState, useRef, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare,
  Send,
  Loader2,
  Bot,
  User,
  Sparkles,
  Zap,
  Copy,
  Check,
  Settings,
  Server,
  Plus,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  FolderOpen,
  Trash2,
  MoreHorizontal,
  Pencil,
  Download,
  Store,
  Globe,
  Terminal,
  Network,
  AlertTriangle,
  Boxes,
  Wrench,
} from 'lucide-react';
import { cn, formatRelativeTime } from '@/lib/utils';
import { useMCPStore } from '@/stores/mcp-store';
import { ROUTES } from '@/lib/constants';
import type { MCPChatMessage, MCPToolCall, ChatProject } from '@/types/mcp';
import { useMCPChat } from '@/hooks/use-mcp-chat';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

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
    renameSession,
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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
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
  };

  const handleNewChat = (projectId?: string) => {
    createSession('New Chat', projectId);
  };

  return (
    <TooltipProvider>
      <div className="h-[calc(100vh-3.5rem)] flex gap-4 p-4 bg-background">
        {/* Left Sidebar - Chats & Tools */}
        <div className="w-72 flex flex-col bg-card border border-border rounded-lg overflow-hidden shrink-0">
          <Tabs
            value={sidebarTab}
            onValueChange={(v) => setSidebarTab(v as 'chats' | 'tools')}
            className="flex flex-col h-full"
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
            <TabsContent value="chats" className="flex-1 m-0 overflow-hidden flex flex-col">
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
            <TabsContent value="tools" className="flex-1 m-0 overflow-hidden flex flex-col">
              <ScrollArea className="flex-1">
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
                        // Status LED colors: green=connected, red=error, grey=disconnected
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
                  <div className="space-y-2">
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
              </ScrollArea>

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
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <MessageSquare className="h-5 w-5 text-blue-500 shrink-0" />
              <div className="min-w-0">
                <h2 className="font-medium text-foreground truncate">
                  {currentSession?.name || 'Chat'}
                </h2>
                <p className="text-xs text-muted-foreground">
                  Using {activeLLMProvider?.name || 'No LLM'} &bull; {activeTools.length} tools
                  available
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {/* LLM Selector */}
              <Select
                value={activeLLMProviderId || ''}
                onValueChange={(v) => setActiveLLMProvider(v)}
              >
                <SelectTrigger className="w-40 h-8 text-xs bg-muted border-border text-foreground">
                  <Bot className="h-3 w-3 mr-2" />
                  <SelectValue placeholder="Select LLM" />
                </SelectTrigger>
                <SelectContent className="bg-muted border-border">
                  {llmProviders
                    .filter((l) => l.isConfigured)
                    .map((llm) => (
                      <SelectItem key={llm.id} value={llm.id} className="text-foreground">
                        {llm.name}
                      </SelectItem>
                    ))}
                  {llmProviders.filter((l) => l.isConfigured).length === 0 && (
                    <div className="p-2 text-xs text-muted-foreground">No LLMs configured</div>
                  )}
                </SelectContent>
              </Select>

              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={() => setShowLLMConfigModal(true)}
              >
                <Settings className="h-4 w-4" />
              </Button>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem className="text-foreground focus:bg-muted focus:text-foreground">
                    <Pencil className="h-4 w-4 mr-2" />
                    Rename Chat
                  </DropdownMenuItem>
                  <DropdownMenuItem className="text-foreground focus:bg-muted focus:text-foreground">
                    <Copy className="h-4 w-4 mr-2" />
                    Duplicate
                  </DropdownMenuItem>
                  <DropdownMenuItem className="text-foreground focus:bg-muted focus:text-foreground">
                    <Download className="h-4 w-4 mr-2" />
                    Export
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-red-400 focus:bg-red-500/10 focus:text-red-400"
                    onClick={() => currentSessionId && deleteSession(currentSessionId)}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

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
          <div className="border-t border-border p-4 shrink-0">
            <div className="max-w-4xl mx-auto">
              <div className="flex gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about your infrastructure..."
                  className="min-h-[44px] max-h-32 resize-none bg-muted border-border text-foreground placeholder:text-muted-foreground"
                  disabled={isStreaming}
                  rows={1}
                />
                <Button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || isStreaming}
                  className="shrink-0 bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-[10px] text-muted-foreground mt-2 text-center">
                Press Enter to send, Shift+Enter for new line
              </p>
            </div>
          </div>
        </div>

        {/* New Project Modal */}
        <Dialog open={showNewProjectModal} onOpenChange={setShowNewProjectModal}>
          <DialogContent className="bg-card border-border text-foreground max-w-md">
            <DialogHeader>
              <DialogTitle>Create New Project</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Projects help you organize your chat conversations by topic or purpose.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <Label htmlFor="projectName" className="text-foreground">
                Project Name
              </Label>
              <Input
                id="projectName"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="e.g., Production Monitoring"
                className="mt-2 bg-muted border-border text-foreground"
                onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
              />
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowNewProjectModal(false)}
                className="border-border text-foreground hover:bg-muted bg-transparent"
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateProject}
                disabled={!newProjectName.trim()}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                <Check className="h-4 w-4 mr-2" />
                Create Project
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* MCP Configuration Modal */}
        <Dialog open={showMCPConfigModal} onOpenChange={setShowMCPConfigModal}>
          <DialogContent className="bg-card border-border text-foreground max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle>MCP Configuration</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Manage connected MCP servers and browse available tools.
              </DialogDescription>
            </DialogHeader>
            <ScrollArea className="flex-1 -mx-6 px-6">
              <div className="space-y-4 py-4">
                {servers.map((mcp) => (
                  <Card key={mcp.id} className="bg-muted/60 border-border">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-card">
                            {mcp.type === 'builtin' ? (
                              <Terminal className="h-5 w-5 text-violet-500" />
                            ) : (
                              <Globe className="h-5 w-5 text-cyan-500" />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-medium text-foreground">{mcp.name}</h4>
                              <Badge
                                variant="outline"
                                className={cn(
                                  mcp.status === 'connected'
                                    ? 'border-emerald-500/30 text-emerald-400'
                                    : 'border-border text-muted-foreground'
                                )}
                              >
                                {mcp.status}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">{(mcp.tools || []).length} tools</p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            mcp.status === 'connected'
                              ? disconnectServer(mcp.id)
                              : connectServer(mcp.id)
                          }
                          className={cn(
                            mcp.status === 'connected'
                              ? 'text-red-400 hover:text-red-300 hover:bg-red-500/10'
                              : 'text-blue-400 hover:text-blue-300 hover:bg-blue-500/10'
                          )}
                        >
                          {mcp.status === 'connected' ? 'Disconnect' : 'Connect'}
                        </Button>
                      </div>
                      {(mcp.tools || []).length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1">
                          {(mcp.tools || []).slice(0, 8).map((tool) => (
                            <Badge
                              key={typeof tool === 'string' ? tool : tool.name}
                              variant="secondary"
                              className="text-[10px] bg-card text-muted-foreground"
                            >
                              {typeof tool === 'string' ? tool : tool.name}
                            </Badge>
                          ))}
                          {(mcp.tools || []).length > 8 && (
                            <Badge variant="secondary" className="text-[10px] bg-card text-muted-foreground">
                              +{(mcp.tools || []).length - 8} more
                            </Badge>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
            <DialogFooter className="border-t border-border pt-4">
              <Button
                variant="outline"
                onClick={() => setShowMCPConfigModal(false)}
                className="border-border text-foreground hover:bg-muted bg-transparent"
              >
                Close
              </Button>
              <Link to={ROUTES.MCP_MARKETPLACE}>
                <Button className="bg-blue-600 hover:bg-blue-700 text-white">
                  <Store className="h-4 w-4 mr-2" />
                  Browse Marketplace
                </Button>
              </Link>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* LLM Configuration Modal */}
        <Dialog open={showLLMConfigModal} onOpenChange={setShowLLMConfigModal}>
          <DialogContent className="bg-card border-border text-foreground max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle>LLM Providers</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Configure language models for the chat interface.
              </DialogDescription>
            </DialogHeader>
            <ScrollArea className="flex-1 -mx-6 px-6">
              <div className="space-y-4 py-4">
                {llmProviders.map((llm) => (
                  <Card key={llm.id} className="bg-muted/60 border-border">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-card">
                            <Bot className="h-5 w-5 text-amber-500" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-medium text-foreground">{llm.name}</h4>
                              {activeLLMProviderId === llm.id && (
                                <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20">
                                  Active
                                </Badge>
                              )}
                              <Badge
                                variant="outline"
                                className={cn(
                                  llm.isConfigured
                                    ? 'border-emerald-500/30 text-emerald-400'
                                    : 'border-border text-muted-foreground'
                                )}
                              >
                                {llm.isConfigured ? 'Configured' : 'Not configured'}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {llm.type} / {llm.model}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {!llm.isConfigured && llm.type !== 'ollama' && (
                            <Input
                              type="password"
                              placeholder="API Key"
                              className="h-8 w-32 text-xs bg-card border-border text-foreground"
                              onChange={(e) =>
                                updateLLMProvider(llm.id, { apiKey: e.target.value })
                              }
                            />
                          )}
                          {llm.isConfigured && activeLLMProviderId !== llm.id && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setActiveLLMProvider(llm.id)}
                              className="border-border text-foreground hover:bg-muted bg-transparent"
                            >
                              Set Active
                            </Button>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
            <DialogFooter className="border-t border-border pt-4">
              <Button
                variant="outline"
                onClick={() => setShowLLMConfigModal(false)}
                className="border-border text-foreground hover:bg-muted bg-transparent"
              >
                Close
              </Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white">
                <Plus className="h-4 w-4 mr-2" />
                Add Provider
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}

// Message Bubble Component
function MessageBubble({ message }: { message: MCPChatMessage }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn('flex gap-3', isUser && 'justify-end')}>
      {!isUser && (
        <div
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
            message.role === 'system' ? 'bg-blue-600' : 'bg-muted'
          )}
        >
          {message.role === 'system' ? (
            <Zap className="h-4 w-4 text-white" />
          ) : (
            <Bot className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      )}

      <div className={cn('flex-1 max-w-[80%]', isUser && 'flex justify-end')}>
        <div
          className={cn(
            'rounded-lg p-4',
            isUser
              ? 'bg-blue-600 text-white'
              : message.role === 'system'
                ? 'bg-blue-500/10 border border-blue-500/30 text-foreground'
                : 'bg-muted text-foreground',
            message.error && 'border border-red-500/30 bg-red-500/10'
          )}
        >
          <div className="text-sm whitespace-pre-wrap break-words">{message.content}</div>

          {/* Tool Calls */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-3 space-y-2">
              {message.toolCalls.map((tool) => (
                <ToolCallDisplay key={tool.id} toolCall={tool} />
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 mt-1 px-1">
          <span className="text-[10px] text-muted-foreground">
            {formatRelativeTime(message.timestamp)}
          </span>
          {!isUser && (
            <button
              onClick={handleCopy}
              className="rounded p-1 hover:bg-muted transition-colors"
            >
              {copied ? (
                <Check className="h-3 w-3 text-emerald-500" />
              ) : (
                <Copy className="h-3 w-3 text-muted-foreground" />
              )}
            </button>
          )}
        </div>
      </div>

      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600">
          <User className="h-4 w-4 text-white" />
        </div>
      )}
    </div>
  );
}

// Tool Call Display Component
function ToolCallDisplay({ toolCall }: { toolCall: MCPToolCall }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Collapsible open={expanded} onOpenChange={setExpanded}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-between h-auto py-2 px-3 bg-card/60 hover:bg-card text-muted-foreground"
        >
          <div className="flex items-center gap-2">
            <Wrench className="h-3 w-3" />
            <span className="text-xs font-mono">{toolCall.name}</span>
          </div>
          <ChevronDown
            className={cn('h-3 w-3 transition-transform', expanded && 'rotate-180')}
          />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 p-3 rounded bg-card text-xs font-mono overflow-auto max-h-48">
          <p className="text-muted-foreground mb-1">Arguments:</p>
          <pre className="text-foreground">{JSON.stringify(toolCall.arguments, null, 2)}</pre>
          {toolCall.result && (
            <>
              <p className="text-muted-foreground mt-2 mb-1">Result:</p>
              <pre className="text-emerald-400">
                {JSON.stringify(toolCall.result, null, 2).slice(0, 500)}
              </pre>
            </>
          )}
          {toolCall.error && <p className="mt-1 text-red-400">{toolCall.error}</p>}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
