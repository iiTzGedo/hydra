import { useState, useCallback, useMemo, useEffect } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Node,
  Edge,
  Position,
  ConnectionMode,
  MarkerType,
  type Viewport,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  RefreshCw,
  Maximize,
  Eye,
  EyeOff,
  Loader2,
  Server,
  Network,
  Boxes,
  Search,
  X,
  Share2,
  Users,
} from 'lucide-react';
import { useLatestTopology, useGenerateTopology, usePrefetchTopologyModes } from '@/api/topologies';
import { useGroups, useGroup, useGroupMembers } from '@/api/groups';
import { TopologyNode as TopologyNodeType, TopologyMode } from '@/types/topology';
import { TopologyNodeComponent } from '@/components/topology/topology-node';
import { TopologyDetailPanel } from '@/components/topology/detail-panel';
import { NODE_CLASS_COLORS } from '@/lib/constants';
import { getLayoutedElements, getGridLayout, getLayoutOptionsForMode } from '@/lib/topology-layout';
import { cn } from '@/lib/utils';
import { useUiStore } from '@/stores/ui-store';
import { useTopologyStore } from '@/stores/topology-store';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

const nodeTypes = {
  topology: TopologyNodeComponent,
};

const modeOptions: { value: TopologyMode; label: string; icon: typeof Server; description: string }[] = [
  {
    value: 'infrastructure',
    label: 'Infrastructure',
    icon: Server,
    description: 'Nodes and parent-child relationships',
  },
  {
    value: 'network',
    label: 'Network',
    icon: Network,
    description: 'Networks and connected nodes',
  },
  {
    value: 'service',
    label: 'Service',
    icon: Boxes,
    description: 'Services and their host nodes',
  },
];

