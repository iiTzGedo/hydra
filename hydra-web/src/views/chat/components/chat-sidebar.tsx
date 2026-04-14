/**
 * ChatSidebar - Left panel of the chat page containing tabs for chats, tools, and configs.
 *
 * Extracted from the main chat page to improve code organization.
 * Contains three tabs:
 * - Chats: Project folders and standalone chat sessions with drag-and-drop
 * - Tools: Hydra MCP, external MCP servers, available tools and prompts
 * - Configs: Model configuration passed in as configTabContent prop
 */

import { useState, type ReactNode } from 'react';
import Link from 'next/link';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import {
  MessageSquare,
  Sparkles,
  Zap,
  Server,
  Plus,
  FolderOpen,
  Store,
  Globe,
  Terminal,
  Network,
  AlertTriangle,
  Boxes,
  Wrench,
  Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import type { ChatProjectResponse, ChatSessionResponse } from '@/api/chat';
import type { LLMProviderResponse } from '@/api/ai';
import type {
  MCPServerResponse,
  MCPToolInfo,
  MCPPromptInfo,
  HydraMCPHealthResponse,
} from '@/api/mcp';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ChatListItem } from './chat-list-item';
import { ProjectFolder, UnorganizedDropTarget } from './project-folder';

export interface ServerWithTools extends MCPServerResponse {
  isActive: boolean;
  tools: MCPToolInfo[];
  resources: Array<{ uri: string; name?: string | null; description?: string | null; mimeType?: string | null }>;
  prompts: MCPPromptInfo[];
}

export interface ActiveTool {
  name: string;
  serverId: string;
  serverName: string;
}

export interface ActivePrompt {
  name: string;
  description?: string | null;
  serverId: string;
  serverName: string;
}

export interface InfraContext {
  nodes: number;
  services: number;
  networks: number;
  notifications: number;
}

export interface ChatSidebarProps {
  // State
  sidebarTab: 'chats' | 'tools' | 'configs';
  onSidebarTabChange: (tab: 'chats' | 'tools' | 'configs') => void;
  mobileSidebarOpen: boolean;

  // Chat list props
  projects: ChatProjectResponse[];
  standaloneSessions: ChatSessionResponse[];
  sessions: ChatSessionResponse[];
  currentSessionId: string | null;
  expandedProjects: string[];
  onToggleProjectExpand: (projectId: string) => void;
  onSelectSession: (sessionId: string) => void;
  onNewChat: (projectId?: string) => void;
  onNewProject: () => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onMoveSessionToProject: (sessionId: string, projectId: string | null) => void;
  onDuplicateSession: (sessionId?: string) => void;
  onExportSession: (sessionId?: string) => void;
  onDeleteSession: (sessionId?: string) => void;
  onRenameProject: (projectId: string, newName: string) => void;
  onDeleteProject: (projectId: string) => void;

  // Tools tab props
  isHydraMcpInSession: boolean;
  isHydraMcpHealthy: boolean;
  hydraMcpHealth: HydraMCPHealthResponse | null | undefined;
  hydraMcpTools: MCPToolInfo[];
  hydraMcpPrompts: MCPPromptInfo[];
  serversWithTools: ServerWithTools[];
  activeTools: ActiveTool[];
  activePrompts: ActivePrompt[];
  onConnectServer: (serverId: string) => void;
  onDisconnectServer: (serverId: string) => void;
  onSend: (text: string) => void;
  infraContext: InfraContext;
  activeLLMProvider: LLMProviderResponse | null | undefined;
  onOpenLLMConfig: () => void;

  // Config tab props
  configTabContent: ReactNode;
}

/**
 * Helper to get sessions belonging to a specific project.
 */
function getProjectSessions(
  sessions: ChatSessionResponse[],
  projectId: string
): ChatSessionResponse[] {
  return sessions.filter((s) => s.projectId === projectId);
}

