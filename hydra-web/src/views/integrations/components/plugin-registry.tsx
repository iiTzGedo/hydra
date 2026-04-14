import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertTriangle,
  Loader2,
  Plug,
  Power,
  PowerOff,
  Search,
  Trash2,
} from 'lucide-react';
import { usePlugins, useEnablePlugin, useDisablePlugin, useUninstallPlugin } from '@/api/plugins';
import { HydraIcon } from '@/components/icons/hydra-icon';
import { getErrorMessage } from '@/lib/api-client';
import type { PluginStatus } from '@/types/plugins';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const STATUS_BADGE: Record<PluginStatus, { variant: 'success' | 'destructive' | 'secondary' | 'warning' | 'info'; label: string }> = {
  active: { variant: 'success', label: 'Active' },
  enabled: { variant: 'info', label: 'Enabled' },
  configured: { variant: 'secondary', label: 'Configured' },
  installed: { variant: 'secondary', label: 'Installed' },
  disabled: { variant: 'secondary', label: 'Disabled' },
  error: { variant: 'destructive', label: 'Error' },
};

const CATEGORY_LABELS: Record<string, string> = {
  infrastructure: 'Infrastructure',
  monitoring: 'Monitoring',
  version_control: 'Version Control',
  databases: 'Databases',
  cloud: 'Cloud',
  development: 'Development',
  other: 'Other',
};

export function PluginRegistry() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<PluginStatus | 'all'>('all');
  const { data, isLoading, error } = usePlugins();
  const enablePlugin = useEnablePlugin();
  const disablePlugin = useDisablePlugin();
  const uninstallPlugin = useUninstallPlugin();

  const plugins = useMemo(() => data?.data ?? [], [data?.data]);

  const filteredPlugins = useMemo(() => {
    let result = plugins;
    if (statusFilter !== 'all') {
      result = result.filter((p) => p.status === statusFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.pluginId.toLowerCase().includes(q) ||
          p.category.toLowerCase().includes(q)
      );
    }
    return result;
  }, [plugins, statusFilter, searchQuery]);

  const handleEnable = async (pluginId: string) => {
    try {
      await enablePlugin.mutateAsync(pluginId);
      toast.success('Plugin enabled');
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to enable plugin'));
    }
  };

  const handleDisable = async (pluginId: string) => {
    try {
      await disablePlugin.mutateAsync(pluginId);
      toast.success('Plugin disabled');
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to disable plugin'));
    }
  };

  const handleUninstall = async (pluginId: string) => {
    try {
      await uninstallPlugin.mutateAsync(pluginId);
      toast.success('Plugin uninstalled');
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to uninstall plugin'));
    }
  };

  if (error) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Unable to load plugins</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The plugin registry is not available. Ensure the plugins API is running.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-10 w-[160px]" />
        </div>
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="text-muted-foreground">Plugin</TableHead>
                <TableHead className="text-muted-foreground">Category</TableHead>
                <TableHead className="text-muted-foreground">Classification</TableHead>
                <TableHead className="text-muted-foreground">Status</TableHead>
                <TableHead className="text-muted-foreground">Nodes</TableHead>
                <TableHead className="w-[140px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {[1, 2, 3, 4].map((i) => (
                <TableRow key={i} className="border-border">
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-24 rounded-md" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20 rounded-md" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20 rounded-md" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-24 rounded-md" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search plugins..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v as PluginStatus | 'all')}
        >
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="enabled">Enabled</SelectItem>
            <SelectItem value="configured">Configured</SelectItem>
            <SelectItem value="installed">Installed</SelectItem>
            <SelectItem value="disabled">Disabled</SelectItem>
            <SelectItem value="error">Error</SelectItem>
          </SelectContent>
        </Select>
        <Badge variant="secondary" className="ml-auto">
          {filteredPlugins.length} plugin{filteredPlugins.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      {/* Table */}
      {filteredPlugins.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Plug className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">
              {plugins.length === 0 ? 'No plugins registered' : 'No matching plugins'}
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {plugins.length === 0
                ? 'Register plugins via the API to manage integrations like Docker, Proxmox, Home Assistant, and more.'
                : 'Try adjusting the search or status filter.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="text-muted-foreground">Plugin</TableHead>
                <TableHead className="text-muted-foreground">Category</TableHead>
                <TableHead className="text-muted-foreground">Classification</TableHead>
                <TableHead className="text-muted-foreground">Status</TableHead>
                <TableHead className="text-muted-foreground">Nodes</TableHead>
                <TableHead className="w-[140px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredPlugins.map((plugin) => {
                const statusCfg = STATUS_BADGE[plugin.status] ?? { variant: 'secondary' as const, label: plugin.status };
                const isActionPending = enablePlugin.isPending || disablePlugin.isPending || uninstallPlugin.isPending;
                const isActive = plugin.status === 'active' || plugin.status === 'enabled';

                return (
                  <TableRow key={plugin.pluginId} className="border-border">
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/60 bg-muted/30">
                          <HydraIcon icon={plugin.icon} fallback="plug" size={20} />
                        </div>
                        <div>
                          <p className="font-medium">{plugin.name}</p>
                          <p className="text-xs text-muted-foreground font-mono">{plugin.pluginId}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{CATEGORY_LABELS[plugin.category] ?? plugin.category}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="capitalize">{plugin.classification}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusCfg.variant}>{statusCfg.label}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {plugin.nodeCount}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {isActive ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDisable(plugin.pluginId)}
                            disabled={isActionPending}
                            title="Disable plugin"
                          >
                            {disablePlugin.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <PowerOff className="h-4 w-4 text-warning" />
                            )}
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEnable(plugin.pluginId)}
                            disabled={isActionPending}
                            title="Enable plugin"
                          >
                            {enablePlugin.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Power className="h-4 w-4 text-success" />
                            )}
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleUninstall(plugin.pluginId)}
                          disabled={isActionPending}
                          title="Uninstall plugin"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
