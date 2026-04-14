import {
  MessageSquare,
  Bot,
  Settings,
  MoreHorizontal,
  Copy,
  Download,
  Trash2,
  Lock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatSessionResponse, SessionContext } from '@/api/chat';
import type { LLMProviderResponse } from '@/api/ai';
import { Button } from '@/components/ui/button';
import { EditableText } from '@/components/ui/editable-text';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { SessionContextPanel } from './session-context-panel';

interface ChatHeaderProps {
  currentSession: ChatSessionResponse | null;
  activeLLMProvider: LLMProviderResponse | undefined;
  activeLLMProviderId: string | null;
  llmProviders: LLMProviderResponse[];
  activeToolsCount: number;
  sessionContext?: SessionContext | null;
  llmConfigLocked?: boolean;
  onLLMProviderChange: (providerId: string) => void;
  onOpenLLMConfig: () => void;
  onRenameSession: (newTitle: string) => void;
  onDuplicateSession: () => void;
  onExportSession: () => void;
  onDeleteSession: () => void;
}

export function ChatHeader({
  currentSession,
  activeLLMProvider,
  activeLLMProviderId,
  llmProviders,
  activeToolsCount,
  sessionContext,
  llmConfigLocked,
  onLLMProviderChange,
  onOpenLLMConfig,
  onRenameSession,
  onDuplicateSession,
  onExportSession,
  onDeleteSession,
}: ChatHeaderProps) {
  const configuredProviders = llmProviders.filter(
    (provider) => provider.apiKeySet || provider.type === 'ollama'
  );

  return (
    <div className="border-b border-border shrink-0">
      {/* Main header row */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <MessageSquare className="h-5 w-5 text-blue-500 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <EditableText
                value={currentSession?.title || 'Chat'}
                onSave={onRenameSession}
                placeholder="Untitled Chat"
                className="font-medium text-foreground"
                inputClassName="font-medium"
                disabled={!currentSession}
                showEditHint
              />
              {llmConfigLocked && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Lock className="h-3.5 w-3.5 text-amber-500" />
                    </TooltipTrigger>
                    <TooltipContent>
                      LLM configuration locked after first response
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Using {activeLLMProvider?.name || 'No LLM'} &bull; {activeToolsCount} tools available
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Select
            value={activeLLMProviderId || ''}
            onValueChange={onLLMProviderChange}
            disabled={llmConfigLocked}
          >
            <SelectTrigger
              className={cn(
                'w-40 h-8 text-xs bg-muted border-border text-foreground',
                llmConfigLocked && 'opacity-60 cursor-not-allowed'
              )}
            >
              <Bot className="h-3 w-3 mr-2" />
              <SelectValue placeholder="Select LLM" />
            </SelectTrigger>
            <SelectContent className="bg-muted border-border">
              {configuredProviders.map((llm) => (
                  <SelectItem
                    key={llm.configId}
                    value={llm.configId}
                    className="text-foreground"
                  >
                    {llm.name}
                  </SelectItem>
                ))}
              {configuredProviders.length === 0 && (
                <div className="p-2 text-xs text-muted-foreground">No LLMs configured</div>
              )}
            </SelectContent>
          </Select>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={onOpenLLMConfig}
            aria-label="Open LLM settings"
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
              <DropdownMenuItem
                className="text-foreground focus:bg-muted focus:text-foreground"
                onClick={onDuplicateSession}
              >
                <Copy className="h-4 w-4 mr-2" />
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-foreground focus:bg-muted focus:text-foreground"
                onClick={onExportSession}
              >
                <Download className="h-4 w-4 mr-2" />
                Export
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-red-400 focus:bg-red-500/10 focus:text-red-400"
                onClick={onDeleteSession}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Session context row (compact) */}
      {sessionContext && (sessionContext.totalTokens > 0 || sessionContext.messageCount > 0) && (
        <div className="px-4 pb-2">
          <SessionContextPanel
            context={sessionContext}
            llmConfigLocked={llmConfigLocked}
            variant="compact"
          />
        </div>
      )}
    </div>
  );
}
