import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';

interface BreadcrumbItem {
  label: string;
  path?: string;
}

const routeLabels: Record<string, string> = {
  dashboard: 'Dashboard',
  nodes: 'Nodes',
  services: 'Services',
  networks: 'Networks',
  groups: 'Groups',
  topology: 'Topology',
  timemachine: 'Time Machine',
  chat: 'Chat',
  admin: 'Admin',
  users: 'Users',
  approvals: 'Approvals',
  tokens: 'Tokens',
  apikeys: 'API Keys',
  audit: 'Audit Log',
  profiles: 'Profiles',
  new: 'New',
};

export function Breadcrumbs() {
  const location = useLocation();
  const pathSegments = location.pathname.split('/').filter(Boolean);

  const breadcrumbs: BreadcrumbItem[] = pathSegments.map((segment, index) => {
    const path = '/' + pathSegments.slice(0, index + 1).join('/');
    const label = routeLabels[segment] || segment;

    if (index === pathSegments.length - 1) {
      return { label };
    }

    return { label, path };
  });

  if (breadcrumbs.length === 0) {
    return null;
  }

  return (
    <nav className="flex items-center gap-1 text-sm text-muted-foreground">
      <Link
        to={ROUTES.DASHBOARD}
        className="flex items-center hover:text-foreground transition-colors"
      >
        <Home className="h-4 w-4" />
      </Link>

      {breadcrumbs.map((crumb, index) => (
        <div key={index} className="flex items-center gap-1">
          <ChevronRight className="h-4 w-4" />
          {crumb.path ? (
            <Link
              to={crumb.path}
              className="hover:text-foreground transition-colors"
            >
              {crumb.label}
            </Link>
          ) : (
            <span className="text-foreground font-medium">{crumb.label}</span>
          )}
        </div>
      ))}
    </nav>
  );
}
