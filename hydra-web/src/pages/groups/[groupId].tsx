import { useEffect, useState } from 'react';
import { useNavigate, useParams, Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  FolderTree,
  Server,
  Edit,
  Trash2,
  Users,
  Tag,
  Code,
} from 'lucide-react';
import { toast } from 'sonner';
import { useDeleteGroup, useGroup, useGroupMembers, useUpdateGroup } from '@/api/groups';
import { getSelectorEntries, getSelectorDisplayValue } from '@/types/group';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { ROUTES, NODE_CLASS_COLORS } from '@/lib/constants';
import { cn, formatDate } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api-client';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export default function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: group, isLoading, error } = useGroup(groupId!);
  const { data: members } = useGroupMembers(groupId!);
  const updateGroup = useUpdateGroup();
  const deleteGroup = useDeleteGroup();
  const selectorEntries = group?.selectors ? getSelectorEntries(group.selectors) : [];

  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    tags: '',
  });

  useEffect(() => {
    if (!group) return;
    setEditForm({
      name: group.name || '',
      description: group.description || '',
      tags: group.tags?.join(', ') || '',
    });
  }, [group]);

  useEffect(() => {
    if (searchParams.get('edit') === '1') {
      setShowEditDialog(true);
    }
    if (searchParams.get('delete') === '1') {
      setShowDeleteDialog(true);
    }
  }, [searchParams]);

  const setSearchParam = (key: string, value?: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      return next;
    });
  };

  const handleSave = async () => {
    if (!group) return;
    const tags = editForm.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    try {
      await updateGroup.mutateAsync({
        id: group.groupId,
        data: {
          name: editForm.name || undefined,
          description: editForm.description || undefined,
          tags,
        },
      });
      toast.success('Group updated');
      setShowEditDialog(false);
      setSearchParam('edit');
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to update group'));
    }
  };

  const handleDelete = async () => {
    if (!group) return;
    try {
      await deleteGroup.mutateAsync(group.groupId);
      toast.success('Group deleted');
      setShowDeleteDialog(false);
      setSearchParam('delete');
      navigate(ROUTES.GROUPS);
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to delete group'));
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeaderLayout isLoading />
        <div className="space-y-6">
          <div className="h-32 animate-pulse rounded-xl bg-muted" />
          <div className="h-64 animate-pulse rounded-xl bg-muted" />
        </div>
      </div>
    );
  }

  if (error || !group) {
    return (
      <div className="space-y-6">
        <PageHeaderLayout title="Group not found" />
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
    <div className="space-y-6">
      <PageHeaderLayout
        title={group.name}
        subtitle={group.description || 'Dynamic infrastructure group'}
        actions={
          <div className="flex items-center gap-2">
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium',
                'hover:bg-muted transition-colors'
              )}
              onClick={() => setSearchParam('edit', '1')}
            >
              <Edit className="h-4 w-4" />
              Edit
            </button>
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border border-error/50 px-4 py-2 text-sm font-medium text-error',
                'hover:bg-error/10 transition-colors'
              )}
              onClick={() => setSearchParam('delete', '1')}
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

      <Dialog open={showEditDialog} onOpenChange={(open) => {
        setShowEditDialog(open);
        if (!open) setSearchParam('edit');
      }}>
        <DialogContent className="sm:max-w-lg bg-card border-border text-foreground">
          <DialogHeader>
            <DialogTitle>Edit Group</DialogTitle>
            <DialogDescription>Update group metadata.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Name</Label>
              <Input
                value={editForm.name}
                onChange={(e) => setEditForm((prev) => ({ ...prev, name: e.target.value }))}
                className="bg-muted border-border text-foreground"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Description</Label>
              <Textarea
                value={editForm.description}
                onChange={(e) =>
                  setEditForm((prev) => ({ ...prev, description: e.target.value }))
                }
                className="bg-muted border-border text-foreground"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Tags</Label>
              <Input
                value={editForm.tags}
                onChange={(e) => setEditForm((prev) => ({ ...prev, tags: e.target.value }))}
                className="bg-muted border-border text-foreground"
                placeholder="comma,separated,tags"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={updateGroup.isPending}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showDeleteDialog} onOpenChange={(open) => {
        setShowDeleteDialog(open);
        if (!open) setSearchParam('delete');
      }}>
        <DialogContent className="sm:max-w-md bg-card border-border text-foreground">
          <DialogHeader>
            <DialogTitle>Delete Group</DialogTitle>
            <DialogDescription>
              This will permanently delete the group and its selectors.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteGroup.isPending}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
