import { useState, useMemo } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Network,
  Search,
  Plus,
  Server,
  Globe,
  Layers,
  GitBranch,
  Eye,
  Edit,
  Trash2,
  MoreHorizontal,
  AlertTriangle,
  X,
  Loader2,
  LayoutGrid,
  LayoutList,
  SlidersHorizontal,
  Columns3,
} from 'lucide-react';
import { useNetworks, useCreateNetwork } from '@/api/networks';
import { NetworkSummary, NetworkType, CreateNetworkRequest } from '@/types/network';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Pagination } from '@/components/ui/pagination';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Network type configuration
const TYPE_CONFIG: Record<NetworkType, {
  icon: typeof Network;
  color: string;
  bgColor: string;
  label: string;
}> = {
  physical: {
    icon: Server,
    color: 'text-network',
    bgColor: 'bg-network/10',
    label: 'Physical'
  },
  virtual: {
    icon: Globe,
    color: 'text-compute',
    bgColor: 'bg-compute/10',
    label: 'Virtual'
  },
  overlay: {
    icon: Layers,
    color: 'text-primary',
    bgColor: 'bg-primary/10',
    label: 'Overlay'
  },
  vlan: {
    icon: GitBranch,
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    label: 'VLAN'
  },
  vxlan: {
    icon: GitBranch,
    color: 'text-info',
    bgColor: 'bg-info/10',
    label: 'VXLAN'
  },
  bridge: {
    icon: Network,
    color: 'text-iot',
    bgColor: 'bg-iot/10',
    label: 'Bridge'
  },
  tunnel: {
    icon: Network,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
    label: 'Tunnel'
  },
};

interface FilterState {
  search: string;
  type: NetworkType | 'all';
}

type TableDensity = 'comfortable' | 'compact';
type ViewMode = 'table' | 'grid';
type NetworkColumnKey = 'network' | 'type' | 'cidr' | 'gateway' | 'vlan' | 'nodes' | 'actions';

