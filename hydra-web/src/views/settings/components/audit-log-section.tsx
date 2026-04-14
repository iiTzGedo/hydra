import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Search, FileText, Settings, Trash2, AlertTriangle } from 'lucide-react';
import { useAuditLog, useDeleteAuditEntries } from '@/api/query';
import { useAuthStore } from '@/stores/auth-store';
import { useToast } from '@/components/ui/use-toast';
import type { AuditEntry } from '@/types/query';
import { formatDate, formatRelativeTime, cn } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Pagination } from '@/components/ui/pagination';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { resourceIcons, actionIcons, actionVariants } from '../constants';

export function AuditLogSection() {
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState<string>('all');
  const [page, setPage] = useState(0);
  const limit = 10;

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteSince, setDeleteSince] = useState('');
  const [deleteUntil, setDeleteUntil] = useState('');
  const [confirmStep, setConfirmStep] = useState(false);

  const { hasAnyRole } = useAuthStore();
  const isAdmin = hasAnyRole(['admin']);
  const { toast } = useToast();
  const deleteAuditMutation = useDeleteAuditEntries();

  useEffect(() => {
    setPage(0);
  }, [search, filterAction]);

  const { data, isLoading, error } = useAuditLog({
    limit,
    offset: page * limit,
    resourceType: filterAction !== 'all' ? filterAction : undefined,
  });

  const logs = data?.items ?? [];
  const normalizedSearch = search.trim().toLowerCase();
  const filteredLogs = normalizedSearch
    ? logs.filter((log) => {
        const resourceText = `${log.resource.type}:${log.resource.id}`.toLowerCase();
        const actorText = `${log.actor.type}:${log.actor.id}`.toLowerCase();
        return (
          log.action.toLowerCase().includes(normalizedSearch) ||
          resourceText.includes(normalizedSearch) ||
          actorText.includes(normalizedSearch)
        );
      })
    : logs;

  const totalPages = normalizedSearch ? 1 : Math.ceil((data?.total ?? 0) / limit);

  function handleDeleteDialogOpen(open: boolean) {
    setDeleteDialogOpen(open);
    if (!open) {
      setDeleteSince('');
      setDeleteUntil('');
      setConfirmStep(false);
    }
  }

  function handleDeleteSubmit() {
    if (!confirmStep) {
      setConfirmStep(true);
      return;
    }

    const sinceISO = new Date(deleteSince).toISOString();
    const untilISO = new Date(deleteUntil).toISOString();

    deleteAuditMutation.mutate(
      { since: sinceISO, until: untilISO },
      {
        onSuccess: (result) => {
          toast({
            title: 'Audit entries deleted',
            description: `Successfully deleted ${result?.deleted ?? 0} audit entries.`,
          });
          handleDeleteDialogOpen(false);
        },
        onError: (err) => {
          toast({
            title: 'Failed to delete audit entries',
            description: err instanceof Error ? err.message : 'An unexpected error occurred.',
            variant: 'destructive',
          });
          setConfirmStep(false);
        },
      }
    );
  }

  const isDeleteFormValid = deleteSince && deleteUntil && new Date(deleteSince) < new Date(deleteUntil);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-foreground">Audit Log</h3>
          <p className="text-sm text-muted-foreground">View system activity and changes</p>
        </div>

        {isAdmin && (
          <Dialog open={deleteDialogOpen} onOpenChange={handleDeleteDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="destructive" size="sm">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Entries
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-background border-border">
              <DialogHeader>
                <DialogTitle className="text-foreground">
                  {confirmStep ? 'Confirm Deletion' : 'Delete Audit Entries'}
                </DialogTitle>
                <DialogDescription>
                  {confirmStep
                    ? 'This action cannot be undone. Are you sure you want to delete the selected audit entries?'
                    : 'Select a time window to delete audit entries. All entries within the specified range will be permanently removed.'}
                </DialogDescription>
              </DialogHeader>

              {confirmStep ? (
                <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                  <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <p className="font-medium text-destructive">Permanent deletion</p>
                    <p className="mt-1 text-muted-foreground">
                      All audit entries from{' '}
                      <span className="font-mono text-foreground">{new Date(deleteSince).toLocaleString()}</span>
                      {' '}to{' '}
                      <span className="font-mono text-foreground">{new Date(deleteUntil).toLocaleString()}</span>
                      {' '}will be permanently deleted.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="delete-since" className="text-foreground">From</Label>
                    <Input
                      id="delete-since"
                      type="datetime-local"
                      value={deleteSince}
                      onChange={(e) => setDeleteSince(e.target.value)}
                      className="bg-muted border-border text-foreground"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="delete-until" className="text-foreground">To</Label>
                    <Input
                      id="delete-until"
                      type="datetime-local"
                      value={deleteUntil}
                      onChange={(e) => setDeleteUntil(e.target.value)}
                      className="bg-muted border-border text-foreground"
                    />
                  </div>
                  {deleteSince && deleteUntil && new Date(deleteSince) >= new Date(deleteUntil) && (
                    <p className="text-sm text-destructive">"From" date must be before "To" date.</p>
                  )}
                </div>
              )}

              <DialogFooter>
                {confirmStep ? (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => setConfirmStep(false)}
                      disabled={deleteAuditMutation.isPending}
                    >
                      Back
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={handleDeleteSubmit}
                      disabled={deleteAuditMutation.isPending}
                    >
                      {deleteAuditMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="destructive"
                    onClick={handleDeleteSubmit}
                    disabled={!isDeleteFormValid}
                  >
                    Continue
                  </Button>
                )}
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 bg-muted border-border text-foreground"
          />
        </div>

        <Select value={filterAction} onValueChange={setFilterAction}>
          <SelectTrigger className="w-[180px] bg-muted border-border text-foreground">
            <SelectValue placeholder="All Actions" />
          </SelectTrigger>
          <SelectContent className="bg-popover border-border">
            <SelectItem value="all">All Actions</SelectItem>
            <SelectItem value="user">User</SelectItem>
            <SelectItem value="node">Node</SelectItem>
            <SelectItem value="service">Service</SelectItem>
            <SelectItem value="network">Network</SelectItem>
            <SelectItem value="group">Group</SelectItem>
            <SelectItem value="topology">Topology</SelectItem>
            <SelectItem value="notification">Notification</SelectItem>
            <SelectItem value="api_key">API Key</SelectItem>
            <SelectItem value="profile">Profile</SelectItem>
            <SelectItem value="command">Command</SelectItem>
            <SelectItem value="chat_project">Chat Project</SelectItem>
            <SelectItem value="chat_session">Chat Session</SelectItem>
            <SelectItem value="audit_log">Audit Log</SelectItem>
            <SelectItem value="password_reset">Password Reset</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <p className="text-destructive">Failed to load audit logs</p>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card className="bg-card border-border">
          <CardContent className="p-6 space-y-4">
            {[...Array(5)].map((_, index) => (
              <Skeleton key={index} className="h-12 w-full rounded-lg bg-muted" />
            ))}
          </CardContent>
        </Card>
      ) : filteredLogs.length === 0 ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold text-foreground">No audit entries</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {normalizedSearch ? 'No entries match your search' : 'Audit log is empty'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
        >
          <Card className="bg-card border-border">
            <div className="divide-y divide-border">
              {filteredLogs.map((log: AuditEntry) => {
                const Icon = resourceIcons[log.resource.type] || FileText;
                const ActionIcon = actionIcons[log.action] || Settings;
                const variant = actionVariants[log.action] || 'secondary';

                return (
                  <motion.div
                    key={log.entryId}
                    variants={staggerItemVariants}
                    className="flex items-start gap-4 p-4 hover:bg-muted/60 transition-colors"
                  >
                    <div
                      className={cn(
                        'rounded-lg p-2',
                        variant === 'success' && 'bg-success/10 text-success',
                        variant === 'default' && 'bg-primary/10 text-primary',
                        variant === 'destructive' && 'bg-destructive/10 text-destructive',
                        variant === 'secondary' && 'bg-muted text-muted-foreground',
                        variant === 'warning' && 'bg-warning/10 text-warning'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <ActionIcon className="h-3 w-3 text-muted-foreground" />
                        <span className="font-medium text-foreground">{log.action}</span>
                        <Badge
                          variant={variant}
                          className={cn(
                            variant === 'success' && 'bg-success/20 text-success',
                            variant === 'default' && 'bg-primary/20 text-primary',
                            variant === 'destructive' && 'bg-destructive/20 text-destructive',
                            variant === 'secondary' && 'bg-muted text-foreground',
                            variant === 'warning' && 'bg-warning/20 text-warning'
                          )}
                        >
                          {log.resource.type}
                        </Badge>
                      </div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        <span className="font-mono">
                          {log.resource.type}:{log.resource.id}
                        </span>
                        <span className="mx-2">by</span>
                        <span>
                          {log.actor.type}:{log.actor.id}
                        </span>
                        {log.actor.ip && <span className="ml-2">({log.actor.ip})</span>}
                      </div>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {Object.entries(log.details).map(([key, value]) => (
                            <Badge
                              key={key}
                              variant="secondary"
                              className="text-xs bg-muted text-muted-foreground"
                            >
                              {key}: {String(value)}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="text-right">
                      <div className="text-sm text-muted-foreground" title={formatDate(log.timestamp)}>
                        {formatRelativeTime(log.timestamp)}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>
        </motion.div>
      )}

      {!normalizedSearch && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
