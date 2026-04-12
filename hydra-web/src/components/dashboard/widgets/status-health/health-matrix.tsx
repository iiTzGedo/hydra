/**
 * HealthMatrixWidget -- tabular view where rows are entities, columns
 * are health checks, and cells are colour-coded status dots.
 *
 * Data shape:
 *   {
 *     rows: { id: string; name: string }[];
 *     columns: string[];
 *     cells: Record<string, Record<string, string>>;
 *       // cells[rowId][columnName] = status string
 *   }
 *
 * Cell status mapping:
 *   ok / healthy / pass  -> green
 *   warn / degraded      -> yellow
 *   fail / error / down  -> red
 *   unknown (default)    -> gray
 */

import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface HealthRow {
  id: string;
  name: string;
}

interface HealthMatrixData {
  rows: HealthRow[];
  columns: string[];
  cells: Record<string, Record<string, string>>;
}

const CELL_COLORS: Record<string, string> = {
  ok: 'bg-emerald-500',
  healthy: 'bg-emerald-500',
  pass: 'bg-emerald-500',
  up: 'bg-emerald-500',
  warn: 'bg-yellow-500',
  warning: 'bg-yellow-500',
  degraded: 'bg-yellow-500',
  fail: 'bg-red-500',
  error: 'bg-red-500',
  down: 'bg-red-500',
  critical: 'bg-red-500',
};

function cellColor(status: string | undefined): string {
  if (!status) return 'bg-gray-400';
  return CELL_COLORS[status.toLowerCase()] ?? 'bg-gray-400';
}

export function HealthMatrixWidget({
  data,
  config: _config,
  isLoading,
  error,
}: WidgetComponentProps<HealthMatrixData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const rows = data?.rows ?? [];
  const columns = data?.columns ?? [];
  const cells = data?.cells ?? {};

  if (rows.length === 0 || columns.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No health data
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-1">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 bg-background px-2 py-1 text-left text-xs font-medium text-muted-foreground">
              Entity
            </th>
            {columns.map((col) => (
              <th
                key={col}
                className="px-2 py-1 text-center text-xs font-medium text-muted-foreground"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-border/40">
              <td className="sticky left-0 bg-background px-2 py-1.5 text-foreground whitespace-nowrap">
                {row.name}
              </td>
              {columns.map((col) => {
                const status = cells[row.id]?.[col];
                return (
                  <td key={col} className="px-2 py-1.5 text-center">
                    <span
                      className={`inline-block h-3 w-3 rounded-full ${cellColor(status)}`}
                      title={status ?? 'unknown'}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
