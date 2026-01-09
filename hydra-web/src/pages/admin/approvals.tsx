import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  UserCheck,
  Clock,
  Check,
  X,
  Loader2,
} from 'lucide-react';
import { useApprovals, useApproveUser, useRejectUser } from '@/api/auth';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, ROLE_LABELS } from '@/lib/constants';
import type { PendingUser } from '@/types/auth';
import { formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';

export default function ApprovalsPage() {
  const { data: approvals, isLoading, error, refetch } = useApprovals();
  const approveMutation = useApproveUser();
  const rejectMutation = useRejectUser();

  const handleApprove = async (userId: string) => {
    await approveMutation.mutateAsync({ userId });
    refetch();
  };

  const handleReject = async (userId: string) => {
    await rejectMutation.mutateAsync(userId);
    refetch();
  };

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
            <p className="text-destructive">Failed to load approvals</p>
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
        title="Pending Approvals"
        description="Review and approve new user registrations"
      />

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="flex items-center gap-3">
                  <Skeleton className="h-12 w-12 rounded-full" />
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-full" />
                </div>
                <div className="mt-6 flex gap-2">
                  <Skeleton className="h-9 flex-1" />
                  <Skeleton className="h-9 flex-1" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : !approvals?.pendingUsers?.length ? (
        <Card>
          <CardContent className="p-8 text-center">
            <UserCheck className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No pending approvals</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              All registration requests have been processed
            </p>
          </CardContent>
        </Card>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="grid gap-4 md:grid-cols-2"
        >
          <AnimatePresence mode="popLayout">
            {approvals.pendingUsers?.map((user: PendingUser) => (
              <motion.div
                key={user.userId}
                variants={staggerItemVariants}
                layout
                exit={{ opacity: 0, scale: 0.9 }}
              >
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <Avatar className="h-12 w-12">
                          <AvatarFallback className="bg-warning/10 text-warning text-lg">
                            {user.username?.charAt(0).toUpperCase() || 'U'}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <h4 className="font-semibold">{user.username}</h4>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                        </div>
                      </div>
                      <Badge variant="warning" className="gap-1">
                        <Clock className="h-3 w-3" />
                        Pending
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Requested Role</span>
                        <span className="font-medium">{ROLE_LABELS[user.role as keyof typeof ROLE_LABELS] || user.role}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Requested</span>
                        <span title={formatDate(new Date(user.requestedAt))}>
                          {formatRelativeTime(new Date(user.requestedAt))}
                        </span>
                      </div>
                    </div>

                    <div className="mt-6 flex items-center gap-2">
                      <Button
                        onClick={() => handleApprove(user.userId)}
                        disabled={approveMutation.isPending}
                        variant="success"
                        className="flex-1"
                      >
                        {approveMutation.isPending ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Check className="mr-2 h-4 w-4" />
                        )}
                        Approve
                      </Button>
                      <Button
                        onClick={() => handleReject(user.userId)}
                        disabled={rejectMutation.isPending}
                        variant="destructive"
                        className="flex-1"
                      >
                        {rejectMutation.isPending ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <X className="mr-2 h-4 w-4" />
                        )}
                        Reject
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}
