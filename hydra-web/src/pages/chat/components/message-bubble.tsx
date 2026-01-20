import { useState } from 'react';
import { Bot, User, Zap, Copy, Check } from 'lucide-react';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { ChatMessageRole, ChatToolCall } from '@/api/chat';
import { ToolCallDisplay } from './tool-call-display';

interface MessageBubbleProps {
  message: {
    messageId?: string;
    role: ChatMessageRole;
    content: string;
    toolCalls?: ChatToolCall[];
    createdAt?: string;
    error?: boolean;
  };
}

export function MessageBubble({ message }: MessageBubbleProps) {
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
            {formatRelativeTime(message.createdAt || new Date().toISOString())}
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