export default function NetworksPage() {
  useDocumentTitle('Network Explorer');

  const [filters, setFilters] = useState<FilterState>({
    search: '',
    type: 'all',
  });
  const [page, setPage] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [tableDensity, setTableDensity] = useState<TableDensity>('comfortable');
  const [visibleColumns, setVisibleColumns] = useState<Record<NetworkColumnKey, boolean>>({
    network: true,
    type: true,
    cidr: true,
    gateway: true,
    vlan: true,
    nodes: true,
    actions: true,
  });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const limit = 20;

  // Build query params
  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) params.search = filters.search;
    if (filters.type !== 'all') params.type = filters.type;
    return params;
  }, [filters, page]);

  const { data, isLoading, error } = useNetworks(queryParams);

  // Calculate stats from current data
  const stats = useMemo(() => {
    const items = data?.items ?? [];
    return {
      physical: items.filter(n => n.type === 'physical').length,
      virtual: items.filter(n => n.type === 'virtual').length,
      vlan: items.filter(n => n.type === 'vlan' || n.type === 'vxlan').length,
      other: items.filter(n => !['physical', 'virtual', 'vlan', 'vxlan'].includes(n.type)).length,
      total: data?.total ?? 0,
    };
  }, [data]);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;
  const hasActiveFilters = filters.type !== 'all';
  const visibleColumnCount = Object.values(visibleColumns).filter(Boolean).length;

  const clearFilters = () => {
    setFilters({ search: '', type: 'all' });
    setPage(0);
  };

  return (
    <TooltipProvider>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Networks</h1>
            <p className="text-muted-foreground">
              View and manage your network segments
            </p>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Network
          </Button>
        </div>

        {/* Status Summary Cards */}
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
        >
          <motion.div variants={staggerItemVariants}>
            <Card className="border-l-4 border-l-network">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Physical</p>
                    {isLoading ? (
                      <Skeleton className="h-8 w-12 mt-1" />
                    ) : (
                      <p className="text-2xl font-bold text-network">{stats.physical}</p>
                    )}
                  </div>
                  <div className="rounded-full bg-network/10 p-3">
                    <Server className="h-5 w-5 text-network" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div variants={staggerItemVariants}>
            <Card className="border-l-4 border-l-compute">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Virtual</p>
                    {isLoading ? (
                      <Skeleton className="h-8 w-12 mt-1" />
                    ) : (
                      <p className="text-2xl font-bold text-compute">{stats.virtual}</p>
                    )}
                  </div>
                  <div className="rounded-full bg-compute/10 p-3">
                    <Globe className="h-5 w-5 text-compute" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div variants={staggerItemVariants}>
            <Card className="border-l-4 border-l-warning">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">VLAN/VXLAN</p>
                    {isLoading ? (
                      <Skeleton className="h-8 w-12 mt-1" />
                    ) : (
                      <p className="text-2xl font-bold text-warning">{stats.vlan}</p>
                    )}
                  </div>
                  <div className="rounded-full bg-warning/10 p-3">
                    <GitBranch className="h-5 w-5 text-warning" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div variants={staggerItemVariants}>
            <Card className="border-l-4 border-l-primary">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Total</p>
                    {isLoading ? (
                      <Skeleton className="h-8 w-12 mt-1" />
                    ) : (
                      <p className="text-2xl font-bold">{stats.total}</p>
                    )}
                  </div>
                  <div className="rounded-full bg-primary/10 p-3">
                    <Network className="h-5 w-5 text-primary" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>

        {/* Filter Bar */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
              {/* Search */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search networks by name or CIDR..."
                  value={filters.search}
                  onChange={(e) => {
                    setFilters(f => ({ ...f, search: e.target.value }));
                    setPage(0);
                  }}
                  className="pl-9"
                />
              </div>

              {/* Filters */}
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={filters.type}
                  onValueChange={(value) => {
                    setFilters(f => ({ ...f, type: value as NetworkType | 'all' }));
                    setPage(0);
                  }}
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="physical">Physical</SelectItem>
                    <SelectItem value="virtual">Virtual</SelectItem>
                    <SelectItem value="vlan">VLAN</SelectItem>
                    <SelectItem value="vxlan">VXLAN</SelectItem>
                    <SelectItem value="overlay">Overlay</SelectItem>
                    <SelectItem value="bridge">Bridge</SelectItem>
                    <SelectItem value="tunnel">Tunnel</SelectItem>
                  </SelectContent>
                </Select>

                {hasActiveFilters && (
                  <Button variant="ghost" size="sm" onClick={clearFilters}>
                    <X className="h-4 w-4 mr-1" />
                    Clear
                  </Button>
                )}

                {/* View Mode Toggle */}
                <div className="flex items-center border rounded-md">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant={viewMode === 'table' ? 'secondary' : 'ghost'}
                        size="sm"
                        className="rounded-r-none border-0"
                        onClick={() => setViewMode('table')}
                      >
                        <LayoutList className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Table View</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                        size="sm"
                        className="rounded-l-none border-l"
                        onClick={() => setViewMode('grid')}
                      >
                        <LayoutGrid className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Grid View</TooltipContent>
                  </Tooltip>
                </div>

                {viewMode === 'table' && (
                  <>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm" title="Table Density">
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
                        <Button variant="outline" size="sm" title="Column Visibility">
                          <Columns3 className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Column Visibility</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.network}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, network: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.network}
                        >
                          Network
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
                          checked={visibleColumns.cidr}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, cidr: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.cidr}
                        >
                          CIDR
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.gateway}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, gateway: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.gateway}
                        >
                          Gateway
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.vlan}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, vlan: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.vlan}
                        >
                          VLAN ID
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.nodes}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, nodes: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.nodes}
                        >
                          Nodes
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.actions}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, actions: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.actions}
                        >
                          Actions
                        </DropdownMenuCheckboxItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Error State */}
        {error && (
          <Card className="border-destructive">
            <CardContent className="p-8 text-center">
              <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
              <h3 className="mt-4 text-lg font-semibold">Failed to load networks</h3>
              <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
            </CardContent>
          </Card>
        )}

        {/* Loading State */}
        {isLoading && !error && (
          <Card>
            <Table className={cn(tableDensity === 'compact' && 'table-compact')}>
              <TableHeader>
                <TableRow>
                  {visibleColumns.network && (
                    <TableHead className="w-[250px] text-muted-foreground">Network</TableHead>
                  )}
                  {visibleColumns.type && (
                    <TableHead className="text-muted-foreground">Type</TableHead>
                  )}
                  {visibleColumns.cidr && (
                    <TableHead className="text-muted-foreground">CIDR</TableHead>
                  )}
                  {visibleColumns.gateway && (
                    <TableHead className="text-muted-foreground">Gateway</TableHead>
                  )}
                  {visibleColumns.vlan && (
                    <TableHead className="text-muted-foreground">VLAN ID</TableHead>
                  )}
                  {visibleColumns.nodes && (
                    <TableHead className="text-muted-foreground">Nodes</TableHead>
                  )}
                  {visibleColumns.actions && (
                    <TableHead className="w-[50px] text-muted-foreground"></TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...Array(5)].map((_, i) => (
                  <TableRow key={i}>
                    {visibleColumns.network && (
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Skeleton className="h-9 w-9 rounded-lg" />
                          <div className="space-y-1">
                            <Skeleton className="h-4 w-32" />
                            <Skeleton className="h-3 w-24" />
                          </div>
                        </div>
                      </TableCell>
                    )}
                    {visibleColumns.type && (
                      <TableCell><Skeleton className="h-6 w-16 rounded-full" /></TableCell>
                    )}
                    {visibleColumns.cidr && (
                      <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                    )}
                    {visibleColumns.gateway && (
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    )}
                    {visibleColumns.vlan && (
                      <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                    )}
                    {visibleColumns.nodes && (
                      <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                    )}
                    {visibleColumns.actions && (
                      <TableCell><Skeleton className="h-8 w-8 rounded" /></TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}

        {/* Empty State */}
        {!isLoading && !error && !data?.items?.length && (
          <Card>
            <CardContent className="p-8 text-center">
              <Network className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">No networks found</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {hasActiveFilters || filters.search
                  ? 'Try adjusting your filters'
                  : 'Networks will appear here once discovered or created'}
              </p>
              <div className="flex justify-center gap-2 mt-4">
                {(hasActiveFilters || filters.search) && (
                  <Button variant="outline" onClick={clearFilters}>
                    Clear Filters
                  </Button>
                )}
                <Button onClick={() => setShowCreateModal(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Network
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Networks Table/Grid */}
        {!isLoading && !error && data?.items && data.items.length > 0 && (
          <motion.div
            variants={staggerContainerVariants}
            initial="hidden"
            animate="visible"
          >
            {viewMode === 'table' ? (
              <Card>
                <div className="flex items-center justify-between p-4 border-b">
                  <span className="text-sm text-muted-foreground">
                    Showing {data.items.length} of {data.total} networks
                  </span>
                </div>
                <Table className={cn(tableDensity === 'compact' && 'table-compact')}>
                  <TableHeader>
                    <TableRow>
                      {visibleColumns.network && (
                        <TableHead className="w-[250px] text-muted-foreground">Network</TableHead>
                      )}
                      {visibleColumns.type && (
                        <TableHead className="text-muted-foreground">Type</TableHead>
                      )}
                      {visibleColumns.cidr && (
                        <TableHead className="text-muted-foreground">CIDR</TableHead>
                      )}
                      {visibleColumns.gateway && (
                        <TableHead className="text-muted-foreground">Gateway</TableHead>
                      )}
                      {visibleColumns.vlan && (
                        <TableHead className="text-muted-foreground">VLAN ID</TableHead>
                      )}
                      {visibleColumns.nodes && (
                        <TableHead className="text-muted-foreground">Nodes</TableHead>
                      )}
                      {visibleColumns.actions && (
                        <TableHead className="w-[50px] text-muted-foreground"></TableHead>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((network) => (
                      <NetworkRow key={network.id} network={network} visibleColumns={visibleColumns} />
                    ))}
                  </TableBody>
                </Table>

                {/* Pagination */}
                <Pagination
                  page={page}
                  totalPages={totalPages}
                  onPageChange={setPage}
                />
              </Card>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-sm text-muted-foreground">
                    Showing {data.items.length} of {data.total} networks
                  </span>
                </div>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {data.items.map((network) => (
                    <NetworkGridCard key={network.id} network={network} />
                  ))}
                </div>
                <Pagination
                  page={page}
                  totalPages={totalPages}
                  onPageChange={setPage}
                  showBorder={false}
                  className="mt-6"
                />
              </div>
            )}
          </motion.div>
        )}

        {/* Create Network Modal */}
        <CreateNetworkModal
          open={showCreateModal}
          onOpenChange={setShowCreateModal}
        />
      </div>
    </TooltipProvider>
  );
}

type NetworkListItem = NetworkSummary & { id: string };

function NetworkGridCard({ network }: { network: NetworkListItem }) {
  const typeConfig = TYPE_CONFIG[network.type] || TYPE_CONFIG.physical;
  const TypeIcon = typeConfig.icon;

  return (
    <motion.div variants={staggerItemVariants}>
      <Card className="group hover:border-primary/50 transition-all">
        <CardContent className="p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className={cn('rounded-lg p-2', typeConfig.bgColor)}>
                <TypeIcon className={cn('h-5 w-5', typeConfig.color)} />
              </div>
              <div className="min-w-0 flex-1">
                <Link
                  to={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}`}
                  className="font-medium hover:text-primary transition-colors block truncate"
                >
                  {network.name}
                </Link>
                <Badge
                  variant="secondary"
                  className={cn('mt-1', typeConfig.bgColor, typeConfig.color)}
                >
                  {typeConfig.label}
                </Badge>
              </div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem asChild>
                  <Link to={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}`}>
                    <Eye className="h-4 w-4 mr-2" />
                    View Details
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <Edit className="h-4 w-4 mr-2" />
                  Edit Network
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive">
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">ID</span>
              <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono">
                {network.networkId}
              </code>
            </div>
            {network.cidr && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">CIDR</span>
                <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono">
                  {network.cidr}
                </code>
              </div>
            )}
            {network.gatewayV4 && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Gateway</span>
                <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono">
                  {network.gatewayV4}
                </code>
              </div>
            )}
            {network.vlanId && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">VLAN ID</span>
                <Badge variant="outline" className="font-mono">
                  {network.vlanId}
                </Badge>
              </div>
            )}
            <div className="flex items-center justify-between pt-2 border-t">
              <span className="text-muted-foreground">Nodes</span>
              <Badge variant="secondary">{network.nodeCount}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function NetworkRow({
  network,
  visibleColumns,
}: {
  network: NetworkListItem;
  visibleColumns: Record<NetworkColumnKey, boolean>;
}) {
  const typeConfig = TYPE_CONFIG[network.type] || TYPE_CONFIG.physical;
  const TypeIcon = typeConfig.icon;

  return (
    <motion.tr
      variants={staggerItemVariants}
      className="group hover:bg-muted/50 transition-colors"
    >
      {/* Network Info */}
      {visibleColumns.network && (
        <TableCell>
          <div className="flex items-center gap-3">
            <div className={cn('rounded-lg p-2', typeConfig.bgColor)}>
              <TypeIcon className={cn('h-5 w-5', typeConfig.color)} />
            </div>
            <div className="min-w-0">
              <Link
                to={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}`}
                className="font-medium hover:text-primary transition-colors block truncate"
              >
                {network.name}
              </Link>
              <span className="text-xs text-muted-foreground font-mono truncate block">
                {network.networkId}
              </span>
            </div>
          </div>
        </TableCell>
      )}

      {/* Type */}
      {visibleColumns.type && (
        <TableCell>
          <Badge
            variant="secondary"
            className={cn(typeConfig.bgColor, typeConfig.color)}
          >
            {typeConfig.label}
          </Badge>
        </TableCell>
      )}

      {/* CIDR */}
      {visibleColumns.cidr && (
        <TableCell>
          {network.cidr ? (
            <code className="text-sm bg-muted px-2 py-1 rounded font-mono">
              {network.cidr}
            </code>
          ) : (
            <span className="text-muted-foreground text-sm">—</span>
          )}
        </TableCell>
      )}

      {/* Gateway */}
      {visibleColumns.gateway && (
        <TableCell>
          {network.gatewayV4 ? (
            <code className="text-sm bg-muted px-2 py-1 rounded font-mono">
              {network.gatewayV4}
            </code>
          ) : (
            <span className="text-muted-foreground text-sm">—</span>
          )}
        </TableCell>
      )}

      {/* VLAN ID */}
      {visibleColumns.vlan && (
        <TableCell>
          {network.vlanId ? (
            <Badge variant="outline" className="font-mono">
              {network.vlanId}
            </Badge>
          ) : (
            <span className="text-muted-foreground text-sm">—</span>
          )}
        </TableCell>
      )}

      {/* Node Count */}
      {visibleColumns.nodes && (
        <TableCell>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="secondary" className="cursor-help">
                {network.nodeCount}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p>{network.nodeCount} node{network.nodeCount !== 1 ? 's' : ''} in this network</p>
            </TooltipContent>
          </Tooltip>
        </TableCell>
      )}

      {/* Actions */}
      {visibleColumns.actions && (
        <TableCell>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link to={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}`}>
                  <Eye className="h-4 w-4 mr-2" />
                  View Details
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Edit className="h-4 w-4 mr-2" />
                Edit Network
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive">
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      )}
    </motion.tr>
  );
}

// Create Network Modal Component
function CreateNetworkModal({
  open,
  onOpenChange
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createNetworkMutation = useCreateNetwork();
  const [formError, setFormError] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<Partial<CreateNetworkRequest>>({
    networkId: '',
    name: '',
    type: 'physical',
    cidr: '',
    cidrV6: '',
    gatewayV4: '',
    gatewayV6: '',
    vlanId: undefined,
    parentNetworkId: '',
    routerNodeId: '',
    description: '',
    tags: [],
    dns: {
      servers: [],
      domain: '',
      searchDomains: [],
    },
  });
  const [tagsInput, setTagsInput] = useState('');
  const [dnsServersInput, setDnsServersInput] = useState('');
  const [dnsSearchDomainsInput, setDnsSearchDomainsInput] = useState('');

  const resetForm = () => {
    setFormData({
      networkId: '',
      name: '',
      type: 'physical',
      cidr: '',
      cidrV6: '',
      gatewayV4: '',
      gatewayV6: '',
      vlanId: undefined,
      parentNetworkId: '',
      routerNodeId: '',
      description: '',
      tags: [],
      dns: { servers: [], domain: '', searchDomains: [] },
    });
    setTagsInput('');
    setDnsServersInput('');
    setDnsSearchDomainsInput('');
    setFormError(null);
  };

  const handleCreate = async () => {
    setFormError(null);
    if (!formData.networkId?.trim() || !formData.name?.trim()) {
      setFormError('Network ID and name are required.');
      return;
    }

    try {
      const request: CreateNetworkRequest = {
        networkId: formData.networkId.trim(),
        name: formData.name.trim(),
        type: formData.type || 'physical',
        cidr: formData.cidr?.trim() || undefined,
        cidrV6: formData.cidrV6?.trim() || undefined,
        gatewayV4: formData.gatewayV4?.trim() || undefined,
        gatewayV6: formData.gatewayV6?.trim() || undefined,
        vlanId: formData.vlanId,
        parentNetworkId: formData.parentNetworkId?.trim() || undefined,
        routerNodeId: formData.routerNodeId?.trim() || undefined,
        description: formData.description?.trim() || undefined,
        tags: tagsInput.split(',').map(t => t.trim()).filter(Boolean),
        dns: dnsServersInput.trim() || formData.dns?.domain?.trim() || dnsSearchDomainsInput.trim()
          ? {
              servers: dnsServersInput.split(',').map(s => s.trim()).filter(Boolean),
              domain: formData.dns?.domain?.trim() || undefined,
              searchDomains: dnsSearchDomainsInput.split(',').map(d => d.trim()).filter(Boolean),
            }
          : undefined,
      };

      await createNetworkMutation.mutateAsync(request);
      onOpenChange(false);
      resetForm();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setFormError(error.response?.data?.detail || 'Failed to create network');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Network</DialogTitle>
          <DialogDescription>
            Add a new network segment to your infrastructure
          </DialogDescription>
        </DialogHeader>

        {formError && (
          <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            {formError}
          </div>
        )}

        <div className="grid gap-4">
          {/* Basic Info */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="networkId">
                Network ID <span className="text-destructive">*</span>
              </Label>
              <Input
                id="networkId"
                value={formData.networkId}
                onChange={(e) => setFormData(f => ({ ...f, networkId: e.target.value }))}
                placeholder="e.g., prod-vlan-10"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g., Production VLAN"
              />
            </div>
          </div>

          {/* Type and VLAN ID */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="type">Type</Label>
              <Select
                value={formData.type}
                onValueChange={(value) => setFormData(f => ({ ...f, type: value as NetworkType }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="physical">Physical</SelectItem>
                  <SelectItem value="virtual">Virtual</SelectItem>
                  <SelectItem value="overlay">Overlay</SelectItem>
                  <SelectItem value="vlan">VLAN</SelectItem>
                  <SelectItem value="vxlan">VXLAN</SelectItem>
                  <SelectItem value="bridge">Bridge</SelectItem>
                  <SelectItem value="tunnel">Tunnel</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="vlanId">VLAN ID</Label>
              <Input
                id="vlanId"
                type="number"
                value={formData.vlanId ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value) : undefined;
                  setFormData(f => ({ ...f, vlanId: val }));
                }}
                placeholder="Optional"
              />
            </div>
          </div>

          {/* CIDR */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="cidr">CIDR (IPv4)</Label>
              <Input
                id="cidr"
                value={formData.cidr}
                onChange={(e) => setFormData(f => ({ ...f, cidr: e.target.value }))}
                placeholder="e.g., 10.0.10.0/24"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cidrV6">CIDR (IPv6)</Label>
              <Input
                id="cidrV6"
                value={formData.cidrV6}
                onChange={(e) => setFormData(f => ({ ...f, cidrV6: e.target.value }))}
                placeholder="Optional IPv6 CIDR"
              />
            </div>
          </div>

          {/* Gateway */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="gatewayV4">Gateway (IPv4)</Label>
              <Input
                id="gatewayV4"
                value={formData.gatewayV4}
                onChange={(e) => setFormData(f => ({ ...f, gatewayV4: e.target.value }))}
                placeholder="Optional"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="gatewayV6">Gateway (IPv6)</Label>
              <Input
                id="gatewayV6"
                value={formData.gatewayV6}
                onChange={(e) => setFormData(f => ({ ...f, gatewayV6: e.target.value }))}
                placeholder="Optional"
              />
            </div>
          </div>

          {/* Parent/Router */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="parentNetworkId">Parent Network ID</Label>
              <Input
                id="parentNetworkId"
                value={formData.parentNetworkId}
                onChange={(e) => setFormData(f => ({ ...f, parentNetworkId: e.target.value }))}
                placeholder="Optional"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="routerNodeId">Router Node ID</Label>
              <Input
                id="routerNodeId"
                value={formData.routerNodeId}
                onChange={(e) => setFormData(f => ({ ...f, routerNodeId: e.target.value }))}
                placeholder="Optional"
              />
            </div>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData(f => ({ ...f, description: e.target.value }))}
              placeholder="Optional description"
              rows={2}
            />
          </div>

          {/* DNS */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="dnsServers">DNS Servers</Label>
              <Input
                id="dnsServers"
                value={dnsServersInput}
                onChange={(e) => setDnsServersInput(e.target.value)}
                placeholder="Comma-separated IPs"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="dnsDomain">DNS Domain</Label>
              <Input
                id="dnsDomain"
                value={formData.dns?.domain || ''}
                onChange={(e) => setFormData(f => ({
                  ...f,
                  dns: { ...f.dns, servers: f.dns?.servers || [], domain: e.target.value }
                }))}
                placeholder="Optional"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="dnsSearchDomains">DNS Search Domains</Label>
            <Input
              id="dnsSearchDomains"
              value={dnsSearchDomainsInput}
              onChange={(e) => setDnsSearchDomainsInput(e.target.value)}
              placeholder="Comma-separated domains"
            />
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <Label htmlFor="tags">Tags</Label>
            <Input
              id="tags"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="Comma-separated tags"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={createNetworkMutation.isPending || !formData.networkId?.trim() || !formData.name?.trim()}
          >
            {createNetworkMutation.isPending && (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            )}
            Create Network
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
