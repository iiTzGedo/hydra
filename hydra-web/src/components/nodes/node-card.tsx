import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Server,
  Wifi,
  Cpu,
  MoreHorizontal,
  Eye,
  Edit,
  Archive,
  Clock,
  Tag,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn, formatRelativeTime } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import type { NodeSummary } from '@/types/node';

interface NodeCardProps {
  node: NodeSummary;
  onEdit?: (node: NodeSummary) => void;
  onArchive?: (node: NodeSummary) => void;
}

const nodeClassIcons: Record<string, React.ElementType> = {
  compute: Server,
  networking: Wifi,
  iot: Cpu,
};

const nodeClassConfig: Record<string, { color: string; bg: string; border: string; label: string }> = {
  compute: {
    color: 'text-purple-500',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    label: 'Compute',
  },
  networking: {
    color: 'text-cyan-500',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/20',
    label: 'Networking',
  },
  iot: {
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    label: 'IoT',
  },
};

const statusConfig: Record<string, { color: string; bg: string; label: string; pulse?: boolean }> = {
  active: {
    color: 'text-success',
    bg: 'bg-success',
    label: 'Online',
    pulse: true,
  },
  inactive: {
    color: 'text-destructive',
    bg: 'bg-destructive',
    label: 'Offline',
  },
  pending: {
    color: 'text-warning',
    bg: 'bg-warning',
    label: 'Warning',
  },
  archived: {
    color: 'text-muted-foreground',
    bg: 'bg-muted-foreground',
    label: 'Archived',
  },
};

/**
 * NodeCard - Enhanced card component for displaying node information
 * 
 * Features:
 * - Hover lift animation
 * - Status pulse indicator for active nodes
 * - Quick action dropdown
 * - Visual class-based styling
 * - Tag overflow handling
 */
