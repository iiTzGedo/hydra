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
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { useAuditLog } from '@/api/query';
import type { AuditAction, AuditEntry } from '@/types/query';

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

const actionColors: Record<AuditAction, string> = {
  create: 'text-success bg-success/10',
  update: 'text-primary bg-primary/10',
  delete: 'text-error bg-error/10',
  login: 'text-primary bg-primary/10',
  logout: 'text-muted-foreground bg-muted',
  register: 'text-success bg-success/10',
  execute: 'text-warning bg-warning/10',
};

export default function AuditPage() {
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const limit = 10;

  useEffect(() => {
    setPage(0);
  }, [search, filterAction]);

  const { data, isLoading, error } = useAuditLog({
    limit,
    offset: page * limit,
    resourceType: filterAction || undefined,
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
      <Link
        to={ROUTES.ADMIN}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Admin
      </Link>

      <PageHeader
        title="Audit Log"
        description="View system activity and changes"
      />

      {/* Filters */}
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={cn(
              'w-full rounded-lg border bg-background pl-10 pr-4 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring',
              'placeholder:text-muted-foreground'
            )}
          />
        </div>

        <select
          value={filterAction || ''}
          onChange={(e) => setFilterAction(e.target.value || null)}
          className={cn(
            'rounded-lg border bg-background px-3 py-2 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-ring'
          )}
        >
          <option value="">All Actions</option>
          <option value="user">User</option>
          <option value="node">Node</option>
          <option value="service">Service</option>
          <option value="network">Network</option>
          <option value="group">Group</option>
          <option value="topology">Topology</option>
        </select>
      </div>

      {/* Audit log list */}
      {error ? (
        <div className="rounded-xl border bg-card p-8 text-center">
          <p className="text-error">Failed to load audit logs</p>
        </div>
      ) : isLoading ? (
        <div className="rounded-xl border bg-card p-6">
          <div className="space-y-4">
            {[...Array(5)].map((_, index) => (
              <div key={index} className="h-12 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="rounded-xl border bg-card p-8 text-center">
          <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No audit entries</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            {normalizedSearch ? 'No entries match your search' : 'Audit log is empty'}
          </p>
        </div>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="rounded-xl border bg-card shadow-sm"
        >
          <div className="divide-y">
            {filteredLogs.map((log: AuditEntry) => {
              const Icon = resourceIcons[log.resource.type] || FileText;
              const ActionIcon = actionIcons[log.action] || Settings;
              const colorClass = actionColors[log.action] || 'text-muted-foreground bg-muted';

              return (
                <motion.div
                  key={log.entryId}
                  variants={staggerItemVariants}
                  className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors"
                >
                  <div className={cn('rounded-lg p-2', colorClass)}>
                    <Icon className="h-4 w-4" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <ActionIcon className="h-3 w-3 text-muted-foreground" />
                      <span className="font-medium">{log.action}</span>
                      <span className={cn('rounded-full px-2 py-0.5 text-xs', colorClass)}>
                        {log.resource.type}
                      </span>
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
                          <span
                            key={key}
                            className="rounded bg-muted px-2 py-0.5 text-xs"
                          >
                            {key}: {String(value)}
                          </span>
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
        </motion.div>
      )}

      {/* Pagination */}
      {totalPages > 1 && !normalizedSearch && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className={cn(
              'rounded-lg p-2 hover:bg-muted transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className={cn(
              'rounded-lg p-2 hover:bg-muted transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
