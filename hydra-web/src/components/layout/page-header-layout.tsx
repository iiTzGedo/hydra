import { cn } from '@/lib/utils';
import { PageBreadcrumbs } from './page-breadcrumbs';
import { SmartBackButton } from './smart-back-button';
import { Skeleton } from '@/components/ui/skeleton';

interface PageHeaderLayoutProps {
  title?: string;
  subtitle?: string;
  /**
   * Whether to show breadcrumbs
   * @default true
   */
  showBreadcrumbs?: boolean;
  /**
   * Whether to show the smart back button
   * @default true for detail pages, false for list pages
   */
  showBackButton?: boolean;
  /**
   * Actions to display on the right side of the header
   */
  actions?: React.ReactNode;
  /**
   * Additional content below the title (e.g., tabs)
   */
  children?: React.ReactNode;
  className?: string;
  /**
   * Loading state
   */
  isLoading?: boolean;
}

/**
 * PageHeaderLayout - Consistent page header with breadcrumbs, back button, and title
 *
 * Combines navigation elements (back button, breadcrumbs) with page title and actions
 * in a consistent layout pattern across all pages.
 *
 * Layout structure:
 * ```
 * [Back Button]  (optional)
 * [Breadcrumbs]  (optional)
 * [Title]                    [Actions]
 * [Subtitle]
 * [Children - tabs, etc.]
 * ```
 *
 * @example
 * // List page - no back button, just breadcrumbs
 * <PageHeaderLayout
 *   title="Node Explorer"
 *   subtitle="12 of 45 nodes"
 *   showBackButton={false}
 *   actions={<Button>Add Node</Button>}
 * />
 *
 * @example
 * // Detail page - back button and breadcrumbs
 * <PageHeaderLayout
 *   title="proxmox-01"
 *   subtitle="Compute node - VM"
 *   actions={<Button>Edit</Button>}
 * >
 *   <Tabs>...</Tabs>
 * </PageHeaderLayout>
 */
export function PageHeaderLayout({
  title,
  subtitle,
  showBreadcrumbs = true,
  showBackButton = true,
  actions,
  children,
  className,
  isLoading = false,
}: PageHeaderLayoutProps) {
  if (isLoading) {
    return <PageHeaderSkeleton showBreadcrumbs={showBreadcrumbs} showBackButton={showBackButton} />;
  }

  // Check if we're on a top-level page (no need for back button on dashboard, nodes list, etc.)
  const isTopLevelPage = typeof window !== 'undefined' && 
    ['/', '/dashboard', '/nodes', '/services', '/networks', '/discovery', '/groups', '/topology', '/time-machine', '/timemachine', '/chat', '/notifications', '/settings', '/profile'].includes(window.location.pathname);

  const shouldShowBackButton = showBackButton && !isTopLevelPage;

  return (
    <div className={cn('space-y-3', className)}>
      {/* Navigation row - back button and breadcrumbs */}
      {(shouldShowBackButton || showBreadcrumbs) && (
        <div className="flex flex-col gap-2">
          {shouldShowBackButton && <SmartBackButton />}
          {showBreadcrumbs && <PageBreadcrumbs />}
        </div>
      )}
      
      {/* Title row */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-1 min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground truncate">
            {title}
          </h1>
          {subtitle && (
            <p className="text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
        
        {actions && (
          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            {actions}
          </div>
        )}
      </div>

      {/* Additional content (tabs, etc.) */}
      {children}
    </div>
  );
}

/**
 * Skeleton loading state for page header
 */
interface PageHeaderSkeletonProps {
  showBreadcrumbs?: boolean;
  showBackButton?: boolean;
}

export function PageHeaderSkeleton({ 
  showBreadcrumbs = true, 
  showBackButton = true 
}: PageHeaderSkeletonProps) {
  return (
    <div className="space-y-3">
      {/* Navigation skeleton */}
      {(showBackButton || showBreadcrumbs) && (
        <div className="flex flex-col gap-2">
          {showBackButton && (
            <Skeleton className="h-9 w-32" />
          )}
          {showBreadcrumbs && (
            <div className="flex items-center gap-1.5">
              <Skeleton className="h-3.5 w-3.5" />
              <Skeleton className="h-3.5 w-3.5" />
              <Skeleton className="h-4 w-24" />
            </div>
          )}
        </div>
      )}
      
      {/* Title skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>
    </div>
  );
}

export type { PageHeaderLayoutProps };
