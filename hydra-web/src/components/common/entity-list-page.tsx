import { ReactNode, useMemo } from 'react';
import { motion } from 'framer-motion';
import { LucideIcon, AlertTriangle, SlidersHorizontal, Columns3 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Pagination } from '@/components/ui/pagination';
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
  TooltipProvider,
} from '@/components/ui/tooltip';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { cn } from '@/lib/utils';
import { ViewModeToggle, type ViewMode } from './view-mode-toggle';

// ─── Types ───────────────────────────────────────────────────────────────────

export type TableDensity = 'comfortable' | 'compact';

export interface StatCard {
  label: string;
  value: number | undefined;
  icon: LucideIcon;
  color: string;
}

export interface ColumnConfig {
  key: string;
  label: string;
}

export interface EntityListPageProps<T> {
  // Page header
  title: string;
  subtitle: string;
  headerAction?: ReactNode;

  // Statistics
  stats?: StatCard[];

  // Data
  items: T[];
  isLoading: boolean;
  error: unknown;
  onRetry?: () => void;

  // Filters (rendered externally — slot for any filter bar content)
  filterBar?: ReactNode;

  // View mode
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;

  // Table controls
  tableDensity: TableDensity;
  onTableDensityChange: (density: TableDensity) => void;
  columns: ColumnConfig[];
  visibleColumns: Record<string, boolean>;
  onVisibleColumnsChange: (columns: Record<string, boolean>) => void;

  // Pagination (optional)
  pagination?: {
    page: number;
    totalPages: number;
    onPageChange: (page: number) => void;
  };

  // Empty state
  emptyIcon: LucideIcon;
  emptyTitle: string;
  emptyDescription: string;
  emptyActions?: ReactNode;

  // Rendering
  renderGridCard: (item: T, index: number) => ReactNode;
  renderTableHeader: (visibleColumns: Record<string, boolean>) => ReactNode;
  renderTableRow: (item: T, visibleColumns: Record<string, boolean>, index: number) => ReactNode;
  renderLoadingSkeleton?: () => ReactNode;

  // Grid layout
  gridClassName?: string;
}

// ─── Stat Card ───────────────────────────────────────────────────────────────

