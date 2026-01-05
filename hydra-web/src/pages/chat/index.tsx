import { useState, useRef, useEffect } from 'react';
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
  AlertCircle,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { cn, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants, fadeInVariants } from '@/lib/animations';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  error?: boolean;
}

interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
}

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
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Simulate AI response (placeholder for MCP integration)
    setTimeout(() => {
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: getMockResponse(userMessage.content),
        timestamp: new Date(),
        toolCalls: getMockToolCalls(userMessage.content),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
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
    setMessages([]);
  };

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Header */}
      <div className="border-b p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-hydra-blue p-2">
            <MessageSquare className="h-5 w-5 text-white" />
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
          <ConnectionStatus status={connectionStatus} />
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
              Ask me about your infrastructure. I can help you find nodes, services,
              analyze topology, and answer questions about your setup.
            </p>

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
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Powered by MCP (Model Context Protocol). Responses are generated based on your infrastructure data.
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
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
            message.error && 'border border-error bg-error/10'
          )}
        >
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>

          {/* Tool calls display */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
              {message.toolCalls.map((tool, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-background/50 p-2 text-xs"
                >
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Zap className="h-3 w-3" />
                    <span className="font-mono">{tool.name}</span>
                  </div>
                  {tool.result && (
                    <pre className="mt-1 overflow-auto text-xs">
                      {JSON.stringify(tool.result, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatRelativeTime(message.timestamp)}</span>
          {!isUser && (
            <button
              onClick={handleCopy}
              className="rounded p-1 hover:bg-muted transition-colors"
            >
              {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function ConnectionStatus({ status }: { status: 'connected' | 'disconnected' | 'connecting' }) {
  const statusConfig = {
    connected: {
      color: 'bg-success',
      label: 'Connected',
    },
    disconnected: {
      color: 'bg-muted-foreground',
      label: 'Disconnected',
    },
    connecting: {
      color: 'bg-warning',
      label: 'Connecting...',
    },
  };

  const config = statusConfig[status];

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span className={cn('h-2 w-2 rounded-full', config.color)} />
      <span>{config.label}</span>
    </div>
  );
}

// Mock response generator (placeholder for real MCP integration)
function getMockResponse(query: string): string {
  const lowerQuery = query.toLowerCase();

  if (lowerQuery.includes('node') && lowerQuery.includes('list')) {
    return `I found 12 nodes in your infrastructure:\n\n**Compute (8):**\n- proxmox-01 (bare-metal, active)\n- docker-host-01 (VM, active)\n- docker-host-02 (VM, active)\n- k8s-master (VM, active)\n- k8s-worker-01 (VM, active)\n- k8s-worker-02 (VM, active)\n- nas-01 (bare-metal, active)\n- backup-server (VM, inactive)\n\n**Networking (3):**\n- opnsense.gw (router, active)\n- switch-core (switch, active)\n- ap-office (access-point, active)\n\n**IoT (1):**\n- hass-controller (controller, active)`;
  }

  if (lowerQuery.includes('service') && lowerQuery.includes('docker')) {
    return `Found 15 Docker services:\n\n| Service | Node | Status | Ports |\n|---------|------|--------|-------|\n| nginx-proxy | docker-host-01 | running | 80, 443 |\n| mongodb | docker-host-01 | running | 27017 |\n| redis | docker-host-01 | running | 6379 |\n| portainer | docker-host-01 | running | 9000 |\n| grafana | docker-host-02 | running | 3000 |\n| prometheus | docker-host-02 | running | 9090 |\n\n*6 more services running...*`;
  }

  if (lowerQuery.includes('network')) {
    return `Your infrastructure has 4 networks:\n\n1. **192.168.1.0/24** (L3)\n   - Gateway: 192.168.1.1\n   - 8 nodes connected\n   - Primary network\n\n2. **192.168.10.0/24** (L3)\n   - Gateway: 192.168.10.1\n   - 4 nodes connected\n   - Container network\n\n3. **10.0.0.0/8** (VXLAN)\n   - Kubernetes overlay\n   - 3 nodes connected\n\n4. **172.17.0.0/16** (L2)\n   - Docker bridge\n   - Local to hosts`;
  }

  if (lowerQuery.includes('topology') || lowerQuery.includes('summarize')) {
    return `**Infrastructure Summary**\n\nYour infrastructure consists of:\n- **12 nodes** across 3 classes (compute, networking, IoT)\n- **24 services** running on various runtimes\n- **4 networks** connecting your infrastructure\n- **3 groups** for logical organization\n\n**Key Observations:**\n- All networking equipment is healthy\n- 1 compute node is currently inactive (backup-server)\n- Last topology update: 5 minutes ago\n- 98% of services are running normally`;
  }

  if (lowerQuery.includes('ram') || lowerQuery.includes('memory')) {
    return `Found 5 nodes with more than 16GB RAM:\n\n| Node | Class | RAM | Usage |\n|------|-------|-----|-------|\n| proxmox-01 | compute | 128 GB | 67% |\n| docker-host-01 | compute | 64 GB | 45% |\n| docker-host-02 | compute | 32 GB | 38% |\n| k8s-master | compute | 32 GB | 52% |\n| nas-01 | compute | 32 GB | 28% |`;
  }

  if (lowerQuery.includes('port')) {
    return `Services with exposed ports:\n\n**Web Services:**\n- nginx-proxy: 80, 443\n- grafana: 3000\n- portainer: 9000\n\n**Databases:**\n- mongodb: 27017\n- redis: 6379\n- postgresql: 5432\n\n**Monitoring:**\n- prometheus: 9090\n- node-exporter: 9100\n\n*Total: 12 services with 18 exposed ports*`;
  }

  return `I understand you're asking about "${query}". \n\nIn the production version, I'll query your infrastructure using MCP tools to provide accurate, real-time information. \n\nHere are some things I can help with:\n- List and filter nodes, services, networks\n- Analyze topology and relationships\n- Find resources by specific criteria\n- Summarize infrastructure status\n\nTry asking something more specific!`;
}

function getMockToolCalls(query: string): ToolCall[] | undefined {
  const lowerQuery = query.toLowerCase();

  if (lowerQuery.includes('node') && lowerQuery.includes('list')) {
    return [
      {
        name: 'list_nodes',
        arguments: { status: 'active' },
        result: { count: 12 },
      },
    ];
  }

  if (lowerQuery.includes('service') && lowerQuery.includes('docker')) {
    return [
      {
        name: 'list_services',
        arguments: { runtime: 'docker' },
        result: { count: 15 },
      },
    ];
  }

  if (lowerQuery.includes('network')) {
    return [
      {
        name: 'list_networks',
        arguments: {},
        result: { count: 4 },
      },
    ];
  }

  return undefined;
}
