import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  FolderTree,
  Server,
  Edit,
  Trash2,
  Users,
  Tag,
  Code,
} from 'lucide-react';
import { useGroup, useGroupMembers } from '@/api/groups';
import { getSelectorEntries, getSelectorDisplayValue } from '@/types/group';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, NODE_CLASS_COLORS } from '@/lib/constants';
import { cn, formatDate } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const { data: group, isLoading, error } = useGroup(groupId!);
  const { data: members } = useGroupMembers(groupId!);
  const selectorEntries = group?.selectors ? getSelectorEntries(group.selectors) : [];

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted mb-6" />
        <div className="space-y-6">
          <div className="h-32 animate-pulse rounded-xl bg-muted" />
          <div className="h-64 animate-pulse rounded-xl bg-muted" />
        </div>
      </div>
    );
  }

  if (error || !group) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.GROUPS}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Groups
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <FolderTree className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Group not found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The group "{groupId}" could not be found
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Link
        to={ROUTES.GROUPS}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Groups
      </Link>

      <PageHeader
        title={group.name}
        description={group.description || 'Dynamic infrastructure group'}
        actions={
          <div className="flex items-center gap-2">
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium',
                'hover:bg-muted transition-colors'
              )}
            >
              <Edit className="h-4 w-4" />
              Edit
            </button>
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border border-error/50 px-4 py-2 text-sm font-medium text-error',
                'hover:bg-error/10 transition-colors'
              )}
            >
              <Trash2 className="h-4 w-4" />
              Delete
            </button>
          </div>
        }
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Overview card */}
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <div className="flex items-start gap-6">
            <div className="rounded-xl bg-iot p-4">
              <FolderTree className="h-8 w-8 text-white" />
            </div>

            <div className="flex-1 grid gap-6 md:grid-cols-2">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Group Info</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Name</span>
                    <span className="font-medium">{group.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Selectors</span>
                    <span className="font-medium">{selectorEntries.length}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Members</span>
                    <span className="font-medium">{members?.items?.length || 0}</span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Timestamps</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Created</span>
                    <span className="text-sm">
                      {group.createdAt ? formatDate(new Date(group.createdAt)) : '—'}
                    </span>
                  </div>
                  {group.updatedAt && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Updated</span>
                      <span className="text-sm">{formatDate(new Date(group.updatedAt))}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Tags */}
          {group.tags && group.tags.length > 0 && (
            <div className="mt-6 pt-6 border-t">
              <h4 className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-3">
                <Tag className="h-4 w-4" />
                Tags
              </h4>
              <div className="flex flex-wrap gap-2">
                {group.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-muted px-3 py-1 text-sm"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </motion.div>

        {/* Selectors */}
        {selectorEntries.length > 0 && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center gap-2 mb-4">
              <Code className="h-5 w-5" />
              <h3 className="text-lg font-semibold">Selectors</h3>
            </div>

            <div className="space-y-3">
              {selectorEntries.map((selector, index) => (
                <div
                  key={index}
                  className="rounded-lg border p-4 bg-muted/30"
                >
                  <div className="flex items-center gap-3">
                    <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      {selector.type}
                    </span>
                  </div>
                  <div className="mt-2 font-mono text-sm">
                    {getSelectorDisplayValue(selector)}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Members */}
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 mb-4">
            <Users className="h-5 w-5" />
            <h3 className="text-lg font-semibold">
              Resolved Members
              {members?.items && (
                <span className="ml-2 text-muted-foreground font-normal">
                  ({members.items.length})
                </span>
              )}
            </h3>
          </div>

          {!members?.items?.length ? (
            <div className="text-center py-8 text-muted-foreground">
              No members match the current selectors
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {members.items.map((member) => {
                const colors = NODE_CLASS_COLORS[member.class || 'unknown'];
                const memberRoute =
                  member.type === 'service'
                    ? ROUTES.SERVICES + '/' + member.id
                    : ROUTES.NODES + '/' + member.id;
                return (
                  <Link
                    key={member.id}
                    to={memberRoute}
                    className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                  >
                    <div className={cn('rounded-lg p-2', colors?.bg || 'bg-muted')}>
                      <Server className="h-4 w-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{member.displayName || member.id}</div>
                      <div className="text-xs text-muted-foreground capitalize">
                        {member.type}
                        {member.nodeId ? ` • ${member.nodeId}` : ''}
                      </div>
                    </div>
                    <span
                      className={cn(
                        'h-2 w-2 rounded-full',
                        member.status === 'active' ? 'bg-success' : 'bg-muted-foreground'
                      )}
                    />
                  </Link>
                );
              })}
            </div>
          )}
        </motion.div>
      </motion.div>
    </div>
  );
}
