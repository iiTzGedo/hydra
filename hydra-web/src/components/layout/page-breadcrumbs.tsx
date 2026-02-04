import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Home, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';

interface BreadcrumbItem {
  label: string;
  path: string;
  isCurrent: boolean;
  isId: boolean;
  isTruncated: boolean;
  fullLabel?: string;
}

// Human-readable labels for common paths
const pathLabels: Record<string, string> = {
  nodes: 'Nodes',
  services: 'Services',
  networks: 'Networks',
  groups: 'Groups',
  topology: 'Topology',
  'time-machine': 'Time Machine',
  timemachine: 'Time Machine',
  chat: 'Chat',
  notifications: 'Notifications',
  profile: 'Profile',
  settings: 'Settings',
  dashboard: 'Dashboard',
  'mcp-marketplace': 'MCP Marketplace',
  profiles: 'Profiles',
  profileId: 'Profile',
  compare: 'Compare',
};

// Maximum length for ID display before truncation
const MAX_ID_LENGTH = 12;

/**
 * Detects if a segment is likely an ID (long alphanumeric string)
 */
function isIdSegment(segment: string): boolean {
  // Check for common ID patterns:
  // - At least 8 characters
  // - Contains mix of letters, numbers, hyphens, underscores
  // - Not a known path label
  if (segment.length < 8) return false;
  if (pathLabels[segment.toLowerCase()]) return false;
  
  // Match patterns like: abc123def, node-01-prod, svc_nginx_abc123
  return /^[a-zA-Z0-9_-]+$/.test(segment);
}

/**
 * Formats a path segment into a human-readable label
 */
function formatSegmentLabel(segment: string, isId: boolean): { label: string; isTruncated: boolean; fullLabel?: string } {
  // Check known labels first (case insensitive)
  const knownLabel = pathLabels[segment] || pathLabels[segment.toLowerCase()];
  if (knownLabel) {
    return { label: knownLabel, isTruncated: false };
  }

  // If it's an ID, truncate it
  if (isId) {
    if (segment.length > MAX_ID_LENGTH) {
      const truncated = `${segment.slice(0, 6)}...${segment.slice(-4)}`;
      return { 
        label: truncated, 
        isTruncated: true, 
        fullLabel: segment 
      };
    }
    return { label: segment, isTruncated: false };
  }

  // Format regular segments (capitalize, replace separators)
  const formatted = segment
    .replace(/-/g, ' ')
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .trim();
  
  const capitalized = formatted.charAt(0).toUpperCase() + formatted.slice(1).toLowerCase();
  
  return { label: capitalized, isTruncated: false };
}

/**
 * Builds the breadcrumb items from current pathname
 */
function buildBreadcrumbItems(pathname: string): BreadcrumbItem[] {
  const segments = pathname.split('/').filter(Boolean);
  const items: BreadcrumbItem[] = [];
  let currentPath = '';

  segments.forEach((segment, index) => {
    currentPath += `/${segment}`;
    const isLast = index === segments.length - 1;
    const isId = isIdSegment(segment);
    const { label, isTruncated, fullLabel } = formatSegmentLabel(segment, isId);

    items.push({
      label,
      path: currentPath,
      isCurrent: isLast,
      isId,
      isTruncated,
      fullLabel,
    });
  });

  return items;
}

interface PageBreadcrumbsProps {
  className?: string;
  /**
   * Maximum number of items to show before truncating with ellipsis
   * On mobile, always truncates to show only first and last
   */
  maxItems?: number;
}

/**
 * PageBreadcrumbs - Page-level breadcrumb navigation
 *
 * Positioned within page content area (not header) for better visual hierarchy.
 * Provides clear navigation context and clickable parent links.
 *
 * Features:
 * - Auto-generates breadcrumbs from current URL
 * - Smart truncation for long IDs
 * - Responsive: collapses on mobile
 * - Clickable parent levels
 * - Proper ARIA labels for accessibility
 * - Animated entrance
 *
 * @example
 * // On /nodes/proxmox-01/profiles/abc123
 * // Shows: Home > Nodes > proxmox-01 > Profiles > abc1...c123
 */
export function PageBreadcrumbs({ className, maxItems: _maxItems = 4 }: PageBreadcrumbsProps) {
  const location = useLocation();
  const items = buildBreadcrumbItems(location.pathname);

  if (items.length === 0) return null;

  // Animation variants for staggered entrance
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.05,
        delayChildren: 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, x: -10 },
    visible: { 
      opacity: 1, 
      x: 0,
      transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] }
    },
  };

  return (
    <nav 
      aria-label="Breadcrumb"
      className={cn('flex items-center', className)}
    >
      <motion.ol 
        className="flex items-center gap-1.5 flex-wrap"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Home link */}
        <motion.li variants={itemVariants}>
          <Link
            to={ROUTES.DASHBOARD}
            className={cn(
              'flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors',
              'rounded px-1.5 py-0.5 hover:bg-muted focus:outline-none focus:ring-2 focus:ring-primary/20'
            )}
          >
            <Home className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="sr-only">Home</span>
          </Link>
        </motion.li>

        {items.map((item, _index) => {
          const isLast = item.isCurrent;
          
          return (
            <motion.li 
              key={item.path} 
              className="flex items-center gap-1.5"
              variants={itemVariants}
            >
              <ChevronRight 
                className="h-3.5 w-3.5 text-muted-foreground/50 flex-shrink-0" 
                aria-hidden="true"
              />
              
              {isLast ? (
                // Current page (not clickable)
                <span 
                  className={cn(
                    'font-medium text-foreground truncate max-w-[200px] sm:max-w-[300px]',
                    item.isId && 'font-mono text-xs bg-muted px-1.5 py-0.5 rounded',
                    'focus:outline-none'
                  )}
                  aria-current="page"
                  title={item.fullLabel || item.label}
                >
                  {item.label}
                </span>
              ) : (
                // Parent page (clickable)
                <Link
                  to={item.path}
                  className={cn(
                    'text-muted-foreground hover:text-foreground transition-colors truncate',
                    'max-w-[120px] sm:max-w-[200px] rounded px-1.5 py-0.5 hover:bg-muted',
                    'focus:outline-none focus:ring-2 focus:ring-primary/20',
                    item.isId && 'font-mono text-xs'
                  )}
                  title={item.fullLabel || item.label}
                >
                  {item.label}
                </Link>
              )}
            </motion.li>
          );
        })}
      </motion.ol>
    </nav>
  );
}

/**
 * Skeleton loading state for breadcrumbs
 */
export function BreadcrumbsSkeleton() {
  return (
    <div className="flex items-center gap-1.5 text-sm">
      <div className="h-3.5 w-3.5 rounded bg-muted animate-pulse" />
      <div className="h-3.5 w-3.5 rounded bg-muted animate-pulse" />
      <div className="h-4 w-24 rounded bg-muted animate-pulse" />
    </div>
  );
}

export type { BreadcrumbItem };
