import { useState, useMemo, useCallback, useEffect } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  Plus,
  Copy,
  Check,
  Loader2,
  RefreshCw,
  Server,
  Eye,
  Edit,
  Archive,
  MoreHorizontal,
} from 'lucide-react';
import { EntityListPage, type StatCard, type TableDensity } from '@/components/common/entity-list-page';
import { FilterBar } from '@/components/common/filter-bar';
import { type ViewMode } from '@/components/common/view-mode-toggle';
import { useNodes, useRegisterNode, useUpdateNode, useArchiveNode } from '@/api/nodes';
import { HydraIcon } from '@/components/icons/hydra-icon';
import { ConfirmDialog } from '@/components/modals/confirm-dialog';
import { DropdownMenuItem } from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { NodeCard, NodeCardGridSkeleton } from '@/components/nodes/node-card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  TableCell,
  TableHead,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { EntityCombobox } from '@/components/ui/entity-combobox';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn, formatRelativeTime } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api-client';
import { ROUTES } from '@/lib/constants';
import type { NodeKind, NodeClass, NodeType, NodeStatus, NodeSummary, UpdateNodeRequest } from '@/types/node';
import {
  NODE_COLUMNS,
  NODE_FILTER_CONFIG,
  nodeClassColors,
} from './list-config';

type NodeSummaryWithId = NodeSummary & { id: string };

