/**
 * AgentGridWidget -- grid of agent cards showing tier, version, and
 * last-seen timestamp for each registered agent.
 *
 * Data shape:
 *   { agents: { nodeId: string; displayName?: string; tier?: string;
 *     version?: string; lastSeen?: string }[] }
 */

import { Bot } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface AgentEntry {
  nodeId: string;
  displayName?: string;
  tier?: string;
  version?: string;
  lastSeen?: string;
}

interface AgentGridData {
  agents: AgentEntry[];
}

const TIER_COLORS: Record<string, { bg: string; text: string }> = {
  full: { bg: 'bg-emerald-500/10', text: 'text-emerald-600' },
  lite: { bg: 'bg-blue-500/10', text: 'text-blue-600' },
  passive: { bg: 'bg-gray-500/10', text: 'text-gray-600' },
};

const DEFAULT_TIER_COLOR = { bg: 'bg-gray-500/10', text: 'text-gray-600' };

function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;

  if (Number.isNaN(diffMs)) return isoString;

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function AgentGridWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<AgentGridData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.agents.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Bot className="h-5 w-5" />
        <div className="text-sm">No agents registered</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-1">
      <div className="grid grid-cols-2 gap-2">
        {data.agents.map((agent) => {
          const tierKey = agent.tier?.toLowerCase() ?? '';
          const tierStyle = TIER_COLORS[tierKey] ?? DEFAULT_TIER_COLOR;

          return (
            <div
              key={agent.nodeId}
              className="flex flex-col gap-1.5 rounded-lg border border-border/60 bg-muted/10 p-2.5 transition-colors hover:bg-muted/20"
            >
              <div className="flex items-center gap-2">
                <Bot className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate text-xs font-semibold">
                  {agent.displayName ?? agent.nodeId}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                {agent.tier && (
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${tierStyle.bg} ${tierStyle.text}`}
                  >
                    {agent.tier}
                  </span>
                )}
                {agent.version && (
                  <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    v{agent.version}
                  </span>
                )}
              </div>

              {agent.lastSeen && (
                <div className="text-[10px] text-muted-foreground/60">
                  Seen {formatRelativeTime(agent.lastSeen)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
