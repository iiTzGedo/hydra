import { useState, useMemo } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  FolderTree,
  Search,
  Plus,
  Server,
  Boxes,
  Users,
  Eye,
  Edit,
  Trash2,
  MoreHorizontal,
  AlertTriangle,
  X,
  Loader2,
  CheckCircle2,
  Tag,
  LayoutGrid,
  LayoutList,
  SlidersHorizontal,
  Columns3,
} from 'lucide-react';
import { useGroups, useCreateGroup } from '@/api/groups';
import { GroupSummary, GroupEntityType, GroupSelectors, CreateGroupRequest } from '@/types/group';
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

interface FilterState {
  search: string;
}

type TableDensity = 'comfortable' | 'compact';
type ViewMode = 'table' | 'grid';
type GroupColumnKey = 'group' | 'types' | 'nodes' | 'services' | 'tags' | 'actions';

export default function GroupsPage() {
  useDocumentTitle('Groups');

  const [filters, setFilters] = useState<FilterState>({
    search: '',
  });
  const [page, setPage] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [tableDensity, setTableDensity] = useState<TableDensity>('comfortable');
  const [visibleColumns, setVisibleColumns] = useState<Record<GroupColumnKey, boolean>>({
    group: true,
    types: true,
    nodes: true,
    services: true,
    tags: true,
    actions: true,
  });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const limit = 20;

  const visibleColumnCount = Object.values(visibleColumns).filter(Boolean).length;

  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) params.search = filters.search;
    return params;
  }, [filters, page]);

  const { data, isLoading, error } = useGroups(queryParams);

  const stats = useMemo(() => {
    const items = data?.items ?? [];
    const nodeGroups = items.filter(g => g.types.includes('node'));
    const serviceGroups = items.filter(g => g.types.includes('service'));
    const totalNodes = items.reduce((acc, g) => acc + (g.memberCount?.nodes || 0), 0);
    const totalServices = items.reduce((acc, g) => acc + (g.memberCount?.services || 0), 0);
    return {
      totalGroups: data?.total ?? 0,
      nodeGroups: nodeGroups.length,
      serviceGroups: serviceGroups.length,
      totalMembers: totalNodes + totalServices,
    };
  }, [data]);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <TooltipProvider>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Groups</h1>
            <p className="text-muted-foreground">
              Organize infrastructure with dynamic selectors
            </p>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Group
          </Button>
        </div>

        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
        >
          <motion.div variants={staggerItemVariants}>
            <Card className="border-l-4 border-l-primary">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Total Groups</p>
                    {isLoading ? (
                      <Skeleton className="h-8 w-12 mt-1" />
                    ) : (
                      <p className="text-2xl font-bold">{stats.totalGroups}</p>
                    )}
                  </div>
                  <div className="rounded-full bg-primary/10 p-3">
                    <FolderTree className="h-5 w-5 text-primary" />
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
                    <p className="text-sm font-medium text-muted-foreground">Node Groups</p>
                    {isLoading ? (
                      <Skeleton className="h-8 w-12 mt-1" />
                    ) : (
                      <p className="text-2xl font-bold text-compute">{stats.nodeGroups}</p>
                    )}
                  </div>
                  <div className="rounded-full bg-compute/10 p-3">
                    <Server className="h-5 w-5 text-compute" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div variants={staggerItemVariants}>
            <Card className="border-l-4 border-l-network">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Service Groups</p>
                    {isLoading ? (
                      <Skeleton className="h-8 w-12 mt-1" />
                    ) : (
                      <p className="text-2xl font-bold text-network">{stats.serviceGroups}</p>
                    )}
                  </div>
                  <div className="rounded-full bg-network/10 p-3">
                    <Boxes className="h-5 w-5 text-network" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div variants={staggerItemVariants}>
            <Card className="border-l-4 border-l-iot">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Total Members</p>
                    {isLoading ? (
                      <Skeleton className="h-8 w-12 mt-1" />
                    ) : (
                      <p className="text-2xl font-bold text-iot">{stats.totalMembers}</p>
                    )}
                  </div>
                  <div className="rounded-full bg-iot/10 p-3">
                    <Users className="h-5 w-5 text-iot" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>

        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search groups by name..."
                  value={filters.search}
                  onChange={(e) => {
                    setFilters(f => ({ ...f, search: e.target.value }));
                    setPage(0);
                  }}
                  className="pl-9"
                />
              </div>

              <div className="flex items-center gap-2">
                {filters.search && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setFilters({ search: '' })}
                    className="text-muted-foreground"
                  >
                    <X className="h-4 w-4 mr-1" />
                    Clear
                  </Button>
                )}

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
                          checked={visibleColumns.group}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, group: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.group}
                        >
                          Group
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.types}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, types: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.types}
                        >
                          Types
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
                          checked={visibleColumns.services}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, services: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.services}
                        >
                          Services
                        </DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem
                          checked={visibleColumns.tags}
                          onCheckedChange={(checked) =>
                            setVisibleColumns((prev) => ({ ...prev, tags: Boolean(checked) }))
                          }
                          disabled={visibleColumnCount === 1 && visibleColumns.tags}
                        >
                          Tags
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

        {error && (
          <Card className="border-destructive">
            <CardContent className="p-8 text-center">
              <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
              <h3 className="mt-4 text-lg font-semibold">Failed to load groups</h3>
              <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
            </CardContent>
          </Card>
        )}

        {isLoading && !error && (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[250px]">Group</TableHead>
                  <TableHead>Types</TableHead>
                  <TableHead>Nodes</TableHead>
                  <TableHead>Services</TableHead>
                  <TableHead>Tags</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...Array(5)].map((_, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Skeleton className="h-9 w-9 rounded-lg" />
                        <div className="space-y-1">
                          <Skeleton className="h-4 w-32" />
                          <Skeleton className="h-3 w-24" />
                        </div>
                      </div>
                    </TableCell>
                    <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                    <TableCell><Skeleton className="h-6 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-8 w-8 rounded" /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}

        {!isLoading && !error && !data?.items?.length && (
          <Card>
            <CardContent className="p-8 text-center">
              <FolderTree className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">No groups found</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {filters.search
                  ? 'Try adjusting your search'
                  : 'Create your first group to organize infrastructure'}
              </p>
              <div className="flex justify-center gap-2 mt-4">
                {filters.search && (
                  <Button variant="outline" onClick={() => setFilters({ search: '' })}>
                    Clear Search
                  </Button>
                )}
                <Button onClick={() => setShowCreateModal(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Group
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

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
                    Showing {data.items.length} of {data.total} groups
                  </span>
                </div>
                <Table className={cn(tableDensity === 'compact' && 'table-compact')}>
                  <TableHeader>
                    <TableRow>
                      {visibleColumns.group && (
                        <TableHead className="w-[250px] text-muted-foreground">Group</TableHead>
                      )}
                      {visibleColumns.types && (
                        <TableHead className="text-muted-foreground">Types</TableHead>
                      )}
                      {visibleColumns.nodes && (
                        <TableHead className="text-muted-foreground">Nodes</TableHead>
                      )}
                      {visibleColumns.services && (
                        <TableHead className="text-muted-foreground">Services</TableHead>
                      )}
                      {visibleColumns.tags && (
                        <TableHead className="text-muted-foreground">Tags</TableHead>
                      )}
                      {visibleColumns.actions && (
                        <TableHead className="w-[50px] text-muted-foreground"></TableHead>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((group) => (
                      <GroupRow key={group.id} group={group} visibleColumns={visibleColumns} />
                    ))}
                  </TableBody>
                </Table>

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
                    Showing {data.items.length} of {data.total} groups
                  </span>
                </div>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {data.items.map((group) => (
                    <GroupGridCard key={group.id} group={group} />
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

        <CreateGroupModal
          open={showCreateModal}
          onOpenChange={setShowCreateModal}
        />
      </div>
    </TooltipProvider>
  );
}

type GroupListItem = GroupSummary & { id: string };

function GroupGridCard({ group }: { group: GroupListItem }) {
  return (
    <motion.div variants={staggerItemVariants}>
      <Card className="group hover:border-primary/50 transition-all">
        <CardContent className="p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-primary/10 p-2">
                <FolderTree className="h-5 w-5 text-primary" />
              </div>
              <div className="min-w-0 flex-1">
                <Link
                  to={`${ROUTES.GROUPS}/${encodeURIComponent(group.groupId)}`}
                  className="font-medium hover:text-primary transition-colors block truncate"
                >
                  {group.name}
                </Link>
                <span className="text-xs text-muted-foreground font-mono truncate block">
                  {group.groupId}
                </span>
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
                  <Link to={`${ROUTES.GROUPS}/${encodeURIComponent(group.groupId)}`}>
                    <Eye className="h-4 w-4 mr-2" />
                    View Members
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to={`${ROUTES.GROUPS}/${encodeURIComponent(group.groupId)}?edit=1`}>
                    <Edit className="h-4 w-4 mr-2" />
                    Edit Group
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild className="text-destructive">
                  <Link to={`${ROUTES.GROUPS}/${encodeURIComponent(group.groupId)}?delete=1`}>
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className="flex gap-1 mb-3">
            {group.types.includes('node') && (
              <Badge variant="secondary" className="bg-compute/10 text-compute">
                <Server className="h-3 w-3 mr-1" />
                Node
              </Badge>
            )}
            {group.types.includes('service') && (
              <Badge variant="secondary" className="bg-network/10 text-network">
                <Boxes className="h-3 w-3 mr-1" />
                Service
              </Badge>
            )}
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Nodes</span>
              <Badge variant="outline" className="font-mono">
                {group.memberCount?.nodes || 0}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Services</span>
              <Badge variant="outline" className="font-mono">
                {group.memberCount?.services || 0}
              </Badge>
            </div>
            {group.tags && group.tags.length > 0 && (
              <div className="flex items-center justify-between pt-2 border-t">
                <span className="text-muted-foreground">Tags</span>
                <div className="flex items-center gap-1 flex-wrap justify-end">
                  {group.tags.slice(0, 2).map((tag, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                  {group.tags.length > 2 && (
                    <Badge variant="secondary" className="text-xs">
                      +{group.tags.length - 2}
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function GroupRow({
  group,
  visibleColumns,
}: {
  group: GroupListItem;
  visibleColumns: Record<GroupColumnKey, boolean>;
}) {
  return (
    <motion.tr
      variants={staggerItemVariants}
      className="group hover:bg-muted/50 transition-colors"
    >
      {visibleColumns.group && (
        <TableCell>
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2">
              <FolderTree className="h-5 w-5 text-primary" />
            </div>
            <div className="min-w-0">
              <Link
                to={`${ROUTES.GROUPS}/${encodeURIComponent(group.groupId)}`}
                className="font-medium hover:text-primary transition-colors block truncate"
              >
                {group.name}
              </Link>
              <span className="text-xs text-muted-foreground font-mono truncate block">
                {group.groupId}
              </span>
            </div>
          </div>
        </TableCell>
      )}

      {visibleColumns.types && (
        <TableCell>
          <div className="flex gap-1">
            {group.types.includes('node') && (
              <Badge variant="secondary" className="bg-compute/10 text-compute">
                <Server className="h-3 w-3 mr-1" />
                Node
              </Badge>
            )}
            {group.types.includes('service') && (
              <Badge variant="secondary" className="bg-network/10 text-network">
                <Boxes className="h-3 w-3 mr-1" />
                Service
              </Badge>
            )}
          </div>
        </TableCell>
      )}

      {visibleColumns.nodes && (
        <TableCell>
          <Badge variant="outline" className="font-mono">
            {group.memberCount?.nodes || 0}
          </Badge>
        </TableCell>
      )}

      {visibleColumns.services && (
        <TableCell>
          <Badge variant="outline" className="font-mono">
            {group.memberCount?.services || 0}
          </Badge>
        </TableCell>
      )}

      {visibleColumns.tags && (
        <TableCell>
          {group.tags && group.tags.length > 0 ? (
            <div className="flex items-center gap-1 flex-wrap">
              {group.tags.slice(0, 2).map((tag, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {group.tags.length > 2 && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="secondary" className="text-xs cursor-help">
                      +{group.tags.length - 2}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">{group.tags.slice(2).join(', ')}</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          ) : (
            <span className="text-muted-foreground text-sm">—</span>
          )}
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
                <Link to={`${ROUTES.GROUPS}/${encodeURIComponent(group.groupId)}`}>
                  <Eye className="h-4 w-4 mr-2" />
                  View Members
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to={`${ROUTES.GROUPS}/${encodeURIComponent(group.groupId)}?edit=1`}>
                  <Edit className="h-4 w-4 mr-2" />
                  Edit Group
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild className="text-destructive">
                <Link to={`${ROUTES.GROUPS}/${encodeURIComponent(group.groupId)}?delete=1`}>
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

function CreateGroupModal({
  open,
  onOpenChange
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createGroupMutation = useCreateGroup();
  const [formError, setFormError] = useState<string | null>(null);
  const [createdGroupId, setCreatedGroupId] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    groupId: '',
    name: '',
    description: '',
    tags: '',
    types: ['node'] as GroupEntityType[],
  });

  const [selectors, setSelectors] = useState({
    ids: '',
    networks: '',
    statuses: '',
    kinds: '',
    runtimes: '',
    tags: '',
    tagMode: 'isAny' as 'isAny' | 'isAll',
  });

  const parseList = (value: string) =>
    value.split(',').map(item => item.trim()).filter(Boolean);

  const resetForm = () => {
    setFormData({
      groupId: '',
      name: '',
      description: '',
      tags: '',
      types: ['node'],
    });
    setSelectors({
      ids: '',
      networks: '',
      statuses: '',
      kinds: '',
      runtimes: '',
      tags: '',
      tagMode: 'isAny',
    });
    setFormError(null);
    setCreatedGroupId(null);
  };

  const toggleType = (type: GroupEntityType) => {
    setFormData(f => ({
      ...f,
      types: f.types.includes(type)
        ? f.types.filter(t => t !== type)
        : [...f.types, type]
    }));
  };

  const buildSelectors = (): GroupSelectors => {
    const result: GroupSelectors = {};
    const ids = parseList(selectors.ids);
    if (ids.length) result.id = { isAll: ids };
    const networks = parseList(selectors.networks);
    if (networks.length) result.network = { isAny: networks };
    const statuses = parseList(selectors.statuses);
    if (statuses.length) result.status = { isAny: statuses };
    const kinds = parseList(selectors.kinds);
    if (kinds.length) result.kind = { isAny: kinds };
    const runtimes = parseList(selectors.runtimes);
    if (runtimes.length) result.runtime = { isAny: runtimes };
    const tagValues = parseList(selectors.tags);
    if (tagValues.length) {
      result.tags = selectors.tagMode === 'isAll' ? { isAll: tagValues } : { isAny: tagValues };
    }
    return result;
  };

  const hasSelectors = () => Object.keys(buildSelectors()).length > 0;

  const handleCreate = async () => {
    setFormError(null);

    if (!formData.groupId.trim()) {
      setFormError('Group ID is required');
      return;
    }
    if (!formData.name.trim()) {
      setFormError('Name is required');
      return;
    }
    if (!formData.types.length) {
      setFormError('Select at least one entity type');
      return;
    }
    if (!hasSelectors()) {
      setFormError('At least one selector is required');
      return;
    }

    try {
      const request: CreateGroupRequest = {
        groupId: formData.groupId.trim(),
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        types: formData.types,
        selectors: buildSelectors(),
        tags: parseList(formData.tags),
      };

      await createGroupMutation.mutateAsync(request);
      setCreatedGroupId(formData.groupId.trim());
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setFormError(error.response?.data?.detail || 'Failed to create group');
    }
  };

  const handleClose = () => {
    onOpenChange(false);
    resetForm();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        {createdGroupId ? (
          <div className="text-center py-6">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-success/10">
              <CheckCircle2 className="h-8 w-8 text-success" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Group Created!</h3>
            <p className="text-sm text-muted-foreground mb-6">
              Your group <span className="font-mono text-foreground">{createdGroupId}</span> has been created successfully.
            </p>
            <div className="flex flex-col gap-3">
              <Button asChild>
                <Link to={`${ROUTES.GROUPS}/${createdGroupId}`}>
                  <FolderTree className="h-4 w-4 mr-2" />
                  View Group
                </Link>
              </Button>
              <Button variant="outline" onClick={handleClose}>
                Close
              </Button>
            </div>
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Create Group</DialogTitle>
              <DialogDescription>
                Create a new group with dynamic selectors to organize your infrastructure
              </DialogDescription>
            </DialogHeader>

            {formError && (
              <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                {formError}
              </div>
            )}

            <div className="grid gap-4">
              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Basic Information
                </h4>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="groupId">
                      Group ID <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="groupId"
                      value={formData.groupId}
                      onChange={(e) => setFormData(f => ({ ...f, groupId: e.target.value }))}
                      placeholder="e.g., production-servers"
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
                      placeholder="e.g., Production Servers"
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

                <div className="space-y-2">
                  <Label htmlFor="tags">Tags</Label>
                  <Input
                    id="tags"
                    value={formData.tags}
                    onChange={(e) => setFormData(f => ({ ...f, tags: e.target.value }))}
                    placeholder="Comma-separated tags"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Entity Types</Label>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant={formData.types.includes('node') ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => toggleType('node')}
                    >
                      <Server className="h-4 w-4 mr-1" />
                      Nodes
                    </Button>
                    <Button
                      type="button"
                      variant={formData.types.includes('service') ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => toggleType('service')}
                    >
                      <Boxes className="h-4 w-4 mr-1" />
                      Services
                    </Button>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Selectors
                </h4>
                <p className="text-xs text-muted-foreground">
                  Add one or more selectors. Each uses comma-separated values.
                </p>

                <div className="space-y-2">
                  <Label>Node/Service IDs</Label>
                  <Input
                    value={selectors.ids}
                    onChange={(e) => setSelectors(s => ({ ...s, ids: e.target.value }))}
                    placeholder="e.g., node-01, node-02"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Networks</Label>
                  <Input
                    value={selectors.networks}
                    onChange={(e) => setSelectors(s => ({ ...s, networks: e.target.value }))}
                    placeholder="e.g., prod-vlan-10"
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Statuses</Label>
                    <Input
                      value={selectors.statuses}
                      onChange={(e) => setSelectors(s => ({ ...s, statuses: e.target.value }))}
                      placeholder="e.g., active"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Kinds</Label>
                    <Input
                      value={selectors.kinds}
                      onChange={(e) => setSelectors(s => ({ ...s, kinds: e.target.value }))}
                      placeholder="e.g., vm, router"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Runtimes</Label>
                  <Input
                    value={selectors.runtimes}
                    onChange={(e) => setSelectors(s => ({ ...s, runtimes: e.target.value }))}
                    placeholder="e.g., docker, kubernetes"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Tags Selector</Label>
                  <div className="flex gap-2">
                    <Input
                      value={selectors.tags}
                      onChange={(e) => setSelectors(s => ({ ...s, tags: e.target.value }))}
                      placeholder="e.g., critical, edge"
                      className="flex-1"
                    />
                    <Select
                      value={selectors.tagMode}
                      onValueChange={(value) => setSelectors(s => ({ ...s, tagMode: value as 'isAny' | 'isAll' }))}
                    >
                      <SelectTrigger className="w-[120px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="isAny">Match any</SelectItem>
                        <SelectItem value="isAll">Match all</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={createGroupMutation.isPending}
              >
                {createGroupMutation.isPending && (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                )}
                Create Group
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
