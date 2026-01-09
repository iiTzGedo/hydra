import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Boxes,
  Search,
  Play,
  Square,
  AlertTriangle,
  AlertCircle,
  RotateCcw,
  RefreshCw,
  HelpCircle,
  Server,
  ChevronLeft,
  ChevronRight,
  Filter,
  X,
  CheckCircle2,
  LayoutGrid,
  LayoutList,
  SlidersHorizontal,
  Columns3,
} from 'lucide-react';
import { useServices } from '@/api/services';
import { ServiceRuntime, ServiceStatus } from '@/types/service';
import { ROUTES, SERVICE_RUNTIME_LABELS } from '@/lib/constants';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Runtime colors
const runtimeColors: Record<ServiceRuntime, string> = {
  docker: 'text-blue-500',
  podman: 'text-orange-500',
  kubernetes: 'text-cyan-500',
  systemd: 'text-green-500',
  pm2: 'text-purple-500',
  launchd: 'text-muted-foreground',
  windows_service: 'text-sky-500',
  cron: 'text-amber-500',
  supervisor: 'text-rose-500',
  custom: 'text-muted-foreground',
};

// Status icons
const statusIcons: Record<ServiceStatus, typeof Play> = {
  running: Play,
  stopped: Square,
  failed: AlertCircle,
  paused: Square,
  restarting: RotateCcw,
  unknown: HelpCircle,
};

interface FilterState {
  search: string;
  runtime: ServiceRuntime | 'all';
  status: ServiceStatus | 'all';
  nodeId: string;
}

type TableDensity = 'comfortable' | 'compact';
type ViewMode = 'table' | 'grid';
type ServiceColumnKey = 'service' | 'host' | 'runtime' | 'ports' | 'status' | 'lastSeen';

