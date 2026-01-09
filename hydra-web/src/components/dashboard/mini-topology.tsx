import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ReactFlow,
  Background,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { motion } from 'framer-motion';
import { ArrowRight, Maximize2 } from 'lucide-react';
import { useLatestTopology } from '@/api/topologies';
import { ROUTES, NODE_CLASS_COLORS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

// Custom node component for topology
function TopologyNode({ data }: { data: { label: string; class: string; type: string } }) {
  const classColors: Record<string, string> = {
    compute: 'bg-compute',
    networking: 'bg-network',
    iot: 'bg-iot',
  };
  const colorClass = classColors[data.class] || 'bg-muted-foreground';

  return (
    <div
      className={cn(
        'rounded-lg border-2 px-3 py-2 text-xs font-medium shadow-sm',
        'bg-card border-border',
        'min-w-[80px] text-center'
      )}
    >
      <div className={cn('mx-auto mb-1 h-2 w-2 rounded-full', colorClass)} />
      <div className="truncate text-foreground">{data.label}</div>
      <div className="text-[10px] text-muted-foreground">{data.type}</div>
    </div>
  );
}

const nodeTypes = {
  topology: TopologyNode,
};

export function MiniTopology() {
  const { data: topology, isLoading } = useLatestTopology();

  // Convert topology data to ReactFlow nodes and edges
  const { initialNodes, initialEdges } = useMemo(() => {
    const topologyNodes = topology?.graph?.nodes || [];
    const topologyEdges = topology?.graph?.edges || [];

    if (!topologyNodes.length) {
      return { initialNodes: [], initialEdges: [] };
    }

    // Create nodes with positions (simple grid layout for mini view)
    const nodes: Node[] = topologyNodes.slice(0, 12).map((node, index) => ({
      id: node.id,
      type: 'topology',
      position: {
        x: (index % 4) * 150 + 50,
        y: Math.floor(index / 4) * 100 + 50,
      },
      data: {
        label: node.label || node.id,
        class: node.data?.class || 'compute',
        type: node.type || 'unknown',
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }));

    // Create edges from topology edges
    const edges: Edge[] = topologyEdges
      .filter((edge) => {
        const sourceExists = nodes.some((n) => n.id === edge.source);
        const targetExists = nodes.some((n) => n.id === edge.target);
        return sourceExists && targetExists;
      })
      .map((edge, index) => ({
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
        type: 'smoothstep',
        animated: edge.type === 'network',
        style: { stroke: 'hsl(var(--border))', strokeWidth: 1 },
      }));

    return { initialNodes: nodes, initialEdges: edges };
  }, [topology]);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  if (isLoading) {
    return (
      <Card className="bg-card border-border">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-foreground">Infrastructure Topology</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] animate-pulse rounded-lg bg-muted" />
        </CardContent>
      </Card>
    );
  }

  if (!topology?.graph?.nodes?.length) {
    return (
      <Card className="bg-card border-border">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-foreground">Infrastructure Topology</CardTitle>
          <Link to={ROUTES.TOPOLOGY}>
            <Button variant="outline" size="sm">
              Open full view
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          <div className="flex h-[300px] items-center justify-center rounded-lg bg-muted/60">
            <p className="text-muted-foreground">No topology data available</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-foreground">Infrastructure Topology</CardTitle>
        <Link to={ROUTES.TOPOLOGY}>
          <Button variant="outline" size="sm">
            <Maximize2 className="mr-2 h-4 w-4" />
            Full view
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="h-[300px] rounded-lg overflow-hidden border border-border"
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.5}
            maxZoom={1.5}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            panOnDrag={false}
            zoomOnScroll={false}
            preventScrolling
          >
            <Background color="hsl(var(--border))" gap={20} size={1} />
          </ReactFlow>
        </motion.div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-3">
          <div className="flex items-center gap-2 text-xs">
            <div className="h-2 w-2 rounded-full bg-compute" />
            <span className="text-muted-foreground">Compute</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="h-2 w-2 rounded-full bg-network" />
            <span className="text-muted-foreground">Networking</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="h-2 w-2 rounded-full bg-iot" />
            <span className="text-muted-foreground">IoT</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
