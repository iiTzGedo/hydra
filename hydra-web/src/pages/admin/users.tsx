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
import { formatDate } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';

const roleVariants: Record<Role, 'destructive' | 'warning' | 'default' | 'success' | 'secondary'> = {
  admin: 'destructive',
  operator: 'warning',
  viewer: 'default',
  family: 'success',
  agent: 'secondary',
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
        <Button variant="ghost" size="sm" asChild className="mb-6">
          <Link to={ROUTES.ADMIN}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Admin
          </Link>
        </Button>
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-destructive">Failed to load users</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Button variant="ghost" size="sm" asChild className="mb-4">
        <Link to={ROUTES.ADMIN}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Admin
        </Link>
      </Button>

      <PageHeader
        title="User Management"
        description="Manage user accounts and their roles"
      />

      {/* Search */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* User list */}
      {isLoading ? (
        <Card>
          <div className="divide-y">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-48" />
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : !data?.items?.length ? (
        <Card>
          <CardContent className="p-8 text-center">
            <UserCog className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No users found</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {search ? 'Try adjusting your search' : 'No users registered yet'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="mb-4 text-sm text-muted-foreground">
            Showing {data.items.length} of {data.total} users
          </div>

          <motion.div
            variants={staggerContainerVariants}
            initial="hidden"
            animate="visible"
          >
            <Card>
              <div className="divide-y">
                <AnimatePresence mode="popLayout">
                  {data.items.map((user: UserSummary) => (
                    <UserRow key={user.userId} user={user} />
                  ))}
                </AnimatePresence>
              </div>
            </Card>
          </motion.div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">
                Page {page + 1} of {totalPages}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function UserRow({ user }: { user: UserSummary }) {
  const archiveMutation = useArchiveUser();
  const elevateMutation = useElevateRole();

  const RoleIcon = roleIcons[user.role] || Shield;
  const roleLabel = ROLE_LABELS[user.role] || user.role;

  const handleArchive = async () => {
    await archiveMutation.mutateAsync(user.userId);
  };

  const handleElevate = async (newRole: Role) => {
    await elevateMutation.mutateAsync({ userId: user.userId, data: { newRole } });
  };

  return (
    <motion.div
      variants={staggerItemVariants}
      layout
      className="group flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors"
    >
      {/* Avatar */}
      <Avatar>
        <AvatarFallback className="bg-primary text-primary-foreground">
          {user.username?.charAt(0).toUpperCase() || 'U'}
        </AvatarFallback>
      </Avatar>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{user.username}</span>
          <Badge variant={roleVariants[user.role]}>
            {roleLabel}
          </Badge>
          {user.status === 'archived' && (
            <Badge variant="secondary">Archived</Badge>
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
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <MoreVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Change Role</DropdownMenuLabel>
          {(['admin', 'operator', 'viewer', 'family'] as Role[]).map((role) => {
            const Icon = roleIcons[role];
            return (
              <DropdownMenuItem
                key={role}
                onClick={() => handleElevate(role)}
                disabled={user.role === role}
              >
                <Icon className="mr-2 h-4 w-4" />
                {ROLE_LABELS[role]}
              </DropdownMenuItem>
            );
          })}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={handleArchive}
            className="text-destructive focus:text-destructive"
          >
            <Archive className="mr-2 h-4 w-4" />
            Archive User
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </motion.div>
  );
}
