import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  UserCheck,
  UserX,
  Clock,
  Check,
  X,
  Loader2,
} from 'lucide-react';
import { useApprovals, useApproveUser, useRejectUser } from '@/api/auth';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, ROLE_LABELS } from '@/lib/constants';
import type { PendingUser } from '@/types/auth';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

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
        <Link
          to={ROUTES.ADMIN}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Admin
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <p className="text-error">Failed to load approvals</p>
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
        title="Pending Approvals"
        description="Review and approve new user registrations"
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : !approvals?.pendingUsers?.length ? (
        <div className="rounded-xl border bg-card p-8 text-center">
          <UserCheck className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No pending approvals</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            All registration requests have been processed
          </p>
        </div>
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
                className="rounded-xl border bg-card p-6 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-warning/10 text-warning font-medium text-lg">
                      {user.username?.charAt(0).toUpperCase() || 'U'}
                    </div>
                    <div>
                      <h4 className="font-semibold">{user.username}</h4>
                      <p className="text-sm text-muted-foreground">{user.email}</p>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning">
                    <Clock className="h-3 w-3" />
                    Pending
                  </span>
                </div>

                <div className="mt-4 space-y-2 text-sm">
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
                  <button
                    onClick={() => handleApprove(user.userId)}
                    disabled={approveMutation.isPending}
                    className={cn(
                      'flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-success px-4 py-2 text-sm font-medium text-white',
                      'hover:bg-success/90 transition-colors',
                      'disabled:opacity-50 disabled:cursor-not-allowed'
                    )}
                  >
                    {approveMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                    Approve
                  </button>
                  <button
                    onClick={() => handleReject(user.userId)}
                    disabled={rejectMutation.isPending}
                    className={cn(
                      'flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-error px-4 py-2 text-sm font-medium text-white',
                      'hover:bg-error/90 transition-colors',
                      'disabled:opacity-50 disabled:cursor-not-allowed'
                    )}
                  >
                    {rejectMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <X className="h-4 w-4" />
                    )}
                    Reject
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}
