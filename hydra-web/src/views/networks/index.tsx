import { useState, useMemo } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Network,
  Plus,
  Server,
  Globe,
  GitBranch,
  Eye,
  Edit,
  Trash2,
  MoreHorizontal,
  Loader2,
} from 'lucide-react';
import { useNetworks, useCreateNetwork } from '@/api/networks';
import { NetworkSummary, NetworkType, CreateNetworkRequest } from '@/types/network';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api-client';
import { staggerItemVariants } from '@/lib/animations';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { EntityListPage, type TableDensity } from '@/components/common/entity-list-page';
import { FilterBar } from '@/components/common/filter-bar';
import { type ViewMode } from '@/components/common/view-mode-toggle';
import {
  NETWORK_COLUMNS,
  NETWORK_FILTER_CONFIG,
  NETWORK_TYPE_CONFIG,
} from './list-config';

// ─── Types ────────────────────────────────────────────────────────────────────

type NetworkColumnKey = 'network' | 'type' | 'cidr' | 'gateway' | 'nodes' | 'actions';
type NetworkListItem = NetworkSummary & { id: string };

interface FilterState {
  search: string;
  type: string;
  [key: string]: string;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

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
    nodes: true,
    actions: true,
  });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const limit = 20;

  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) params.search = filters.search;
    if (filters.type !== 'all') params.type = filters.type;
    return params;
  }, [filters, page]);

  const { data, isLoading, error } = useNetworks(queryParams);

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

  const clearFilters = () => {
    setFilters({ search: '', type: 'all' });
    setPage(0);
  };

  return (
    <div className="p-6">
      <EntityListPage<NetworkListItem>
        title="Networks"
        subtitle="View and manage your network segments"
        headerAction={
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Network
          </Button>
        }
        stats={[
          { label: 'Physical', value: stats.physical, icon: Server, color: 'network' },
          { label: 'Virtual', value: stats.virtual, icon: Globe, color: 'compute' },
          { label: 'VLAN/VXLAN', value: stats.vlan, icon: GitBranch, color: 'warning' },
          { label: 'Total', value: stats.total, icon: Network, color: 'primary' },
        ]}
        items={data?.items ?? []}
        isLoading={isLoading}
        error={error}
        filterBar={
          <FilterBar
            filters={filters}
            onFilterChange={(key, value) => {
              setFilters(f => ({ ...f, [key]: value }));
              setPage(0);
            }}
            onClearAll={() => {
              setFilters({ search: '', type: 'all' });
              setPage(0);
            }}
            config={NETWORK_FILTER_CONFIG}
          />
        }
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        tableDensity={tableDensity}
        onTableDensityChange={setTableDensity}
        columns={NETWORK_COLUMNS}
        visibleColumns={visibleColumns}
        onVisibleColumnsChange={(cols) => setVisibleColumns(cols as Record<NetworkColumnKey, boolean>)}
        pagination={{
          page,
          totalPages,
          onPageChange: setPage,
        }}
        emptyIcon={Network}
        emptyTitle="No networks found"
        emptyDescription={
          hasActiveFilters || filters.search
            ? 'Try adjusting your filters'
            : 'Networks will appear here once discovered or created'
        }
        emptyActions={
          <>
            {(hasActiveFilters || filters.search) && (
              <Button variant="outline" onClick={clearFilters}>
                Clear Filters
              </Button>
            )}
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Network
            </Button>
          </>
        }
        renderGridCard={(network) => (
          <NetworkGridCard key={network.id} network={network} />
        )}
        renderTableHeader={(visCols) => (
          <tr className="border-b">
            {visCols.network && (
              <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground w-[250px]">Network</th>
            )}
            {visCols.type && (
              <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Type</th>
            )}
            {visCols.cidr && (
              <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">CIDR</th>
            )}
            {visCols.gateway && (
              <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Gateway</th>
            )}
            {visCols.nodes && (
              <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Nodes</th>
            )}
            {visCols.actions && (
              <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground w-[50px]"></th>
            )}
          </tr>
        )}
        renderTableRow={(network, visCols) => (
          <NetworkRow
            key={network.id}
            network={network}
            visibleColumns={visCols as Record<NetworkColumnKey, boolean>}
          />
        )}
        renderLoadingSkeleton={() => (
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
        gridClassName="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
      />
      <CreateNetworkModal open={showCreateModal} onOpenChange={setShowCreateModal} />
    </div>
  );
}

// ─── Grid Card ────────────────────────────────────────────────────────────────

function NetworkGridCard({ network }: { network: NetworkListItem }) {
  const typeConfig = NETWORK_TYPE_CONFIG[network.type] || NETWORK_TYPE_CONFIG.physical;
  const TypeIcon = typeConfig.icon;

  return (
    <Card className="group hover:border-primary/50 transition-all">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={cn('rounded-lg p-2', typeConfig.bgColor)}>
              <TypeIcon className={cn('h-5 w-5', typeConfig.color)} />
            </div>
            <div className="min-w-0 flex-1">
              <Link
                href={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}`}
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
                <Link href={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}`}>
                  <Eye className="h-4 w-4 mr-2" />
                  View Details
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}?edit=1`}>
                  <Edit className="h-4 w-4 mr-2" />
                  Edit Network
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild className="text-destructive">
                <Link href={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}?delete=1`}>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </Link>
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
          <div className="flex items-center justify-between pt-2 border-t">
            <span className="text-muted-foreground">Nodes</span>
            <Badge variant="secondary">{network.nodeCount}</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Table Row ────────────────────────────────────────────────────────────────

