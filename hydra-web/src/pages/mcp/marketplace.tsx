import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useQueries } from '@tanstack/react-query';
import {
  ExternalLink,
  Plus,
  Server,
  AlertCircle,
  ArrowLeft,
  Globe,
  Trash2,
  RefreshCw,
  Link2,
  CheckCircle,
  XCircle,
  Loader2,
  Terminal,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import {
  useMCPServers,
  useCreateMCPServer,
  useUpdateMCPServer,
  useDeleteMCPServer,
  useCheckMCPServerHealth,
  type MCPServerCategory,
  type MCPToolsResponse,
  type MCPServerResponse,
} from '@/api/mcp';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const categories: MCPServerCategory[] = [
  'infrastructure',
  'monitoring',
  'version-control',
  'databases',
  'cloud',
  'development',
  'other',
];

interface MarketplaceSource {
  id: string;
  name: string;
  url: string;
  status: 'connected' | 'disconnected' | 'error';
  lastSync?: Date;
  serverCount?: number;
}

export default function MCPMarketplacePage() {
  const { toast } = useToast();
  const { data: serversData } = useMCPServers();
  const createServerMutation = useCreateMCPServer();
  const updateServerMutation = useUpdateMCPServer();
  const deleteServerMutation = useDeleteMCPServer();
  const checkHealthMutation = useCheckMCPServerHealth();

  const servers = useMemo(() => serversData?.servers || [], [serversData?.servers]);
  const [activeTab, setActiveTab] = useState<'servers' | 'sources'>('servers');
  const [showAddServerModal, setShowAddServerModal] = useState(false);
  const [showAddSourceModal, setShowAddSourceModal] = useState(false);

  const [name, setName] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState<MCPServerCategory>('other');
  const [docsUrl, setDocsUrl] = useState('');
  const [healthMessages, setHealthMessages] = useState<Record<string, string>>({});

  const [sources, setSources] = useState<MarketplaceSource[]>([
    {
      id: 'default',
      name: 'Hydra Registry',
      url: import.meta.env.VITE_MCP_REGISTRY_URL || '/mcp/registry',
      status: 'connected',
      lastSync: new Date(),
      serverCount: 24,
    },
  ]);
  const [newSourceName, setNewSourceName] = useState('');
  const [newSourceUrl, setNewSourceUrl] = useState('');
  const [isSyncing, setIsSyncing] = useState<string | null>(null);

  const toolQueries = useQueries({
    queries: servers.map((server) => ({
      queryKey: queryKeys.mcp.tools(server.serverId),
      queryFn: async () => {
        const response = await apiClient.get<MCPToolsResponse>(
          `/mcp/servers/${server.serverId}/tools`
        );
        return response.data;
      },
      enabled: !!server.serverId,
    })),
  });

  const toolsByServerId = useMemo(() => {
    const toolMap = new Map<string, MCPToolsResponse['tools']>();
    servers.forEach((server, index) => {
      toolMap.set(server.serverId, toolQueries[index]?.data?.tools || []);
    });
    return toolMap;
  }, [servers, toolQueries]);

  const serversWithTools = useMemo(
    () =>
      servers.map((server) => ({
        ...server,
        tools: toolsByServerId.get(server.serverId) || [],
      })),
    [servers, toolsByServerId]
  );

  const handleAddServer = async () => {
    if (!name.trim() || !endpoint.trim()) {
      toast({
        title: 'Missing required fields',
        description: 'Name and endpoint are required.',
        variant: 'destructive',
      });
      return;
    }

    try {
      const server = await createServerMutation.mutateAsync({
        name: name.trim(),
        endpoint: endpoint.trim(),
        description: description.trim() || 'Custom MCP server',
        category,
        docsUrl: docsUrl.trim() || undefined,
        enabled: true,
      });

      setName('');
      setEndpoint('');
      setDescription('');
      setDocsUrl('');
      setCategory('other');
      setShowAddServerModal(false);

      const result = await checkHealthMutation.mutateAsync(server.serverId);
      setHealthMessages((prev) => ({
        ...prev,
        [server.serverId]: result.message,
      }));
    } catch {
      toast({
        title: 'Failed to add server',
        description: 'Please check the configuration and try again.',
        variant: 'destructive',
      });
    }
  };

  const handleAddSource = () => {
    if (!newSourceName.trim() || !newSourceUrl.trim()) return;
    const newSource: MarketplaceSource = {
      id: `source-${Date.now()}`,
      name: newSourceName.trim(),
      url: newSourceUrl.trim(),
      status: 'disconnected',
    };
    setSources([...sources, newSource]);
    setNewSourceName('');
    setNewSourceUrl('');
    setShowAddSourceModal(false);
  };

  const handleToggleServer = async (server: MCPServerResponse) => {
    const nextEnabled = !server.enabled;

    try {
      await updateServerMutation.mutateAsync({
        serverId: server.serverId,
        data: { enabled: nextEnabled },
      });

      if (nextEnabled) {
        const result = await checkHealthMutation.mutateAsync(server.serverId);
        setHealthMessages((prev) => ({
          ...prev,
          [server.serverId]: result.message,
        }));
        return;
      }

      setHealthMessages((prev) => {
        const next = { ...prev };
        delete next[server.serverId];
        return next;
      });
    } catch {
      toast({
        title: 'Failed to update server',
        description: 'Please try again.',
        variant: 'destructive',
      });
    }
  };

  const handleRemoveServer = async (serverId: string) => {
    try {
      await deleteServerMutation.mutateAsync(serverId);
      setHealthMessages((prev) => {
        const next = { ...prev };
        delete next[serverId];
        return next;
      });
    } catch {
      toast({
        title: 'Failed to remove server',
        description: 'Please try again.',
        variant: 'destructive',
      });
    }
  };

  const handleSyncSource = async (sourceId: string) => {
    setIsSyncing(sourceId);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setSources((prev) =>
      prev.map((s) =>
        s.id === sourceId
          ? { ...s, status: 'connected' as const, lastSync: new Date(), serverCount: Math.floor(Math.random() * 30) + 10 }
          : s
      )
    );
    setIsSyncing(null);
  };

  const handleRemoveSource = (sourceId: string) => {
    setSources((prev) => prev.filter((s) => s.id !== sourceId));
  };

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link to={ROUTES.CHAT}>
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Chat
            </Button>
          </Link>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-foreground">MCP Marketplace</h1>
            <p className="text-sm text-muted-foreground">
              Configure MCP servers and marketplace sources for the chat interface
            </p>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'servers' | 'sources')}>
          <TabsList className="bg-card border border-border">
            <TabsTrigger
              value="servers"
              className="data-[state=active]:bg-muted data-[state=active]:text-foreground text-muted-foreground"
            >
              <Server className="h-4 w-4 mr-2" />
              Servers ({servers.length})
            </TabsTrigger>
            <TabsTrigger
              value="sources"
              className="data-[state=active]:bg-muted data-[state=active]:text-foreground text-muted-foreground"
            >
              <Globe className="h-4 w-4 mr-2" />
              Marketplace Sources ({sources.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="servers" className="mt-6 space-y-6">
            <div className="flex justify-end">
              <Button onClick={() => setShowAddServerModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Server
              </Button>
            </div>

            {servers.length === 0 ? (
              <Card className="bg-card border-border">
                <CardContent className="p-8 text-center">
                  <Server className="mx-auto h-12 w-12 text-muted-foreground" />
                  <h3 className="mt-4 text-lg font-semibold text-foreground">No MCP servers configured</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Add a server to enable MCP tools in the chat interface.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <motion.div
                variants={staggerContainerVariants}
                initial="hidden"
                animate="visible"
                className="grid gap-4 md:grid-cols-2"
              >
                {serversWithTools.map((server) => (
                  <motion.div key={server.serverId} variants={staggerItemVariants}>
                    <Card className="bg-card border-border hover:border-foreground/20 transition-colors">
                      <CardContent className="p-5 space-y-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3">
                            <div
                              className={cn(
                                'h-10 w-10 rounded-lg flex items-center justify-center shrink-0',
                                server.enabled ? 'bg-success/10' : 'bg-muted'
                              )}
                            >
                              {server.serverId === 'hydra-mcp' ? (
                                <Terminal className="h-5 w-5 text-primary" />
                              ) : (
                                <Globe className="h-5 w-5 text-info" />
                              )}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="font-semibold text-foreground">{server.name}</h3>
                                <Badge
                                  variant="outline"
                                  className={cn(
                                    'text-[10px]',
                                    server.enabled && server.status === 'healthy'
                                      ? 'border-success/30 text-success'
                                      : server.enabled && server.status === 'unhealthy'
                                        ? 'border-destructive/30 text-destructive'
                                        : 'border-border text-muted-foreground'
                                  )}
                                >
                                  {server.enabled ? server.status : 'disabled'}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">{server.description}</p>
                            </div>
                          </div>
                          {server.enabled && server.status === 'unhealthy' && (
                            <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
                          )}
                        </div>

                        {server.endpoint && (
                          <div className="text-xs text-muted-foreground font-mono bg-muted/60 rounded px-2 py-1">
                            {server.endpoint}
                          </div>
                        )}

                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge variant="secondary" className="text-[10px] bg-muted text-muted-foreground capitalize">
                              {server.category.replace('-', ' ')}
                            </Badge>
                            {server.tools.length > 0 && (
                              <Badge variant="secondary" className="text-[10px] bg-primary/20 text-primary">
                                {server.tools.length} tools
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-1">
                            {server.docsUrl && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <a
                                    href={server.docsUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                  >
                                    <ExternalLink className="h-4 w-4" />
                                  </a>
                                </TooltipTrigger>
                                <TooltipContent className="bg-popover border-border text-foreground">
                                  View Docs
                                </TooltipContent>
                              </Tooltip>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleServer(server)}
                              className={cn(
                                'h-8 text-xs',
                                server.enabled
                                  ? 'text-destructive hover:text-destructive hover:bg-destructive/10'
                                  : 'text-success hover:text-success hover:bg-success/10'
                              )}
                            >
                              {server.enabled ? 'Disconnect' : 'Connect'}
                            </Button>
                            {server.serverId !== 'hydra-mcp' && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleRemoveServer(server.serverId)}
                                    className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                    aria-label={`Remove ${server.name}`}
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent className="bg-popover border-border text-foreground">
                                  Remove Server
                                </TooltipContent>
                              </Tooltip>
                            )}
                          </div>
                        </div>

                        {server.enabled &&
                          server.status === 'unhealthy' &&
                          healthMessages[server.serverId] && (
                          <p className="text-xs text-destructive bg-destructive/10 rounded px-2 py-1">
                            {healthMessages[server.serverId]}
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </TabsContent>

          <TabsContent value="sources" className="mt-6 space-y-6">
            <Card className="bg-card border-border">
              <CardHeader className="pb-4">
                <CardTitle className="text-foreground flex items-center gap-2 text-base">
                  <Link2 className="h-4 w-4 text-primary" />
                  Marketplace Sources
                </CardTitle>
                <CardDescription className="text-muted-foreground text-xs">
                  Add remote marketplace URLs to discover and install MCP servers. Hydra will fetch
                  available servers from these registries.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-end">
                  <Button onClick={() => setShowAddSourceModal(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Source
                  </Button>
                </div>

                {sources.length === 0 ? (
                  <div className="text-center py-8">
                    <Globe className="mx-auto h-12 w-12 text-muted-foreground" />
                    <h3 className="mt-4 text-lg font-semibold text-foreground">No marketplace sources</h3>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Add a marketplace source URL to discover MCP servers.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {sources.map((source) => (
                      <div
                        key={source.id}
                        className="flex items-center gap-4 p-4 rounded-lg bg-muted/60 border border-border"
                      >
                        <div
                          className={cn(
                            'h-10 w-10 rounded-lg flex items-center justify-center shrink-0',
                            source.status === 'connected' ? 'bg-success/10' : 'bg-muted'
                          )}
                        >
                          <Globe
                            className={cn(
                              'h-5 w-5',
                              source.status === 'connected' ? 'text-success' : 'text-muted-foreground'
                            )}
                          />
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-foreground">{source.name}</span>
                            {source.status === 'connected' ? (
                              <CheckCircle className="h-4 w-4 text-success" />
                            ) : source.status === 'error' ? (
                              <XCircle className="h-4 w-4 text-destructive" />
                            ) : null}
                          </div>
                          <div className="text-xs text-muted-foreground font-mono truncate">{source.url}</div>
                          {source.lastSync && (
                            <div className="text-[10px] text-muted-foreground mt-1">
                              Last synced: {source.lastSync.toLocaleString()} &bull;{' '}
                              {source.serverCount} servers available
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleSyncSource(source.id)}
                                disabled={isSyncing === source.id}
                                className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted"
                                aria-label={`Sync ${source.name}`}
                              >
                                {isSyncing === source.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <RefreshCw className="h-4 w-4" />
                                )}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent className="bg-popover border-border text-foreground">
                              Sync Now
                            </TooltipContent>
                          </Tooltip>

                          {source.id !== 'default' && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleRemoveSource(source.id)}
                                  className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                  aria-label={`Remove ${source.name}`}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent className="bg-popover border-border text-foreground">
                                Remove Source
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <Dialog open={showAddServerModal} onOpenChange={setShowAddServerModal}>
          <DialogContent className="bg-popover border-border text-foreground max-w-md">
            <DialogHeader>
              <DialogTitle>Add MCP Server</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Configure a new MCP server connection.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label className="text-foreground">Name *</Label>
                <Input
                  aria-label="Server name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., My MCP Server"
                  className="bg-background border-border text-foreground"
                />
              </div>

              <div className="space-y-2">
                <Label className="text-foreground">Endpoint URL</Label>
                <Input
                  aria-label="Server endpoint URL"
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  placeholder="ws://localhost:3000 or http://..."
                  className="bg-background border-border text-foreground"
                />
              </div>

              <div className="space-y-2">
                <Label className="text-foreground">Description</Label>
                <Input
                  aria-label="Server description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional description"
                  className="bg-background border-border text-foreground"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-foreground">Category</Label>
                  <Select value={category} onValueChange={(v) => setCategory(v as MCPServerCategory)}>
                    <SelectTrigger
                      className="bg-background border-border text-foreground"
                      aria-label="Server category"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-popover border-border">
                      {categories.map((cat) => (
                        <SelectItem key={cat} value={cat} className="text-foreground capitalize">
                          {cat.replace('-', ' ')}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label className="text-foreground">Docs URL</Label>
                  <Input
                    aria-label="Server docs URL"
                    value={docsUrl}
                    onChange={(e) => setDocsUrl(e.target.value)}
                    placeholder="https://..."
                    className="bg-background border-border text-foreground"
                  />
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowAddServerModal(false)}
                className="border-border text-foreground hover:bg-muted bg-transparent"
              >
                Cancel
              </Button>
              <Button
                onClick={handleAddServer}
                disabled={!name.trim()}
              >
                Add Server
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={showAddSourceModal} onOpenChange={setShowAddSourceModal}>
          <DialogContent className="bg-popover border-border text-foreground max-w-md">
            <DialogHeader>
              <DialogTitle>Add Marketplace Source</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Add a remote marketplace URL to discover MCP servers.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label className="text-foreground">Name *</Label>
                <Input
                  aria-label="Marketplace source name"
                  value={newSourceName}
                  onChange={(e) => setNewSourceName(e.target.value)}
                  placeholder="e.g., Community Registry"
                  className="bg-background border-border text-foreground"
                />
              </div>

              <div className="space-y-2">
                <Label className="text-foreground">URL *</Label>
                <Input
                  aria-label="Marketplace source URL"
                  value={newSourceUrl}
                  onChange={(e) => setNewSourceUrl(e.target.value)}
                  placeholder="https://registry.example.com/mcp"
                  className="bg-background border-border text-foreground"
                />
                <p className="text-[10px] text-muted-foreground">
                  The URL should return a JSON list of available MCP servers.
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowAddSourceModal(false)}
                className="border-border text-foreground hover:bg-muted bg-transparent"
              >
                Cancel
              </Button>
              <Button
                onClick={handleAddSource}
                disabled={!newSourceName.trim() || !newSourceUrl.trim()}
              >
                Add Source
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
