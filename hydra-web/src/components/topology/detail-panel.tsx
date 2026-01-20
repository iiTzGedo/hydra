import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  X,
  Server,
  Network,
  Cpu,
  ExternalLink,
  Clock,
} from 'lucide-react';
import { TopologyNode } from '@/types/topology';
import { ROUTES, NODE_CLASS_COLORS, NODE_KIND_LABELS, STATUS_COLORS } from '@/lib/constants';
import { cn, formatRelativeTime } from '@/lib/utils';
import { slideInVariants } from '@/lib/animations';

interface TopologyDetailPanelProps {
  node: TopologyNode;
  onClose: () => void;
}

const classIcons = {
  compute: Server,
  networking: Network,
  iot: Cpu,
};

export function TopologyDetailPanel({ node, onClose }: TopologyDetailPanelProps) {
  const nodeClass = node.data.class as string | undefined;
  const nodeStatus = node.data.status as string | undefined;
  const nodeKind = node.data.kind as string | undefined;

  const Icon = classIcons[nodeClass as keyof typeof classIcons] || Server;
  const colors = NODE_CLASS_COLORS[nodeClass as keyof typeof NODE_CLASS_COLORS];
  const statusColors = STATUS_COLORS[nodeStatus as keyof typeof STATUS_COLORS] || STATUS_COLORS.inactive;
  const kindLabel = NODE_KIND_LABELS[nodeKind as keyof typeof NODE_KIND_LABELS] || nodeKind;

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      exit="hidden"
      variants={slideInVariants}
      className="absolute right-4 top-4 w-80 rounded-xl border bg-card shadow-xl overflow-hidden"
    >
      <div className={cn('flex items-center justify-between p-4', colors?.bg || 'bg-muted')}>
        <div className="flex items-center gap-3">
          <Icon className="h-6 w-6 text-white" />
          <div>
            <h3 className="font-semibold text-white">{node.id}</h3>
            <p className="text-xs text-white/80 capitalize">{nodeClass}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1 text-white/80 hover:text-white hover:bg-white/20 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Status</span>
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
              statusColors.bg + '/10',
              statusColors.text
            )}
          >
            <span className={cn('h-1.5 w-1.5 rounded-full', statusColors.dot)} />
            {nodeStatus}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-xs text-muted-foreground">Type</span>
            <div className="font-medium capitalize">{node.type}</div>
          </div>
          <div>
            <span className="text-xs text-muted-foreground">Kind</span>
            <div className="font-medium">{kindLabel}</div>
          </div>
        </div>

        {node.data.lastProfileAt && (
          <div className="flex items-center gap-2 text-sm">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Last profiled:</span>
            <span>{formatRelativeTime(new Date(node.data.lastProfileAt as string))}</span>
          </div>
        )}
      </div>

      <div className="border-t p-4">
        <Link
          to={ROUTES.NODES + '/' + node.id}
          className={cn(
            'flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
            'hover:bg-primary/90 transition-colors w-full'
          )}
        >
          View Details
          <ExternalLink className="h-4 w-4" />
        </Link>
      </div>
    </motion.div>
  );
}
