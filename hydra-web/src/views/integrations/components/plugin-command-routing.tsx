import { useState } from 'react';
import {
  AlertTriangle,
  Plug,
  Route,
} from 'lucide-react';
import { usePlugins, usePlugin } from '@/api/plugins';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
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

export function PluginCommandRouting() {
  const { data, isLoading: listLoading, error: listError } = usePlugins();
  const plugins = data?.data ?? [];

  const [selectedPluginId, setSelectedPluginId] = useState<string>('');
  const { data: pluginDetail, isLoading: detailLoading } = usePlugin(selectedPluginId);

  const contributedCommands = pluginDetail?.manifest.contributedCommands ?? [];
  const touchpoints = pluginDetail?.manifest.touchpoints;

  if (listError) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Unable to load plugins</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The plugin API is not available.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (listLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-48 w-full" />
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
            Command routing will appear here once plugins that contribute commands are registered.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Plugin Selector */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={selectedPluginId} onValueChange={setSelectedPluginId}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="Select a plugin..." />
          </SelectTrigger>
          <SelectContent>
            {plugins.map((p) => (
              <SelectItem key={p.pluginId} value={p.pluginId}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Routing Info */}
      {!selectedPluginId ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Route className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">Select a plugin</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Choose a plugin to view its command routing configuration and touchpoints.
            </p>
          </CardContent>
        </Card>
      ) : detailLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : pluginDetail ? (
        <div className="space-y-4">
          {/* Touchpoints Card */}
          <Card>
            <CardContent className="p-5 space-y-3">
              <h3 className="text-sm font-semibold">Plugin Touchpoints</h3>
              <p className="text-xs text-muted-foreground">
                Capabilities this plugin contributes to the platform.
              </p>
              <div className="flex flex-wrap gap-2">
                {touchpoints?.profileEnrichment && (
                  <Badge variant="info">Profile Enrichment</Badge>
                )}
                {touchpoints?.discoveryProvider && (
                  <Badge variant="info">Discovery Provider</Badge>
                )}
                {touchpoints?.commandProvider && (
                  <Badge variant="info">Command Provider</Badge>
                )}
                {touchpoints?.executionHandler && (
                  <Badge variant="info">Execution Handler</Badge>
                )}
                {touchpoints?.topologyProvider && (
                  <Badge variant="info">Topology Provider</Badge>
                )}
                {touchpoints?.workflowBlockProvider && (
                  <Badge variant="info">Workflow Block Provider</Badge>
                )}
                {touchpoints && !Object.values(touchpoints).some(Boolean) && (
                  <span className="text-xs text-muted-foreground">No active touchpoints</span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Contributed Commands */}
          <Card>
            <CardContent className="p-5 space-y-3">
              <h3 className="text-sm font-semibold">Contributed Commands</h3>
              <p className="text-xs text-muted-foreground">
                Command registry IDs this plugin provides. These commands are routed through the plugin&apos;s execution handler.
              </p>

              {contributedCommands.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  This plugin does not contribute any commands.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="border-border hover:bg-transparent">
                      <TableHead className="text-muted-foreground">Registry ID</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {contributedCommands.map((cmdId) => (
                      <TableRow key={cmdId} className="border-border">
                        <TableCell className="font-mono text-sm">{cmdId}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Supported Tiers */}
          <Card>
            <CardContent className="p-5 space-y-3">
              <h3 className="text-sm font-semibold">Supported Agent Tiers</h3>
              <div className="flex flex-wrap gap-2">
                {pluginDetail.manifest.supportedTiers.map((tier) => (
                  <Badge key={tier} variant="outline" className="capitalize">
                    {tier}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
