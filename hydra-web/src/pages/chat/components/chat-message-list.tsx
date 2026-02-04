import React from 'react';
import { Bot, Loader2, Sparkles, Server, Network, Bell, Boxes } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MessageBubble } from './message-bubble';
import type { ChatMessageResponse } from '@/api/chat';

const suggestedPrompts = [
  { icon: Server, text: 'List all compute nodes', category: 'nodes' },
  { icon: Boxes, text: 'Show services with health issues', category: 'services' },
  { icon: Network, text: 'What networks are configured?', category: 'networks' },
  { icon: Bell, text: 'Show active notifications', category: 'notifications' },
];

interface ChatMessageListProps {
  messages: Array<ChatMessageResponse & { error?: boolean }>;
  isStreaming: boolean;
  streamingContent: string;
  onSend: (text: string) => void;
  onRetryMessage: (messageId: string) => void;
  messagesEndRef: React.RefObject<HTMLDivElement>;
}

export function ChatMessageList({
  messages,
  isStreaming,
  streamingContent,
  onSend,
  onRetryMessage,
  messagesEndRef,
}: ChatMessageListProps) {
  return (
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
                    onClick={() => onSend(prompt.text)}
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
            {messages.map((message, index) => {
              // Detect orphaned user messages: last message is from user with no assistant response
              const isLastMessage = index === messages.length - 1;
              const isOrphanedUserMessage = isLastMessage && message.role === 'user' && !isStreaming;

              return (
                <MessageBubble
                  key={message.messageId}
                  message={message}
                  canResend={isOrphanedUserMessage}
                  onResend={isOrphanedUserMessage && message.messageId ? () => onRetryMessage(message.messageId!) : undefined}
                />
              );
            })}
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
  );
}
