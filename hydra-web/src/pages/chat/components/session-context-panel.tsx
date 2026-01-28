import { Bot, Coins, FileText, Lock, MessageSquare, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SessionContext } from '@/api/chat';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface SessionContextPanelProps {
  context: SessionContext | null | undefined;
  llmConfigLocked?: boolean;
  className?: string;
  variant?: 'compact' | 'full';
}

export function SessionContextPanel({
  context,
  llmConfigLocked,
  className,
  variant = 'compact',
}: SessionContextPanelProps) {
  if (!context) {
    return null;
  }

  const formatTokenCount = (count: number): string => {
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(1)}M`;
    }
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}K`;
    }
    return count.toString();
  };

  const formatCost = (cost: number): string => {
    if (cost < 0.01) {
      return `$${cost.toFixed(4)}`;
    }
    return `$${cost.toFixed(2)}`;
  };

  if (variant === 'compact') {
    return (
      <div className={cn('flex items-center gap-3 text-xs text-muted-foreground', className)}>
        {llmConfigLocked && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger>
                <Lock className="h-3 w-3 text-amber-500" />
              </TooltipTrigger>
              <TooltipContent>LLM configuration locked for this session</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        {context.modelUsed && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger>
                <div className="flex items-center gap-1">
                  <Bot className="h-3 w-3" />
                  <span className="truncate max-w-[120px]">{context.modelUsed}</span>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                Model: {context.modelUsed}
                {context.providerType && ` (${context.providerType})`}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>
              <div className="flex items-center gap-1">
                <FileText className="h-3 w-3" />
                <span>{formatTokenCount(context.totalTokens)}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <div className="space-y-1">
                <div>Total tokens: {context.totalTokens.toLocaleString()}</div>
                <div>Input: {context.inputTokens.toLocaleString()}</div>
                <div>Output: {context.outputTokens.toLocaleString()}</div>
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        {context.estimatedCost > 0 && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger>
                <div className="flex items-center gap-1">
                  <Coins className="h-3 w-3" />
                  <span>{formatCost(context.estimatedCost)}</span>
                </div>
              </TooltipTrigger>
              <TooltipContent>Estimated cost for this session</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        {context.toolCallsCount > 0 && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger>
                <div className="flex items-center gap-1">
                  <Wrench className="h-3 w-3" />
                  <span>{context.toolCallsCount}</span>
                </div>
              </TooltipTrigger>
              <TooltipContent>Tool calls made in this session</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>
              <div className="flex items-center gap-1">
                <MessageSquare className="h-3 w-3" />
                <span>{context.messageCount}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent>Messages in this session</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    );
  }

  // Full variant for sidebar or expanded view
  return (
    <div className={cn('space-y-3 p-3 bg-muted/50 rounded-lg', className)}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-foreground">Session Context</h4>
        {llmConfigLocked && (
          <Badge variant="outline" className="h-5 border-amber-500/30 text-amber-400">
            <Lock className="h-3 w-3 mr-1" />
            Locked
          </Badge>
        )}
      </div>

      {context.modelUsed && (
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-muted-foreground" />
          <div>
            <div className="text-sm text-foreground">{context.modelUsed}</div>
            {context.providerType && (
              <div className="text-xs text-muted-foreground capitalize">{context.providerType}</div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="space-y-1">
          <div className="text-muted-foreground">Tokens</div>
          <div className="text-foreground font-medium">
            {context.totalTokens.toLocaleString()}
          </div>
          <div className="text-muted-foreground">
            {context.inputTokens.toLocaleString()} in / {context.outputTokens.toLocaleString()} out
          </div>
        </div>
        <div className="space-y-1">
          <div className="text-muted-foreground">Estimated Cost</div>
          <div className="text-foreground font-medium">{formatCost(context.estimatedCost)}</div>
        </div>
        <div className="space-y-1">
          <div className="text-muted-foreground">Messages</div>
          <div className="text-foreground font-medium">{context.messageCount}</div>
        </div>
        <div className="space-y-1">
          <div className="text-muted-foreground">Tool Calls</div>
          <div className="text-foreground font-medium">{context.toolCallsCount}</div>
        </div>
      </div>
    </div>
  );
}
