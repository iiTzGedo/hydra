import { Link } from 'react-router-dom';
import { Network, Globe } from 'lucide-react';
import type { Node } from '@/types/node';
import { ROUTES } from '@/lib/constants';
import { EmptyState } from '@/components/common/empty-state';

interface NetworksTabProps {
  node: Node;
}

export function NetworksTab({ node }: NetworksTabProps) {
  if (!node.networkIds || node.networkIds.length === 0) {
    return (
      <EmptyState
        icon={Globe}
        title="No network membership"
        description="This node is not connected to any networks"
        action={{
          label: 'View All Networks',
          href: ROUTES.NETWORKS,
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {node.networkIds.length} network{node.networkIds.length !== 1 ? 's' : ''}
        </p>
        <Link
          to={ROUTES.NETWORKS}
          className="text-sm text-primary hover:underline"
        >
          View all networks
        </Link>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {node.networkIds.map((networkId) => {
          const membership = node.networks?.find(n => n.networkId === networkId);
          return (
            <Link
              key={networkId}
              to={ROUTES.NETWORKS + '/' + networkId}
              className="flex items-start gap-3 rounded-lg border bg-card p-4 hover:bg-muted/50 transition-colors group"
            >
              <div className="rounded-lg bg-muted p-2">
                <Network className="h-5 w-5 text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate group-hover:text-primary transition-colors">
                  {networkId}
                </div>
                {membership && (
                  <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                    {membership.ipAddress && (
                      <div className="flex items-center gap-1">
                        <span className="text-muted-foreground/60">IP:</span>
                        <span className="font-mono">{membership.ipAddress}</span>
                      </div>
                    )}
                    {membership.interfaceName && (
                      <div className="flex items-center gap-1">
                        <span className="text-muted-foreground/60">Interface:</span>
                        <span>{membership.interfaceName}</span>
                      </div>
                    )}
                    {membership.macAddress && (
                      <div className="flex items-center gap-1">
                        <span className="text-muted-foreground/60">MAC:</span>
                        <span className="font-mono text-[10px]">{membership.macAddress}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
