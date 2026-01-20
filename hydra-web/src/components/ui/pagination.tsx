import * as React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './button';

export interface PaginationProps {
  /** Current page index (0-based) */
  page: number;
  /** Total number of pages */
  totalPages: number;
  /** Callback when page changes */
  onPageChange: (page: number) => void;
  /** Additional class names */
  className?: string;
  /** Show pagination only when totalPages > 1 (default: true) */
  hideOnSinglePage?: boolean;
  /** Show border on top (default: true) */
  showBorder?: boolean;
}

const Pagination = React.forwardRef<HTMLDivElement, PaginationProps>(
  (
    {
      page,
      totalPages,
      onPageChange,
      className,
      hideOnSinglePage = true,
      showBorder = true,
    },
    ref
  ) => {
    if (hideOnSinglePage && totalPages <= 1) {
      return null;
    }

    const handlePrevious = () => {
      onPageChange(Math.max(0, page - 1));
    };

    const handleNext = () => {
      onPageChange(Math.min(totalPages - 1, page + 1));
    };

    return (
      <nav
        ref={ref}
        role="navigation"
        aria-label="Pagination"
        className={cn(
          'flex items-center justify-center gap-2 p-4',
          showBorder && 'border-t border-border',
          className
        )}
      >
        <Button
          variant="ghost"
          size="icon"
          onClick={handlePrevious}
          disabled={page === 0}
          className="text-muted-foreground"
          aria-label="Go to previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="text-sm text-muted-foreground px-4">
          Page {page + 1} of {totalPages}
        </span>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleNext}
          disabled={page >= totalPages - 1}
          className="text-muted-foreground"
          aria-label="Go to next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </nav>
    );
  }
);

Pagination.displayName = 'Pagination';

export { Pagination };
