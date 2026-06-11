import { useCallback, useMemo, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  AlertTriangle,
  Clock,
  Loader2,
  XCircle,
} from 'lucide-react';
import { useCommands, useCancelCommand, type CommandStatus } from '@/api/commands';
import { EntityCombobox } from '@/components/ui/entity-combobox';
import { getErrorMessage } from '@/lib/api-client';
import { cn, formatRelativeTime } from '@/lib/utils';
import { CommandStatusBadge } from '@/components/commands/command-status-badge';
import { HydraIcon } from '@/components/icons/hydra-icon';
import { categoryToCommandKind, getCommandIconDescriptor } from '@/lib/command-icons';
import { commandToken } from '@/lib/design-tokens';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import type { CommandSummary } from '@/api/commands';

function CommandActionCell({ cmd }: { cmd: CommandSummary }) {
  const kind = categoryToCommandKind(
    cmd.type === 'service' || cmd.type === 'node' || cmd.type === 'agent' ? cmd.type : null,
    cmd.type,
  );
  const icon = getCommandIconDescriptor({
    registryId: cmd.registryId ?? null,
    type: cmd.type,
  });
  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          'flex h-7 w-7 shrink-0 items-center justify-center rounded-md border',
          commandToken({ kind, surface: 'soft' }),
        )}
        aria-hidden="true"
      >
        <HydraIcon icon={icon} fallback="terminal" size={14} />
      </span>
      <span className="truncate">{cmd.action}</span>
    </div>
  );
}
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const RUNNING_STATUSES: CommandStatus[] = ['executing'];
const QUEUED_STATUSES: CommandStatus[] = ['queued', 'pending', 'pending_confirmation'];

export function ExecutionQueue() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [nodeFilter, setNodeFilter] = useState<string>(
    () => searchParams?.get('nodeId') || ''
  );

  const handleNodeFilterChange = useCallback(
    (value: string) => {
      setNodeFilter(value);
      const params = new URLSearchParams(searchParams?.toString() ?? '');
      if (value) {
        params.set('nodeId', value);
      } else {
        params.delete('nodeId');
      }
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams]
  );

  const { data: allCommands, isLoading, error } = useCommands(
    nodeFilter ? { nodeId: nodeFilter } : undefined
  );
  const cancelCommand = useCancelCommand();

  const running = useMemo(
    () =>
      (allCommands ?? []).filter((cmd) =>
        RUNNING_STATUSES.includes(cmd.status)
      ),
    [allCommands]
  );

  const queued = useMemo(
    () =>
      (allCommands ?? []).filter((cmd) =>
        QUEUED_STATUSES.includes(cmd.status)
      ),
    [allCommands]
  );

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
          <h3 className="mt-4 text-lg font-semibold">Failed to load execution queue</h3>
          <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        {[1, 2].map((section) => (
          <div key={section} className="space-y-3">
            <Skeleton className="h-6 w-40" />
            <Card>
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="text-muted-foreground">Action</TableHead>
                    <TableHead className="text-muted-foreground">Target</TableHead>
                    <TableHead className="text-muted-foreground">Status</TableHead>
                    <TableHead className="text-muted-foreground">Created</TableHead>
                    <TableHead className="w-[80px]" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[1, 2, 3].map((i) => (
                    <TableRow key={i} className="border-border">
                      <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-20 rounded-md" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-8 w-8 rounded-md" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Node filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Filter by node</span>
        <div className="w-64">
          <EntityCombobox
            entityType="node"
            value={nodeFilter}
            onValueChange={handleNodeFilterChange}
            clearable
            placeholder="All nodes"
          />
        </div>
      </div>

      {/* Running Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-warning animate-spin" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Running
          </h3>
          <Badge variant="warning">{running.length}</Badge>
        </div>

        {running.length === 0 ? (
          <Card>
            <CardContent className="py-6 text-center">
              <p className="text-sm text-muted-foreground">No commands currently executing</p>
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
                {running.map((cmd) => (
                  <TableRow key={cmd.commandId} className="border-border">
                    <TableCell className="font-medium">
                      <CommandActionCell cmd={cmd} />
                    </TableCell>
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

      {/* Queued Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-info" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Queued
          </h3>
          <Badge variant="info">{queued.length}</Badge>
        </div>

        {queued.length === 0 ? (
          <Card>
            <CardContent className="py-6 text-center">
              <p className="text-sm text-muted-foreground">No commands in queue</p>
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
                  <TableHead className="w-[80px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {queued.map((cmd) => (
                  <TableRow key={cmd.commandId} className="border-border">
                    <TableCell className="font-medium">
                      <CommandActionCell cmd={cmd} />
                    </TableCell>
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
                    <TableCell>
                      {(cmd.status === 'queued' || cmd.status === 'pending') && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCancel(cmd.commandId)}
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
    </div>
  );
}
