import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertTriangle,
  Link2Off,
  Loader2,
  Plug,
  Server,
} from 'lucide-react';
import { usePlugins, usePlugin, useUnbindNode } from '@/api/plugins';
import { getErrorMessage } from '@/lib/api-client';
import { formatRelativeTime } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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

export function PluginNodeBindings() {
  const { data, isLoading: listLoading, error: listError } = usePlugins();
  const plugins = data?.data ?? [];

  const [selectedPluginId, setSelectedPluginId] = useState<string>('');
  const { data: pluginDetail, isLoading: detailLoading } = usePlugin(selectedPluginId);
  const unbindNode = useUnbindNode();

  const bindings = useMemo(() => pluginDetail?.nodeBindings ?? [], [pluginDetail]);

  const handleUnbind = async (nodeId: string) => {
    if (!selectedPluginId) return;
    try {
      await unbindNode.mutateAsync({ pluginId: selectedPluginId, nodeId });
      toast.success(`Unbound node ${nodeId}`);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to unbind node'));
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
            Node bindings will appear here once plugins are registered.
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
                <div className="flex items-center gap-2">
                  <span>{p.name}</span>
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                    {p.nodeCount} node{p.nodeCount !== 1 ? 's' : ''}
                  </Badge>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Bindings Table */}
      {!selectedPluginId ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Server className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">Select a plugin</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Choose a plugin from the dropdown to view its node bindings.
            </p>
          </CardContent>
        </Card>
      ) : detailLoading ? (
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="text-muted-foreground">Node ID</TableHead>
                <TableHead className="text-muted-foreground">Status</TableHead>
                <TableHead className="text-muted-foreground">Allowed Commands</TableHead>
                <TableHead className="text-muted-foreground">Bound At</TableHead>
                <TableHead className="w-[80px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {[1, 2, 3].map((i) => (
                <TableRow key={i} className="border-border">
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-16 rounded-md" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8 rounded-md" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      ) : bindings.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Server className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No node bindings</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              This plugin is not bound to any nodes. Bind nodes via the API to enable plugin operations on them.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="text-muted-foreground">Node ID</TableHead>
                <TableHead className="text-muted-foreground">Status</TableHead>
                <TableHead className="text-muted-foreground">Allowed Commands</TableHead>
                <TableHead className="text-muted-foreground">Bound At</TableHead>
                <TableHead className="w-[80px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {bindings.map((binding) => (
                <TableRow key={binding.nodeId} className="border-border">
                  <TableCell className="font-mono text-sm">{binding.nodeId}</TableCell>
                  <TableCell>
                    <Badge variant={binding.enabled ? 'success' : 'secondary'}>
                      {binding.enabled ? 'Active' : 'Disabled'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {binding.allowedCommands.length > 0
                      ? binding.allowedCommands.join(', ')
                      : 'All'}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatRelativeTime(binding.boundAt)}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleUnbind(binding.nodeId)}
                      disabled={unbindNode.isPending}
                      title="Unbind node"
                    >
                      {unbindNode.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Link2Off className="h-4 w-4 text-destructive" />
                      )}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
