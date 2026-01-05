import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  Search,
  MoreVertical,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Archive,
  UserCog,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useUsers, useArchiveUser, useElevateRole } from '@/api/users';
import type { UserSummary, Role } from '@/types/user';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, ROLE_LABELS } from '@/lib/constants';
import { cn, formatDate } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

const roleColors: Record<Role, string> = {
  admin: 'bg-error/10 text-error',
  operator: 'bg-warning/10 text-warning',
  viewer: 'bg-primary/10 text-primary',
  family: 'bg-success/10 text-success',
  agent: 'bg-muted text-muted-foreground',
};

const roleIcons: Record<Role, typeof Shield> = {
  admin: ShieldAlert,
  operator: ShieldCheck,
  viewer: Shield,
  family: Shield,
  agent: Shield,
};

export default function UsersPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading, error } = useUsers({
    limit,
    offset: page * limit,
    search: search || undefined,
  });

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  if (error) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.ADMIN}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Admin
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <p className="text-error">Failed to load users</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Link
        to={ROUTES.ADMIN}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Admin
      </Link>

      <PageHeader
        title="User Management"
        description="Manage user accounts and their roles"
      />

      {/* Search */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={cn(
              'w-full rounded-lg border bg-background pl-10 pr-4 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring',
              'placeholder:text-muted-foreground'
            )}
          />
        </div>
      </div>

      {/* User list */}
      {isLoading ? (
        <div className="rounded-xl border bg-card shadow-sm">
          <div className="divide-y">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4">
                <div className="h-10 w-10 animate-pulse rounded-full bg-muted" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-32 animate-pulse rounded bg-muted" />
                  <div className="h-3 w-48 animate-pulse rounded bg-muted" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : !data?.items?.length ? (
        <div className="rounded-xl border bg-card p-8 text-center">
          <UserCog className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No users found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            {search ? 'Try adjusting your search' : 'No users registered yet'}
          </p>
        </div>
      ) : (
        <>
          <div className="mb-4 text-sm text-muted-foreground">
            Showing {data.items.length} of {data.total} users
          </div>

          <motion.div
            variants={staggerContainerVariants}
            initial="hidden"
            animate="visible"
            className="rounded-xl border bg-card shadow-sm"
          >
            <div className="divide-y">
              <AnimatePresence mode="popLayout">
                {data.items.map((user: UserSummary) => (
                  <UserRow key={user.userId} user={user} />
                ))}
              </AnimatePresence>
            </div>
          </motion.div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
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
        </>
      )}
    </div>
  );
}

function UserRow({ user }: { user: UserSummary }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const archiveMutation = useArchiveUser();
  const elevateMutation = useElevateRole();

  const RoleIcon = roleIcons[user.role] || Shield;
  const roleLabel = ROLE_LABELS[user.role] || user.role;

  const handleArchive = async () => {
    setMenuOpen(false);
    await archiveMutation.mutateAsync(user.userId);
  };

  const handleElevate = async (newRole: Role) => {
    setMenuOpen(false);
    await elevateMutation.mutateAsync({ userId: user.userId, data: { newRole } });
  };

  return (
    <motion.div
      variants={staggerItemVariants}
      layout
      className="group flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors"
    >
      {/* Avatar */}
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground font-medium">
        {user.username?.charAt(0).toUpperCase() || 'U'}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{user.username}</span>
          <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', roleColors[user.role])}>
            {roleLabel}
          </span>
          {user.status === 'archived' && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              Archived
            </span>
          )}
        </div>
        <div className="mt-1 text-sm text-muted-foreground truncate">
          {user.email}
        </div>
      </div>

      {/* Created date */}
      <div className="hidden md:block text-right text-sm text-muted-foreground">
        {formatDate(new Date(user.createdAt))}
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
            <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
            <div className="absolute right-0 top-full z-50 mt-1 w-48 rounded-lg border bg-popover p-1 shadow-lg">
              <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                Change Role
              </div>
              {(['admin', 'operator', 'viewer', 'family'] as Role[]).map((role) => (
                <button
                  key={role}
                  onClick={() => handleElevate(role)}
                  disabled={user.role === role}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  <RoleIcon className="h-4 w-4" />
                  {ROLE_LABELS[role]}
                </button>
              ))}
              <div className="my-1 border-t" />
              <button
                onClick={handleArchive}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-error hover:bg-error/10"
              >
                <Archive className="h-4 w-4" />
                Archive User
              </button>
            </div>
          </>
        )}
      </div>
    </motion.div>
  );
}