function StatCardItem({ stat, isLoading }: { stat: StatCard; isLoading: boolean }) {
  const Icon = stat.icon;
  return (
    <motion.div variants={staggerItemVariants}>
      <Card className={`border-l-4 border-l-${stat.color}`}>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
              {isLoading ? (
                <Skeleton className="h-8 w-12 mt-1" />
              ) : (
                <p className={cn('text-2xl font-bold', `text-${stat.color}`)}>{stat.value ?? 0}</p>
              )}
            </div>
            <div className={cn('rounded-full p-3', `bg-${stat.color}/10`)}>
              <Icon className={cn('h-5 w-5', `text-${stat.color}`)} />
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// ─── Table Controls ──────────────────────────────────────────────────────────

function TableControls({
  tableDensity,
  onTableDensityChange,
  columns,
  visibleColumns,
  onVisibleColumnsChange,
}: {
  tableDensity: TableDensity;
  onTableDensityChange: (density: TableDensity) => void;
  columns: ColumnConfig[];
  visibleColumns: Record<string, boolean>;
  onVisibleColumnsChange: (columns: Record<string, boolean>) => void;
}) {
  const visibleColumnCount = useMemo(
    () => Object.values(visibleColumns).filter(Boolean).length,
    [visibleColumns]
  );

  return (
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
            onValueChange={(value) => onTableDensityChange(value as TableDensity)}
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
          {columns.map((col) => (
            <DropdownMenuCheckboxItem
              key={col.key}
              checked={visibleColumns[col.key]}
              onCheckedChange={(checked) =>
                onVisibleColumnsChange({ ...visibleColumns, [col.key]: Boolean(checked) })
              }
              disabled={visibleColumnCount === 1 && visibleColumns[col.key]}
            >
              {col.label}
            </DropdownMenuCheckboxItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}

// ─── Default Loading Skeleton ────────────────────────────────────────────────

function DefaultLoadingSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {[...Array(8)].map((_, i) => (
        <Card key={i}>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-3">
              <Skeleton className="h-9 w-9 rounded-lg" />
              <div className="space-y-1 flex-1">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-24" />
              </div>
            </div>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function EntityListPage<T>({
  title,
  subtitle,
  headerAction,
  stats,
  items,
  isLoading,
  error,
  onRetry,
  filterBar,
  viewMode,
  onViewModeChange,
  tableDensity,
  onTableDensityChange,
  columns,
  visibleColumns,
  onVisibleColumnsChange,
  pagination,
  emptyIcon: EmptyIcon,
  emptyTitle,
  emptyDescription,
  emptyActions,
  renderGridCard,
  renderTableHeader,
  renderTableRow,
  renderLoadingSkeleton,
  gridClassName = 'grid gap-4 md:grid-cols-2 lg:grid-cols-3',
}: EntityListPageProps<T>) {
  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
            <p className="text-muted-foreground">{subtitle}</p>
          </div>
          {headerAction}
        </div>

        {/* Statistics Cards */}
        {stats && stats.length > 0 && (
          <motion.div
            variants={staggerContainerVariants}
            initial="hidden"
            animate="visible"
            className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
          >
            {stats.map((stat) => (
              <StatCardItem key={stat.label} stat={stat} isLoading={isLoading} />
            ))}
          </motion.div>
        )}

        {/* Filter Bar + Table Controls */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
              <div className="flex-1">{filterBar}</div>
              <div className="flex flex-wrap items-center gap-2">
                <ViewModeToggle viewMode={viewMode} onViewModeChange={onViewModeChange} />
                {viewMode === 'table' && (
                  <TableControls
                    tableDensity={tableDensity}
                    onTableDensityChange={onTableDensityChange}
                    columns={columns}
                    visibleColumns={visibleColumns}
                    onVisibleColumnsChange={onVisibleColumnsChange}
                  />
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Error State */}
        {error && !isLoading && (
          <Card className="border-destructive">
            <CardContent className="p-8 text-center">
              <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
              <h3 className="mt-4 text-lg font-semibold">Failed to load {title.toLowerCase()}</h3>
              <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
              {onRetry && (
                <Button variant="outline" className="mt-4" onClick={onRetry}>
                  Retry
                </Button>
              )}
            </CardContent>
          </Card>
        )}

        {/* Loading State */}
        {isLoading && !error && (
          renderLoadingSkeleton ? renderLoadingSkeleton() : <DefaultLoadingSkeleton />
        )}

        {/* Empty State */}
        {!isLoading && !error && items.length === 0 && (
          <Card>
            <CardContent className="p-8 text-center">
              <EmptyIcon className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">{emptyTitle}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{emptyDescription}</p>
              {emptyActions && (
                <div className="flex justify-center gap-2 mt-4">{emptyActions}</div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Grid View */}
        {!isLoading && !error && items.length > 0 && viewMode === 'grid' && (
          <>
            <motion.div
              variants={staggerContainerVariants}
              initial="hidden"
              animate="visible"
              className={gridClassName}
            >
              {items.map((item, index) => (
                <motion.div key={index} variants={staggerItemVariants}>
                  {renderGridCard(item, index)}
                </motion.div>
              ))}
            </motion.div>
            {pagination && (
              <Pagination
                page={pagination.page}
                totalPages={pagination.totalPages}
                onPageChange={pagination.onPageChange}
                showBorder={false}
              />
            )}
          </>
        )}

        {/* Table View */}
        {!isLoading && !error && items.length > 0 && viewMode === 'table' && (
          <Card>
            <div className="overflow-x-auto">
              <table className={cn(
                'w-full caption-bottom text-sm',
                tableDensity === 'compact' && 'table-compact'
              )}>
                <thead className="[&_tr]:border-b">
                  {renderTableHeader(visibleColumns)}
                </thead>
                <tbody className="[&_tr:last-child]:border-0">
                  {items.map((item, index) => renderTableRow(item, visibleColumns, index))}
                </tbody>
              </table>
            </div>
            {pagination && (
              <Pagination
                page={pagination.page}
                totalPages={pagination.totalPages}
                onPageChange={pagination.onPageChange}
              />
            )}
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
}
