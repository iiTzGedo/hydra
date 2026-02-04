import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Server, Wifi, Cpu, HardDrive, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { useNodes } from '@/api/nodes';
import { ROUTES } from '@/lib/constants';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { NodeSummary, NodeClass } from '@/types/node';

const nodeClassIcons: Record<NodeClass, typeof Server> = {
  compute: Cpu,
  networking: Wifi,
  iot: HardDrive,
};

const nodeClassConfig: Record<NodeClass, { color: string; bg: string; label: string }> = {
  compute: { color: 'text-compute', bg: 'bg-compute/10', label: 'Compute' },
  networking: { color: 'text-network', bg: 'bg-network/10', label: 'Network' },
  iot: { color: 'text-iot', bg: 'bg-iot/10', label: 'IoT' },
};

const statusConfig: Record<
  string,
  { color: string; bg: string; label: string; pulse?: boolean }
> = {
  active: { color: 'text-success', bg: 'bg-success', label: 'Online', pulse: true },
  inactive: { color: 'text-destructive', bg: 'bg-destructive', label: 'Offline' },
  pending: { color: 'text-warning', bg: 'bg-warning', label: 'Warning' },
  archived: { color: 'text-muted-foreground', bg: 'bg-muted-foreground', label: 'Archived' },
};

interface NodeStatusItemProps {
  node: NodeSummary;
  index: number;
}

/**
 * NodeStatusItem - Single node status card
 */
function NodeStatusItem({ node, index }: NodeStatusItemProps) {
  const navigate = useNavigate();
  const Icon = nodeClassIcons[node.class] || Server;
  const classConfig = nodeClassConfig[node.class];
  const status = statusConfig[node.status] || statusConfig.inactive;

  const handleClick = () => {
    navigate(`${ROUTES.NODES}/${node.nodeId}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="link"
      tabIndex={0}
      className={cn(
        'group flex items-center gap-3 rounded-xl border border-border bg-card/60 p-3',
        'transition-all duration-200',
        'hover:bg-muted hover:shadow-sm hover:border-foreground/10',
        'cursor-pointer',
        'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:bg-muted'
      )}
    >
      {/* Icon */}
      <div
        className={cn(
          'rounded-xl p-2.5 transition-transform duration-200 group-hover:scale-110',
          classConfig.bg
        )}
      >
        <Icon className={cn('h-5 w-5', classConfig.color)} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-foreground truncate group-hover:text-primary transition-colors">
            {node.displayName || node.nodeId}
          </p>
          {node.tags && node.tags.length > 0 && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 hidden sm:inline-flex">
              {node.tags[0]}
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground font-mono truncate">{node.nodeId}</p>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-muted">
          <span className={cn('relative flex h-2 w-2', status.pulse && 'status-pulse')}>
            <span className={cn('relative inline-flex rounded-full h-2 w-2', status.bg)} />
            {status.pulse && (
              <span
                className={cn(
                  'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
                  status.bg
                )}
              />
            )}
          </span>
          <span className={cn('text-xs font-medium hidden sm:inline', status.color)}>
            {status.label}
          </span>
        </div>
      </div>
    </motion.div>
  );
}

/**
 * NodeStatusGrid - Dashboard widget showing node status overview
 *
 * Features:
 * - Shows node cards in a responsive grid
 * - "Show more" pagination (increments by 8)
 * - Links to full nodes list
 * - Loading and empty states
 * - Status summary in header
 */
export function NodeStatusGrid() {
  const [limit, setLimit] = useState(8);
  const { data, isLoading, error } = useNodes({ limit });
  const nodes = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasMore = total > limit;

  // Calculate status summary
  const statusSummary = useMemo(() => {
    return nodes.reduce(
      (acc, node) => {
        acc[node.status] = (acc[node.status] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
  }, [nodes]);

  // Handle show more
  const handleShowMore = () => {
    setLimit((prev) => prev + 8);
  };

  // Loading state
  if (isLoading && nodes.length === 0) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {[...Array(8)].map((_, index) => (
          <div key={index} className="h-20 rounded-xl bg-muted animate-pulse" />
        ))}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl bg-muted/60 border border-dashed border-border">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">Failed to load nodes</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl bg-muted/60 border border-dashed border-border">
        <div className="text-center">
          <Server className="h-8 w-8 text-muted-foreground/50 mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No nodes available</p>
          <Link to={ROUTES.NODES}>
            <Button variant="link" size="sm" className="mt-1">
              Register a node
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {nodes.map((node, index) => (
          <NodeStatusItem key={node.nodeId} node={node} index={index} />
        ))}
      </div>

      {/* Show more button */}
      {hasMore && (
        <div className="mt-6 text-center">
          <Button
            variant="outline"
            size="sm"
            onClick={handleShowMore}
            disabled={isLoading}
            className="min-w-[140px]"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading...
              </>
            ) : (
              <>Show more ({total - limit} remaining)</>
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
