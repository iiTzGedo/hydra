import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  History,
  Search,
} from 'lucide-react';
import { useCommands, type CommandStatus } from '@/api/commands';
import { ROUTES } from '@/lib/constants';
import { formatRelativeTime } from '@/lib/utils';
import { CommandStatusBadge } from '@/components/commands/command-status-badge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

type TimeRange = 'hour' | 'day' | 'week' | 'all';

const TIME_RANGE_LABELS: Record<TimeRange, string> = {
  hour: 'Last Hour',
  day: 'Last 24 Hours',
  week: 'Last 7 Days',
  all: 'All Time',
};

const COMPLETED_STATUSES: CommandStatus[] = [
  'completed',
  'failed',
  'timeout',
  'cancelled',
  'rejected',
];

function getTimeRangeFilter(range: TimeRange): Date | null {
  const now = new Date();
  switch (range) {
    case 'hour':
      return new Date(now.getTime() - 60 * 60 * 1000);
    case 'day':
      return new Date(now.getTime() - 24 * 60 * 60 * 1000);
    case 'week':
      return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    case 'all':
      return null;
  }
}

function formatTimeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return 'just now';
  if (diffMs < 60_000) return `${Math.floor(diffMs / 1000)}s ago`;
  if (diffMs < 3_600_000) return `${Math.floor(diffMs / 60_000)}m ago`;
  if (diffMs < 86_400_000) return `${Math.floor(diffMs / 3_600_000)}h ago`;
  return `${Math.floor(diffMs / 86_400_000)}d ago`;
}

export function CommandHistory() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<CommandStatus | 'all'>('all');
  const [timeRange, setTimeRange] = useState<TimeRange>('day');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // Fetch commands with status filter if specified
  const queryParams = useMemo(() => {
    const params: { status?: CommandStatus } = {};
    if (statusFilter !== 'all') {
      params.status = statusFilter;
    }
    return params;
  }, [statusFilter]);

  const { data: commands, isLoading, error } = useCommands(
    Object.keys(queryParams).length > 0 ? queryParams : undefined
  );

  // Apply client-side filtering for time range, search, and completed-only
  const filteredCommands = useMemo(() => {
    if (!commands) return [];

    const timeThreshold = getTimeRangeFilter(timeRange);
    const query = searchQuery.toLowerCase().trim();

    return commands.filter((cmd) => {
      // Only show completed/terminal statuses in history (unless explicitly filtered)
      if (statusFilter === 'all' && !COMPLETED_STATUSES.includes(cmd.status)) {
        return false;
      }

      // Time range filter
      if (timeThreshold) {
        const cmdTime = new Date(cmd.createdAt);
        if (cmdTime < timeThreshold) return false;
      }

      // Search filter
      if (query) {
        const matchesAction = cmd.action.toLowerCase().includes(query);
        const matchesNode = cmd.target.nodeId.toLowerCase().includes(query);
        const matchesService = cmd.target.serviceId?.toLowerCase().includes(query);
        if (!matchesAction && !matchesNode && !matchesService) return false;
      }

      return true;
    });
  }, [commands, statusFilter, timeRange, searchQuery]);

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
          <h3 className="mt-4 text-lg font-semibold">Failed to load command history</h3>
          <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Skeleton className="h-10 w-[160px]" />
          <Skeleton className="h-10 w-[160px]" />
          <Skeleton className="h-10 w-64" />
        </div>
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="w-[30px]" />
                <TableHead className="text-muted-foreground">Timestamp</TableHead>
                <TableHead className="text-muted-foreground">Action</TableHead>
                <TableHead className="text-muted-foreground">Target</TableHead>
                <TableHead className="text-muted-foreground">Status</TableHead>
                <TableHead className="text-muted-foreground">Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[1, 2, 3, 4, 5].map((i) => (
                <TableRow key={i} className="border-border">
                  <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20 rounded-md" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={statusFilter}
          onValueChange={(value) => setStatusFilter(value as CommandStatus | 'all')}
        >
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="timeout">Timeout</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={timeRange}
          onValueChange={(value) => setTimeRange(value as TimeRange)}
        >
          <SelectTrigger className="w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.entries(TIME_RANGE_LABELS) as [TimeRange, string][]).map(
              ([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              )
            )}
          </SelectContent>
        </Select>

        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by action or target..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        <Badge variant="secondary" className="ml-auto">
          {filteredCommands.length} result{filteredCommands.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      {/* Table */}
      {filteredCommands.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <History className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No commands found</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {statusFilter !== 'all' || searchQuery
                ? 'Try adjusting the filters'
                : 'Command history will appear here after commands are executed'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="w-[30px]" />
                <TableHead className="text-muted-foreground">Timestamp</TableHead>
                <TableHead className="text-muted-foreground">Action</TableHead>
                <TableHead className="text-muted-foreground">Target</TableHead>
                <TableHead className="text-muted-foreground">Status</TableHead>
                <TableHead className="text-muted-foreground">Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredCommands.map((cmd) => {
                const isExpanded = expandedRow === cmd.commandId;

                return (
                  <TableRow
                    key={cmd.commandId}
                    className="border-border cursor-pointer hover:bg-muted/60"
                  >
                    <TableCell
                      onClick={() =>
                        setExpandedRow(isExpanded ? null : cmd.commandId)
                      }
                    >
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </TableCell>
                    <TableCell
                      className="text-sm text-muted-foreground"
                      onClick={() =>
                        navigate(`${ROUTES.COMMANDS}/${cmd.commandId}`)
                      }
                    >
                      {formatRelativeTime(cmd.createdAt)}
                    </TableCell>
                    <TableCell
                      className="font-medium"
                      onClick={() =>
                        navigate(`${ROUTES.COMMANDS}/${cmd.commandId}`)
                      }
                    >
                      {cmd.action}
                    </TableCell>
                    <TableCell
                      onClick={() =>
                        navigate(`${ROUTES.COMMANDS}/${cmd.commandId}`)
                      }
                    >
                      <span className="text-sm text-muted-foreground font-mono">
                        {cmd.target.nodeId}
                        {cmd.target.serviceId ? ` / ${cmd.target.serviceId}` : ''}
                      </span>
                    </TableCell>
                    <TableCell
                      onClick={() =>
                        navigate(`${ROUTES.COMMANDS}/${cmd.commandId}`)
                      }
                    >
                      <CommandStatusBadge status={cmd.status} />
                    </TableCell>
                    <TableCell
                      className="text-sm text-muted-foreground"
                      onClick={() =>
                        navigate(`${ROUTES.COMMANDS}/${cmd.commandId}`)
                      }
                    >
                      {formatTimeAgo(cmd.createdAt)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