export function NodeCard({ node, onEdit, onArchive }: NodeCardProps) {
  const NodeIcon = nodeClassIcons[node.class] || Server;
  const classConfig = nodeClassConfig[node.class] || nodeClassConfig.compute;
  const status = statusConfig[node.status] || statusConfig.inactive;

  return (
    <motion.div
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      whileTap={{ scale: 0.98 }}
      className="h-full"
    >
      <Card className="group h-full border-border bg-card overflow-hidden transition-all duration-200 hover:shadow-lg hover:border-foreground/10">
        <Link to={`${ROUTES.NODES}/${node.nodeId}`} className="block h-full">
          <CardContent className="p-5 h-full flex flex-col">
            {/* Main content: left details + right status/actions */}
            <div className="flex flex-1 items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="mb-4">
                  <div
                    className={cn(
                      'h-12 w-12 rounded-xl flex items-center justify-center transition-transform duration-200 group-hover:scale-110',
                      classConfig.bg,
                      classConfig.border,
                      'border'
                    )}
                  >
                    <NodeIcon className={cn('h-6 w-6', classConfig.color)} />
                  </div>
                </div>

                <h3 className="font-semibold text-foreground text-base mb-1 truncate group-hover:text-primary transition-colors">
                  {node.displayName}
                </h3>
                <p className="text-xs text-muted-foreground font-mono truncate mb-4">
                  {node.nodeId}
                </p>

                {/* Meta info */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="secondary"
                      className={cn(
                        'text-[10px] uppercase tracking-wider font-medium',
                        classConfig.bg,
                        classConfig.color,
                        'border-0'
                      )}
                    >
                      {node.type}
                    </Badge>
                    <span className="text-muted-foreground">/</span>
                    <span className="text-xs text-muted-foreground capitalize">
                      {node.kind || 'unknown'}
                    </span>
                  </div>

                  {/* Last profile */}
                  {node.lastProfileAt && (
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>Profiled {formatRelativeTime(node.lastProfileAt)}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex h-full flex-col items-end justify-between gap-3">
                {/* Status indicator */}
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-muted">
                  <span
                    className={cn(
                      'relative flex h-2 w-2',
                      status.pulse && 'status-pulse'
                    )}
                  >
                    <span
                      className={cn(
                        'relative inline-flex rounded-full h-2 w-2',
                        status.bg
                      )}
                    />
                    {status.pulse && (
                      <span
                        className={cn(
                          'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
                          status.bg
                        )}
                      />
                    )}
                  </span>
                  <span className={cn('text-xs font-medium', status.color)}>
                    {status.label}
                  </span>
                </div>

                {/* Actions dropdown */}
                {(onEdit || onArchive) && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild onClick={(e) => e.preventDefault()}>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                      <DropdownMenuItem asChild>
                        <Link to={`${ROUTES.NODES}/${node.nodeId}`}>
                          <Eye className="h-4 w-4 mr-2" />
                          View Details
                        </Link>
                      </DropdownMenuItem>
                      {onEdit && (
                        <DropdownMenuItem onClick={() => onEdit(node)}>
                          <Edit className="h-4 w-4 mr-2" />
                          Edit
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      {onArchive && (
                        <DropdownMenuItem
                          onClick={() => onArchive(node)}
                          className="text-destructive"
                        >
                          <Archive className="h-4 w-4 mr-2" />
                          Archive
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            </div>

            {/* Footer - Tags */}
            {node.tags && node.tags.length > 0 && (
              <div className="mt-4 pt-4 border-t border-border/50">
                <div className="flex flex-wrap gap-1.5">
                  {node.tags.slice(0, 3).map((tag) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className="text-[10px] border-border/60 text-muted-foreground font-normal"
                    >
                      <Tag className="h-2.5 w-2.5 mr-1" />
                      {tag}
                    </Badge>
                  ))}
                  {node.tags.length > 3 && (
                    <Badge
                      variant="outline"
                      className="text-[10px] border-border/60 text-muted-foreground font-normal"
                    >
                      +{node.tags.length - 3}
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Link>
      </Card>
    </motion.div>
  );
}

/**
 * NodeCardCompact - Compact variant for dense lists
 */
export function NodeCardCompact({ node }: { node: NodeSummary }) {
  const NodeIcon = nodeClassIcons[node.class] || Server;
  const classConfig = nodeClassConfig[node.class] || nodeClassConfig.compute;
  const status = statusConfig[node.status] || statusConfig.inactive;

  return (
    <Link to={`${ROUTES.NODES}/${node.nodeId}`}>
      <div className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors group">
        <div className={cn(
          'h-10 w-10 rounded-lg flex items-center justify-center shrink-0',
          classConfig.bg
        )}>
          <NodeIcon className={cn('h-5 w-5', classConfig.color)} />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="font-medium text-sm text-foreground truncate group-hover:text-primary transition-colors">
              {node.displayName}
            </h4>
            <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', status.bg)} />
          </div>
          <p className="text-xs text-muted-foreground font-mono truncate">
            {node.nodeId}
          </p>
        </div>

        <Badge variant="secondary" className="text-[10px] shrink-0">
          {node.type}
        </Badge>
      </div>
    </Link>
  );
}

/**
 * NodeCardSkeleton - Loading skeleton for node cards
 */
export function NodeCardSkeleton() {
  return (
    <Card className="h-full border-border">
      <CardContent className="p-5 h-full">
        <div className="flex items-start justify-between mb-4">
          <div className="h-12 w-12 rounded-xl bg-muted animate-pulse" />
          <div className="h-6 w-16 rounded-full bg-muted animate-pulse" />
        </div>
        <div className="space-y-2">
          <div className="h-5 w-32 bg-muted animate-pulse rounded" />
          <div className="h-3 w-24 bg-muted animate-pulse rounded" />
        </div>
        <div className="mt-4 flex gap-2">
          <div className="h-5 w-16 bg-muted animate-pulse rounded" />
          <div className="h-5 w-20 bg-muted animate-pulse rounded" />
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * NodeCardGridSkeleton - Grid of skeleton cards
 */
export function NodeCardGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <NodeCardSkeleton key={i} />
      ))}
    </div>
  );
}
