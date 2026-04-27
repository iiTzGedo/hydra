/**
 * EntityTableWidget
 *
 * Renders a sortable HTML table with alternating row backgrounds.
 * Columns default to the keys of the first data item when not specified
 * in the widget config. Client-side sorting by clicking column headers.
 *
 * Data binding:
 *   source: hydra::nodes | hydra::services | hydra::networks | hydra::groups
 *   endpoint: /nodes | /services | /networks | /groups
 *
 * Accepts two data shapes:
 *   1. Envelope: { items: Record[], total?: number } — explicit shape
 *   2. Raw array: Record[] — unwrapped API response (auto-normalized)
 */

import { useState, useMemo } from 'react';
import { Database, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface EntityTableData {
  items: Record<string, unknown>[];
  total?: number;
}

interface EntityTableConfig extends Record<string, unknown> {
  entityType?: string;
  pageSize?: number;
  columns?: string[];
}

/**
 * Normalize incoming data to EntityTableData envelope.
 *
 * Handles:
 * - Already-shaped envelope: { items: [...], total?: N }
 * - Raw array from API: [...] → wrapped into { items: [...], total: N }
 * - null / undefined → null
 */
function normalizeEntityTableData(
  raw: unknown,
): EntityTableData | null {
  if (raw == null) return null;

  // Already envelope-shaped
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.items)) {
      return {
        items: obj.items as Record<string, unknown>[],
        total: typeof obj.total === 'number' ? obj.total : (obj.items as unknown[]).length,
      };
    }
  }

  // Raw array from API
  if (Array.isArray(raw)) {
    return {
      items: raw as Record<string, unknown>[],
      total: raw.length,
    };
  }

  return null;
}

type SortDirection = 'asc' | 'desc';

interface SortState {
  column: string;
  direction: SortDirection;
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return '--';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function formatColumnHeader(key: string): string {
  return key
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function EntityTableWidget({
  data: rawData,
  config,
  isLoading,
  error,
}: WidgetComponentProps<unknown, EntityTableConfig>) {
  const [sort, setSort] = useState<SortState | null>(null);
  const data = useMemo(() => normalizeEntityTableData(rawData), [rawData]);

  const typedConfig = config as EntityTableConfig;
  const pageSize = typedConfig.pageSize ?? 20;

  const columns = useMemo(() => {
    if (typedConfig.columns && typedConfig.columns.length > 0) {
      return typedConfig.columns;
    }
    if (data?.items && data.items.length > 0) {
      return Object.keys(data.items[0]);
    }
    return [];
  }, [typedConfig.columns, data]);

  const sortedItems = useMemo(() => {
    if (!data?.items) return [];
    const items = data.items.slice(0, pageSize);

    if (!sort) return items;

    return [...items].sort((a, b) => {
      const aVal = a[sort.column];
      const bVal = b[sort.column];

      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      let cmp = 0;
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        cmp = aVal - bVal;
      } else {
        cmp = String(aVal).localeCompare(String(bVal));
      }

      return sort.direction === 'asc' ? cmp : -cmp;
    });
  }, [data, sort, pageSize]);

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Database className="h-5 w-5" />
        <div className="text-sm">Configure a data source</div>
      </div>
    );
  }

  if (!data.items || data.items.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Database className="h-5 w-5" />
        <div className="text-sm">No data available</div>
      </div>
    );
  }

  const handleSort = (column: string) => {
    setSort((prev) => {
      if (prev?.column === column) {
        return prev.direction === 'asc'
          ? { column, direction: 'desc' }
          : null;
      }
      return { column, direction: 'asc' };
    });
  };

  const getSortIcon = (column: string) => {
    if (sort?.column !== column) {
      return <ArrowUpDown className="h-3 w-3 opacity-40" />;
    }
    return sort.direction === 'asc' ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    );
  };

  return (
    <div className="flex h-full flex-col gap-2">
      {(typedConfig.entityType || data.total !== undefined) && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          {typedConfig.entityType && (
            <span className="font-medium capitalize">{typedConfig.entityType}</span>
          )}
          {data.total !== undefined && (
            <span>{data.total} total</span>
          )}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto rounded-md border border-border/60">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="cursor-pointer select-none whitespace-nowrap px-3 py-2 text-left text-xs font-medium text-muted-foreground hover:text-foreground"
                  onClick={() => handleSort(col)}
                >
                  <div className="flex items-center gap-1">
                    {formatColumnHeader(col)}
                    {getSortIcon(col)}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedItems.map((item, rowIdx) => (
              <tr
                key={rowIdx}
                className={
                  rowIdx % 2 === 0
                    ? 'bg-background'
                    : 'bg-muted/30'
                }
              >
                {columns.map((col) => (
                  <td
                    key={col}
                    className="whitespace-nowrap px-3 py-1.5 text-sm"
                  >
                    {formatCellValue(item[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