export default function NodesPage() {
  useDocumentTitle('Node Explorer');

  const [filters, setFilters] = useState({ search: '', class: 'all', status: 'all' });
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [tableDensity, setTableDensity] = useState<TableDensity>('comfortable');
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>({
    node: true,
    class: true,
    type: true,
    status: true,
    lastProfile: true,
  });
  const [showRegisterForm, setShowRegisterForm] = useState(false);
  const [editingNode, setEditingNode] = useState<NodeSummaryWithId | null>(null);
  const [archivingNode, setArchivingNode] = useState<NodeSummaryWithId | null>(null);
  const { data: nodesData, isLoading, error, refetch } = useNodes({
    search: filters.search || undefined,
    class: filters.class !== 'all' ? (filters.class as NodeClass) : undefined,
    status: filters.status !== 'all' ? (filters.status as NodeStatus) : undefined,
  });
  const registerMutation = useRegisterNode();
  const updateNodeMutation = useUpdateNode();
  const archiveNodeMutation = useArchiveNode();

  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [registeredNodeId, setRegisteredNodeId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [nodeId, setNodeId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [nodeClass, setNodeClass] = useState<NodeClass>('compute');
  const [nodeType, setNodeType] = useState<NodeType>('physical');
  const [kind, setKind] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [parentNodeId, setParentNodeId] = useState('');

  const statusCounts = useMemo(() => {
    const items = nodesData?.items ?? [];
    return {
      active: items.filter((n) => n.status === 'active').length,
      inactive: items.filter((n) => n.status === 'inactive').length,
      pending: items.filter((n) => n.status === 'pending').length,
      archived: items.filter((n) => n.status === 'archived').length,
    };
  }, [nodesData]);

  const filteredNodes = nodesData?.items ?? [];
  const totalNodes = nodesData?.total ?? 0;

  const stats: StatCard[] = useMemo(() => [
    { label: 'Online', value: statusCounts.active, icon: Server, color: 'success' },
    { label: 'Warning', value: statusCounts.pending, icon: Server, color: 'warning' },
    { label: 'Offline', value: statusCounts.inactive, icon: Server, color: 'destructive' },
    { label: 'Archived', value: statusCounts.archived, icon: Server, color: 'muted-foreground' },
  ], [statusCounts]);

  const resetForm = () => {
    setNodeId('');
    setDisplayName('');
    setNodeClass('compute');
    setNodeType('physical');
    setKind('');
    setDescription('');
    setTags('');
    setParentNodeId('');
    setFormError(null);
  };

  const handleCopy = async () => {
    if (newApiKey) {
      await navigator.clipboard.writeText(newApiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRegister = async () => {
    setFormError(null);
    if (!nodeId.trim() || !displayName.trim()) {
      setFormError('Node ID and display name are required.');
      return;
    }

    try {
      const result = await registerMutation.mutateAsync({
        nodeId: nodeId.trim(),
        class: nodeClass,
        type: nodeType,
        kind: (kind.trim() || undefined) as NodeKind | undefined,
        displayName: displayName.trim(),
        description: description.trim() || undefined,
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
        parentNodeId: parentNodeId.trim() || undefined,
      });
      setNewApiKey(result.apiKey);
      setRegisteredNodeId(result.nodeId);
    } catch (err: unknown) {
      setFormError(getErrorMessage(err, 'Failed to register node'));
    }
  };

  const handleArchiveNode = useCallback(async () => {
    if (!archivingNode) return;
    try {
      await archiveNodeMutation.mutateAsync(archivingNode.nodeId);
      toast.success(`Node "${archivingNode.displayName}" archived successfully`);
      setArchivingNode(null);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to archive node'));
    }
  }, [archivingNode, archiveNodeMutation]);

  const handleEditNode = useCallback(async (data: UpdateNodeRequest) => {
    if (!editingNode) return;
    try {
      await updateNodeMutation.mutateAsync({ id: editingNode.nodeId, data });
      toast.success(`Node "${editingNode.displayName}" updated successfully`);
      setEditingNode(null);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to update node'));
    }
  }, [editingNode, updateNodeMutation]);

  const hasActiveFilters = filters.search || filters.class !== 'all' || filters.status !== 'all';

  const clearFilters = useCallback(() => {
    setFilters({ search: '', class: 'all', status: 'all' });
  }, []);

  const renderFilterBar = () => (
    <FilterBar
      filters={filters}
      onFilterChange={(key, value) => setFilters(f => ({ ...f, [key]: value }))}
      onClearAll={clearFilters}
      config={NODE_FILTER_CONFIG}
    />
  );

  const renderGridCard = (node: NodeSummary) => {
    return (
      <NodeCard
        node={node}
        onEdit={(n) => setEditingNode(n as NodeSummaryWithId)}
        onArchive={(n) => setArchivingNode(n as NodeSummaryWithId)}
      />
    );
  };

  const renderTableHeader = (cols: Record<string, boolean>) => (
    <TableRow className="border-border hover:bg-transparent">
      {cols.node && <TableHead className="text-muted-foreground">Node</TableHead>}
      {cols.class && <TableHead className="text-muted-foreground">Class</TableHead>}
      {cols.type && <TableHead className="text-muted-foreground">Type</TableHead>}
      {cols.tier && <TableHead className="text-muted-foreground">Tier</TableHead>}
      {cols.status && <TableHead className="text-muted-foreground">Status</TableHead>}
      {cols.lastProfile && <TableHead className="text-muted-foreground">Last Profile</TableHead>}
      <TableHead className="w-[50px]"></TableHead>
    </TableRow>
  );

  const renderTableRow = (node: NodeSummary, cols: Record<string, boolean>) => {
    const statusVariant =
      node.status === 'active'
        ? 'online'
        : node.status === 'pending'
          ? 'pending'
          : node.status === 'inactive' || node.status === 'archived'
            ? 'offline'
            : 'unknown';

    return (
      <motion.tr
        key={node.nodeId}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="group border-border hover:bg-muted/60 cursor-pointer border-b transition-colors"
      >
        {cols.node && (
          <TableCell>
            <Link
              href={`${ROUTES.NODES}/${node.nodeId}`}
              className="flex items-center gap-3"
            >
              <div className={cn('h-8 w-8 flex items-center justify-center rounded bg-muted', nodeClassColors[node.class])}>
                <HydraIcon icon={node.icon} fallback={node.kind || node.class || 'server'} size={16} />
              </div>
              <div>
                <p className="text-foreground font-medium truncate max-w-[150px]">{node.displayName}</p>
                <p className="text-xs text-muted-foreground font-mono">
                  {node.nodeId}
                </p>
              </div>
            </Link>
          </TableCell>
        )}
        {cols.class && (
          <TableCell>
            <Badge variant="secondary" className={`${nodeClassColors[node.class]} bg-transparent`}>
              {node.class}
            </Badge>
          </TableCell>
        )}
        {cols.type && (
          <TableCell className="text-muted-foreground">
            {node.type} / {node.kind || 'unknown'}
          </TableCell>
        )}
        {cols.tier && (
          <TableCell className="text-muted-foreground text-sm capitalize">
            {node.agentTier || 'normal'}
          </TableCell>
        )}
        {cols.status && (
          <TableCell>
            <Badge variant={statusVariant}>
              {node.status}
            </Badge>
          </TableCell>
        )}
        {cols.lastProfile && (
          <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
            {node.lastProfileAt
              ? formatRelativeTime(node.lastProfileAt)
              : 'Never'}
          </TableCell>
        )}
        <TableCell>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`${ROUTES.NODES}/${node.nodeId}`}>
                  <Eye className="h-4 w-4 mr-2" />
                  View Details
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setEditingNode(node as NodeSummaryWithId)}>
                <Edit className="h-4 w-4 mr-2" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => setArchivingNode(node as NodeSummaryWithId)}
                className="text-destructive"
              >
                <Archive className="h-4 w-4 mr-2" />
                Archive
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      </motion.tr>
    );
  };

  const renderLoadingSkeleton = () => <NodeCardGridSkeleton count={8} />;

  return (
    <>
      <EntityListPage<NodeSummary>
        title="Node Explorer"
        subtitle={`${filteredNodes.length} of ${totalNodes} nodes`}
        headerAction={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <Button
              onClick={() => {
                resetForm();
                setNewApiKey(null);
                setRegisteredNodeId(null);
                setShowRegisterForm(true);
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add Node
            </Button>
          </div>
        }
        stats={stats}
        items={filteredNodes}
        isLoading={isLoading}
        error={error}
        onRetry={() => refetch()}
        filterBar={renderFilterBar()}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        tableDensity={tableDensity}
        onTableDensityChange={setTableDensity}
        columns={NODE_COLUMNS}
        visibleColumns={visibleColumns}
        onVisibleColumnsChange={setVisibleColumns}
        emptyIcon={Server}
        emptyTitle="No nodes found"
        emptyDescription={
          hasActiveFilters
            ? 'Try adjusting your filters'
            : 'Nodes will appear here once agents report them'
        }
        emptyActions={
          hasActiveFilters ? (
            <Button variant="outline" onClick={clearFilters}>
              Clear Filters
            </Button>
          ) : undefined
        }
        renderGridCard={renderGridCard}
        renderTableHeader={renderTableHeader}
        renderTableRow={renderTableRow}
        renderLoadingSkeleton={renderLoadingSkeleton}
        gridClassName="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
      />

      <Dialog open={showRegisterForm} onOpenChange={setShowRegisterForm}>
        <DialogContent className="sm:max-w-lg">
          {newApiKey ? (
            <div className="text-center py-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <Check className="h-6 w-6 text-success" />
              </div>
              <DialogHeader className="mt-4">
                <DialogTitle className="text-foreground">Node Registered</DialogTitle>
                <DialogDescription>
                  API key for {registeredNodeId}. Copy this key now - it won't be shown again.
                </DialogDescription>
              </DialogHeader>
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted p-3">
                <code className="flex-1 text-sm font-mono break-all text-left text-foreground">
                  {newApiKey}
                </code>
                <Button variant="ghost" size="icon" onClick={handleCopy} className="text-muted-foreground">
                  {copied ? (
                    <Check className="h-4 w-4 text-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <Button
                className="mt-6 w-full"
                onClick={() => {
                  setShowRegisterForm(false);
                  setNewApiKey(null);
                  setRegisteredNodeId(null);
                }}
              >
                Done
              </Button>
            </div>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle className="text-foreground">Register Node</DialogTitle>
                <DialogDescription>
                  Register a new infrastructure node to receive an API key.
                </DialogDescription>
              </DialogHeader>

              {formError && (
                <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                  {formError}
                </div>
              )}

              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="nodeId" className="text-foreground">
                    Node ID <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="nodeId"
                    value={nodeId}
                    onChange={(e) => setNodeId(e.target.value)}
                    placeholder="e.g., core-router-01"
                    className="bg-background"
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="displayName" className="text-foreground">
                    Display Name <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="displayName"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="e.g., Core Router"
                    className="bg-background"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="class" className="text-foreground">Class</Label>
                    <Select value={nodeClass} onValueChange={(v) => setNodeClass(v as NodeClass)}>
                      <SelectTrigger id="class">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="compute">Compute</SelectItem>
                        <SelectItem value="networking">Networking</SelectItem>
                        <SelectItem value="iot">IoT</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="type" className="text-foreground">Type</Label>
                    <Select value={nodeType} onValueChange={(v) => setNodeType(v as NodeType)}>
                      <SelectTrigger id="type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="physical">Physical</SelectItem>
                        <SelectItem value="logical">Logical</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="kind" className="text-foreground">Kind</Label>
                    <Input
                      id="kind"
                      value={kind}
                      onChange={(e) => setKind(e.target.value)}
                      placeholder="e.g., router, vm"
                      className="bg-background"
                    />
                  </div>

                  <div className="grid gap-2">
                    <Label className="text-foreground">Parent Node</Label>
                    <EntityCombobox
                      entityType="node"
                      value={parentNodeId}
                      onValueChange={setParentNodeId}
                      clearable
                      placeholder="Select parent node..."
                    />
                  </div>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="description" className="text-foreground">Description</Label>
                  <Textarea
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Optional description"
                    rows={2}
                    className="bg-background"
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="tags" className="text-foreground">Tags</Label>
                  <Input
                    id="tags"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    placeholder="Comma-separated tags"
                    className="bg-background"
                  />
                </div>
              </div>

              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowRegisterForm(false);
                    setNewApiKey(null);
                    setRegisteredNodeId(null);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleRegister}
                  disabled={registerMutation.isPending || !nodeId.trim() || !displayName.trim()}
                >
                  {registerMutation.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Register
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!archivingNode}
        onOpenChange={(open) => !open && setArchivingNode(null)}
        title="Archive Node"
        description={`Are you sure you want to archive "${archivingNode?.displayName}"? This will mark the node as archived and stop collecting profiles from it.`}
        confirmLabel="Archive"
        variant="destructive"
        onConfirm={handleArchiveNode}
        isLoading={archiveNodeMutation.isPending}
      />

      <NodeEditModal
        node={editingNode}
        open={!!editingNode}
        onOpenChange={(open) => !open && setEditingNode(null)}
        onSave={handleEditNode}
        isLoading={updateNodeMutation.isPending}
      />
    </>
  );
}

interface NodeEditModalProps {
  node: NodeSummaryWithId | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (data: UpdateNodeRequest) => Promise<void>;
  isLoading: boolean;
}

function NodeEditModal({ node, open, onOpenChange, onSave, isLoading }: NodeEditModalProps) {
  const [editDisplayName, setEditDisplayName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editTags, setEditTags] = useState('');
  const [editParentNodeId, setEditParentNodeId] = useState('');

  // Reset form when node changes
  useEffect(() => {
    if (node) {
      setEditDisplayName(node.displayName || '');
      setEditDescription('');
      setEditTags(node.tags?.join(', ') || '');
      setEditParentNodeId('');
    }
  }, [node]);

  const handleSave = async () => {
    const data: UpdateNodeRequest = {};
    if (editDisplayName.trim() && editDisplayName.trim() !== node?.displayName) {
      data.displayName = editDisplayName.trim();
    }
    if (editDescription.trim()) {
      data.description = editDescription.trim();
    }
    const newTags = editTags.split(',').map(t => t.trim()).filter(Boolean);
    if (newTags.length > 0 || (node?.tags && node.tags.length > 0)) {
      data.tags = newTags;
    }
    if (editParentNodeId.trim()) {
      data.parentNodeId = editParentNodeId.trim();
    }
    await onSave(data);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Node</DialogTitle>
          <DialogDescription>
            Update details for {node?.nodeId}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="editDisplayName">Display Name</Label>
            <Input
              id="editDisplayName"
              value={editDisplayName}
              onChange={(e) => setEditDisplayName(e.target.value)}
              placeholder="Display name"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="editDescription">Description</Label>
            <Textarea
              id="editDescription"
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="Optional description"
              rows={2}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="editTags">Tags</Label>
            <Input
              id="editTags"
              value={editTags}
              onChange={(e) => setEditTags(e.target.value)}
              placeholder="Comma-separated tags"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="editParentNodeId">Parent Node ID</Label>
            <Input
              id="editParentNodeId"
              value={editParentNodeId}
              onChange={(e) => setEditParentNodeId(e.target.value)}
              placeholder="Optional parent node"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading || !editDisplayName.trim()}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
