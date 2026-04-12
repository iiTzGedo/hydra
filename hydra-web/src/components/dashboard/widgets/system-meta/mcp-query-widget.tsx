/**
 * McpQueryWidget -- config-only placeholder for MCP natural-language queries.
 * Displays a text input with a "Query" button. On submit, shows a toast
 * indicating MCP integration is coming in Wave 5.
 *
 * Config: none required
 *
 * No data binding. This widget will integrate with the MCP chat system
 * once that infrastructure is surfaced as a widget-consumable API.
 */

import { MessageSquare, Send } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

export function McpQueryWidget({
  isLoading,
  error,
}: WidgetComponentProps) {
  const [query, setQuery] = useState('');

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    toast.info('MCP integration coming in Wave 5', {
      description: query
        ? `Your query: "${query}"`
        : 'Enter a natural-language query to interact with your infrastructure.',
    });
  }

  return (
    <div className="flex h-full flex-col gap-3 p-1">
      {/* Header */}
      <div className="flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">MCP Query</span>
        <span className="ml-auto rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-600">
          Wave 5
        </span>
      </div>

      {/* Query input */}
      <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-2">
        <div className="flex flex-1 gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about your infrastructure..."
            className="min-w-0 flex-1 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs placeholder:text-muted-foreground/50 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
          <button
            type="submit"
            className="flex shrink-0 items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/20"
          >
            <Send className="h-3.5 w-3.5" />
            Query
          </button>
        </div>
      </form>

      <div className="text-center text-[10px] text-muted-foreground/60">
        Natural-language queries to Hydra MCP
      </div>
    </div>
  );
}
