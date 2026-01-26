import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FolderTree,
  MoreVertical,
  Eye,
  Edit,
  Trash2,
  Users,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useGroups } from '@/api/groups';
import { GroupSummary } from '@/types/group';
import { GroupFilterState } from './group-filters';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

interface GroupListProps {
  filters: GroupFilterState;
}

export function GroupList({ filters }: GroupListProps) {
  const [page, setPage] = useState(0);
  const limit = 20;

  const queryFilters = useMemo(() => {
    const f: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) f.search = filters.search;
    return f;
  }, [filters, page]);

  const { data, isLoading, error } = useGroups(queryFilters);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  if (error) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center">
        <p className="text-error">Failed to load groups</p>
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
        <FolderTree className="mx-auto h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">No groups found</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          {filters.search
            ? 'Try adjusting your search'
            : 'Create your first group to organize infrastructure'}
        </p>
        <Link
          to={ROUTES.GROUP_NEW}
          className={cn(
            'mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
            'hover:bg-primary/90 transition-colors'
          )}
        >
          Create Group
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing {data.items.length} of {data.total} groups
        </span>
      </div>

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
      >
        <AnimatePresence mode="popLayout">
          {data.items.map((group) => (
            <GroupCard key={group.id} group={group} />
          ))}
        </AnimatePresence>
      </motion.div>

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

type GroupListItem = GroupSummary & { id: string };

function GroupCard({ group }: { group: GroupListItem }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const typeLabel = group.types.length
    ? group.types.map((type) => (type === 'node' ? 'Nodes' : 'Services')).join(', ')
    : '—';

  return (
    <motion.div
      variants={staggerItemVariants}
      layout
      className="group relative rounded-xl border bg-card p-5 shadow-sm hover:border-primary/50 transition-colors"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="rounded-lg bg-iot p-2.5">
          <FolderTree className="h-5 w-5 text-white" />
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
                  to={ROUTES.GROUPS + '/' + group.id}
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

      <Link to={ROUTES.GROUPS + '/' + group.id}>
        <h3 className="font-semibold hover:text-primary transition-colors mb-2">
          {group.name}
        </h3>

        {group.description && (
          <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
            {group.description}
          </p>
        )}

        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Types</span>
            <span className="font-medium">{typeLabel}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Created</span>
            <span>{group.createdAt ? formatDate(new Date(group.createdAt)) : '—'}</span>
          </div>
        </div>
      </Link>

      {group.memberCount && group.memberCount.nodes + group.memberCount.services > 0 && (
        <div className="mt-4 pt-4 border-t">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Users className="h-4 w-4" />
            <span>{group.memberCount.nodes + group.memberCount.services} members</span>
          </div>
        </div>
      )}

    </motion.div>
  );
}