export default function TopologyPage() {
  useDocumentTitle('Topology');

  const { topologyMode, setTopologyMode } = useUiStore();
  const {
    selectedGroupId,
    setSelectedGroupId,
    highlightedNodeIds,
    setHighlightedNodeIds,
    setViewport,
    getViewport,
  } = useTopologyStore();
  const { data: topology, isLoading, refetch } = useLatestTopology(topologyMode);
  const generateMutation = useGenerateTopology();
  const { prefetch: prefetchTopologyModes } = usePrefetchTopologyModes();
  const { data: groupsData } = useGroups({});
  const { data: selectedGroup } = useGroup(selectedGroupId || '');
  const { data: selectedGroupMembers } = useGroupMembers(selectedGroupId || '', {
    entityType: 'node',
    limit: 1000,
  });

  // Prefetch other topology modes when current mode loads
  useEffect(() => {
    if (!isLoading && topology) {
      prefetchTopologyModes(topologyMode);
    }
  }, [isLoading, topology, topologyMode, prefetchTopologyModes]);

  const [selectedNode, setSelectedNode] = useState<TopologyNodeType | null>(null);
  const [showMiniMap, setShowMiniMap] = useState(true);
  const [filterClass, setFilterClass] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Get saved viewport for current mode
  const savedViewport = getViewport(topologyMode);

  // Handler to save viewport on move end
  const handleMoveEnd = useCallback(
    (_event: unknown, viewport: Viewport) => {
      setViewport(topologyMode, {
        x: viewport.x,
        y: viewport.y,
        zoom: viewport.zoom,
      });
    },
    [topologyMode, setViewport]
  );

  // Update highlighted nodes when selected group changes
  useEffect(() => {
    if (selectedGroupMembers?.items?.length) {
      // Extract node IDs from group members
      const nodeIds = selectedGroupMembers.items
        .filter((m) => m.type === 'node')
        .map((m) => m.id);
      setHighlightedNodeIds(nodeIds);
    } else {
      setHighlightedNodeIds([]);
    }
  }, [selectedGroupMembers, setHighlightedNodeIds]);

  // Build nodes and edges from topology data
  const { rawNodes, rawEdges, layoutOptions } = useMemo(() => {
    const topologyNodes = topology?.graph?.nodes || [];
    const topologyEdges = topology?.graph?.edges || [];

    if (!topologyNodes.length) {
      return { rawNodes: [], rawEdges: [], layoutOptions: getLayoutOptionsForMode(topologyMode, 0) };
    }

    // Apply filters
    let filteredTopologyNodes = filterClass !== 'all'
      ? topologyNodes.filter((n) => n.data?.class === filterClass)
      : topologyNodes;

    // Apply search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filteredTopologyNodes = filteredTopologyNodes.filter((n) => {
        const id = n.id.toLowerCase();
        const label = (n.label || '').toLowerCase();
        const nodeId = (n.data?.nodeId || '').toLowerCase();
        const serviceId = (n.data?.serviceId || '').toLowerCase();
        const networkId = (n.data?.networkId || '').toLowerCase();
        return (
          id.includes(query) ||
          label.includes(query) ||
          nodeId.includes(query) ||
          serviceId.includes(query) ||
          networkId.includes(query)
        );
      });
    }

    // Create ReactFlow nodes with initial positions
    const nodeCount = filteredTopologyNodes.length;
    const nodes: Node[] = filteredTopologyNodes.map((node) => {
      const nodeId = node.data?.nodeId as string | undefined;
      const isHighlighted = nodeId ? highlightedNodeIds.includes(nodeId) : false;
      return {
        id: node.id,
        type: 'topology',
        position: node.position || { x: 0, y: 0 }, // Will be set by layout
        data: {
          ...node,
          label: node.label || node.id,
          isHighlighted,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      };
    });

    // Create ReactFlow edges
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges: Edge[] = topologyEdges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge, index) => ({
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
        type: 'smoothstep',
        animated: edge.type === 'network-connection' || edge.type === 'service-dependency',
        style: {
          stroke: getEdgeColor(edge.type),
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 15,
          height: 15,
        },
        label: edge.label,
        labelStyle: { fontSize: 10, fill: 'hsl(var(--muted-foreground))' },
      }));

    // Get layout options for this mode
    const options = getLayoutOptionsForMode(topologyMode, nodeCount);

    // Apply grid layout initially (sync) - ELK layout will be applied async
    const gridLayoutedNodes = getGridLayout(nodes, options);

    return { rawNodes: gridLayoutedNodes, rawEdges: edges, layoutOptions: options };
  }, [topology, topologyMode, filterClass, searchQuery, highlightedNodeIds]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Apply async ELK layout when nodes change
  useEffect(() => {
    if (rawNodes.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }

    // Set grid layout immediately for quick feedback
    setNodes(rawNodes);
    setEdges(rawEdges);

    // Then compute ELK layout asynchronously
    let cancelled = false;
    getLayoutedElements(rawNodes, rawEdges, layoutOptions)
      .then(({ nodes: elkNodes }) => {
        if (!cancelled) {
          setNodes(elkNodes);
        }
      })
      .catch((error) => {
        console.error('ELK layout failed:', error);
        // Keep grid layout on error
      });

    return () => {
      cancelled = true;
    };
  }, [rawNodes, rawEdges, layoutOptions, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const topologyNode = topology?.graph?.nodes?.find((n) => n.id === node.id);
      setSelectedNode(topologyNode || null);
    },
    [topology]
  );

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleRegenerateTopology = async () => {
    await generateMutation.mutateAsync({ mode: topologyMode });
    refetch();
  };

  const handleModeChange = (mode: string) => {
    setTopologyMode(mode as TopologyMode);
    // Don't reset filters/search/selection on mode change to preserve user context
  };

  const currentModeOption = modeOptions.find((m) => m.value === topologyMode) || modeOptions[0];

  // Check if we have no data (not just loading)
  const hasNoData = !isLoading && !topology?.graph?.nodes?.length;

  return (
    <TooltipProvider>
      <div className="h-[calc(100vh-3.5rem)] flex flex-col">
        <div className="border-b p-4 flex items-center justify-between flex-wrap gap-4 bg-background">
          <div className="flex items-center gap-4">
            <Tabs value={topologyMode} onValueChange={handleModeChange}>
              <TabsList>
                {modeOptions.map((option) => {
                  const Icon = option.icon;
                  return (
                    <TabsTrigger key={option.value} value={option.value} className="gap-1.5" title={option.description}>
                      <Icon className="h-4 w-4" />
                      <span className="hidden sm:inline">{option.label}</span>
                    </TabsTrigger>
                  );
                })}
              </TabsList>
            </Tabs>

            <div>
              <h1 className="text-lg font-semibold">{currentModeOption.label} Topology</h1>
              <div className="text-sm text-muted-foreground">
                <Badge variant="secondary" className="mr-2">{topology?.graph?.nodes?.length || 0} nodes</Badge>
                <Badge variant="outline">{topology?.graph?.edges?.length || 0} connections</Badge>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search nodes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-48 pl-9 pr-8"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            <Select value={filterClass} onValueChange={setFilterClass}>
              <SelectTrigger className="w-[130px]">
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {topologyMode === 'service' ? (
                  <>
                    <SelectItem value="service">Services</SelectItem>
                    <SelectItem value="compute">Hosts</SelectItem>
                  </>
                ) : topologyMode === 'network' ? (
                  <>
                    <SelectItem value="network">Networks</SelectItem>
                    <SelectItem value="compute">Compute</SelectItem>
                    <SelectItem value="networking">Networking</SelectItem>
                    <SelectItem value="iot">IoT</SelectItem>
                  </>
                ) : (
                  <>
                    <SelectItem value="compute">Compute</SelectItem>
                    <SelectItem value="networking">Networking</SelectItem>
                    <SelectItem value="iot">IoT</SelectItem>
                  </>
                )}
              </SelectContent>
            </Select>

            <Tooltip>
              <TooltipTrigger asChild>
                <div>
                  <Select
                    value={selectedGroupId || 'none'}
                    onValueChange={(value) => setSelectedGroupId(value === 'none' ? null : value)}
                  >
                    <SelectTrigger className="w-[150px]">
                      <Users className="h-4 w-4 mr-2" />
                      <SelectValue placeholder="Highlight Group" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No Highlight</SelectItem>
                      {groupsData?.items?.map((group) => (
                        <SelectItem key={group.id} value={group.id}>
                          {group.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                Highlight group members
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={showMiniMap ? 'secondary' : 'outline'}
                  size="icon"
                  onClick={() => setShowMiniMap(!showMiniMap)}
                >
                  {showMiniMap ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {showMiniMap ? 'Hide minimap' : 'Show minimap'}
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  onClick={handleRegenerateTopology}
                  disabled={generateMutation.isPending}
                >
                  {generateMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                  <span className="ml-2 hidden sm:inline">Regenerate</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Regenerate topology from current data</TooltipContent>
            </Tooltip>
          </div>
        </div>

        <div className="flex-1 relative">
          {/* Loading overlay - only covers the graph area */}
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-50">
              <div className="text-center">
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
                <p className="mt-2 text-muted-foreground">Loading {currentModeOption.label.toLowerCase()} topology...</p>
              </div>
            </div>
          )}

          {/* Empty state - shown when no data */}
          {hasNoData && (
            <div className="absolute inset-0 flex items-center justify-center z-40">
              <Card className="max-w-md">
                <CardContent className="p-8 text-center">
                  <Share2 className="mx-auto h-12 w-12 text-muted-foreground" />
                  <h3 className="mt-4 text-lg font-semibold">No {currentModeOption.label.toLowerCase()} topology data</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Generate a {currentModeOption.label.toLowerCase()} topology from your registered nodes
                  </p>
                  <Button
                    onClick={handleRegenerateTopology}
                    disabled={generateMutation.isPending}
                    className="mt-4"
                  >
                    {generateMutation.isPending ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4 mr-2" />
                    )}
                    Generate Topology
                  </Button>
                </CardContent>
              </Card>
            </div>
          )}

          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            onPaneClick={handlePaneClick}
            onMoveEnd={handleMoveEnd}
            nodeTypes={nodeTypes}
            fitView={!savedViewport}
            fitViewOptions={{ padding: 0.2 }}
            defaultViewport={savedViewport || undefined}
            minZoom={0.1}
            maxZoom={2}
            connectionMode={ConnectionMode.Loose}
            defaultEdgeOptions={{
              type: 'smoothstep',
            }}
          >
            <Background color="hsl(var(--muted-foreground))" gap={20} size={1} />
            <Controls showInteractive={false} />
            {showMiniMap && (
              <MiniMap
                nodeColor={(node) => {
                  const nodeClass = node.data?.class || node.data?.type;
                  switch (nodeClass) {
                    case 'compute':
                    case 'compute-physical':
                    case 'compute-logical':
                      return '#8B5CF6';
                    case 'networking':
                      return '#06B6D4';
                    case 'iot':
                      return '#10B981';
                    case 'service':
                      return '#F59E0B';
                    case 'network':
                      return '#3B82F6';
                    default:
                      return '#6B7280';
                  }
                }}
                maskColor="hsl(var(--background) / 0.8)"
                pannable
                zoomable
              />
            )}

            <Panel position="bottom-left" className="bg-card/90 backdrop-blur rounded-lg border p-3 shadow-lg">
              <div className="text-xs font-medium mb-2 text-muted-foreground uppercase tracking-wider">Node Types</div>
              <div className="flex flex-col gap-1.5">
                {topologyMode === 'service' ? (
                  <>
                    <div className="flex items-center gap-2">
                      <div className="h-3 w-3 rounded bg-amber-500" />
                      <span className="text-xs">Service</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-3 w-3 rounded bg-violet-500" />
                      <span className="text-xs">Host</span>
                    </div>
                  </>
                ) : topologyMode === 'network' ? (
                  <>
                    <div className="flex items-center gap-2">
                      <div className="h-3 w-3 rounded bg-blue-500" />
                      <span className="text-xs">Network</span>
                    </div>
                    {Object.entries(NODE_CLASS_COLORS).map(([nodeClass, colors]) => (
                      <div key={nodeClass} className="flex items-center gap-2">
                        <div className={cn('h-3 w-3 rounded', colors.bg)} />
                        <span className="text-xs capitalize">{nodeClass}</span>
                      </div>
                    ))}
                  </>
                ) : (
                  Object.entries(NODE_CLASS_COLORS).map(([nodeClass, colors]) => (
                    <div key={nodeClass} className="flex items-center gap-2">
                      <div className={cn('h-3 w-3 rounded', colors.bg)} />
                      <span className="text-xs capitalize">{nodeClass}</span>
                    </div>
                  ))
                )}
              </div>
            </Panel>
          </ReactFlow>

          {selectedNode && (
            <TopologyDetailPanel
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
            />
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}

function getEdgeColor(edgeType: string): string {
  switch (edgeType) {
    case 'network-connection':
      return '#3B82F6'; // blue
    case 'parent-child':
      return '#8B5CF6'; // violet
    case 'service-host':
      return '#F59E0B'; // amber
    case 'service-dependency':
      return '#EF4444'; // red
    case 'network-gateway':
      return '#06B6D4'; // cyan
    case 'vlan-trunk':
      return '#10B981'; // emerald
    default:
      return 'hsl(var(--muted-foreground))';
  }
}
