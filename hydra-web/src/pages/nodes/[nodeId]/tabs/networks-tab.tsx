import { Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import { Network, Globe } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import type { Network as NetworkType } from '@/types/network';
import type { Node } from '@/types/node';
import { ROUTES, NETWORK_TYPE_LABELS } from '@/lib/constants';
import { EmptyState } from '@/components/common/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';

interface NetworksTabProps {
  node: Node;
}

export function NetworksTab({ node }: NetworksTabProps) {
  const networkIds = node.networkIds ?? [];

  // Fetch each network individually instead of fetching all and filtering
  const networkQueries = useQueries({
    queries: networkIds.map((networkId) => ({
      queryKey: queryKeys.networks.detail(networkId),
      queryFn: async () => {
        const response = await apiClient.get<ApiResponse<NetworkType>>(
          `/networks/${encodeURIComponent(networkId)}`
        );
        return response.data.data;
      },
      enabled: !!networkId,
      staleTime: 5 * 60 * 1000,
    })),
  });

  const isLoading = networkQueries.some((q) => q.isLoading);
  const networks = networkQueries
    .map((q) => q.data)
    .filter(Boolean) as NetworkType[];

  if (networkIds.length === 0) {
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
          {networkIds.length} network{networkIds.length !== 1 ? 's' : ''}
        </p>
        <Link
          to={ROUTES.NETWORKS}
          className="text-sm text-primary hover:underline"
        >
          View all networks
        </Link>
      </div>

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {networkIds.map((networkId) => (
            <div key={networkId} className="rounded-lg border bg-card p-4">
              <div className="flex items-start gap-3">
                <Skeleton className="h-9 w-9 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-3 w-32" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {networkIds.map((networkId) => {
            const network = networks.find((n) => n.networkId === networkId);
            return (
              <Link
                key={networkId}
                to={ROUTES.NETWORKS + '/' + encodeURIComponent(networkId)}
                className="flex items-start gap-3 rounded-lg border bg-card p-4 hover:bg-muted/50 transition-colors group"
              >
                <div className="rounded-lg bg-muted p-2">
                  <Network className="h-5 w-5 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate group-hover:text-primary transition-colors">
                    {network?.name || networkId}
                  </div>
                  {network ? (
                    <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                      {network.cidr && (
                        <div className="font-mono">{network.cidr}</div>
                      )}
                      <Badge variant="secondary" className="text-[10px] mt-1">
                        {NETWORK_TYPE_LABELS[network.type] || network.type}
                      </Badge>
                    </div>
                  ) : (
                    <div className="mt-1 text-xs text-muted-foreground font-mono">
                      {networkId}
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
