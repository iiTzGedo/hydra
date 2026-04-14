import { useQuery } from '@tanstack/react-query';
import {
  Plug,
  Server,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { formatRelativeTime } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

// ── Plugin Types (inline, minimal — plugins API may or may not exist) ──

interface PluginSummary {
  pluginId: string;
  name: string;
  category: string;
  status: 'active' | 'disabled' | 'error' | 'installing' | 'uninstalling';
  boundNodeCount: number;
  lastHealthCheck?: string | null;
  healthy?: boolean | null;
}

const PLUGIN_STATUS_BADGE: Record<
  string,
  { variant: 'success' | 'destructive' | 'secondary' | 'warning'; label: string }
> = {
  active: { variant: 'success', label: 'Active' },
  error: { variant: 'destructive', label: 'Error' },
  disabled: { variant: 'secondary', label: 'Disabled' },
  installing: { variant: 'warning', label: 'Installing' },
  uninstalling: { variant: 'warning', label: 'Uninstalling' },
};

function usePlugins() {
  return useQuery({
    queryKey: ['plugins', 'list'],
    queryFn: async (): Promise<PluginSummary[]> => {
      const response = await apiClient.get<{ data: PluginSummary[] }>('/plugins');
      return response.data.data;
    },
    retry: false,
  });
}

export function IntegrationStatus() {
  const { data: plugins, isLoading, error } = usePlugins();

  // If the endpoint doesn't exist (404) or fails, show a graceful fallback
  if (error) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <Plug className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No plugins configured</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Plugin management is available in the Integrations page.
            Configure integrations like Docker, Proxmox, Home Assistant, and more.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardContent className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <Skeleton className="h-5 w-28" />
                <Skeleton className="h-6 w-16 rounded-md" />
              </div>
              <Skeleton className="h-4 w-20" />
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (!plugins || plugins.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <Plug className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No plugins configured</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Plugin management is available in the Integrations page.
            Configure integrations like Docker, Proxmox, Home Assistant, and more.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {plugins.map((plugin) => {
        const statusConfig = PLUGIN_STATUS_BADGE[plugin.status] ?? {
          variant: 'secondary' as const,
          label: plugin.status,
        };

        return (
          <Card key={plugin.pluginId} className="transition-colors hover:border-primary/20">
            <CardContent className="p-5 space-y-3">
              {/* Header: name + status */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div
                    className={`h-2.5 w-2.5 rounded-full shrink-0 ${
                      plugin.healthy === true
                        ? 'bg-success'
                        : plugin.healthy === false
                          ? 'bg-destructive'
                          : 'bg-muted-foreground'
                    }`}
                  />
                  <h4 className="text-sm font-medium truncate">{plugin.name}</h4>
                </div>
                <Badge variant={statusConfig.variant}>{statusConfig.label}</Badge>
              </div>

              {/* Category */}
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {plugin.category}
              </Badge>

              {/* Details */}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                  <Server className="h-3 w-3" />
                  <span>
                    {plugin.boundNodeCount} node{plugin.boundNodeCount !== 1 ? 's' : ''}
                  </span>
                </div>
                {plugin.lastHealthCheck && (
                  <span>Checked {formatRelativeTime(plugin.lastHealthCheck)}</span>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
