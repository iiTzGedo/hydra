import { Link } from 'react-router-dom';
import { Boxes } from 'lucide-react';
import { useNodeServices } from '@/api/services';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/common/empty-state';
import { StatusBadge } from '@/components/ui/status-badge';

interface ServicesTabProps {
  nodeId: string;
}

export function ServicesTab({ nodeId }: ServicesTabProps) {
  const { data: services, isLoading, error } = useNodeServices(nodeId);

  if (isLoading) {
    return (
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {[...Array(6)].map((_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={Boxes}
        title="Failed to load services"
        description="There was an error loading services for this node"
      />
    );
  }

  if (!services?.items || services.items.length === 0) {
    return (
      <EmptyState
        icon={Boxes}
        title="No services found"
        description="No services have been discovered on this node"
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {services.total} service{services.total !== 1 ? 's' : ''} on this node
        </p>
        <Link
          to={ROUTES.SERVICES + '?node=' + nodeId}
          className="text-sm text-primary hover:underline"
        >
          View all in Service Explorer
        </Link>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {services.items.map((service) => (
          <Link
            key={service.id}
            to={ROUTES.SERVICES + '/' + encodeURIComponent(service.id)}
            className="flex items-center gap-3 rounded-lg border bg-card p-4 hover:bg-muted/50 transition-colors group"
          >
            <div className="rounded-lg bg-muted p-2">
              <Boxes className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium truncate group-hover:text-primary transition-colors">
                {service.name}
              </div>
              <div className="text-xs text-muted-foreground">{service.runtime}</div>
            </div>
            <StatusBadge
              status={service.status}
              size="sm"
              showDot
            />
          </Link>
        ))}
      </div>
    </div>
  );
}
