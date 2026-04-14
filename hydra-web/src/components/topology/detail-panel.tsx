import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  X,
  Server,
  Network,
  Cpu,
  ExternalLink,
  Clock,
  Boxes,
} from 'lucide-react';
import { TopologyNode } from '@/types/topology';
import { ROUTES, NODE_CLASS_COLORS, NODE_KIND_LABELS, STATUS_COLORS } from '@/lib/constants';
import { cn, formatRelativeTime } from '@/lib/utils';
import { slideInVariants } from '@/lib/animations';
import { useTopologySubgraph } from '@/api/topologies';
import { Skeleton } from '@/components/ui/skeleton';

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
  const nodeId = node.data.nodeId as string | undefined;

  // Fetch subgraph data for this node
  const { data: subgraph, isLoading: subgraphLoading } = useTopologySubgraph(nodeId);

  const Icon = classIcons[nodeClass as keyof typeof classIcons] || Server;
  const colors = NODE_CLASS_COLORS[nodeClass as keyof typeof NODE_CLASS_COLORS];
  const statusColors = STATUS_COLORS[nodeStatus as keyof typeof STATUS_COLORS] || STATUS_COLORS.inactive;
  const kindLabel = NODE_KIND_LABELS[nodeKind as keyof typeof NODE_KIND_LABELS] || nodeKind;

  // Extract services and networks from subgraph
  const connectedServices = subgraph?.graph?.nodes?.filter(n => n.data?.serviceId) || [];
  const connectedNetworks = subgraph?.graph?.nodes?.filter(n => n.data?.networkId) || [];

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
            <h3 className="font-semibold text-white truncate max-w-[200px]">{node.id}</h3>
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

        {!!node.data.lastProfileAt && (
          <div className="flex items-center gap-2 text-sm">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Last profiled:</span>
            <span>{formatRelativeTime(new Date(node.data.lastProfileAt as string))}</span>
          </div>
        )}

        {/* Subgraph data: Connected services and networks */}
        {subgraphLoading ? (
          <div className="space-y-2 pt-2 border-t">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : (
          <>
            {connectedServices.length > 0 && (
              <div className="pt-2 border-t">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <Boxes className="h-4 w-4" />
                  <span>Services ({connectedServices.length})</span>
                </div>
                <div className="space-y-1 max-h-24 overflow-y-auto">
                  {connectedServices.slice(0, 5).map((service) => (
                    <Link
                      key={service.id}
                      href={`${ROUTES.SERVICES}/${service.data?.serviceId}`}
                      className="block px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80 truncate"
                    >
                      {service.label || service.data?.serviceId}
                    </Link>
                  ))}
                  {connectedServices.length > 5 && (
                    <div className="text-xs text-muted-foreground px-2">
                      +{connectedServices.length - 5} more
                    </div>
                  )}
                </div>
              </div>
            )}

            {connectedNetworks.length > 0 && (
              <div className="pt-2 border-t">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <Network className="h-4 w-4" />
                  <span>Networks ({connectedNetworks.length})</span>
                </div>
                <div className="space-y-1 max-h-24 overflow-y-auto">
                  {connectedNetworks.slice(0, 5).map((network) => (
                    <Link
                      key={network.id}
                      href={`${ROUTES.NETWORKS}/${network.data?.networkId}`}
                      className="block px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80 truncate"
                    >
                      {network.label || network.data?.networkId}
                    </Link>
                  ))}
                  {connectedNetworks.length > 5 && (
                    <div className="text-xs text-muted-foreground px-2">
                      +{connectedNetworks.length - 5} more
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="border-t p-4">
        <Link
          href={ROUTES.NODES + '/' + node.id}
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
