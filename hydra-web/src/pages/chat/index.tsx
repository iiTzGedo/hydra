/**
 * Chat Page with MCP Integration
 * Allows users to interact with their infrastructure through AI
 */

import { useState, useRef, useEffect } from 'react';
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
  RefreshCw,
  Copy,
  Check,
  Settings,
  Server,
  Plus,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import { cn, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants, fadeInVariants } from '@/lib/animations';
import { useMCPStore } from '@/stores/mcp-store';
import { useHydraMCPTools, useMCPChat } from '@/api/mcp';
import { ROUTES } from '@/lib/constants';
import type { MCPChatMessage, MCPToolCall, LLMProvider } from '@/types/mcp';

// Suggested queries for users
const suggestedQueries = [
  'List all nodes with status active',
  'Show me services running on Docker',
  'What networks are in my infrastructure?',
  'Summarize my infrastructure topology',
  'Find nodes with more than 16GB RAM',
  'Which services have exposed ports?',
];

export default function ChatPage() {
  const {
    servers,
    sessions,
    currentSessionId,
    llmProviders,
    activeLLMProviderId,
    createSession,
    addMessage,
    updateMessage,
    addToolCall,
    updateToolCall,
    getCurrentSession,
    getActiveServers,
    getActiveLLMProvider,
    connectServer,
  } = useMCPStore();

  const [input, setInput] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Get current session or create one
  const currentSession = getCurrentSession();
  const messages = currentSession?.messages || [];
  const activeServers = getActiveServers();
  const activeLLMProvider = getActiveLLMProvider();

  // MCP hooks
  const { data: tools } = useHydraMCPTools();
  const chatMutation = useMCPChat();

  // Auto-create session if none exists
  useEffect(() => {
    if (!currentSessionId && sessions.length === 0) {
      createSession('New Chat');
    }
  }, [currentSessionId, sessions.length, createSession]);

  // Auto-connect to Hydra MCP on mount
  useEffect(() => {
    const hydraMCP = servers.find((s) => s.id === 'hydra-mcp');
    if (hydraMCP && hydraMCP.status === 'disconnected') {
      connectServer('hydra-mcp');
    }
  }, [servers, connectServer]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || chatMutation.isPending || !currentSessionId) return;

    // Check if LLM provider is configured
    if (!activeLLMProvider?.isConfigured) {
      setShowSettings(true);
      return;
    }

    const userContent = input.trim();
    setInput('');

    // Add user message
    addMessage(currentSessionId, {
      role: 'user',
      content: userContent,
    });

    // Create pending assistant message
    const pendingMessageId = crypto.randomUUID();
    addMessage(currentSessionId, {
      role: 'assistant',
      content: '',
      pending: true,
    });

    try {
      // Build messages array for API
      const chatMessages = [
        ...messages.map((m) => ({
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content,
        })),
        { role: 'user' as const, content: userContent },
      ];

      // Call MCP chat API
      const response = await chatMutation.mutateAsync({
        messages: chatMessages,
        tools: tools || [],
        model: activeLLMProvider.model,
      });

      // Update message with response
      updateMessage(currentSessionId, pendingMessageId, {
        content: response.content,
        pending: false,
        toolCalls: response.toolCalls?.map((tc) => ({
          ...tc,
          status: 'success' as const,
        })),
      });
    } catch (error) {
      // Update message with error
      updateMessage(currentSessionId, pendingMessageId, {
        content:
          error instanceof Error
            ? `Error: ${error.message}`
            : 'An error occurred while processing your request.',
        pending: false,
        error: true,
      });
    }
  };

  const handleSuggestedQuery = (query: string) => {
    setInput(query);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    createSession('New Chat');
  };

  const isLoading = chatMutation.isPending;

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Header */}
      <div className="border-b p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary p-2">
            <MessageSquare className="h-5 w-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-lg font-semibold flex items-center gap-2">
              Hydra AI Assistant
              <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                <Sparkles className="mr-1 h-3 w-3" />
                MCP
              </span>
            </h1>
            <p className="text-sm text-muted-foreground">
              Query your infrastructure using natural language
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <ServerStatusBadges servers={activeServers} />
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm',
              'hover:bg-muted transition-colors',
              showSettings && 'bg-muted'
            )}
          >
            <Settings className="h-4 w-4" />
            Settings
          </button>
          <button
            onClick={clearChat}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm',
              'hover:bg-muted transition-colors'
            )}
          >
            <RefreshCw className="h-4 w-4" />
            Clear
          </button>
        </div>
      </div>

      {/* Settings Panel */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-b overflow-hidden"
          >
            <SettingsPanel
              llmProviders={llmProviders}
              activeLLMProviderId={activeLLMProviderId}
              servers={servers}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4">
        {messages.length === 0 ? (
          <motion.div
            initial="hidden"
            animate="visible"
            variants={fadeInVariants}
            className="h-full flex flex-col items-center justify-center text-center"
          >
            <div className="rounded-full bg-primary/10 p-4">
              <Bot className="h-8 w-8 text-primary" />
            </div>
            <h2 className="mt-4 text-xl font-semibold">How can I help you today?</h2>
            <p className="mt-2 text-muted-foreground max-w-md">
              Ask me about your infrastructure. I can help you find nodes, services, analyze
              topology, and answer questions about your setup.
            </p>

            {/* LLM Provider Warning */}
            {!activeLLMProvider?.isConfigured && (
              <div className="mt-4 flex items-center gap-2 text-warning bg-warning/10 rounded-lg px-4 py-2">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm">
                  Configure an LLM provider in settings to start chatting
                </span>
              </div>
            )}

            {/* Suggested queries */}
            <div className="mt-8 max-w-2xl">
              <p className="text-sm text-muted-foreground mb-3">Try asking:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {suggestedQueries.map((query) => (
                  <button
                    key={query}
                    onClick={() => handleSuggestedQuery(query)}
                    className={cn(
                      'rounded-full border px-4 py-2 text-sm',
                      'hover:bg-muted hover:border-primary/50 transition-colors'
                    )}
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>

            {/* MCP Marketplace Link */}
            <Link
              to={ROUTES.MCP_MARKETPLACE}
              className="mt-6 inline-flex items-center gap-2 text-sm text-primary hover:underline"
            >
              <Plus className="h-4 w-4" />
              Add more MCP servers from the marketplace
            </Link>
          </motion.div>
        ) : (
          <motion.div
            variants={staggerContainerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-4 max-w-3xl mx-auto"
          >
            <AnimatePresence>
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
            </AnimatePresence>

            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-start gap-3"
              >
                <div className="rounded-full bg-primary/10 p-2">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="rounded-lg bg-muted p-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">Thinking...</span>
                  </div>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </motion.div>
        )}
      </div>

      {/* Input */}
      <div className="border-t p-4">
        <div className="max-w-3xl mx-auto flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your infrastructure..."
              rows={1}
              className={cn(
                'w-full rounded-xl border bg-background px-4 py-3 pr-12 text-sm resize-none',
                'focus:outline-none focus:ring-2 focus:ring-ring',
                'placeholder:text-muted-foreground',
                'min-h-[48px] max-h-[200px]'
              )}
              style={{ height: 'auto' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = Math.min(target.scrollHeight, 200) + 'px';
              }}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className={cn(
              'rounded-xl bg-primary p-3 text-primary-foreground',
              'hover:bg-primary/90 transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Connected to {activeServers.length} MCP server{activeServers.length !== 1 ? 's' : ''}.{' '}
          <Link to={ROUTES.MCP_MARKETPLACE} className="text-primary hover:underline">
            Add more
          </Link>
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: MCPChatMessage }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = message.role === 'user';

  return (
    <motion.div
      variants={staggerItemVariants}
      className={cn('flex items-start gap-3', isUser && 'flex-row-reverse')}
    >
      <div className={cn('rounded-full p-2', isUser ? 'bg-primary' : 'bg-primary/10')}>
        {isUser ? (
          <User className="h-4 w-4 text-primary-foreground" />
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>

      <div className={cn('flex-1 max-w-[80%]', isUser && 'flex flex-col items-end')}>
        <div
          className={cn(
            'rounded-xl p-4',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-muted',
            message.error && 'border border-destructive bg-destructive/10',
            message.pending && 'animate-pulse'
          )}
        >
          {message.pending ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Generating response...</span>
            </div>
          ) : (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          )}

          {/* Tool calls display */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
              {message.toolCalls.map((tool) => (
                <ToolCallDisplay key={tool.id} toolCall={tool} />
              ))}
            </div>
          )}
        </div>

        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatRelativeTime(message.timestamp)}</span>
          {!isUser && !message.pending && (
            <button onClick={handleCopy} className="rounded p-1 hover:bg-muted transition-colors">
              {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function ToolCallDisplay({ toolCall }: { toolCall: MCPToolCall }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg bg-background/50 p-2 text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors w-full"
      >
        <Zap
          className={cn(
            'h-3 w-3',
            toolCall.status === 'success' && 'text-green-500',
            toolCall.status === 'error' && 'text-red-500',
            toolCall.status === 'pending' && 'animate-pulse'
          )}
        />
        <span className="font-mono">{toolCall.name}</span>
        <span className="text-muted-foreground/50">({toolCall.serverName})</span>
        {toolCall.status === 'pending' && <Loader2 className="h-3 w-3 animate-spin ml-auto" />}
      </button>
      {expanded && toolCall.result && (
        <pre className="mt-2 p-2 bg-muted rounded overflow-auto text-xs max-h-40">
          {JSON.stringify(toolCall.result, null, 2)}
        </pre>
      )}
      {toolCall.error && (
        <p className="mt-1 text-red-500 text-xs">{toolCall.error}</p>
      )}
    </div>
  );
}

function ServerStatusBadges({ servers }: { servers: { id: string; name: string }[] }) {
  if (servers.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="h-2 w-2 rounded-full bg-muted-foreground" />
        <span>No servers connected</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-2 rounded-full bg-green-500" />
      <span className="text-sm text-muted-foreground">
        {servers.length} server{servers.length !== 1 ? 's' : ''}
      </span>
    </div>
  );
}

interface SettingsPanelProps {
  llmProviders: LLMProvider[];
  activeLLMProviderId: string | null;
  servers: { id: string; name: string; status: string }[];
}

function SettingsPanel({ llmProviders, activeLLMProviderId, servers }: SettingsPanelProps) {
  const { setActiveLLMProvider, updateLLMProvider, connectServer, disconnectServer } =
    useMCPStore();

  return (
    <div className="p-4 grid gap-6 md:grid-cols-2">
      {/* LLM Provider Selection */}
      <div className="space-y-3">
        <h3 className="font-medium flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          LLM Provider
        </h3>
        <p className="text-sm text-muted-foreground">
          Select and configure your preferred AI model for chat.
        </p>
        <div className="space-y-2">
          {llmProviders.map((provider) => (
            <div
              key={provider.id}
              className={cn(
                'flex items-center justify-between p-3 rounded-lg border',
                activeLLMProviderId === provider.id && 'border-primary bg-primary/5'
              )}
            >
              <div className="flex items-center gap-3">
                <input
                  type="radio"
                  name="llm-provider"
                  checked={activeLLMProviderId === provider.id}
                  onChange={() => setActiveLLMProvider(provider.id)}
                  className="accent-primary"
                />
                <div>
                  <p className="font-medium text-sm">{provider.name}</p>
                  <p className="text-xs text-muted-foreground">{provider.model}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {provider.isConfigured ? (
                  <span className="text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded">
                    Configured
                  </span>
                ) : (
                  <input
                    type="password"
                    placeholder="API Key"
                    className="text-xs border rounded px-2 py-1 w-32"
                    onChange={(e) =>
                      updateLLMProvider(provider.id, { apiKey: e.target.value })
                    }
                  />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* MCP Servers */}
      <div className="space-y-3">
        <h3 className="font-medium flex items-center gap-2">
          <Server className="h-4 w-4" />
          MCP Servers
        </h3>
        <p className="text-sm text-muted-foreground">
          Manage connected MCP servers that provide tools and resources.
        </p>
        <div className="space-y-2">
          {servers.map((server) => (
            <div
              key={server.id}
              className="flex items-center justify-between p-3 rounded-lg border"
            >
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    'h-2 w-2 rounded-full',
                    server.status === 'connected' && 'bg-green-500',
                    server.status === 'disconnected' && 'bg-gray-400',
                    server.status === 'error' && 'bg-red-500'
                  )}
                />
                <span className="text-sm font-medium">{server.name}</span>
              </div>
              <button
                onClick={() =>
                  server.status === 'connected'
                    ? disconnectServer(server.id)
                    : connectServer(server.id)
                }
                className={cn(
                  'text-xs px-3 py-1 rounded',
                  server.status === 'connected'
                    ? 'text-red-600 hover:bg-red-50'
                    : 'text-primary hover:bg-primary/10'
                )}
              >
                {server.status === 'connected' ? 'Disconnect' : 'Connect'}
              </button>
            </div>
          ))}
        </div>
        <Link
          to={ROUTES.MCP_MARKETPLACE}
          className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
        >
          <ExternalLink className="h-3 w-3" />
          Browse MCP Marketplace
        </Link>
      </div>
    </div>
  );
}
