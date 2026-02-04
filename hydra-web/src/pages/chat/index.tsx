import { useState } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import {
  AlertCircle,
  Menu,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TooltipProvider } from '@/components/ui/tooltip';

import {
  ChatHeader,
  ChatInput,
  ChatSidebar,
  ChatSettingsPanel,
  ChatMessageList,
} from './components';
import { NewProjectModal, MCPConfigModal, LLMConfigModal } from './modals';
import { useChatOrchestration } from './hooks/use-chat-orchestration';

export default function ChatPage() {
  useDocumentTitle('Chat');

  // ── UI-only state ──────────────────────────────────────────────────
  const [sidebarTab, setSidebarTab] = useState<'chats' | 'tools' | 'configs'>('chats');
  const [expandedProjects, setExpandedProjects] = useState<string[]>([]);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [showMCPConfigModal, setShowMCPConfigModal] = useState(false);
  const [showLLMConfigModal, setShowLLMConfigModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // ── Orchestration hook ─────────────────────────────────────────────
  const chat = useChatOrchestration();

  // ── UI event wrappers ──────────────────────────────────────────────

  const toggleProjectExpand = (projectId: string) => {
    setExpandedProjects((prev) =>
      prev.includes(projectId) ? prev.filter((p) => p !== projectId) : [...prev, projectId]
    );
  };

  const handleSelectSession = (sessionId: string) => {
    chat.handleSelectSession(sessionId);
    setMobileSidebarOpen(false);
  };

  const handleNewChat = (projectId?: string) => {
    chat.handleNewChat(projectId, () => setMobileSidebarOpen(false));
  };

  const handleCreateProject = () => {
    if (!newProjectName.trim()) return;
    chat.handleCreateProject(newProjectName, () => {
      setNewProjectName('');
      setShowNewProjectModal(false);
    });
  };

  const handleSend = async (text?: string) => {
    const result = await chat.handleSend(text);
    if (result?.needsLLMConfig) {
      setShowLLMConfigModal(true);
    }
  };

  // ── Settings panel ─────────────────────────────────────────────────
  const settingsPanel = (
    <ChatSettingsPanel
      modelConfig={chat.modelConfig}
      onModelConfigChange={chat.setModelConfig}
      reasoningLevel={chat.reasoningLevel}
      onReasoningLevelChange={chat.setReasoningLevel}
      webSearchEnabled={chat.webSearchEnabled}
      onWebSearchEnabledChange={chat.setWebSearchEnabled}
      supportsReasoning={chat.supportsReasoning}
      supportsWebSearch={chat.supportsWebSearch}
      isStreaming={chat.isStreaming}
      sessionUsage={chat.sessionUsage}
      sessionContext={chat.sessionContext}
      activeLLMProvider={chat.activeLLMProvider ?? null}
      onOpenLLMConfig={() => setShowLLMConfigModal(true)}
    />
  );

  // ── Render ─────────────────────────────────────────────────────────
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
          projects={chat.projects}
          standaloneSessions={chat.standaloneSessions}
          sessions={chat.sessions}
          currentSessionId={chat.currentSessionId}
          expandedProjects={expandedProjects}
          onToggleProjectExpand={toggleProjectExpand}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onNewProject={() => setShowNewProjectModal(true)}
          onRenameSession={chat.handleRenameSession}
          onMoveSessionToProject={chat.handleMoveSessionToProject}
          onDuplicateSession={chat.handleDuplicateSession}
          onExportSession={chat.handleExportSession}
          onDeleteSession={chat.handleDeleteSession}
          isHydraMcpInSession={chat.isHydraMcpInSession}
          isHydraMcpHealthy={chat.isHydraMcpHealthy}
          hydraMcpHealth={chat.hydraMcpHealth}
          hydraMcpTools={chat.hydraMcpTools}
          hydraMcpPrompts={chat.hydraMcpPrompts}
          serversWithTools={chat.serversWithTools}
          activeTools={chat.activeTools}
          activePrompts={chat.activePrompts}
          onConnectServer={chat.handleConnectServer}
          onDisconnectServer={chat.handleDisconnectServer}
          onSend={handleSend}
          infraContext={chat.infraContext}
          activeLLMProvider={chat.activeLLMProvider}
          onOpenLLMConfig={() => setShowLLMConfigModal(true)}
          configTabContent={settingsPanel}
        />

        <div className="flex-1 h-full flex flex-col bg-card border border-border rounded-lg overflow-hidden min-w-0">
          <ChatHeader
            currentSession={chat.currentSession}
            activeLLMProvider={chat.activeLLMProvider}
            activeLLMProviderId={chat.activeLLMProviderId}
            llmProviders={chat.llmProviders}
            activeToolsCount={chat.activeTools.length}
            sessionContext={chat.sessionContext}
            llmConfigLocked={chat.llmConfigLocked}
            onLLMProviderChange={chat.handleSetActiveProvider}
            onOpenLLMConfig={() => setShowLLMConfigModal(true)}
            onRenameSession={(newTitle) =>
              chat.currentSession && chat.handleRenameSession(chat.currentSession.sessionId, newTitle)
            }
            onDuplicateSession={() => chat.handleDuplicateSession()}
            onExportSession={() => chat.handleExportSession()}
            onDeleteSession={() => chat.handleDeleteSession()}
          />

          {/* Hydra MCP Status Banner */}
          {!chat.isHydraMcpInSession ? (
            <div className="mx-4 mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-foreground">
                Connect <code className="bg-muted px-1 rounded text-foreground">Hydra MCP</code> in
                the Tools tab to access infrastructure tools.
              </span>
            </div>
          ) : !chat.isHydraMcpHealthy ? (
            <div className="mx-4 mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-red-500" />
              <span className="text-sm text-foreground">
                <code className="bg-muted px-1 rounded text-foreground">Hydra MCP</code> is
                unreachable — check if the hydra-mcp service is running.
              </span>
            </div>
          ) : null}

          <ChatMessageList
            messages={chat.allMessages}
            isStreaming={chat.isStreaming}
            streamingContent={chat.streamingContent}
            onSend={handleSend}
            onRetryMessage={chat.retryMessage}
            messagesEndRef={chat.messagesEndRef}
          />

          <ChatInput
            value={chat.input}
            onChange={chat.setInput}
            onSend={() => handleSend()}
            isStreaming={chat.isStreaming}
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
          servers={chat.serversWithTools}
          onConnectServer={chat.handleConnectServer}
          onDisconnectServer={chat.handleDisconnectServer}
        />

        <LLMConfigModal
          open={showLLMConfigModal}
          onOpenChange={setShowLLMConfigModal}
          llmProviders={chat.llmProviders}
          activeLLMProviderId={chat.activeLLMProviderId}
          onSetActiveProvider={chat.handleSetActiveProvider}
          onUpdateProvider={chat.handleUpdateProvider}
          onCreateProvider={chat.handleCreateProvider}
          onDeleteProvider={chat.handleDeleteProvider}
          onValidateProvider={chat.handleValidateProvider}
        />
      </div>
    </TooltipProvider>
  );
}