export default function ServicesPage() {
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    runtime: 'all',
    status: 'all',
    nodeId: '',
  });
  const [page, setPage] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [tableDensity, setTableDensity] = useState<TableDensity>('comfortable');
  const [visibleColumns, setVisibleColumns] = useState<Record<ServiceColumnKey, boolean>>({
    service: true,
    host: true,
    runtime: true,
    ports: true,
    status: true,
    lastSeen: true,
  });
  const limit = 20;

  // Build query params
  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) params.search = filters.search;
    if (filters.runtime !== 'all') params.runtime = filters.runtime;
    if (filters.status !== 'all') params.status = filters.status;
    if (filters.nodeId) params.nodeId = filters.nodeId;
    return params;
  }, [filters, page]);

  const { data, isLoading, error } = useServices(queryParams);

  // Calculate stats from current data
  const stats = useMemo(() => {
    const items = data?.items ?? [];
    return {
      running: items.filter(s => s.status === 'running').length,
      stopped: items.filter(s => s.status === 'stopped').length,
      restarting: items.filter(s => s.status === 'restarting').length,
      error: items.filter(s => s.status === 'failed').length,
    };
  }, [data]);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;
  const hasActiveFilters = filters.runtime !== 'all' || filters.status !== 'all' || filters.nodeId;
  const visibleColumnCount = Object.values(visibleColumns).filter(Boolean).length;

  const clearFilters = () => {
    setFilters({ search: '', runtime: 'all', status: 'all', nodeId: '' });
    setPage(0);
  };

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-foreground">Service Explorer</h2>
            <p className="text-sm text-muted-foreground">
              {data?.items?.length ?? 0} of {data?.total ?? 0} services
            </p>
          </div>
        </div>

        {/* Status Summary Cards */}
        <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
          <Card>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <p className="text-xs text-muted-foreground">Running</p>
                <p className="text-xl font-semibold text-success">{stats.running}</p>
              </div>
              <CheckCircle2 className="h-5 w-5 text-success" />
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <p className="text-xs text-muted-foreground">Stopped</p>
                <p className="text-xl font-semibold text-muted-foreground">{stats.stopped}</p>
              </div>
              <Square className="h-5 w-5 text-muted-foreground" />
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <p className="text-xs text-muted-foreground">Restarting</p>
                <p className="text-xl font-semibold text-warning">{stats.restarting}</p>
              </div>
              <RotateCcw className="h-5 w-5 text-warning" />
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <p className="text-xs text-muted-foreground">Error</p>
                <p className="text-xl font-semibold text-destructive">{stats.error}</p>
              </div>
              <AlertCircle className="h-5 w-5 text-destructive" />
            </CardContent>
          </Card>
        </div>

        {/* Filter Bar */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              {/* Search */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search by name or image..."
                  value={filters.search}
                  onChange={(e) => {
                    setFilters(f => ({ ...f, search: e.target.value }));
                    setPage(0);
                  }}
                  className="pl-9 bg-background"
                />
              </div>

              {/* Filters */}
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <Select
                  value={filters.runtime}
                  onValueChange={(value) => {
                    setFilters(f => ({ ...f, runtime: value as ServiceRuntime | 'all' }));
                    setPage(0);
                  }}
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Runtime" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Runtimes</SelectItem>
                    <SelectItem value="docker">Docker</SelectItem>
                    <SelectItem value="podman">Podman</SelectItem>
                    <SelectItem value="kubernetes">Kubernetes</SelectItem>
                    <SelectItem value="systemd">Systemd</SelectItem>
                  </SelectContent>
                </Select>

                <Select
                  value={filters.status}
                  onValueChange={(value) => {
                    setFilters(f => ({ ...f, status: value as ServiceStatus | 'all' }));
                    setPage(0);
                  }}
                >
                  <SelectTrigger className="w-[130px]">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="running">Running</SelectItem>
                    <SelectItem value="stopped">Stopped</SelectItem>
                    <SelectItem value="restarting">Restarting</SelectItem>
                    <SelectItem value="failed">Error</SelectItem>
                  </SelectContent>
                </Select>

                {hasActiveFilters && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearFilters}
                    className="text-muted-foreground"
                  >
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
                          checked={visibleColumns.service}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, service: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.service}
                        >
                          Service
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.host}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, host: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.host}
                        >
                          Host Node
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.runtime}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, runtime: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.runtime}
                        >
                          Runtime
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.ports}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, ports: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.ports}
                        >
                          Ports
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
                          checked={visibleColumns.lastSeen}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, lastSeen: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.lastSeen}
                        >
                          Last Seen
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
          <Card className="border-destructive/40">
            <CardContent className="p-8 text-center">
              <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load services</h3>
              <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
            </CardContent>
          </Card>
        )}

        {/* Loading State */}
        {isLoading && !error && (
          <Card>
            <Table className={cn(tableDensity === 'compact' && 'table-compact')}>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  {visibleColumns.service && (
                    <TableHead className="text-muted-foreground">Service</TableHead>
                  )}
                  {visibleColumns.host && (
                    <TableHead className="text-muted-foreground">Host Node</TableHead>
                  )}
                  {visibleColumns.runtime && (
                    <TableHead className="text-muted-foreground">Runtime</TableHead>
                  )}
                  {visibleColumns.ports && (
                    <TableHead className="text-muted-foreground">Ports</TableHead>
                  )}
                  {visibleColumns.status && (
                    <TableHead className="text-muted-foreground">Status</TableHead>
                  )}
                  {visibleColumns.lastSeen && (
                    <TableHead className="text-muted-foreground">Last Seen</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...Array(5)].map((_, i) => (
                  <TableRow key={i} className="border-border">
                    {visibleColumns.service && (
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <Skeleton className="h-4 w-32 bg-muted" />
                          <Skeleton className="h-3 w-24 bg-muted" />
                        </div>
                      </TableCell>
                    )}
                    {visibleColumns.host && (
                      <TableCell><Skeleton className="h-4 w-24 bg-muted" /></TableCell>
                    )}
                    {visibleColumns.runtime && (
                      <TableCell><Skeleton className="h-6 w-16 rounded-full bg-muted" /></TableCell>
                    )}
                    {visibleColumns.ports && (
                      <TableCell><Skeleton className="h-5 w-20 bg-muted" /></TableCell>
                    )}
                    {visibleColumns.status && (
                      <TableCell><Skeleton className="h-6 w-16 rounded-full bg-muted" /></TableCell>
                    )}
                    {visibleColumns.lastSeen && (
                      <TableCell><Skeleton className="h-4 w-16 bg-muted" /></TableCell>
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
              <Boxes className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">No services found</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {hasActiveFilters || filters.search
                  ? 'Try adjusting your filters'
                  : 'Services will appear here once nodes report them'}
              </p>
              {(hasActiveFilters || filters.search) && (
                <Button variant="outline" className="mt-4" onClick={clearFilters}>
                  Clear Filters
                </Button>
              )}
            </CardContent>
          </Card>
        )}

        {/* Services Table */}
        {!isLoading && !error && data?.items && data.items.length > 0 && (
          <Card>
            <Table className={cn(tableDensity === 'compact' && 'table-compact')}>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  {visibleColumns.service && (
                    <TableHead className="text-muted-foreground">Service</TableHead>
                  )}
                  {visibleColumns.host && (
                    <TableHead className="text-muted-foreground">Host Node</TableHead>
                  )}
                  {visibleColumns.runtime && (
                    <TableHead className="text-muted-foreground">Runtime</TableHead>
                  )}
                  {visibleColumns.ports && (
                    <TableHead className="text-muted-foreground">Ports</TableHead>
                  )}
                  {visibleColumns.status && (
                    <TableHead className="text-muted-foreground">Status</TableHead>
                  )}
                  {visibleColumns.lastSeen && (
                    <TableHead className="text-muted-foreground">Last Seen</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((service) => {
                  const StatusIcon = statusIcons[service.status] || HelpCircle;
                  const runtimeColor = runtimeColors[service.runtime] || 'text-muted-foreground';
                  const runtimeLabel = SERVICE_RUNTIME_LABELS[service.runtime] || service.runtime;
                  const statusVariant =
                    service.status === 'running'
                      ? 'success'
                      : service.status === 'restarting'
                        ? 'warning'
                        : service.status === 'failed'
                          ? 'destructive'
                          : service.status === 'stopped'
                            ? 'secondary'
                            : 'outline';

                  return (
                    <TableRow key={service.serviceId} className="border-border hover:bg-muted/60">
                      {visibleColumns.service && (
                        <TableCell>
                          <Link to={`${ROUTES.SERVICES}/${encodeURIComponent(service.serviceId)}`} className="flex flex-col">
                            <span className="text-foreground font-medium hover:text-primary">{service.name}</span>
                            <span className="text-xs text-muted-foreground font-mono">{service.serviceId}</span>
                          </Link>
                        </TableCell>
                      )}
                      {visibleColumns.host && (
                        <TableCell>
                          <Link
                            to={`${ROUTES.NODES}/${service.nodeId}`}
                            className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
                          >
                            <Server className="h-4 w-4" />
                            <span className="text-sm">{service.nodeId}</span>
                          </Link>
                        </TableCell>
                      )}
                      {visibleColumns.runtime && (
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={`${runtimeColor} border-current bg-transparent`}
                          >
                            {runtimeLabel}
                          </Badge>
                        </TableCell>
                      )}
                      {visibleColumns.ports && (
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {service.ports?.slice(0, 2).map((port, i) => (
                              <Badge
                                key={i}
                                variant="secondary"
                                className="text-[10px]"
                              >
                                {port}
                              </Badge>
                            ))}
                            {(service.ports?.length ?? 0) > 2 && (
                              <Badge variant="secondary" className="text-[10px]">
                                +{(service.ports?.length ?? 0) - 2}
                              </Badge>
                            )}
                            {!service.ports?.length && <span className="text-muted-foreground text-sm">-</span>}
                          </div>
                        </TableCell>
                      )}
                      {visibleColumns.status && (
                        <TableCell>
                          <Badge
                            variant={statusVariant}
                            className="flex items-center gap-1"
                          >
                            <StatusIcon className="h-3 w-3 fill-current" />
                            {service.status}
                          </Badge>
                        </TableCell>
                      )}
                      {visibleColumns.lastSeen && (
                        <TableCell className="text-muted-foreground text-sm">
                          {service.lastSeen ? formatRelativeTime(service.lastSeen) : '-'}
                        </TableCell>
                      )}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 p-4 border-t border-border">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="text-muted-foreground"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm text-muted-foreground px-4">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="text-muted-foreground"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
}
