import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ROUTES } from '@/lib/constants';

interface NavigationContext {
  label: string;
  path: string;
  type: 'parent' | 'sibling' | 'home';
}

/**
 * Get navigation context from current pathname
 * Analyzes the URL to determine the logical parent page
 */
function getNavigationContext(pathname: string, search: string): NavigationContext | null {
  const segments = pathname.split('/').filter(Boolean);
  const params = new URLSearchParams(search);
  const from = params.get('from');
  const fromId = params.get('fromId');

  // Root level - no back button needed
  if (segments.length === 0) return null;

  // Handle referrer-based navigation first
  if (from === 'node' && fromId) {
    return {
      label: 'Node Services',
      path: `${ROUTES.NODES}/${fromId}?tab=services`,
      type: 'parent',
    };
  }

  // Single level - link back to dashboard
  if (segments.length === 1) {
    return {
      label: 'Dashboard',
      path: ROUTES.DASHBOARD,
      type: 'home',
    };
  }

  const [section, id, subSection, subId] = segments;

  // Detail pages: /nodes/:id, /services/:id, etc.
  if (segments.length === 2) {
    const sectionLabels: Record<string, string> = {
      nodes: 'Nodes',
      services: 'Services',
      networks: 'Networks',
      groups: 'Groups',
    };

    return {
      label: sectionLabels[section] || section,
      path: `/${section}`,
      type: 'parent',
    };
  }

  // Deep nesting patterns
  if (segments.length >= 3) {
    // /nodes/:id/profiles
    if (section === 'nodes' && subSection === 'profiles') {
      return {
        label: 'Node',
        path: `${ROUTES.NODES}/${id}`,
        type: 'parent',
      };
    }

    // /nodes/:id/profile/:profileId
    if (section === 'nodes' && subSection === 'profile' && subId) {
      return {
        label: 'Profiles',
        path: `${ROUTES.NODES}/${id}/profiles`,
        type: 'parent',
      };
    }

    // /nodes/:id/profiles/compare
    if (section === 'nodes' && subSection === 'profiles' && subId === 'compare') {
      return {
        label: 'Profiles',
        path: `${ROUTES.NODES}/${id}/profiles`,
        type: 'parent',
      };
    }

    // /services/:id (from node context)
    if (section === 'services' && from === 'nodes' && fromId) {
      return {
        label: 'Node Services',
        path: `${ROUTES.NODES}/${fromId}?tab=services`,
        type: 'parent',
      };
    }

    // Generic fallback for other patterns
    return {
      label: section,
      path: `/${section}`,
      type: 'parent',
    };
  }

  return null;
}

interface SmartBackButtonProps {
  className?: string;
  fallbackLabel?: string;
  /**
   * Force a specific navigation context
   */
  forceContext?: NavigationContext;
}

/**
 * SmartBackButton - Intelligent back navigation
 *
 * Features:
 * - Analyzes current URL to determine logical parent page
 * - Shows descriptive label ("Back to Nodes" instead of just "Back")
 * - Handles deep nesting hierarchies
 * - Supports referrer-based navigation via query params
 * - Keyboard accessible with proper focus management
 *
 * @example
 * // On /nodes/proxmox-01, shows "Back to Nodes"
 * // On /nodes/proxmox-01/profiles/abc123, shows "Back to Profiles"
 */
export function SmartBackButton({
  className,
  fallbackLabel: _fallbackLabel = 'Back',
  forceContext,
}: SmartBackButtonProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const context = forceContext || getNavigationContext(location.pathname, location.search);

  // Don't render if we're at root or no context available
  if (!context) {
    return null;
  }

  const handleClick = () => {
    navigate(context.path);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      navigate(context.path);
    }
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        'h-9 px-2 text-muted-foreground hover:text-foreground -ml-2',
        'transition-colors duration-200',
        className
      )}
      aria-label={`Back to ${context.label}`}
      aria-describedby={`back-button-desc-${context.path.replace(/\//g, '-')}`}
    >
      <ArrowLeft className="h-4 w-4 mr-1.5" aria-hidden="true" />
      <span className="text-sm">
        Back to <span className="font-medium">{context.label}</span>
      </span>
      <span
        id={`back-button-desc-${context.path.replace(/\//g, '-')}`}
        className="sr-only"
      >
        Returns to the {context.label} page
      </span>
    </Button>
  );
}

export type { NavigationContext };