export function ChatSidebar({
  sidebarTab,
  onSidebarTabChange,
  mobileSidebarOpen,
  projects,
  standaloneSessions,
  sessions,
  currentSessionId,
  expandedProjects,
  onToggleProjectExpand,
  onSelectSession,
  onNewChat,
  onNewProject,
  onRenameSession,
  onMoveSessionToProject,
  onDuplicateSession,
  onExportSession,
  onDeleteSession,
  onRenameProject,
  onDeleteProject,
  isHydraMcpInSession,
  isHydraMcpHealthy,
  hydraMcpHealth,
  hydraMcpTools,
  hydraMcpPrompts,
  serversWithTools,
  activeTools,
  activePrompts,
  onConnectServer,
  onDisconnectServer,
  onSend,
  infraContext,
  activeLLMProvider,
  onOpenLLMConfig,
  configTabContent,
}: ChatSidebarProps) {
  const [showAllTools, setShowAllTools] = useState(false);
  const [showAllPrompts, setShowAllPrompts] = useState(false);

  return (
    <div
      className={cn(
        'flex flex-col bg-card border border-border rounded-lg overflow-hidden min-h-0',
        'fixed inset-y-0 left-0 z-40 w-96 m-4 transition-transform duration-200 ease-in-out',
        'md:static md:translate-x-0 md:shrink-0 md:h-full md:m-0',
        mobileSidebarOpen ? 'translate-x-0' : '-translate-x-[calc(100%+2rem)]'
      )}
    >
      <Tabs
        value={sidebarTab}
        onValueChange={(v) => onSidebarTabChange(v as 'chats' | 'tools' | 'configs')}
        className="flex flex-col h-full min-h-0"
      >
        <TabsList className="w-full rounded-none border-b border-border bg-transparent h-auto p-0 shrink-0">
          <TabsTrigger
            value="chats"
            className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-blue-500 data-[state=active]:bg-transparent py-3 text-muted-foreground data-[state=active]:text-foreground text-sm"
          >
            <MessageSquare className="h-4 w-4 mr-1.5" />
            Chats
          </TabsTrigger>
          <TabsTrigger
            value="tools"
            className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-blue-500 data-[state=active]:bg-transparent py-3 text-muted-foreground data-[state=active]:text-foreground text-sm"
          >
            <Wrench className="h-4 w-4 mr-1.5" />
            Tools
          </TabsTrigger>
          <TabsTrigger
            value="configs"
            className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-violet-500 data-[state=active]:bg-transparent py-3 text-muted-foreground data-[state=active]:text-foreground text-sm"
          >
            <Settings className="h-4 w-4 mr-1.5" />
            Config
          </TabsTrigger>
        </TabsList>

        {/* Chats Tab */}
        <TabsContent value="chats" className="data-[state=inactive]:hidden flex-1 m-0 overflow-hidden flex flex-col">
          <div className="p-2 border-b border-border shrink-0 flex gap-2">
            <Button
              onClick={() => onNewChat()}
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
                  onClick={() => onNewProject()}
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
                        const projectSessions = getProjectSessions(sessions, project.projectId);
                        return (
                          <ProjectFolder
                            key={project.projectId}
                            project={project}
                            sessionCount={projectSessions.length}
                            isOpen={expandedProjects.includes(project.projectId)}
                            onOpenChange={() => onToggleProjectExpand(project.projectId)}
                            onDrop={(sessionId) =>
                              onMoveSessionToProject(sessionId, project.projectId)
                            }
                            onRename={(newName) => onRenameProject(project.projectId, newName)}
                            onDelete={() => onDeleteProject(project.projectId)}
                          >
                            {projectSessions.map((session) => (
                              <ChatListItem
                                key={session.sessionId}
                                session={session}
                                isActive={currentSessionId === session.sessionId}
                                onSelect={() => onSelectSession(session.sessionId)}
                                onRename={(newTitle) =>
                                  onRenameSession(session.sessionId, newTitle)
                                }
                                onMoveToProject={(projectId) =>
                                  onMoveSessionToProject(session.sessionId, projectId)
                                }
                                onDuplicate={() => onDuplicateSession(session.sessionId)}
                                onExport={() => onExportSession(session.sessionId)}
                                onDelete={() => onDeleteSession(session.sessionId)}
                                projects={projects}
                              />
                            ))}
                            <button
                              onClick={() => onNewChat(project.projectId)}
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
                  onDrop={(sessionId) => onMoveSessionToProject(sessionId, null)}
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
                        onSelect={() => onSelectSession(session.sessionId)}
                        onRename={(newTitle) =>
                          onRenameSession(session.sessionId, newTitle)
                        }
                        onMoveToProject={(projectId) =>
                          onMoveSessionToProject(session.sessionId, projectId)
                        }
                        onDuplicate={() => onDuplicateSession(session.sessionId)}
                        onExport={() => onExportSession(session.sessionId)}
                        onDelete={() => onDeleteSession(session.sessionId)}
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

        {/* Tools Tab */}
        <TabsContent value="tools" className="data-[state=inactive]:hidden flex-1 min-h-0 m-0 p-0 overflow-hidden flex flex-col">
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
                  role="button"
                  tabIndex={0}
                  aria-label={isHydraMcpInSession ? 'Disconnect Hydra MCP' : 'Connect Hydra MCP'}
                  onClick={() =>
                    isHydraMcpInSession
                      ? onDisconnectServer('hydra-mcp')
                      : onConnectServer('hydra-mcp')
                  }
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (isHydraMcpInSession) {
                        onDisconnectServer('hydra-mcp');
                      } else {
                        onConnectServer('hydra-mcp');
                      }
                    }
                  }}
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
                    <Link href={ROUTES.MCP_MARKETPLACE}>
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
                          role="button"
                          tabIndex={0}
                          aria-label={mcp.isActive ? `Disconnect ${mcp.name}` : `Connect ${mcp.name}`}
                          onClick={() =>
                            mcp.isActive
                              ? onDisconnectServer(mcp.serverId)
                              : onConnectServer(mcp.serverId)
                          }
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              if (mcp.isActive) {
                                onDisconnectServer(mcp.serverId);
                              } else {
                                onConnectServer(mcp.serverId);
                              }
                            }
                          }}
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
                  <Link href={ROUTES.MCP_MARKETPLACE}>
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
                          onClick={() => onSend(`Use the ${tool.name} tool`)}
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
                        onClick={() => onSend(`Run the ${prompt.name} prompt`)}
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

          {/* Tools Tab Bottom Section */}
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
                  { icon: AlertTriangle, text: 'Active notifications' },
                  { icon: Globe, text: 'Topology overview' },
                  { icon: Terminal, text: 'Recent changes' },
                ].map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => onSend(prompt.text)}
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
                  <div className="text-sm font-bold text-foreground">{infraContext.notifications}</div>
                  <div className="text-[9px] text-muted-foreground">Notifs</div>
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
                onClick={onOpenLLMConfig}
              >
                Switch
              </Button>
            </div>
          </div>
        </TabsContent>

        {/* Configs Tab - Model parameters, reasoning, web search */}
        <TabsContent value="configs" className="data-[state=inactive]:hidden flex-1 min-h-0 m-0 p-0 overflow-hidden flex flex-col">
          {configTabContent}
        </TabsContent>
      </Tabs>
    </div>
  );
}
