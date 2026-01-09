import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  FileText,
  Search,
  User,
  Server,
  Boxes,
  Network,
  FolderTree,
  Settings,
  LogIn,
  LogOut,
  UserPlus,
  Zap,
  Edit,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { useAuditLog } from '@/api/query';
import type { AuditAction, AuditEntry } from '@/types/query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

const resourceIcons: Record<string, typeof User> = {
  user: User,
  node: Server,
  service: Boxes,
  network: Network,
  group: FolderTree,
  topology: Settings,
  system: Settings,
};

const actionIcons: Record<AuditAction, typeof User> = {
  create: UserPlus,
  update: Edit,
  delete: Trash2,
  login: LogIn,
  logout: LogOut,
  register: UserPlus,
  execute: Zap,
};

const actionVariants: Record<AuditAction, 'success' | 'default' | 'destructive' | 'secondary' | 'warning'> = {
  create: 'success',
  update: 'default',
  delete: 'destructive',
  login: 'default',
  logout: 'secondary',
  register: 'success',
  execute: 'warning',
};

export default function AuditPage() {
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState<string>('all');
  const [page, setPage] = useState(0);
  const limit = 10;

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

  const totalPages = normalizedSearch
    ? 1
    : Math.ceil((data?.total ?? 0) / limit);

  return (
    <div className="p-6">
      <Button variant="ghost" size="sm" asChild className="mb-4">
        <Link to={ROUTES.ADMIN}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Admin
        </Link>
      </Button>

      <PageHeader
        title="Audit Log"
        description="View system activity and changes"
      />

      {/* Filters */}
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>

        <Select value={filterAction} onValueChange={setFilterAction}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Actions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Actions</SelectItem>
            <SelectItem value="user">User</SelectItem>
            <SelectItem value="node">Node</SelectItem>
            <SelectItem value="service">Service</SelectItem>
            <SelectItem value="network">Network</SelectItem>
            <SelectItem value="group">Group</SelectItem>
            <SelectItem value="topology">Topology</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Audit log list */}
      {error ? (
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-destructive">Failed to load audit logs</p>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card>
          <CardContent className="p-6 space-y-4">
            {[...Array(5)].map((_, index) => (
              <Skeleton key={index} className="h-12 w-full rounded-lg" />
            ))}
          </CardContent>
        </Card>
      ) : filteredLogs.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No audit entries</h3>
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
          <Card>
            <div className="divide-y">
              {filteredLogs.map((log: AuditEntry) => {
                const Icon = resourceIcons[log.resource.type] || FileText;
                const ActionIcon = actionIcons[log.action] || Settings;
                const variant = actionVariants[log.action] || 'secondary';

                return (
                  <motion.div
                    key={log.entryId}
                    variants={staggerItemVariants}
                    className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors"
                  >
                    <div className={cn(
                      'rounded-lg p-2',
                      variant === 'success' && 'bg-success/10 text-success',
                      variant === 'default' && 'bg-primary/10 text-primary',
                      variant === 'destructive' && 'bg-destructive/10 text-destructive',
                      variant === 'secondary' && 'bg-muted text-muted-foreground',
                      variant === 'warning' && 'bg-warning/10 text-warning',
                    )}>
                      <Icon className="h-4 w-4" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <ActionIcon className="h-3 w-3 text-muted-foreground" />
                        <span className="font-medium">{log.action}</span>
                        <Badge variant={variant}>
                          {log.resource.type}
                        </Badge>
                      </div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        <span className="font-mono">{log.resource.type}:{log.resource.id}</span>
                        <span className="mx-2">by</span>
                        <span>{log.actor.type}:{log.actor.id}</span>
                        {log.actor.ip && <span className="ml-2">({log.actor.ip})</span>}
                      </div>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {Object.entries(log.details).map(([key, value]) => (
                            <Badge key={key} variant="secondary" className="text-xs">
                              {key}: {String(value)}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="text-right">
                      <div className="text-sm" title={formatDate(log.timestamp)}>
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

      {/* Pagination */}
      {totalPages > 1 && !normalizedSearch && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm">
            Page {page + 1} of {totalPages}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
