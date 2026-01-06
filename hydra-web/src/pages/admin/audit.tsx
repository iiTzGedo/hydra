import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  FileText,
  Search,
  Filter,
  User,
  Server,
  Boxes,
  Network,
  FolderTree,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

// Mock audit log data - in a real app, this would come from an API
const mockAuditLogs = [
  {
    id: '1',
    timestamp: new Date(Date.now() - 5 * 60 * 1000),
    action: 'node.profile.created',
    actor: 'agent:proxmox-01',
    resource: 'profile:prof_123',
    details: { version: 'E0-0.1.2.3' },
  },
  {
    id: '2',
    timestamp: new Date(Date.now() - 15 * 60 * 1000),
    action: 'user.login',
    actor: 'user:admin',
    resource: 'session:sess_456',
    details: { ip: '192.168.1.100' },
  },
  {
    id: '3',
    timestamp: new Date(Date.now() - 30 * 60 * 1000),
    action: 'service.discovered',
    actor: 'system',
    resource: 'service:svc-nginx-e5f6',
    details: { node: 'docker-host-01' },
  },
  {
    id: '4',
    timestamp: new Date(Date.now() - 45 * 60 * 1000),
    action: 'topology.generated',
    actor: 'system',
    resource: 'topology:topo_789',
    details: { nodes: 12, edges: 24 },
  },
  {
    id: '5',
    timestamp: new Date(Date.now() - 60 * 60 * 1000),
    action: 'group.created',
    actor: 'user:admin',
    resource: 'group:production-servers',
    details: { selectors: 2 },
  },
  {
    id: '6',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
    action: 'user.approved',
    actor: 'user:admin',
    resource: 'user:john.doe',
    details: { role: 'viewer' },
  },
  {
    id: '7',
    timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000),
    action: 'network.discovered',
    actor: 'system',
    resource: 'network:192.168.1.0/24',
    details: { type: 'L3' },
  },
  {
    id: '8',
    timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000),
    action: 'node.registered',
    actor: 'token:reg_abc123',
    resource: 'node:docker-host-02',
    details: { class: 'compute', kind: 'docker' },
  },
];

const actionIcons: Record<string, typeof User> = {
  user: User,
  node: Server,
  service: Boxes,
  network: Network,
  group: FolderTree,
  topology: Settings,
  system: Settings,
};

const actionColors: Record<string, string> = {
  created: 'text-success bg-success/10',
  updated: 'text-primary bg-primary/10',
  deleted: 'text-error bg-error/10',
  login: 'text-primary bg-primary/10',
  logout: 'text-muted-foreground bg-muted',
  approved: 'text-success bg-success/10',
  rejected: 'text-error bg-error/10',
  registered: 'text-success bg-success/10',
  discovered: 'text-networking bg-networking/10',
  generated: 'text-compute bg-compute/10',
};

export default function AuditPage() {
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const filteredLogs = mockAuditLogs.filter((log) => {
    if (search && !log.action.includes(search) && !log.resource.includes(search)) {
      return false;
    }
    if (filterAction && !log.action.startsWith(filterAction)) {
      return false;
    }
    return true;
  });

  const limit = 10;
  const totalPages = Math.ceil(filteredLogs.length / limit);
  const paginatedLogs = filteredLogs.slice(page * limit, (page + 1) * limit);

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
      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="rounded-xl border bg-card shadow-sm"
      >
        <div className="divide-y">
          {paginatedLogs.map((log) => {
            const [category, action] = log.action.split('.');
            const Icon = actionIcons[category] || FileText;
            const colorClass = actionColors[action] || 'text-muted-foreground bg-muted';

            return (
              <motion.div
                key={log.id}
                variants={staggerItemVariants}
                className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors"
              >
                <div className={cn('rounded-lg p-2', colorClass)}>
                  <Icon className="h-4 w-4" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium">{log.action}</span>
                    <span className={cn('rounded-full px-2 py-0.5 text-xs', colorClass)}>
                      {action}
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    <span className="font-mono">{log.resource}</span>
                    <span className="mx-2">by</span>
                    <span>{log.actor}</span>
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

      {/* Pagination */}
      {totalPages > 1 && (
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
