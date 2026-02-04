import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';

interface BreadcrumbSegment {
  label: string;
  path: string;
  isId?: boolean;
}

// Human-readable labels for common paths
const pathLabels: Record<string, string> = {
  'nodes': 'Nodes',
  'services': 'Services',
  'networks': 'Networks',
  'groups': 'Groups',
  'topology': 'Topology',
  'time-machine': 'Time Machine',
  'timemachine': 'Time Machine',
  'chat': 'Chat',
  'notifications': 'Notifications',
  'profile': 'Profile',
  'settings': 'Settings',
  'dashboard': 'Dashboard',
  'mcp-marketplace': 'MCP Marketplace',
  'profiles': 'Profiles',
  'profileId': 'Profile',
  'nodeId': 'Node',
  'serviceId': 'Service',
  'networkId': 'Network',
  'groupId': 'Group',
};

/**
 * Breadcrumbs - Enhanced navigation breadcrumb component
 * 
 * Features:
 * - Auto-generates breadcrumbs from current path
 * - Smart truncation for long IDs
 * - Responsive: collapses on mobile
 * - Clickable parent navigation
 * - Visual hierarchy with home icon
 */
export function Breadcrumbs({ 
  className,
  maxIdLength = 12,
}: { 
  className?: string;
  maxIdLength?: number;
}) {
  const location = useLocation();
  const segments = location.pathname.split('/').filter(Boolean);
  
  if (segments.length === 0) return null;

  // Build breadcrumb segments
  const breadcrumbs: BreadcrumbSegment[] = [];
  let currentPath = '';

  segments.forEach((segment, _index) => {
    currentPath += `/${segment}`;
    
    // Determine if this is likely an ID (long alphanumeric string)
    const isId = /^[a-zA-Z0-9_-]{8,}$/.test(segment) && 
                 !pathLabels[segment.toLowerCase()];
    
    // Get label
    let label = pathLabels[segment] || 
                pathLabels[segment.toLowerCase()] ||
                segment;
    
    // If it's an ID, show truncated version
    if (isId && segment.length > maxIdLength) {
      label = `${segment.slice(0, maxIdLength)}...`;
    }

    // Format label (capitalize, replace hyphens/underscores)
    if (!pathLabels[segment] && !pathLabels[segment.toLowerCase()]) {
      label = segment
        .replace(/-/g, ' ')
        .replace(/_/g, ' ')
        .replace(/([A-Z])/g, ' $1')
        .trim();
      label = label.charAt(0).toUpperCase() + label.slice(1).toLowerCase();
    }

    breadcrumbs.push({
      label,
      path: currentPath,
      isId,
    });
  });

  return (
    <nav 
      aria-label="Breadcrumb"
      className={cn('flex items-center text-sm', className)}
    >
      <ol className="flex items-center gap-1 flex-wrap">
        {/* Home link */}
        <li>
          <Link
            to={ROUTES.DASHBOARD}
            className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
          >
            <Home className="h-3.5 w-3.5" />
            <span className="sr-only">Home</span>
          </Link>
        </li>

        {breadcrumbs.map((crumb, index) => {
          const isLast = index === breadcrumbs.length - 1;
          
          return (
            <li key={crumb.path} className="flex items-center gap-1">
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
              
              {isLast ? (
                // Current page (not clickable)
                <span 
                  className={cn(
                    'font-medium text-foreground truncate max-w-[150px] sm:max-w-[200px]',
                    crumb.isId && 'font-mono text-xs'
                  )}
                  aria-current="page"
                >
                  {crumb.label}
                </span>
              ) : (
                // Parent page (clickable)
                <Link
                  to={crumb.path}
                  className={cn(
                    'text-muted-foreground hover:text-foreground transition-colors truncate max-w-[100px] sm:max-w-[150px]',
                    crumb.isId && 'font-mono text-xs'
                  )}
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/**
 * BreadcrumbsSkeleton - Loading state for breadcrumbs
 */
export function BreadcrumbsSkeleton() {
  return (
    <div className="flex items-center gap-1 text-sm">
      <div className="h-3.5 w-3.5 rounded bg-muted animate-pulse" />
      <div className="h-3.5 w-3.5 rounded bg-muted animate-pulse" />
      <div className="h-4 w-24 rounded bg-muted animate-pulse" />
    </div>
  );
}

/**
 * PageHeader - Consistent page header with breadcrumbs and title
 */
interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: boolean;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeaderLayout({
  title,
  subtitle,
  breadcrumbs: showBreadcrumbs = true,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn('space-y-2', className)}>
      {showBreadcrumbs && <Breadcrumbs />}
      
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {subtitle && (
            <p className="text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
        
        {actions && (
          <div className="flex items-center gap-2 shrink-0">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
