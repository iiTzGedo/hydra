import { useEffect, useState } from 'react';
import { useNavigate, useParams, Link, useSearchParams } from 'react-router-dom';
import {
  Server,
  Network,
  Cpu,
  ArrowLeft,
  Edit,
  Archive,
  RefreshCw,
  Info,
  Boxes,
  GitBranch,
  Globe,
  FolderTree,
  FileText,
} from 'lucide-react';
import { toast } from 'sonner';
import { useArchiveNode, useNode, useUpdateNode } from '@/api/nodes';
import type { NodeKind } from '@/types/node';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, NODE_CLASS_COLORS, NODE_KIND_LABELS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  OverviewTab,
  ProfileTab,
  ServicesTab,
  TopologyTab,
  NetworksTab,
  GroupsTab,
} from './tabs';

const classIcons = {
  compute: Server,
  networking: Network,
  iot: Cpu,
};

const tabs = [
  { id: 'overview', label: 'Overview', icon: Info },
  { id: 'profile', label: 'Profile', icon: FileText },
  { id: 'services', label: 'Services', icon: Boxes },
  { id: 'topology', label: 'Topology', icon: GitBranch },
  { id: 'networks', label: 'Networks', icon: Globe },
  { id: 'groups', label: 'Groups', icon: FolderTree },
];

