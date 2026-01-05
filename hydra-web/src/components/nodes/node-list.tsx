import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Server,
  Network,
  Cpu,
  MoreVertical,
  Eye,
  Edit,
  Archive,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useNodes } from '@/api/nodes';
import { NodeSummary } from '@/types/node';
import { NodeFilterState } from './node-filters';
import { ROUTES, NODE_CLASS_COLORS, NODE_KIND_LABELS, STATUS_COLORS } from '@/lib/constants';
import { cn, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

// Extended type with id alias (matching what the API returns)
type NodeListItem = NodeSummary & { id: string; profileVersion?: string };

interface NodeListProps {
  filters: NodeFilterState;
}

const classIcons = {
  compute: Server,
  networking: Network,
  iot: Cpu,
};

export function NodeList({ filters }: NodeListProps) {
  const [page, setPage] = useState(0);
  const limit = 20;

  const queryFilters = useMemo(() => {
    const f: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) f.search = filters.search;
    if (filters.class) f.class = filters.class;
    if (filters.type) f.type = filters.type;
    if (filters.kind) f.kind = filters.kind;
    if (filters.status) f.status = filters.status;
    return f;
  }, [filters, page]);

  const { data, isLoading, error } = useNodes(queryFilters);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  if (error) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center">
        <p className="text-error">Failed to load nodes</p>
        <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="rounded-xl border bg-card shadow-sm">
        <div className="divide-y">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 p-4">
              <div className="h-10 w-10 animate-pulse rounded-lg bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-32 animate-pulse rounded bg-muted" />
                <div className="h-3 w-48 animate-pulse rounded bg-muted" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!data?.items?.length) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center">
        <Server className="mx-auto h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">No nodes found</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          {filters.search || filters.class || filters.type || filters.kind || filters.status
            ? 'Try adjusting your filters'
            : 'Register your first node to get started'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results count */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing {data.items.length} of {data.total} nodes
        </span>
      </div>

      {/* Node list */}
      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="rounded-xl border bg-card shadow-sm"
      >
        <div className="divide-y">
          <AnimatePresence mode="popLayout">
            {data.items.map((node) => (
              <NodeRow key={node.id} node={node} />
            ))}
          </AnimatePresence>
        </div>
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

function NodeRow({ node }: { node: NodeListItem }) {
  const [menuOpen, setMenuOpen] = useState(false);

  const Icon = classIcons[node.class] || Server;
  const colors = NODE_CLASS_COLORS[node.class];
  const statusColors = STATUS_COLORS[node.status] || STATUS_COLORS.inactive;
  const kindLabel = NODE_KIND_LABELS[node.kind as keyof typeof NODE_KIND_LABELS] || node.kind;

  return (
    <motion.div
      variants={staggerItemVariants}
      layout
      className="group flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors"
    >
      {/* Icon */}
      <div className={cn('rounded-lg p-2.5', colors?.bg || 'bg-muted')}>
        <Icon className="h-5 w-5 text-white" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link
            to={ROUTES.NODES + '/' + node.id}
            className="font-medium hover:text-primary transition-colors truncate"
          >
            {node.id}
          </Link>
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
              statusColors.bg + '/10',
              statusColors.text
            )}
          >
            <span className={cn('h-1.5 w-1.5 rounded-full', statusColors.dot)} />
            {node.status}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
          <span className="capitalize">{node.class}</span>
          <span>•</span>
          <span>{kindLabel}</span>
          {node.tags && node.tags.length > 0 && (
            <>
              <span>•</span>
              <span className="truncate">{node.tags.slice(0, 3).join(', ')}</span>
            </>
          )}
        </div>
      </div>

      {/* Profile info */}
      <div className="hidden md:block text-right">
        {node.profileVersion && (
          <div className="text-sm font-mono">{node.profileVersion}</div>
        )}
        {node.lastProfileAt && (
          <div className="text-xs text-muted-foreground">
            {formatRelativeTime(new Date(node.lastProfileAt))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="relative">
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="rounded-lg p-2 hover:bg-muted transition-colors opacity-0 group-hover:opacity-100"
        >
          <MoreVertical className="h-4 w-4" />
        </button>

        {menuOpen && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setMenuOpen(false)}
            />
            <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-lg border bg-popover p-1 shadow-lg">
              <Link
                to={ROUTES.NODES + '/' + node.id}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                onClick={() => setMenuOpen(false)}
              >
                <Eye className="h-4 w-4" />
                View Details
              </Link>
              <Link
                to={ROUTES.NODES + '/' + node.id + '/profiles'}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                onClick={() => setMenuOpen(false)}
              >
                <RefreshCw className="h-4 w-4" />
                View Profiles
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
                <Archive className="h-4 w-4" />
                Archive
              </button>
            </div>
          </>
        )}
      </div>
    </motion.div>
  );
}
