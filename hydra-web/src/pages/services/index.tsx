import { useState, useMemo, useEffect, useCallback } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { Link, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Boxes,
  Play,
  Square,
  AlertTriangle,
  AlertCircle,
  RotateCcw,
  HelpCircle,
  Server,
  CheckCircle2,
  LayoutGrid,
  LayoutList,
  SlidersHorizontal,
  Columns3,
  MoreHorizontal,
  Eye,
} from 'lucide-react';
import { useServices } from '@/api/services';
import { useCreateCommand } from '@/api/commands';
import { FilterBar, type FilterConfig } from '@/components/common/filter-bar';
import { ConfirmDialog } from '@/components/modals/confirm-dialog';
import { DropdownMenuItem } from '@/components/ui/dropdown-menu';
import { ServiceStatus } from '@/types/service';
import { ROUTES, SERVICE_RUNTIME_LABELS, SERVICE_RUNTIME_COLORS } from '@/lib/constants';
import { cn, formatRelativeTime } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api-client';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Pagination } from '@/components/ui/pagination';
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


const statusIcons: Record<ServiceStatus, typeof Play> = {
  running: Play,
  stopped: Square,
  paused: Square,
  exited: Square,
  failed: AlertCircle,
  restarting: RotateCcw,
  unknown: HelpCircle,
};

interface FilterState {
  search: string;
  runtime: string;
  status: string;
  nodeId: string;
  [key: string]: string;
}

const SERVICE_FILTER_CONFIG: FilterConfig[] = [
  {
    type: 'search',
    key: 'search',
    placeholder: 'Search by name or image...',
    className: 'flex-1',
  },
  {
    type: 'select',
    key: 'runtime',
    label: 'Runtimes',
    options: [
      { value: 'docker', label: 'Docker' },
      { value: 'podman', label: 'Podman' },
      { value: 'kubernetes', label: 'Kubernetes' },
      { value: 'systemd', label: 'Systemd' },
    ],
    allLabel: 'All Runtimes',
    className: 'w-[140px]',
  },
  {
    type: 'select',
    key: 'status',
    label: 'Status',
    options: [
      { value: 'running', label: 'Running' },
      { value: 'stopped', label: 'Stopped' },
      { value: 'restarting', label: 'Restarting' },
      { value: 'failed', label: 'Error' },
    ],
    allLabel: 'All Status',
    className: 'w-[130px]',
  },
];

type TableDensity = 'comfortable' | 'compact';
type ViewMode = 'table' | 'grid';
type ServiceColumnKey = 'service' | 'host' | 'runtime' | 'version' | 'status' | 'lastSeen';

