import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Button } from './button';
import { Badge } from './badge';

export interface ResponsiveColumn<T> {
  key: string;
  header: string;
  cell: (item: T) => React.ReactNode;
  className?: string;
  priority?: 'high' | 'medium' | 'low'; // high = always show, low = hide on mobile
}

interface ResponsiveTableProps<T> {
  data: T[];
  columns: ResponsiveColumn<T>[];
  keyExtractor: (item: T) => string;
  onRowClick?: (item: T) => void;
  isLoading?: boolean;
  emptyState?: React.ReactNode;
  className?: string;
}

interface MobileCardProps<T> {
  item: T;
  columns: ResponsiveColumn<T>[];
  onClick?: () => void;
}

function MobileCard<T>({ item, columns, onClick }: MobileCardProps<T>) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Get high priority columns for the card header
  const highPriorityCols = columns.filter(c => c.priority !== 'low');
  const lowPriorityCols = columns.filter(c => c.priority === 'low');

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'rounded-xl border border-border bg-card overflow-hidden',
        onClick && 'cursor-pointer hover:border-foreground/20 hover:shadow-sm'
      )}
      onClick={onClick}
    >
      {/* Card Header - Always visible */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0 space-y-1">
            {highPriorityCols.slice(0, 2).map((col) => (
              <div key={col.key} className={col.className}>
                <span className="text-xs text-muted-foreground block sm:hidden">
                  {col.header}
                </span>
                {col.cell(item)}
              </div>
            ))}
          </div>
          
          {lowPriorityCols.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(!isExpanded);
              }}
            >
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Expandable Content - Low priority columns */}
      <AnimatePresence>
        {isExpanded && lowPriorityCols.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-border bg-muted/30"
          >
            <div className="p-4 space-y-3">
              {lowPriorityCols.map((col) => (
                <div key={col.key} className="flex items-start justify-between gap-3">
                  <span className="text-xs text-muted-foreground shrink-0">
                    {col.header}
                  </span>
                  <div className={cn('text-right', col.className)}>
                    {col.cell(item)}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function ResponsiveTable<T>({
  data,
  columns,
  keyExtractor,
  onRowClick,
  isLoading,
  emptyState,
  className,
}: ResponsiveTableProps<T>) {
  // Desktop: Traditional table
  // Mobile: Card list

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-16 rounded-xl bg-muted animate-pulse" />
        ))}
      </div>
    );
  }

  if (data.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <div className={className}>
      {/* Desktop Table */}
      <div className="hidden md:block overflow-x-auto rounded-xl border border-border">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.map((item) => (
              <tr
                key={keyExtractor(item)}
                className={cn(
                  'bg-card hover:bg-muted/50 transition-colors',
                  onRowClick && 'cursor-pointer'
                )}
                onClick={() => onRowClick?.(item)}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn('px-4 py-3 text-sm', col.className)}
                  >
                    {col.cell(item)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Cards */}
      <div className="md:hidden space-y-3">
        {data.map((item) => (
          <MobileCard
            key={keyExtractor(item)}
            item={item}
            columns={columns}
            onClick={() => onRowClick?.(item)}
          />
        ))}
      </div>
    </div>
  );
}

// Usage example helper
export function createColumn<T>(
  key: string,
  header: string,
  cell: (item: T) => React.ReactNode,
  options?: { className?: string; priority?: 'high' | 'medium' | 'low' }
): ResponsiveColumn<T> {
  return {
    key,
    header,
    cell,
    className: options?.className,
    priority: options?.priority ?? 'medium',
  };
}

// Helper for status cells
export function StatusCell({
  status,
  label,
}: {
  status: 'success' | 'error' | 'warning' | 'info' | 'default';
  label: string;
}) {
  const variants = {
    success: 'bg-success/10 text-success border-success/20',
    error: 'bg-destructive/10 text-destructive border-destructive/20',
    warning: 'bg-warning/10 text-warning border-warning/20',
    info: 'bg-info/10 text-info border-info/20',
    default: 'bg-muted text-muted-foreground',
  };

  return (
    <Badge variant="outline" className={cn('font-medium', variants[status])}>
      {label}
    </Badge>
  );
}
