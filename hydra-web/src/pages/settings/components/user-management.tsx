import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, MoreVertical, Archive, UserCog } from 'lucide-react';
import { useUsers, useArchiveUser, useElevateRole } from '@/api/users';
import type { UserSummary, Role } from '@/types/user';
import { ROLE_LABELS } from '@/lib/constants';
import { formatDate } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { Pagination } from '@/components/ui/pagination';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { roleVariants, roleIcons } from '../constants';

export function UserManagement() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const limit = 10;

  const { data, isLoading, error } = useUsers({
    limit,
    offset: page * limit,
    search: search || undefined,
  });

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  if (error) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="p-8 text-center">
          <p className="text-destructive">Failed to load users</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 bg-muted border-border text-foreground"
          />
        </div>
      </div>

      {isLoading ? (
        <Card className="bg-card border-border">
          <div className="divide-y divide-border">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4">
                <Skeleton className="h-10 w-10 rounded-full bg-muted" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32 bg-muted" />
                  <Skeleton className="h-3 w-48 bg-muted" />
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : !data?.items?.length ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <UserCog className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold text-foreground">No users found</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {search ? 'Try adjusting your search' : 'No users registered yet'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="text-sm text-muted-foreground">
            Showing {data.items.length} of {data.total} users
          </div>

          <motion.div
            variants={staggerContainerVariants}
            initial="hidden"
            animate="visible"
          >
            <Card className="bg-card border-border">
              <div className="divide-y divide-border">
                <AnimatePresence mode="popLayout">
                  {data.items.map((user: UserSummary) => (
                    <UserRow key={user.userId} user={user} />
                  ))}
                </AnimatePresence>
              </div>
            </Card>
          </motion.div>

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            showBorder={false}
          />
        </>
      )}
    </div>
  );
}

function UserRow({ user }: { user: UserSummary }) {
  const archiveMutation = useArchiveUser();
  const elevateMutation = useElevateRole();

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
      className="group flex items-center gap-4 p-4 hover:bg-muted/60 transition-colors"
    >
      <Avatar>
        <AvatarFallback className="bg-primary text-primary-foreground">
          {user.username?.charAt(0).toUpperCase() || 'U'}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground truncate">{user.username}</span>
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

      <div className="hidden md:block text-right text-sm text-muted-foreground">
        {formatDate(new Date(user.createdAt))}
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
          >
            <MoreVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="bg-popover border-border">
          <DropdownMenuLabel className="text-foreground">Change Role</DropdownMenuLabel>
          {(['admin', 'operator', 'viewer', 'family'] as Role[]).map((role) => {
            const Icon = roleIcons[role];
            return (
              <DropdownMenuItem
                key={role}
                onClick={() => handleElevate(role)}
                disabled={user.role === role}
                className="text-foreground focus:text-foreground focus:bg-muted"
              >
                <Icon className="mr-2 h-4 w-4" />
                {ROLE_LABELS[role]}
              </DropdownMenuItem>
            );
          })}
          <DropdownMenuSeparator className="bg-border" />
          <DropdownMenuItem
            onClick={handleArchive}
            className="text-destructive focus:text-destructive focus:bg-destructive/10"
          >
            <Archive className="mr-2 h-4 w-4" />
            Archive User
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </motion.div>
  );
}