export default function NodeDetailPage() {
  const { nodeId } = useParams<{ nodeId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialTab = searchParams.get('tab') || 'overview';
  const [activeTab, setActiveTab] = useState(initialTab);

  const { data: node, isLoading, error } = useNode(nodeId!);
  const updateNode = useUpdateNode();
  const archiveNode = useArchiveNode();

  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showArchiveDialog, setShowArchiveDialog] = useState(false);
  const [editForm, setEditForm] = useState({
    displayName: '',
    description: '',
    kind: '',
    status: 'active',
    tags: '',
    parentNodeId: '',
  });

  useDocumentTitle(node ? `${node.displayName || node.id} - Node` : 'Node Details');

  useEffect(() => {
    if (!node) return;
    setEditForm({
      displayName: node.displayName || '',
      description: node.description || '',
      kind: node.kind || '',
      status: node.status,
      tags: node.tags?.join(', ') || '',
      parentNodeId: node.parentNodeId || '',
    });
  }, [node]);

  useEffect(() => {
    const shouldEdit = searchParams.get('edit') === '1';
    const shouldArchive = searchParams.get('archive') === '1';
    if (shouldEdit) {
      setShowEditDialog(true);
    }
    if (shouldArchive) {
      setShowArchiveDialog(true);
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

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    setSearchParam('tab', value);
  };

  const handleSaveNode = async () => {
    if (!node) return;
    const tags = editForm.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    try {
      await updateNode.mutateAsync({
        nodeId: node.id,
        data: {
          displayName: editForm.displayName || undefined,
          description: editForm.description || undefined,
          kind: (editForm.kind || undefined) as NodeKind | undefined,
          status: editForm.status as typeof node.status,
          tags,
          parentNodeId: editForm.parentNodeId || undefined,
        },
      });
      toast.success('Node updated');
      setShowEditDialog(false);
      setSearchParam('edit');
    } catch (err) {
      toast.error('Failed to update node');
    }
  };

  const handleArchiveNode = async () => {
    if (!node) return;
    try {
      await archiveNode.mutateAsync(node.id);
      toast.success('Node archived');
      setShowArchiveDialog(false);
      setSearchParam('archive');
      navigate(ROUTES.NODES);
    } catch (err) {
      toast.error('Failed to archive node');
    }
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <Skeleton className="h-8 w-48 mb-6" />
        <div className="space-y-6">
          <Skeleton className="h-32" />
          <Skeleton className="h-12" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (error || !node) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.NODES}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Nodes
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <Server className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Node not found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The node "{nodeId}" could not be found
          </p>
        </div>
      </div>
    );
  }

  const Icon = classIcons[node.class] || Server;
  const colors = NODE_CLASS_COLORS[node.class];

  return (
    <div className="p-6">
      <Link
        to={ROUTES.NODES}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Nodes
      </Link>

      <PageHeader
        title={node.displayName || node.id}
        description={`${node.class} node - ${node.type}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" asChild>
              <Link to={ROUTES.NODES + '/' + node.id + '/profiles'}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Profiles
              </Link>
            </Button>
            <Button variant="outline" onClick={() => setSearchParam('edit', '1')}>
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </Button>
            <Button
              variant="outline"
              className="text-destructive hover:text-destructive"
              onClick={() => setSearchParam('archive', '1')}
            >
              <Archive className="mr-2 h-4 w-4" />
              Archive
            </Button>
          </div>
        }
      />

      <Tabs value={activeTab} onValueChange={handleTabChange} className="mt-6">
        <TabsList className="bg-card border border-border p-1 h-auto flex-wrap">
          {tabs.map((tab) => {
            const TabIcon = tab.icon;
            return (
              <TabsTrigger
                key={tab.id}
                value={tab.id}
                className="data-[state=active]:bg-muted data-[state=active]:text-foreground text-muted-foreground px-4 py-2 text-sm"
              >
                <TabIcon className="h-4 w-4 mr-2" />
                {tab.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <OverviewTab node={node} />
        </TabsContent>

        <TabsContent value="profile" className="mt-6">
          <ProfileTab nodeId={nodeId!} />
        </TabsContent>

        <TabsContent value="services" className="mt-6">
          <ServicesTab nodeId={nodeId!} />
        </TabsContent>

        <TabsContent value="topology" className="mt-6">
          <TopologyTab nodeId={nodeId!} />
        </TabsContent>

        <TabsContent value="networks" className="mt-6">
          <NetworksTab node={node} />
        </TabsContent>

        <TabsContent value="groups" className="mt-6">
          <GroupsTab node={node} />
        </TabsContent>
      </Tabs>

      <Dialog open={showEditDialog} onOpenChange={(open) => {
        setShowEditDialog(open);
        if (!open) setSearchParam('edit');
      }}>
        <DialogContent className="sm:max-w-lg bg-card border-border text-foreground">
          <DialogHeader>
            <DialogTitle>Edit Node</DialogTitle>
            <DialogDescription>Update node metadata and classification.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Display Name</Label>
              <Input
                value={editForm.displayName}
                onChange={(e) => setEditForm((prev) => ({ ...prev, displayName: e.target.value }))}
                className="bg-muted border-border text-foreground"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Description</Label>
              <Textarea
                value={editForm.description}
                onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value }))}
                className="bg-muted border-border text-foreground"
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Kind</Label>
                <Select
                  value={editForm.kind || 'none'}
                  onValueChange={(value) =>
                    setEditForm((prev) => ({ ...prev, kind: value === 'none' ? '' : value }))
                  }
                >
                  <SelectTrigger className="bg-muted border-border text-foreground">
                    <SelectValue placeholder="Select kind" />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-border">
                    <SelectItem value="none">Unspecified</SelectItem>
                    {Object.entries(NODE_KIND_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Status</Label>
                <Select
                  value={editForm.status}
                  onValueChange={(value) =>
                    setEditForm((prev) => ({ ...prev, status: value }))
                  }
                >
                  <SelectTrigger className="bg-muted border-border text-foreground">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-border">
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="archived">Archived</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Parent Node ID</Label>
              <Input
                value={editForm.parentNodeId}
                onChange={(e) => setEditForm((prev) => ({ ...prev, parentNodeId: e.target.value }))}
                className="bg-muted border-border text-foreground"
                placeholder="Optional parent node ID"
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
            <Button onClick={handleSaveNode} disabled={updateNode.isPending}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showArchiveDialog} onOpenChange={(open) => {
        setShowArchiveDialog(open);
        if (!open) setSearchParam('archive');
      }}>
        <DialogContent className="sm:max-w-md bg-card border-border text-foreground">
          <DialogHeader>
            <DialogTitle>Archive Node</DialogTitle>
            <DialogDescription>
              This will archive the node and keep its data for historical views.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowArchiveDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleArchiveNode}
              disabled={archiveNode.isPending}
            >
              Archive
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
