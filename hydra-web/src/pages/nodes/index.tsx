import { useState, useMemo } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Plus,
  Copy,
  Check,
  Loader2,
  Search,
  Filter,
  LayoutGrid,
  LayoutList,
  SlidersHorizontal,
  Columns3,
  RefreshCw,
  Server,
  Wifi,
  Cpu,
  AlertTriangle,
} from 'lucide-react';
import { EmptyState } from '@/components/common/empty-state';
import { useNodes, useRegisterNode } from '@/api/nodes';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
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
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { cn, formatRelativeTime } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import type { NodeKind, NodeClass, NodeType, NodeStatus } from '@/types/node';

type ViewMode = 'grid' | 'table';
type TableDensity = 'comfortable' | 'compact';
type NodeColumnKey = 'node' | 'class' | 'type' | 'status' | 'lastProfile';

const nodeClassIcons: Record<string, React.ElementType> = {
  compute: Server,
  networking: Wifi,
  iot: Cpu,
};

const classColors: Record<string, string> = {
  compute: 'text-compute',
  networking: 'text-network',
  iot: 'text-iot',
};

export default function NodesPage() {
  useDocumentTitle('Node Explorer');

  const [search, setSearch] = useState('');
  const [classFilter, setClassFilter] = useState<NodeClass | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<NodeStatus | 'all'>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [tableDensity, setTableDensity] = useState<TableDensity>('comfortable');
  const [visibleColumns, setVisibleColumns] = useState<Record<NodeColumnKey, boolean>>({
    node: true,
    class: true,
    type: true,
    status: true,
    lastProfile: true,
  });
  const [showRegisterForm, setShowRegisterForm] = useState(false);

  // API data
  const { data: nodesData, isLoading, error, refetch } = useNodes({
    search: search || undefined,
    class: classFilter !== 'all' ? classFilter : undefined,
    status: statusFilter !== 'all' ? statusFilter : undefined,
  });
  const registerMutation = useRegisterNode();

  // Form state
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

  // Status counts
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
  const visibleColumnCount = Object.values(visibleColumns).filter(Boolean).length;

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
      const error = err as { response?: { data?: { detail?: string } } };
      setFormError(error.response?.data?.detail || 'Failed to register node');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Node Explorer</h2>
          <p className="text-sm text-muted-foreground">
            {filteredNodes.length} of {totalNodes} nodes
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => refetch()}
          >
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
      </div>

      {/* Status Summary */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
        <Card>
          <CardContent className="flex items-center justify-between p-4">
            <div>
              <p className="text-xs text-muted-foreground">Online</p>
              <p className="text-xl font-semibold text-success">{statusCounts.active}</p>
            </div>
            <div className="h-3 w-3 rounded-full bg-success" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center justify-between p-4">
            <div>
              <p className="text-xs text-muted-foreground">Warning</p>
              <p className="text-xl font-semibold text-warning">{statusCounts.pending}</p>
            </div>
            <div className="h-3 w-3 rounded-full bg-warning" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center justify-between p-4">
            <div>
              <p className="text-xs text-muted-foreground">Offline</p>
              <p className="text-xl font-semibold text-destructive">{statusCounts.inactive}</p>
            </div>
            <div className="h-3 w-3 rounded-full bg-destructive" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center justify-between p-4">
            <div>
              <p className="text-xs text-muted-foreground">Archived</p>
              <p className="text-xl font-semibold text-muted-foreground">{statusCounts.archived}</p>
            </div>
            <div className="h-3 w-3 rounded-full bg-muted-foreground" />
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by hostname, IP, or tag..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 bg-background"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground hidden sm:block" />
              <Select
                value={classFilter}
                onValueChange={(v) => setClassFilter(v as NodeClass | 'all')}
              >
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="Class" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Classes</SelectItem>
                  <SelectItem value="compute">Compute</SelectItem>
                  <SelectItem value="networking">Networking</SelectItem>
                  <SelectItem value="iot">IoT</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={statusFilter}
                onValueChange={(v) => setStatusFilter(v as NodeStatus | 'all')}
              >
                <SelectTrigger className="w-[120px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Online</SelectItem>
                  <SelectItem value="pending">Warning</SelectItem>
                  <SelectItem value="inactive">Offline</SelectItem>
                  <SelectItem value="archived">Archived</SelectItem>
                </SelectContent>
              </Select>
              <div className="flex rounded-md border border-border">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setViewMode('table')}
                  className={cn(
                    'rounded-none rounded-l-md',
                    viewMode === 'table' ? 'bg-muted text-foreground' : 'text-muted-foreground'
                  )}
                >
                  <LayoutList className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setViewMode('grid')}
                  className={cn(
                    'rounded-none rounded-r-md',
                    viewMode === 'grid' ? 'bg-muted text-foreground' : 'text-muted-foreground'
                  )}
                >
                  <LayoutGrid className="h-4 w-4" />
                </Button>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="icon" title="Table Density">
                    <SlidersHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Table Density</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuRadioGroup
                    value={tableDensity}
                    onValueChange={(value) => setTableDensity(value as TableDensity)}
                  >
                    <DropdownMenuRadioItem value="comfortable">Comfortable</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="compact">Compact</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="icon" title="Column Visibility">
                    <Columns3 className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Column Visibility</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuCheckboxItem
                    checked={visibleColumns.node}
                    onCheckedChange={(checked) =>
                      setVisibleColumns((prev) => ({ ...prev, node: Boolean(checked) }))
                    }
                    disabled={visibleColumnCount === 1 && visibleColumns.node}
                  >
                    Node
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={visibleColumns.class}
                    onCheckedChange={(checked) =>
                      setVisibleColumns((prev) => ({ ...prev, class: Boolean(checked) }))
                    }
                    disabled={visibleColumnCount === 1 && visibleColumns.class}
                  >
                    Class
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={visibleColumns.type}
                    onCheckedChange={(checked) =>
                      setVisibleColumns((prev) => ({ ...prev, type: Boolean(checked) }))
                    }
                    disabled={visibleColumnCount === 1 && visibleColumns.type}
                  >
                    Type
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={visibleColumns.status}
                    onCheckedChange={(checked) =>
                      setVisibleColumns((prev) => ({ ...prev, status: Boolean(checked) }))
                    }
                    disabled={visibleColumnCount === 1 && visibleColumns.status}
                  >
                    Status
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={visibleColumns.lastProfile}
                    onCheckedChange={(checked) =>
                      setVisibleColumns((prev) => ({ ...prev, lastProfile: Boolean(checked) }))
                    }
                    disabled={visibleColumnCount === 1 && visibleColumns.lastProfile}
                  >
                    Last Profile
                  </DropdownMenuCheckboxItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && !isLoading && (
        <Card className="border-destructive">
          <CardContent className="p-8 text-center">
            <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
            <h3 className="mt-4 text-lg font-semibold">Failed to load nodes</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              There was a problem fetching the node list. Please try again.
            </p>
            <Button variant="outline" className="mt-4" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!isLoading && !error && filteredNodes.length === 0 && (
        <EmptyState
          icon={Server}
          title="No nodes found"
          description={
            search || classFilter !== 'all' || statusFilter !== 'all'
              ? 'Try adjusting your filters'
              : 'Nodes will appear here once agents report them'
          }
          action={
            search || classFilter !== 'all' || statusFilter !== 'all'
              ? {
                  label: 'Clear Filters',
                  onClick: () => {
                    setSearch('');
                    setClassFilter('all');
                    setStatusFilter('all');
                  },
                }
              : undefined
          }
        />
      )}

      {/* Results */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[...Array(8)].map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-3">
                <Skeleton className="h-8 w-8 rounded bg-muted" />
                <Skeleton className="h-5 w-32 mt-2 bg-muted" />
                <Skeleton className="h-4 w-24 bg-muted" />
              </CardHeader>
              <CardContent className="pt-0 space-y-3">
                <Skeleton className="h-4 w-full bg-muted" />
                <Skeleton className="h-4 w-3/4 bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : !error && filteredNodes.length > 0 && viewMode === 'grid' ? (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        >
          {filteredNodes.map((node) => {
            const NodeIcon = nodeClassIcons[node.class] || Server;
            const statusColor =
              node.status === 'active'
                ? 'bg-success'
                : node.status === 'inactive' || node.status === 'archived'
                  ? 'bg-destructive'
                  : node.status === 'pending'
                    ? 'bg-warning'
                    : 'bg-muted-foreground';

            return (
              <motion.div key={node.nodeId} variants={staggerItemVariants}>
                <Link to={`${ROUTES.NODES}/${node.nodeId}`}>
                  <Card className="transition-all hover:border-foreground/20 hover:bg-muted/60 cursor-pointer h-full">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className={cn('h-10 w-10 flex items-center justify-center rounded-lg bg-muted', classColors[node.class])}>
                          <NodeIcon className="h-5 w-5" />
                        </div>
                        <div className={cn('h-2.5 w-2.5 rounded-full shrink-0', statusColor)} />
                      </div>
                      <CardTitle className="text-base text-foreground mt-2 truncate">
                        {node.displayName}
                      </CardTitle>
                      <CardDescription className="text-muted-foreground font-mono text-xs truncate">
                        {node.nodeId}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="space-y-2">
                        {/* Type */}
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">Type</span>
                          <Badge
                            variant="secondary"
                            className={`text-[10px] ${classColors[node.class]} bg-transparent border border-current`}
                          >
                            {node.type} / {node.kind || 'unknown'}
                          </Badge>
                        </div>
                        {/* Tags */}
                        <div className="flex flex-wrap gap-1 pt-1">
                          {node.tags?.slice(0, 3).map((tag) => (
                            <Badge key={tag} variant="outline" className="text-[10px] border-border text-muted-foreground">
                              {tag}
                            </Badge>
                          ))}
                          {(node.tags?.length ?? 0) > 3 && (
                            <Badge variant="outline" className="text-[10px] border-border text-muted-foreground">
                              +{(node.tags?.length ?? 0) - 3}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              </motion.div>
            );
          })}
        </motion.div>
      ) : !isLoading && !error && filteredNodes.length > 0 ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <Table className={cn(tableDensity === 'compact' && 'table-compact')}>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  {visibleColumns.node && (
                    <TableHead className="text-muted-foreground">Node</TableHead>
                  )}
                  {visibleColumns.class && (
                    <TableHead className="text-muted-foreground">Class</TableHead>
                  )}
                  {visibleColumns.type && (
                    <TableHead className="text-muted-foreground">Type</TableHead>
                  )}
                  {visibleColumns.status && (
                    <TableHead className="text-muted-foreground">Status</TableHead>
                  )}
                  {visibleColumns.lastProfile && (
                    <TableHead className="text-muted-foreground">Last Profile</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredNodes.map((node) => {
                  const NodeIcon = nodeClassIcons[node.class] || Server;
                  const statusVariant =
                    node.status === 'active'
                      ? 'online'
                      : node.status === 'pending'
                        ? 'pending'
                        : node.status === 'inactive' || node.status === 'archived'
                          ? 'offline'
                          : 'unknown';
                  return (
                    <TableRow key={node.nodeId} className="border-border hover:bg-muted/60 cursor-pointer">
                      {visibleColumns.node && (
                        <TableCell>
                          <Link
                            to={`${ROUTES.NODES}/${node.nodeId}`}
                            className="flex items-center gap-3"
                          >
                            <div className={cn('h-8 w-8 flex items-center justify-center rounded bg-muted', classColors[node.class])}>
                              <NodeIcon className="h-4 w-4" />
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
                      {visibleColumns.class && (
                        <TableCell>
                          <Badge variant="secondary" className={`${classColors[node.class]} bg-transparent`}>
                            {node.class}
                          </Badge>
                        </TableCell>
                      )}
                      {visibleColumns.type && (
                        <TableCell className="text-muted-foreground">
                          {node.type} / {node.kind || 'unknown'}
                        </TableCell>
                      )}
                      {visibleColumns.status && (
                        <TableCell>
                          <Badge variant={statusVariant}>
                            {node.status}
                          </Badge>
                        </TableCell>
                      )}
                      {visibleColumns.lastProfile && (
                        <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                          {node.lastProfileAt
                            ? formatRelativeTime(node.lastProfileAt)
                            : 'Never'}
                        </TableCell>
                      )}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </Card>
      ) : null}

      {/* Register Node Modal */}
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
                    <Label htmlFor="parentNodeId" className="text-foreground">Parent Node</Label>
                    <Input
                      id="parentNodeId"
                      value={parentNodeId}
                      onChange={(e) => setParentNodeId(e.target.value)}
                      placeholder="Optional"
                      className="bg-background"
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
    </div>
  );
}
