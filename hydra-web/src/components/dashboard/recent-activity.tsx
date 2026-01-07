import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  Server,
  Boxes,
  Network,
  RefreshCw,
  Plus,
  Trash2,
  Edit,
  LogIn,
  LogOut,
  UserPlus,
  Zap,
  FolderTree,
  ArrowRight,
} from 'lucide-react';
import { cn, formatRelativeTime } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { useAuditLog } from '@/api/query';
import type { AuditEntry, AuditAction } from '@/types/query';

const typeIcons: Record<string, typeof Server> = {
  node: Server,
  service: Boxes,
  network: Network,
  profile: RefreshCw,
  group: FolderTree,
  topology: RefreshCw,
};

const actionIcons: Record<AuditAction, typeof Plus> = {
  create: Plus,
  update: Edit,
  delete: Trash2,
  login: LogIn,
  logout: LogOut,
  register: UserPlus,
  execute: Zap,
};

const typeColors: Record<string, string> = {
  node: 'text-compute bg-compute/10',
  service: 'text-hydra-blue bg-hydra-blue/10',
  network: 'text-networking bg-networking/10',
  profile: 'text-success bg-success/10',
  group: 'text-warning bg-warning/10',
  topology: 'text-muted-foreground bg-muted',
};

function toActivity(entry: AuditEntry) {
  return {
    id: entry.entryId,
    type: entry.resource.type,
    action: entry.action,
    entityName: entry.resource.id,
    timestamp: entry.timestamp,
  };
}

export function RecentActivity() {
  const { data, isLoading } = useAuditLog({ limit: 5, offset: 0 });
  const activity = data?.items?.map(toActivity) ?? [];

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold">Recent Activity</h3>
        <Link
          to={ROUTES.ADMIN + '/audit'}
          className="flex items-center gap-1 text-sm text-primary hover:underline"
        >
          View all
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, index) => (
            <div key={index} className="h-12 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      ) : activity.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-lg bg-muted/50">
          <p className="text-sm text-muted-foreground">No recent activity available</p>
        </div>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-3"
        >
          {activity.map((item) => {
            const TypeIcon = typeIcons[item.type] || RefreshCw;
            const ActionIcon = actionIcons[item.action] || RefreshCw;

            return (
              <motion.div
                key={item.id}
                variants={staggerItemVariants}
                className="flex items-center gap-3 rounded-lg p-2 hover:bg-muted/50 transition-colors"
              >
                <div className={cn('rounded-lg p-2', typeColors[item.type] || 'bg-muted')}>
                  <TypeIcon className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <ActionIcon className="h-3 w-3 text-muted-foreground" />
                    <span className="font-medium truncate">{item.entityName}</span>
                  </div>
                  <p className="text-xs text-muted-foreground capitalize">
                    {item.type} {item.action}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {formatRelativeTime(item.timestamp)}
                </span>
              </motion.div>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}
