import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Network,
  MoreVertical,
  Eye,
  Edit,
  Trash2,
  Server,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useNetworks } from '@/api/networks';
import { NetworkSummary } from '@/types/network';
import { NetworkFilterState } from './network-filters';
import { ROUTES, NETWORK_TYPE_LABELS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

interface NetworkListProps {
  filters: NetworkFilterState;
}

export function NetworkList({ filters }: NetworkListProps) {
  const [page, setPage] = useState(0);
  const limit = 20;

  const queryFilters = useMemo(() => {
    const f: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) f.search = filters.search;
    if (filters.type) f.type = filters.type;
    return f;
  }, [filters, page]);

  const { data, isLoading, error } = useNetworks(queryFilters);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  if (error) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center">
        <p className="text-error">Failed to load networks</p>
        <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-40 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    );
  }

  if (!data?.items?.length) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center">
        <Network className="mx-auto h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">No networks found</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          {filters.search || filters.type
            ? 'Try adjusting your filters'
            : 'Networks will be auto-discovered from node profiles'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results count */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing {data.items.length} of {data.total} networks
        </span>
      </div>

      {/* Network grid */}
      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
      >
        <AnimatePresence mode="popLayout">
          {data.items.map((network) => (
            <NetworkCard key={network.id} network={network} />
          ))}
        </AnimatePresence>
      </motion.div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
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

type NetworkListItem = NetworkSummary & { id: string };

function NetworkCard({ network }: { network: NetworkListItem }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const typeLabel = NETWORK_TYPE_LABELS[network.type] || network.type;

  return (
    <motion.div
      variants={staggerItemVariants}
      layout
      className="group relative rounded-xl border bg-card p-5 shadow-sm hover:border-primary/50 transition-colors"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="rounded-lg bg-networking p-2.5">
          <Network className="h-5 w-5 text-white" />
        </div>

        <div className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="rounded-lg p-1.5 hover:bg-muted transition-colors opacity-0 group-hover:opacity-100"
          >
            <MoreVertical className="h-4 w-4" />
          </button>

          {menuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setMenuOpen(false)}
              />
              <div className="absolute right-0 top-full z-50 mt-1 w-36 rounded-lg border bg-popover p-1 shadow-lg">
                <Link
                  to={ROUTES.NETWORKS + '/' + network.id}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => setMenuOpen(false)}
                >
                  <Eye className="h-4 w-4" />
                  View
                </Link>
                <button
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => setMenuOpen(false)}
                >
                  <Edit className="h-4 w-4" />
                  Edit
                </button>
                <div className="my-1 border-t" />
                <button
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-error hover:bg-error/10"
                  onClick={() => setMenuOpen(false)}
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <Link to={ROUTES.NETWORKS + '/' + network.id}>
        <h3 className="font-semibold hover:text-primary transition-colors mb-2">
          {network.name || network.cidr || 'Unnamed network'}
        </h3>

        <div className="space-y-2 text-sm">
          {network.cidr && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">CIDR</span>
              <span className="font-mono">{network.cidr}</span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Type</span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{typeLabel}</span>
          </div>
          {network.vlanId && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">VLAN ID</span>
              <span className="font-mono">{network.vlanId}</span>
            </div>
          )}
          {network.gatewayV4 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Gateway v4</span>
              <span className="font-mono">{network.gatewayV4}</span>
            </div>
          )}
          {network.gatewayV6 && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Gateway v6</span>
              <span className="font-mono">{network.gatewayV6}</span>
            </div>
          )}
        </div>
      </Link>

      {/* Node count */}
      {network.nodeCount !== undefined && network.nodeCount > 0 && (
        <div className="mt-4 pt-4 border-t">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Server className="h-4 w-4" />
            <span>{network.nodeCount} nodes</span>
          </div>
        </div>
      )}
    </motion.div>
  );
}