export default function ServicesPage() {
  useDocumentTitle('Service Explorer');

  const [searchParams] = useSearchParams();
  const nodeIdParam = searchParams.get('nodeId') || '';
  const runtimeParam = searchParams.get('runtime') || '';
  const statusParam = searchParams.get('status') || '';

  const [filters, setFilters] = useState<FilterState>({
    search: '',
    runtime: runtimeParam || 'all',
    status: statusParam || 'all',
    nodeId: nodeIdParam,
  });
  const [page, setPage] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [tableDensity, setTableDensity] = useState<TableDensity>('comfortable');
  const [visibleColumns, setVisibleColumns] = useState<Record<ServiceColumnKey, boolean>>({
    service: true,
    host: true,
    runtime: true,
    version: true,
    status: true,
    lastSeen: true,
  });
  const limit = 20;

  // Service action state
  const [actionService, setActionService] = useState<{ serviceId: string; nodeId: string; name: string; action: 'start' | 'stop' | 'restart' } | null>(null);

  const createCommandMutation = useCreateCommand();

  const handleServiceAction = useCallback(async () => {
    if (!actionService) return;
    try {
      await createCommandMutation.mutateAsync({
        registryId: `reg::service::${actionService.action}`,
        target: {
          nodeId: actionService.nodeId,
          serviceId: actionService.serviceId,
        },
      });
      toast.success(`Command queued: ${actionService.action} ${actionService.name}`);
      setActionService(null);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, `Failed to ${actionService.action} service`));
    }
  }, [actionService, createCommandMutation]);

  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) params.search = filters.search;
    if (filters.runtime !== 'all') params.runtime = filters.runtime;
    if (filters.status !== 'all') params.status = filters.status;
    if (filters.nodeId) params.nodeId = filters.nodeId;
    return params;
  }, [filters, page]);

  const { data, isLoading, error } = useServices(queryParams);

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

  // Sync URL params with filter state
  useEffect(() => {
    const updates: Partial<FilterState> = {};
    
    if (nodeIdParam && nodeIdParam !== filters.nodeId) {
      updates.nodeId = nodeIdParam;
    }
    if (runtimeParam && runtimeParam !== filters.runtime) {
      updates.runtime = runtimeParam;
    }
    if (statusParam && statusParam !== filters.status) {
      updates.status = statusParam;
    }
    
    if (Object.keys(updates).length > 0) {
      setFilters((prev) => ({ ...prev, ...updates } as FilterState));
      setPage(0);
    }
  }, [nodeIdParam, runtimeParam, statusParam, filters.nodeId, filters.runtime, filters.status]);

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <PageHeaderLayout
          title="Service Explorer"
          subtitle={`${data?.items?.length ?? 0} of ${data?.total ?? 0} services`}
          showBackButton={false}
        />

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

                <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <FilterBar
                filters={filters}
                onFilterChange={(key, value) => {
                  setFilters(f => ({ ...f, [key]: value }));
                  setPage(0);
                }}
                onClearAll={() => {
                  clearFilters();
                }}
                config={SERVICE_FILTER_CONFIG}
                className="flex-1"
              />

              <div className="flex items-center gap-2">
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
                          checked={visibleColumns.version}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, version: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.version}
                        >
                          Version
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

                {error && (
          <Card className="border-destructive/40">
            <CardContent className="p-8 text-center">
              <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">Failed to load services</h3>
              <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
            </CardContent>
          </Card>
        )}

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
                  {visibleColumns.version && (
                    <TableHead className="text-muted-foreground">Version</TableHead>
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
                    {visibleColumns.version && (
                      <TableCell><Skeleton className="h-4 w-20 bg-muted" /></TableCell>
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
                  {visibleColumns.version && (
                    <TableHead className="text-muted-foreground">Version</TableHead>
                  )}
                  {visibleColumns.status && (
                    <TableHead className="text-muted-foreground">Status</TableHead>
                  )}
                  {visibleColumns.lastSeen && (
                    <TableHead className="text-muted-foreground">Last Seen</TableHead>
                  )}
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((service) => {
                  const StatusIcon = statusIcons[service.status] || HelpCircle;
                  const runtimeColor = SERVICE_RUNTIME_COLORS[service.runtime]?.text || 'text-muted-foreground';
                  const runtimeLabel = SERVICE_RUNTIME_LABELS[service.runtime] || service.runtime;
                  const statusVariant =
                    service.status === 'running'
                      ? 'success'
                      : service.status === 'restarting'
                        ? 'warning'
                        : service.status === 'failed'
                          ? 'destructive'
                          : service.status === 'stopped' || service.status === 'exited' || service.status === 'paused'
                            ? 'secondary'
                            : 'outline';

                  return (
                    <TableRow key={service.serviceId} className="group border-border hover:bg-muted/60">
                      {visibleColumns.service && (
                        <TableCell>
                          <Link to={`${ROUTES.SERVICES}/${encodeURIComponent(service.serviceId)}`} className="flex flex-col">
                            <span className="text-foreground font-medium hover:text-primary">
                              {service.displayName || service.name}
                            </span>
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
                      {visibleColumns.version && (
                        <TableCell>
                          <span className="text-muted-foreground text-sm">
                            {service.version ? `v${service.version}` : '-'}
                          </span>
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
                              <Link to={`${ROUTES.SERVICES}/${encodeURIComponent(service.serviceId)}`}>
                                <Eye className="h-4 w-4 mr-2" />
                                View Details
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => setActionService({
                                serviceId: service.serviceId,
                                nodeId: service.nodeId,
                                name: service.displayName || service.name,
                                action: 'start',
                              })}
                              disabled={service.status === 'running'}
                            >
                              <Play className="h-4 w-4 mr-2" />
                              Start
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setActionService({
                                serviceId: service.serviceId,
                                nodeId: service.nodeId,
                                name: service.displayName || service.name,
                                action: 'stop',
                              })}
                              disabled={service.status !== 'running'}
                            >
                              <Square className="h-4 w-4 mr-2" />
                              Stop
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setActionService({
                                serviceId: service.serviceId,
                                nodeId: service.nodeId,
                                name: service.displayName || service.name,
                                action: 'restart',
                              })}
                            >
                              <RotateCcw className="h-4 w-4 mr-2" />
                              Restart
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

                        <Pagination
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </Card>
        )}

        <ConfirmDialog
          open={!!actionService}
          onOpenChange={(open) => !open && setActionService(null)}
          title={`${actionService?.action.charAt(0).toUpperCase()}${actionService?.action.slice(1)} Service`}
          description={`Are you sure you want to ${actionService?.action} "${actionService?.name}"? This will queue the command to be executed on the host node.`}
          confirmLabel={actionService?.action.charAt(0).toUpperCase() + (actionService?.action.slice(1) || '')}
          variant="default"
          onConfirm={handleServiceAction}
          isLoading={createCommandMutation.isPending}
        />
      </div>
    </TooltipProvider>
  );
}
