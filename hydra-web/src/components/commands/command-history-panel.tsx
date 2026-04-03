import { Link } from 'react-router-dom';
import { History, ChevronRight } from 'lucide-react';
import { useCommands } from '@/api/commands';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { CommandStatusBadge } from '@/components/commands/command-status-badge';
import { formatRelativeTime } from '@/lib/utils';

interface CommandHistoryPanelProps {
  nodeId: string;
  serviceId?: string;
  limit?: number;
}

export function CommandHistoryPanel({
  nodeId,
  serviceId,
  limit = 10,
}: CommandHistoryPanelProps) {
  const { data: commands, isLoading } = useCommands({ nodeId, serviceId });
  const visibleCommands = commands?.slice(0, limit) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <History className="h-4 w-4" />
          Recent Commands
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-10 animate-pulse rounded-md bg-muted"
              />
            ))}
          </div>
        ) : visibleCommands.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            No commands yet
          </div>
        ) : (
          <div className="space-y-1">
            {visibleCommands.map((cmd) => (
              <Link
                key={cmd.commandId}
                to={`/commands/${cmd.commandId}`}
                className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted/50 group"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <CommandStatusBadge status={cmd.status} />
                  <span className="truncate font-medium">{cmd.action}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0 text-muted-foreground">
                  <span className="text-xs">
                    {formatRelativeTime(cmd.createdAt)}
                  </span>
                  <ChevronRight className="h-3.5 w-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
