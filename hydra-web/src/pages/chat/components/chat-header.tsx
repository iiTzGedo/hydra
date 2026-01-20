import {
  MessageSquare,
  Bot,
  Settings,
  MoreHorizontal,
  Pencil,
  Copy,
  Download,
  Trash2,
} from 'lucide-react';
import type { MCPChatSession, LLMProvider } from '@/types/mcp';
import { Button } from '@/components/ui/button';
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

interface ChatHeaderProps {
  currentSession: MCPChatSession | null;
  activeLLMProvider: LLMProvider | undefined;
  activeLLMProviderId: string | null;
  llmProviders: LLMProvider[];
  activeToolsCount: number;
  onLLMProviderChange: (providerId: string) => void;
  onOpenLLMConfig: () => void;
  onDeleteSession: () => void;
}

export function ChatHeader({
  currentSession,
  activeLLMProvider,
  activeLLMProviderId,
  llmProviders,
  activeToolsCount,
  onLLMProviderChange,
  onOpenLLMConfig,
  onDeleteSession,
}: ChatHeaderProps) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <MessageSquare className="h-5 w-5 text-blue-500 shrink-0" />
        <div className="min-w-0">
          <h2 className="font-medium text-foreground truncate">
            {currentSession?.name || 'Chat'}
          </h2>
          <p className="text-xs text-muted-foreground">
            Using {activeLLMProvider?.name || 'No LLM'} &bull; {activeToolsCount} tools available
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {/* LLM Selector */}
        <Select
          value={activeLLMProviderId || ''}
          onValueChange={onLLMProviderChange}
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
          onClick={onOpenLLMConfig}
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
              onClick={onDeleteSession}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
