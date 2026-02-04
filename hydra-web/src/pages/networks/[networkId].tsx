import { useEffect, useState } from 'react';
import { useNavigate, useParams, Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Network,
  Server,
  Edit,
  Trash2,
  Globe,
  Tag,
} from 'lucide-react';
import { toast } from 'sonner';
import { useDeleteNetwork, useNetwork, useNetworkNodes, useUpdateNetwork } from '@/api/networks';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, NETWORK_TYPE_LABELS, NODE_CLASS_COLORS } from '@/lib/constants';
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

export default function NetworkDetailPage() {
  const { networkId } = useParams<{ networkId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: network, isLoading, error } = useNetwork(networkId!);
  const { data: networkNodes } = useNetworkNodes(networkId!);
  const updateNetwork = useUpdateNetwork();
  const deleteNetwork = useDeleteNetwork();

  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    gatewayV4: '',
    gatewayV6: '',
    routerNodeId: '',
    tags: '',
  });

  useEffect(() => {
    if (!network) return;
    setEditForm({
      name: network.name || '',
      description: network.description || '',
      gatewayV4: network.gatewayV4 || '',
      gatewayV6: network.gatewayV6 || '',
      routerNodeId: network.routerNodeId || '',
      tags: network.tags?.join(', ') || '',
    });
  }, [network]);

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
    if (!network) return;
    const tags = editForm.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    try {
      await updateNetwork.mutateAsync({
        networkId: network.networkId,
        data: {
          name: editForm.name || undefined,
          description: editForm.description || undefined,
          gatewayV4: editForm.gatewayV4 || undefined,
          gatewayV6: editForm.gatewayV6 || undefined,
          routerNodeId: editForm.routerNodeId || undefined,
          tags,
        },
      });
      toast.success('Network updated');
      setShowEditDialog(false);
      setSearchParam('edit');
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to update network'));
    }
  };

  const handleDelete = async () => {
    if (!network) return;
    try {
      await deleteNetwork.mutateAsync({ networkId: network.networkId });
      toast.success('Network deleted');
      setShowDeleteDialog(false);
      setSearchParam('delete');
      navigate(ROUTES.NETWORKS);
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to delete network'));
    }
  };

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

  if (error || !network) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.NETWORKS}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Networks
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <Network className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Network not found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The network "{networkId}" could not be found
          </p>
        </div>
      </div>
    );
  }

  const typeLabel = NETWORK_TYPE_LABELS[network.type] || network.type;

  return (
    <div className="p-6">
      <Link
        to={ROUTES.NETWORKS}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Networks
      </Link>

      <PageHeader
        title={network.name || network.cidr || 'Network'}
        description={`${typeLabel} network`}
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
            <div className="rounded-xl bg-networking p-4">
              <Network className="h-8 w-8 text-white" />
            </div>

            <div className="flex-1 grid gap-6 md:grid-cols-3">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Network Info</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">CIDR</span>
                    <span className="font-mono">{network.cidr || '—'}</span>
                  </div>
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
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Gateway & DNS</h4>
                <div className="space-y-2">
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
                  {network.dns?.servers && network.dns.servers.length > 0 && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">DNS</span>
                      <span className="font-mono">{network.dns.servers.join(', ')}</span>
                    </div>
                  )}
                  {network.dns?.domain && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Domain</span>
                      <span>{network.dns.domain}</span>
                    </div>
                  )}
                  {network.dns?.searchDomains && network.dns.searchDomains.length > 0 && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Search</span>
                      <span className="font-mono">
                        {network.dns.searchDomains.join(', ')}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Timestamps</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Created</span>
                    <span className="text-sm">{network.createdAt ? formatDate(new Date(network.createdAt)) : '—'}</span>
                  </div>
                  {network.updatedAt && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Updated</span>
                      <span className="text-sm">{formatDate(new Date(network.updatedAt))}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

                    {network.description && (
            <div className="mt-6 pt-6 border-t">
              <h4 className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-2">
                <Globe className="h-4 w-4" />
                Description
              </h4>
              <p className="text-sm">{network.description}</p>
            </div>
          )}

                    {network.tags && network.tags.length > 0 && (
            <div className="mt-6 pt-6 border-t">
              <h4 className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-3">
                <Tag className="h-4 w-4" />
                Tags
              </h4>
              <div className="flex flex-wrap gap-2">
                {network.tags.map((tag) => (
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

                <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 mb-4">
            <Server className="h-5 w-5" />
            <h3 className="text-lg font-semibold">
              Connected Nodes
              {networkNodes?.items && (
                <span className="ml-2 text-muted-foreground font-normal">
                  ({networkNodes.items.length})
                </span>
              )}
            </h3>
          </div>

          {!networkNodes?.items?.length ? (
            <div className="text-center py-8 text-muted-foreground">
              No nodes connected to this network
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {networkNodes.items.map((node) => {
                const colors = NODE_CLASS_COLORS[node.class];
                return (
                  <Link
                    key={node.nodeId}
                    to={ROUTES.NODES + '/' + node.nodeId}
                    className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                  >
                    <div className={cn('rounded-lg p-2', colors?.bg || 'bg-muted')}>
                      <Server className="h-4 w-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{node.displayName}</div>
                      <div className="text-xs text-muted-foreground capitalize">
                        {node.class}
                      </div>
                    </div>
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
            <DialogTitle>Edit Network</DialogTitle>
            <DialogDescription>Update network configuration.</DialogDescription>
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
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Gateway v4</Label>
                <Input
                  value={editForm.gatewayV4}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, gatewayV4: e.target.value }))}
                  className="bg-muted border-border text-foreground"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Gateway v6</Label>
                <Input
                  value={editForm.gatewayV6}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, gatewayV6: e.target.value }))}
                  className="bg-muted border-border text-foreground"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Router Node ID</Label>
              <Input
                value={editForm.routerNodeId}
                onChange={(e) =>
                  setEditForm((prev) => ({ ...prev, routerNodeId: e.target.value }))
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
            <Button onClick={handleSave} disabled={updateNetwork.isPending}>
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
            <DialogTitle>Delete Network</DialogTitle>
            <DialogDescription>
              This will permanently delete the network. Nodes may be orphaned.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteNetwork.isPending}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
