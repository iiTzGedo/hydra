import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Server, Network, Cpu, Clock, Tag, Box } from 'lucide-react';
import { NodeSummary } from '@/types/node';
import { ROUTES, NODE_CLASS_COLORS, NODE_KIND_LABELS, STATUS_COLORS } from '@/lib/constants';
import { cn, formatRelativeTime } from '@/lib/utils';
import { staggerItemVariants } from '@/lib/animations';

type NodeListItem = NodeSummary & { id: string };

interface NodeCardProps {
  node: NodeListItem;
}

const classIcons = {
  compute: Server,
  networking: Network,
  iot: Cpu,
};

export function NodeCard({ node }: NodeCardProps) {
  const Icon = classIcons[node.class] || Server;
  const colors = NODE_CLASS_COLORS[node.class];
  const statusColors = STATUS_COLORS[node.status] || STATUS_COLORS.inactive;
  const kindLabel = NODE_KIND_LABELS[node.kind as keyof typeof NODE_KIND_LABELS] || node.kind;

  return (
    <motion.div variants={staggerItemVariants} layout>
      <Link
        to={ROUTES.NODES + '/' + node.id}
        className={cn(
          'block rounded-xl border bg-card p-4 shadow-sm',
          'hover:shadow-md hover:border-primary/50 transition-all'
        )}
      >
        <div className="flex items-start gap-3">
          <div className={cn('rounded-lg p-2.5 shrink-0', colors?.bg || 'bg-muted')}>
            <Icon className="h-5 w-5 text-white" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-medium truncate">{node.displayName || node.id}</h3>
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium shrink-0',
                  statusColors.bg + '/10',
                  statusColors.text
                )}
              >
                <span className={cn('h-1.5 w-1.5 rounded-full', statusColors.dot)} />
                {node.status}
              </span>
            </div>
            <p className="text-xs text-muted-foreground truncate mt-0.5 font-mono">
              {node.id}
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Box className="h-3.5 w-3.5" />
            <span className="capitalize">{node.class}</span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Server className="h-3.5 w-3.5" />
            <span>{kindLabel}</span>
          </div>
        </div>

        {node.tags && node.tags.length > 0 && (
          <div className="mt-3 flex items-center gap-1.5">
            <Tag className="h-3 w-3 text-muted-foreground shrink-0" />
            <div className="flex flex-wrap gap-1">
              {node.tags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="px-1.5 py-0.5 bg-muted rounded text-xs text-muted-foreground"
                >
                  {tag}
                </span>
              ))}
              {node.tags.length > 3 && (
                <span className="px-1.5 py-0.5 text-xs text-muted-foreground">
                  +{node.tags.length - 3}
                </span>
              )}
            </div>
          </div>
        )}

        <div className="mt-4 pt-3 border-t flex items-center justify-between text-xs text-muted-foreground">
          {node.lastProfileAt ? (
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span>{formatRelativeTime(new Date(node.lastProfileAt))}</span>
            </div>
          ) : (
            <span>No profiles yet</span>
          )}
        </div>
      </Link>
    </motion.div>
  );
}
