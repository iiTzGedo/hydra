import { useEffect } from 'react';
import { cn } from '@/lib/utils';
import { PageBreadcrumbs } from './page-breadcrumbs';
import { SmartBackButton } from './smart-back-button';
import { Skeleton } from '@/components/ui/skeleton';
import { usePageTitleStore } from '@/stores/page-title-store';

interface PageHeaderLayoutProps {
  title?: string;
  subtitle?: string;
  /**
   * Whether to show breadcrumbs in the page body
   * @default true
   */
  showBreadcrumbs?: boolean;
  /**
   * Whether to show the smart back button
   * @default true for detail pages, false for top-level pages
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
 * PageHeaderLayout - Page body header row with breadcrumbs, back button, and subtitle/actions.
 *
 * The large page title lives in the top application Header. This component pushes
 * its `title` prop to the shared page-title store so the Header displays dynamic
 * names (e.g., node or service names). The page body renders a small muted
 * breadcrumb row in place of a bold h1 title.
 *
 * Layout structure:
 * ```
 * [Back Button]  (optional, detail pages only)
 * [Breadcrumbs]  (small, muted)
 * [Subtitle]                                              [Actions]
 * [Children - tabs, etc.]
 * ```
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
  const setPageTitle = usePageTitleStore((s) => s.setPageTitle);
  const clearPageTitle = usePageTitleStore((s) => s.clearPageTitle);

  useEffect(() => {
    if (title) {
      setPageTitle(title, subtitle ?? null);
    }
    return () => {
      if (title) {
        clearPageTitle();
      }
    };
  }, [title, subtitle, setPageTitle, clearPageTitle]);

  if (isLoading) {
    return <PageHeaderSkeleton showBreadcrumbs={showBreadcrumbs} showBackButton={showBackButton} />;
  }

  // Top-level pages don't get a back button.
  const isTopLevelPage =
    typeof window !== 'undefined' &&
    [
      '/',
      '/dashboard',
      '/dashboards',
      '/nodes',
      '/services',
      '/networks',
      '/discovery',
      '/groups',
      '/topology',
      '/time-machine',
      '/timemachine',
      '/chat',
      '/notifications',
      '/settings',
      '/profile',
      '/commands',
      '/integrations',
      '/docs',
    ].includes(window.location.pathname);

  const shouldShowBackButton = showBackButton && !isTopLevelPage;

  return (
    <div className={cn('space-y-3', className)}>
      {/* Navigation row - back button and breadcrumbs */}
      {(shouldShowBackButton || showBreadcrumbs) && (
        <div className="flex flex-col gap-2">
          {shouldShowBackButton && <SmartBackButton />}
          {showBreadcrumbs ? <PageBreadcrumbs /> : null}
        </div>
      )}

      {title ? <h1 className="sr-only">{title}</h1> : null}

      {(subtitle || actions) ? (
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1 space-y-1">
            {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2 lg:shrink-0">{actions}</div> : null}
        </div>
      ) : null}

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
  showBackButton = true,
}: PageHeaderSkeletonProps) {
  return (
    <div className="space-y-3">
      {/* Navigation skeleton */}
      {(showBackButton || showBreadcrumbs) && (
        <div className="flex flex-col gap-2">
          {showBackButton && <Skeleton className="h-9 w-32" />}
          {showBreadcrumbs && (
            <div className="flex items-center gap-1.5">
              <Skeleton className="h-3 w-3" />
              <Skeleton className="h-3 w-3" />
              <Skeleton className="h-3 w-24" />
            </div>
          )}
        </div>
      )}

      {/* Subtitle skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2">
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