function NetworkRow({
  network,
  visibleColumns,
}: {
  network: NetworkListItem;
  visibleColumns: Record<NetworkColumnKey, boolean>;
}) {
  const typeConfig = NETWORK_TYPE_CONFIG[network.type] || NETWORK_TYPE_CONFIG.physical;
  const TypeIcon = typeConfig.icon;

  return (
    <motion.tr
      variants={staggerItemVariants}
      className="group hover:bg-muted/50 transition-colors"
    >
      {visibleColumns.network && (
        <TableCell>
          <div className="flex items-center gap-3">
            <div className={cn('rounded-lg p-2', typeConfig.bgColor)}>
              <TypeIcon className={cn('h-5 w-5', typeConfig.color)} />
            </div>
            <div className="min-w-0">
              <Link
                href={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}`}
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

      {visibleColumns.cidr && (
        <TableCell>
          {network.cidr ? (
            <code className="text-sm bg-muted px-2 py-1 rounded font-mono">
              {network.cidr}
            </code>
          ) : (
            <span className="text-muted-foreground text-sm">--</span>
          )}
        </TableCell>
      )}

      {visibleColumns.gateway && (
        <TableCell>
          {network.gatewayV4 ? (
            <code className="text-sm bg-muted px-2 py-1 rounded font-mono">
              {network.gatewayV4}
            </code>
          ) : (
            <span className="text-muted-foreground text-sm">--</span>
          )}
        </TableCell>
      )}

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
                <Link href={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}`}>
                  <Eye className="h-4 w-4 mr-2" />
                  View Details
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}?edit=1`}>
                  <Edit className="h-4 w-4 mr-2" />
                  Edit Network
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild className="text-destructive">
                <Link href={`${ROUTES.NETWORKS}/${encodeURIComponent(network.networkId)}?delete=1`}>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      )}
    </motion.tr>
  );
}

// ─── Create Network Modal ─────────────────────────────────────────────────────

function CreateNetworkModal({
  open,
  onOpenChange
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createNetworkMutation = useCreateNetwork();
  const [formError, setFormError] = useState<string | null>(null);

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
      setFormError(getErrorMessage(err, 'Failed to create network'));
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
