import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Terminal,
  Play,
  Clock,
  History,
  AlertTriangle,
  XCircle,
  Loader2,
  Server,
  Boxes,
  Bot,
} from 'lucide-react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import {
  useCommandCatalog,
  useCommandQueue,
  useCommands,
  useCancelCommand,
  type CommandStatus,
  type CommandCategory,
  type CommandDefinitionSummary,
} from '@/api/commands';
import { getErrorMessage } from '@/lib/api-client';
import { formatRelativeTime } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { CommandStatusBadge } from '@/components/commands/command-status-badge';
import { ExecuteCommandDialog } from '@/components/commands/execute-command-dialog';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

// ── Category icons ────────────────────────────────────────────────────────
const CATEGORY_ICONS: Record<CommandCategory, typeof Server> = {
  service: Boxes,
  node: Server,
  agent: Bot,
};

const CATEGORY_LABELS: Record<CommandCategory, string> = {
  service: 'Service',
  node: 'Node',
  agent: 'Agent',
};

// ── Catalog Tab ───────────────────────────────────────────────────────────
function CatalogTab() {
  const { data: catalog, isLoading, error } = useCommandCatalog();
  const [selectedDef, setSelectedDef] = useState<CommandDefinitionSummary | undefined>();
  const [dialogOpen, setDialogOpen] = useState(false);

  const grouped = useMemo(() => {
    if (!catalog) return {};
    const groups: Partial<Record<CommandCategory, CommandDefinitionSummary[]>> = {};
    for (const def of catalog) {
      if (def.deprecated) continue;
      if (!groups[def.category]) {
        groups[def.category] = [];
      }
      groups[def.category]!.push(def);
    }
    return groups;
  }, [catalog]);

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
          <h3 className="mt-4 text-lg font-semibold">Failed to load catalog</h3>
          <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-3">
            <Skeleton className="h-6 w-32" />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((j) => (
                <Skeleton key={j} className="h-32 rounded-lg" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  const categories = Object.keys(grouped) as CommandCategory[];

  if (categories.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <Terminal className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No commands available</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Command definitions will appear here once registered
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="space-y-6">
        {categories.map((category) => {
          const CategoryIcon = CATEGORY_ICONS[category] ?? Terminal;
          const items = grouped[category] ?? [];

          return (
            <div key={category} className="space-y-3">
              <div className="flex items-center gap-2">
                <CategoryIcon className="h-5 w-5 text-muted-foreground" />
                <h3 className="text-lg font-semibold">
                  {CATEGORY_LABELS[category] ?? category} Commands
                </h3>
                <Badge variant="secondary">{items.length}</Badge>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((def) => (
                  <Card
                    key={def.registryId}
                    className="cursor-pointer transition-colors hover:border-primary/40 hover:bg-muted/30"
                    onClick={() => {
                      setSelectedDef(def);
                      setDialogOpen(true);
                    }}
                  >
                    <CardContent className="p-4 space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="text-sm font-medium leading-tight">
                          {def.displayName}
                        </h4>
                        <Play className="h-4 w-4 text-muted-foreground shrink-0" />
                      </div>
                      {def.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {def.description}
                        </p>
                      )}
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                          {def.minimumRole}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground">
                          {def.timeout}s timeout
                        </span>
                        {def.requiresConfirmation && (
                          <Badge variant="warning" className="text-[10px] px-1.5 py-0">
                            Confirm
                          </Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <ExecuteCommandDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        definition={selectedDef}
      />
    </>
  );
}

// ── Queue Tab ─────────────────────────────────────────────────────────────
function QueueTab() {
  const { data, isLoading, error } = useCommandQueue();
  const cancelCommand = useCancelCommand();

  const handleCancel = async (commandId: string) => {
    try {
      await cancelCommand.mutateAsync(commandId);
      toast.success('Command cancelled');
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to cancel command'));
    }
  };

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
          <h3 className="mt-4 text-lg font-semibold">Failed to load queue</h3>
          <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 grid-cols-2">
          <Skeleton className="h-20 rounded-lg" />
          <Skeleton className="h-20 rounded-lg" />
        </div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  const stats = data?.stats;
  const queue = data?.queue ?? [];

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid gap-3 grid-cols-2">
        <Card>
          <CardContent className="flex items-center justify-between p-4">
            <div>
              <p className="text-xs text-muted-foreground">Queued</p>
              <p className="text-xl font-semibold text-info">{stats?.totalQueued ?? 0}</p>
            </div>
            <Clock className="h-5 w-5 text-info" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center justify-between p-4">
            <div>
              <p className="text-xs text-muted-foreground">Executing</p>
              <p className="text-xl font-semibold text-warning">{stats?.totalExecuting ?? 0}</p>
            </div>
            <Loader2 className="h-5 w-5 text-warning animate-spin" />
          </CardContent>
        </Card>
      </div>

      {/* Queue List */}
      {queue.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Clock className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">Queue is empty</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              No commands are currently queued or executing
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="text-muted-foreground">Action</TableHead>
                <TableHead className="text-muted-foreground">Target</TableHead>
                <TableHead className="text-muted-foreground">Status</TableHead>
                <TableHead className="text-muted-foreground">Created</TableHead>
                <TableHead className="w-[80px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((item) => (
                <TableRow key={item.commandId} className="border-border">
                  <TableCell className="font-medium">{item.action}</TableCell>
                  <TableCell>
                    <span className="text-sm text-muted-foreground font-mono">
                      {item.target.nodeId}
                      {item.target.serviceId ? ` / ${item.target.serviceId}` : ''}
                    </span>
                  </TableCell>
                  <TableCell>
                    <CommandStatusBadge status={item.status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatRelativeTime(item.createdAt)}
                  </TableCell>
                  <TableCell>
                    {(item.status === 'queued' || item.status === 'pending') && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCancel(item.commandId)}
                        disabled={cancelCommand.isPending}
                      >
                        <XCircle className="h-4 w-4 text-destructive" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

// ── History Tab ───────────────────────────────────────────────────────────
function HistoryTab() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<CommandStatus | 'all'>('all');

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

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
          <h3 className="mt-4 text-lg font-semibold">Failed to load history</h3>
          <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="text-muted-foreground">Action</TableHead>
              <TableHead className="text-muted-foreground">Target</TableHead>
              <TableHead className="text-muted-foreground">Status</TableHead>
              <TableHead className="text-muted-foreground">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {[...Array(5)].map((_, i) => (
              <TableRow key={i} className="border-border">
                <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                <TableCell><Skeleton className="h-6 w-20 rounded-md" /></TableCell>
                <TableCell><Skeleton className="h-4 w-20" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex items-center gap-3">
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
            <SelectItem value="executing">Executing</SelectItem>
            <SelectItem value="queued">Queued</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {!commands || commands.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <History className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No commands found</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {statusFilter !== 'all'
                ? 'Try adjusting the status filter'
                : 'Command history will appear here'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="text-muted-foreground">Action</TableHead>
                <TableHead className="text-muted-foreground">Target</TableHead>
                <TableHead className="text-muted-foreground">Status</TableHead>
                <TableHead className="text-muted-foreground">Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {commands.map((cmd) => (
                <TableRow
                  key={cmd.commandId}
                  className="border-border cursor-pointer hover:bg-muted/60"
                  onClick={() => navigate(`${ROUTES.COMMANDS}/${cmd.commandId}`)}
                >
                  <TableCell className="font-medium">{cmd.action}</TableCell>
                  <TableCell>
                    <span className="text-sm text-muted-foreground font-mono">
                      {cmd.target.nodeId}
                      {cmd.target.serviceId ? ` / ${cmd.target.serviceId}` : ''}
                    </span>
                  </TableCell>
                  <TableCell>
                    <CommandStatusBadge status={cmd.status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatRelativeTime(cmd.createdAt)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────
export default function CommandsPage() {
  useDocumentTitle('Command Center');

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title="Command Center"
        subtitle="Manage, execute, and monitor infrastructure commands"
        showBackButton={false}
      />

      <Tabs defaultValue="catalog">
        <TabsList>
          <TabsTrigger value="catalog">
            <Terminal className="h-4 w-4 mr-1.5" />
            Catalog
          </TabsTrigger>
          <TabsTrigger value="queue">
            <Clock className="h-4 w-4 mr-1.5" />
            Queue
          </TabsTrigger>
          <TabsTrigger value="history">
            <History className="h-4 w-4 mr-1.5" />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="catalog">
          <CatalogTab />
        </TabsContent>

        <TabsContent value="queue">
          <QueueTab />
        </TabsContent>

        <TabsContent value="history">
          <HistoryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
