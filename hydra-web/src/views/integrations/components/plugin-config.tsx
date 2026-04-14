import { useState } from 'react';
import { toast } from 'sonner';
import {
  AlertTriangle,
  Loader2,
  Plug,
  Save,
  Settings2,
} from 'lucide-react';
import { usePlugins, usePlugin, useUpdatePluginConfig } from '@/api/plugins';
import { getErrorMessage } from '@/lib/api-client';
import type { PluginStatus } from '@/types/plugins';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const STATUS_BADGE: Record<PluginStatus, { variant: 'success' | 'destructive' | 'secondary' | 'warning' | 'info'; label: string }> = {
  active: { variant: 'success', label: 'Active' },
  enabled: { variant: 'info', label: 'Enabled' },
  configured: { variant: 'secondary', label: 'Configured' },
  installed: { variant: 'secondary', label: 'Installed' },
  disabled: { variant: 'secondary', label: 'Disabled' },
  error: { variant: 'destructive', label: 'Error' },
};

export function PluginConfig() {
  const { data, isLoading: listLoading, error: listError } = usePlugins();
  const plugins = data?.data ?? [];

  const [selectedPluginId, setSelectedPluginId] = useState<string>('');
  const { data: pluginDetail, isLoading: detailLoading } = usePlugin(selectedPluginId);
  const updateConfig = useUpdatePluginConfig();

  const [configJson, setConfigJson] = useState('');
  const [configDirty, setConfigDirty] = useState(false);

  // When plugin detail loads, set the JSON editor
  const currentConfig = pluginDetail?.config ?? {};
  if (pluginDetail && !configDirty) {
    const formatted = JSON.stringify(currentConfig, null, 2);
    if (configJson !== formatted) {
      setConfigJson(formatted);
    }
  }

  const handleSelectPlugin = (id: string) => {
    setSelectedPluginId(id);
    setConfigDirty(false);
    setConfigJson('');
  };

  const handleSave = async () => {
    if (!selectedPluginId) return;
    try {
      const parsed = JSON.parse(configJson);
      await updateConfig.mutateAsync({
        pluginId: selectedPluginId,
        request: { config: parsed },
      });
      setConfigDirty(false);
      toast.success('Configuration saved');
    } catch (err: unknown) {
      if (err instanceof SyntaxError) {
        toast.error('Invalid JSON format');
      } else {
        toast.error(getErrorMessage(err, 'Failed to save configuration'));
      }
    }
  };

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
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (plugins.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <Plug className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No plugins to configure</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Register plugins to configure their connection settings and credentials.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Plugin Selector */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={selectedPluginId} onValueChange={handleSelectPlugin}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="Select a plugin to configure..." />
          </SelectTrigger>
          <SelectContent>
            {plugins.map((p) => {
              const statusCfg = STATUS_BADGE[p.status] ?? { variant: 'secondary' as const, label: p.status };
              return (
                <SelectItem key={p.pluginId} value={p.pluginId}>
                  <div className="flex items-center gap-2">
                    <span>{p.name}</span>
                    <Badge variant={statusCfg.variant} className="text-[10px] px-1.5 py-0">
                      {statusCfg.label}
                    </Badge>
                  </div>
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
      </div>

      {/* Config Editor */}
      {!selectedPluginId ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Settings2 className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">Select a plugin</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Choose a plugin from the dropdown above to view and edit its configuration.
            </p>
          </CardContent>
        </Card>
      ) : detailLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : pluginDetail ? (
        <Card>
          <CardContent className="p-5 space-y-4">
            {/* Plugin Info */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold">{pluginDetail.manifest.name}</h3>
                <p className="text-xs text-muted-foreground">
                  {pluginDetail.manifest.description || pluginDetail.manifest.pluginId}
                </p>
              </div>
              <Badge
                variant={STATUS_BADGE[pluginDetail.status]?.variant ?? 'secondary'}
              >
                {STATUS_BADGE[pluginDetail.status]?.label ?? pluginDetail.status}
              </Badge>
            </div>

            {/* JSON Editor */}
            <div className="space-y-2">
              <label htmlFor="plugin-config-editor" className="text-sm font-medium text-foreground">
                Configuration (JSON)
              </label>
              <Textarea
                id="plugin-config-editor"
                value={configJson}
                onChange={(e) => {
                  setConfigJson(e.target.value);
                  setConfigDirty(true);
                }}
                placeholder="{}"
                className="font-mono text-sm min-h-[200px]"
              />
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
              <Button
                onClick={handleSave}
                disabled={!configDirty || updateConfig.isPending}
              >
                {updateConfig.isPending ? (
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                ) : (
                  <Save className="h-4 w-4 mr-1.5" />
                )}
                Save Configuration
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
