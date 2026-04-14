import { useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Clock,
  ArrowRight,
  Server,
  Boxes,
  Network,
  FolderTree,
  User,
  Settings,
  Shield,
  Plus,
  Edit,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { formatRelativeTime } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useAuditLog } from '@/api/query';
import { useDashboardStore } from '@/stores/dashboard-store';
import type { AuditEntry } from '@/types/query';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// Resource type to icon mapping
const resourceIcons: Record<string, React.ElementType> = {
  node: Server,
  service: Boxes,
  network: Network,
  group: FolderTree,
  user: User,
  setting: Settings,
  permission: Shield,
};

// Resource type to route mapping
const resourceRoutes: Record<string, string> = {
  node: ROUTES.NODES,
  service: ROUTES.SERVICES,
  network: ROUTES.NETWORKS,
  group: ROUTES.GROUPS,
  user: ROUTES.SETTINGS, // Users managed in settings
};

// Action to icon and color mapping
const actionConfig: Record<
  string,
  { icon: React.ElementType; color: string; bg: string; label: string }
> = {
  create: { icon: Plus, color: 'text-success', bg: 'bg-success/10', label: 'Created' },
  update: { icon: Edit, color: 'text-info', bg: 'bg-info/10', label: 'Updated' },
  delete: { icon: Trash2, color: 'text-destructive', bg: 'bg-destructive/10', label: 'Deleted' },
  sync: { icon: RefreshCw, color: 'text-warning', bg: 'bg-warning/10', label: 'Synced' },
};

interface ActivityItemProps {
  entry: AuditEntry;
  index: number;
}

/**
 * ActivityItem - Single activity entry
 *
 * Features:
 * - Click to navigate to related entity
 * - Visual indicators for action type
 * - Resource type badge
 * - Timestamp
 * - Actor information
 */
function ActivityItem({ entry, index }: ActivityItemProps) {
  const router = useRouter();
  const ResourceIcon = resourceIcons[entry.resource.type] || Server;
  const action =
    actionConfig[entry.action] || {
      icon: Edit,
      color: 'text-muted-foreground',
      bg: 'bg-muted',
      label: entry.action,
    };
  const ActionIcon = action.icon;

  // Handle click - navigate to related entity
  const handleClick = useCallback(() => {
    const baseRoute = resourceRoutes[entry.resource.type];
    if (baseRoute) {
      router.push(`${baseRoute}/${entry.resource.id}`);
    }
  }, [router, entry.resource.type, entry.resource.id]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleClick();
      }
    },
    [handleClick]
  );

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="link"
      tabIndex={0}
      className={cn(
        'group flex gap-3 p-3 rounded-xl transition-colors cursor-pointer',
        'hover:bg-muted/60',
        'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:bg-muted/60'
      )}
      aria-label={`${action.label} ${entry.resource.type}: ${entry.resource.id}`}
    >
      {/* Action Icon */}
      <div
        className={cn(
          'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl',
          action.bg
        )}
      >
        <ActionIcon className={cn('h-5 w-5', action.color)} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-foreground capitalize">
            {action.label} {entry.resource.type}
          </p>
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 hidden sm:inline-flex">
            <ResourceIcon className="h-3 w-3 mr-1" />
            {entry.resource.type}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground font-mono truncate">
          {entry.resource.id}
        </p>
        <div className="flex items-center gap-2 text-xs text-muted-foreground/70">
          <Clock className="h-3 w-3" />
          <span>{formatRelativeTime(entry.timestamp)}</span>
          {entry.actor?.id && entry.actor.type === 'user' && (
            <>
              <span>•</span>
              <span className="font-mono">{entry.actor.id}</span>
            </>
          )}
        </div>
      </div>

      {/* Arrow indicator on hover */}
      <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity self-center shrink-0" />
    </motion.div>
  );
}

/**
 * RecentActivity - Dashboard widget showing recent audit log entries
 *
 * Features:
 * - Click any activity to navigate to the related entity
 * - Shows latest 10 events
 * - Links to full audit log in settings
 * - Loading and empty states
 */
export function RecentActivity() {
  const timeRange = useDashboardStore((s) => s.timeRange);
  const customTimeRange = useDashboardStore((s) => s.customTimeRange);

  const { since, until } = useMemo(() => {
    const now = new Date();
    let from: Date;
    let to: Date = now;

    switch (timeRange) {
      case 'last1h':
        from = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case 'last7d':
        from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case 'last30d':
        from = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case 'custom':
        if (customTimeRange) {
          from = customTimeRange.from;
          to = customTimeRange.to;
        } else {
          from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        }
        break;
      case 'last24h':
      default:
        from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
    }

    return { since: from.toISOString(), until: to.toISOString() };
  }, [timeRange, customTimeRange]);

  const { data, isLoading, error } = useAuditLog({
    limit: 10,
    offset: 0,
    since,
    until,
  });
  const activities = data?.items ?? [];

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, index) => (
          <div key={index} className="flex gap-3">
            <div className="h-10 w-10 rounded-xl bg-muted animate-pulse shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-48 items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">Failed to load activity</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
        <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-muted mb-3">
          <Clock className="h-7 w-7 text-muted-foreground/50" />
        </div>
        <h4 className="text-base font-medium text-foreground mb-1">No recent activity</h4>
        <p className="text-sm text-muted-foreground/70 max-w-[200px]">
          Events will appear here when changes occur
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-1 py-2">
      {activities.map((entry, index) => (
        <ActivityItem key={entry.entryId} entry={entry} index={index} />
      ))}
    </div>
  );
}
