import { cn } from '@/lib/utils';

/**
 * Skeleton - Base skeleton component with shimmer animation
 * 
 * @example
 * <Skeleton className="h-4 w-[250px]" />
 * <Skeleton className="h-12 w-12 rounded-full" />
 */
function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...props}
    />
  );
}

/**
 * SkeletonCard - A card-shaped skeleton with multiple lines
 */
function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-lg border bg-card p-4 space-y-3', className)}>
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <div className="space-y-2 flex-1">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-24" />
        </div>
      </div>
      <Skeleton className="h-16 w-full" />
    </div>
  );
}

/**
 * SkeletonCardGrid - Multiple card skeletons in a grid
 */
function SkeletonCardGrid({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

/**
 * SkeletonTable - Table skeleton with header and rows
 */
function SkeletonTable({
  rows = 5,
  columns = 4,
}: {
  rows?: number;
  columns?: number;
}) {
  return (
    <div className="w-full space-y-3">
      {/* Header */}
      <div className="flex gap-4 pb-2 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={`header-${i}`} className="h-4 flex-1" />
        ))}
      </div>
      
      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={`row-${rowIndex}`} className="flex gap-4 py-3">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton
              key={`cell-${rowIndex}-${colIndex}`}
              className="h-4 flex-1"
              style={{ opacity: 1 - colIndex * 0.15 }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * SkeletonStats - Stats cards skeleton
 */
function SkeletonStats({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-lg border bg-card p-4 space-y-2"
        >
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-8 w-16" />
        </div>
      ))}
    </div>
  );
}

/**
 * SkeletonPage - Full page skeleton with header and content
 */
function SkeletonPage() {
  return (
    <div className="space-y-6 animate-in fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-10 w-32" />
      </div>
      
      {/* Content */}
      <SkeletonStats />
      <SkeletonCardGrid count={4} />
    </div>
  );
}

/**
 * SkeletonText - Text skeleton with multiple lines
 */
function SkeletonText({
  lines = 3,
  className,
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-4 w-full"
          style={{
            width: i === lines - 1 ? '60%' : '100%',
          }}
        />
      ))}
    </div>
  );
}

/**
 * SkeletonAvatar - Avatar skeleton with optional text
 */
function SkeletonAvatar({
  showText = true,
  lines = 2,
}: {
  showText?: boolean;
  lines?: number;
}) {
  return (
    <div className="flex items-center gap-3">
      <Skeleton className="h-10 w-10 rounded-full" />
      {showText && (
        <div className="space-y-2 flex-1">
          {Array.from({ length: lines }).map((_, i) => (
            <Skeleton
              key={i}
              className="h-3"
              style={{ width: i === 0 ? '40%' : '60%' }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Shimmer - Skeleton with shimmer animation effect
 */
function Shimmer({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'shimmer rounded-md',
        className
      )}
    />
  );
}

export {
  Skeleton,
  SkeletonCard,
  SkeletonCardGrid,
  SkeletonTable,
  SkeletonStats,
  SkeletonPage,
  SkeletonText,
  SkeletonAvatar,
  Shimmer,
};
