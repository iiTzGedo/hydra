import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  Position,
  ConnectionMode,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  RefreshCw,
  Maximize,
  Eye,
  EyeOff,
  Loader2,
} from 'lucide-react';
import { useLatestTopology, useGenerateTopology } from '@/api/topologies';
import { TopologyNode as TopologyNodeType } from '@/types/topology';
import { PageHeader } from '@/components/layout/page-header';
import { TopologyNodeComponent } from '@/components/topology/topology-node';
import { TopologyDetailPanel } from '@/components/topology/detail-panel';
import { NODE_CLASS_COLORS } from '@/lib/constants';
import { cn } from '@/lib/utils';

const nodeTypes = {
  topology: TopologyNodeComponent,
};

export default function TopologyPage() {
  const { data: topology, isLoading, refetch } = useLatestTopology();
  const generateMutation = useGenerateTopology();

  const [selectedNode, setSelectedNode] = useState<TopologyNodeType | null>(null);
  const [showMiniMap, setShowMiniMap] = useState(true);
  const [filterClass, setFilterClass] = useState<string | null>(null);

  // Convert topology data to ReactFlow nodes and edges
  const { initialNodes, initialEdges } = useMemo(() => {
    const topologyNodes = topology?.graph?.nodes || [];
    const topologyEdges = topology?.graph?.edges || [];

    if (!topologyNodes.length) {
      return { initialNodes: [], initialEdges: [] };
    }

    // Filter by class if selected
    const filteredTopologyNodes = filterClass
      ? topologyNodes.filter((n) => n.data?.class === filterClass)
      : topologyNodes;

    // Calculate grid layout with smart positioning
    const nodeCount = filteredTopologyNodes.length;
    const cols = Math.ceil(Math.sqrt(nodeCount));
    const spacing = { x: 200, y: 150 };

    // Group nodes by class for better layout
    const nodesByClass: Record<string, typeof filteredTopologyNodes> = {};
    filteredTopologyNodes.forEach((node) => {
      const nodeClass = node.data?.class || 'unknown';
      if (!nodesByClass[nodeClass]) nodesByClass[nodeClass] = [];
      nodesByClass[nodeClass].push(node);
    });

    let nodeIndex = 0;
    const nodes: Node[] = [];

    Object.entries(nodesByClass).forEach(([, classNodes]) => {
      classNodes.forEach((node) => {
        const row = Math.floor(nodeIndex / cols);
        const col = nodeIndex % cols;
        nodes.push({
          id: node.id,
          type: 'topology',
          position: {
            x: col * spacing.x + 50,
            y: row * spacing.y + 50,
          },
          data: {
            ...node,
            label: node.id,
          },
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
        });
        nodeIndex++;
      });
    });

    // Create node ID set for filtering edges
    const nodeIds = new Set(nodes.map((n) => n.id));

    // Create edges from topology edges
    const edges: Edge[] = topologyEdges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge, index) => ({
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
        type: 'smoothstep',
        animated: edge.type === 'network',
        style: {
          stroke: 'hsl(var(--muted-foreground))',
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

    return { initialNodes: nodes, initialEdges: edges };
  }, [topology, filterClass]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes/edges when topology changes
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const topologyNode = topology?.graph?.nodes.find((n) => n.id === node.id);
      setSelectedNode(topologyNode || null);
    },
    [topology]
  );

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleRegenerateTopology = async () => {
    await generateMutation.mutateAsync({ mode: 'infrastructure' });
    refetch();
  };

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-3.5rem)] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-2 text-muted-foreground">Loading topology...</p>
        </div>
      </div>
    );
  }

  if (!topology?.graph?.nodes?.length) {
    return (
      <div className="p-6">
        <PageHeader
          title="Infrastructure Topology"
          description="Visualize your infrastructure as an interactive graph"
        />
        <div className="rounded-xl border bg-card p-8 text-center">
          <Maximize className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No topology data</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Generate a topology from your registered nodes
          </p>
          <button
            onClick={handleRegenerateTopology}
            disabled={generateMutation.isPending}
            className={cn(
              'mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {generateMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Generate Topology
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Header */}
      <div className="border-b p-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Infrastructure Topology</h1>
          <p className="text-sm text-muted-foreground">
            {topology.graph?.nodes.length || 0} nodes • {topology.graph?.edges?.length || 0} connections
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Class filter */}
          <select
            value={filterClass || ''}
            onChange={(e) => setFilterClass(e.target.value || null)}
            className={cn(
              'rounded-lg border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring'
            )}
          >
            <option value="">All Classes</option>
            <option value="compute">Compute</option>
            <option value="networking">Networking</option>
            <option value="iot">IoT</option>
          </select>

          {/* Toggle minimap */}
          <button
            onClick={() => setShowMiniMap(!showMiniMap)}
            className={cn(
              'rounded-lg border px-3 py-2 text-sm',
              'hover:bg-muted transition-colors',
              showMiniMap && 'bg-muted'
            )}
          >
            {showMiniMap ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
          </button>

          {/* Regenerate */}
          <button
            onClick={handleRegenerateTopology}
            disabled={generateMutation.isPending}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm',
              'hover:bg-muted transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {generateMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Regenerate
          </button>
        </div>
      </div>

      {/* Topology canvas */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onPaneClick={handlePaneClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
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
                const colors = NODE_CLASS_COLORS[node.data?.class as keyof typeof NODE_CLASS_COLORS];
                if (colors) {
                  // Return CSS color based on class
                  switch (node.data?.class) {
                    case 'compute':
                      return '#8B5CF6';
                    case 'networking':
                      return '#06B6D4';
                    case 'iot':
                      return '#10B981';
                    default:
                      return '#6B7280';
                  }
                }
                return '#6B7280';
              }}
              maskColor="hsl(var(--background) / 0.8)"
              pannable
              zoomable
            />
          )}

          {/* Legend */}
          <Panel position="bottom-left" className="bg-card/90 backdrop-blur rounded-lg border p-3 shadow-lg">
            <div className="text-xs font-medium mb-2">Node Classes</div>
            <div className="flex flex-col gap-1">
              {Object.entries(NODE_CLASS_COLORS).map(([nodeClass, colors]) => (
                <div key={nodeClass} className="flex items-center gap-2">
                  <div className={cn('h-3 w-3 rounded', colors.bg)} />
                  <span className="text-xs capitalize">{nodeClass}</span>
                </div>
              ))}
            </div>
          </Panel>
        </ReactFlow>

        {/* Detail panel */}
        {selectedNode && (
          <TopologyDetailPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
}
