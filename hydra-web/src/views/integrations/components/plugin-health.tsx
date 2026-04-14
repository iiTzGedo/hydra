import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Plug,
  Server,
  XCircle,
} from 'lucide-react';
import { usePlugins } from '@/api/plugins';
import { formatRelativeTime } from '@/lib/utils';
import type { PluginStatus } from '@/types/plugins';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

const STATUS_BADGE: Record<PluginStatus, { variant: 'success' | 'destructive' | 'secondary' | 'warning' | 'info'; label: string }> = {
  active: { variant: 'success', label: 'Active' },
  enabled: { variant: 'info', label: 'Enabled' },
  configured: { variant: 'secondary', label: 'Configured' },
  installed: { variant: 'secondary', label: 'Installed' },
  disabled: { variant: 'secondary', label: 'Disabled' },
  error: { variant: 'destructive', label: 'Error' },
};

function HealthIcon({ status }: { status: string }) {
  if (status === 'healthy') return <CheckCircle2 className="h-5 w-5 text-success" />;
  if (status === 'unhealthy') return <XCircle className="h-5 w-5 text-destructive" />;
  return <Clock className="h-5 w-5 text-muted-foreground" />;
}

export function PluginHealth() {
  const { data, isLoading, error } = usePlugins();
  const plugins = data?.data ?? [];

  if (error) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Unable to load health status</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The plugin API is not available.
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

  if (plugins.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <Plug className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No plugins registered</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Health monitoring will appear here once plugins are registered and enabled.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {plugins.map((plugin) => {
        const statusCfg = STATUS_BADGE[plugin.status] ?? { variant: 'secondary' as const, label: plugin.status };

        return (
          <Card key={plugin.pluginId} className="transition-colors hover:border-primary/20">
            <CardContent className="p-5 space-y-3">
              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <HealthIcon status={plugin.healthStatus} />
                  <h4 className="text-sm font-medium truncate">{plugin.name}</h4>
                </div>
                <Badge variant={statusCfg.variant}>{statusCfg.label}</Badge>
              </div>

              {/* Category */}
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 capitalize">
                {plugin.category.replace('_', ' ')}
              </Badge>

              {/* Details */}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                  <Server className="h-3 w-3" />
                  <span>{plugin.nodeCount} node{plugin.nodeCount !== 1 ? 's' : ''}</span>
                </div>
                <span className="capitalize">{plugin.healthStatus}</span>
              </div>

              {/* Created */}
              <p className="text-xs text-muted-foreground">
                Registered {formatRelativeTime(plugin.createdAt)}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
