import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Server,
  Network,
  Cpu,
  Clock,
  Loader2,
} from 'lucide-react';
import { TopologyNodeComponent } from '@/components/topology/topology-node';
import { ROUTES, NODE_CLASS_COLORS } from '@/lib/constants';
import { cn, formatDate } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

interface HistoricalTopologyProps {
  timestamp: Date;
  compareTimestamp: Date | null;
  topologyState: {
    nodes?: Array<{
      id: string;
      class: string;
      type: string;
      kind: string;
      status: string;
    }>;
    edges?: Array<{
      from: string;
      to: string;
      type?: string;
    }>;
  } | null;
  isLoading: boolean;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const nodeTypes: Record<string, any> = {
  topology: TopologyNodeComponent,
};

const classIcons = {
  compute: Server,
  networking: Network,
  iot: Cpu,
};

export function HistoricalTopology({
  timestamp,
  compareTimestamp: _compareTimestamp,
  topologyState,
  isLoading,
}: HistoricalTopologyProps) {
  const { nodes, edges } = useMemo(() => {
    if (!topologyState?.nodes?.length) {
      return { nodes: [], edges: [] };
    }

    const cols = Math.ceil(Math.sqrt(topologyState.nodes.length));
    const spacing = { x: 200, y: 150 };

    const rfNodes: Node[] = topologyState.nodes.map((node, index) => ({
      id: node.id,
      type: 'topology',
      position: {
        x: (index % cols) * spacing.x + 50,
        y: Math.floor(index / cols) * spacing.y + 50,
      },
      data: {
        ...node,
        label: node.id,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }));

    const nodeIds = new Set(rfNodes.map((n) => n.id));

    const rfEdges: Edge[] = (topologyState.edges || [])
      .filter((e) => nodeIds.has(e.from) && nodeIds.has(e.to))
      .map((edge, index) => ({
        id: `edge-${index}`,
        source: edge.from,
        target: edge.to,
        type: 'smoothstep',
        animated: edge.type === 'network',
        style: {
          stroke: 'hsl(var(--muted-foreground))',
          strokeWidth: 1,
        },
      }));

    return { nodes: rfNodes, edges: rfEdges };
  }, [topologyState]);

  const [flowNodes, , onNodesChange] = useNodesState(nodes);
  const [flowEdges, , onEdgesChange] = useEdgesState(edges);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-2 text-muted-foreground">Loading historical state...</p>
        </div>
      </div>
    );
  }

  if (!topologyState?.nodes?.length) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <Clock className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No data at this time</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            No topology snapshot exists for {formatDate(timestamp)}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex">
      <div className="flex-1 relative">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.1}
          maxZoom={2}
          nodesDraggable={false}
          nodesConnectable={false}
        >
          <Background color="hsl(var(--muted-foreground))" gap={20} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>

        <div className="absolute top-4 left-4 rounded-lg bg-card/90 backdrop-blur border px-3 py-2 shadow-lg">
          <div className="flex items-center gap-2 text-sm">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{formatDate(timestamp)}</span>
          </div>
        </div>
      </div>

      <div className="w-80 border-l bg-card overflow-auto">
        <div className="p-4 border-b sticky top-0 bg-card z-10">
          <h3 className="font-semibold">Nodes at this time</h3>
          <p className="text-sm text-muted-foreground">
            {topologyState.nodes.length} nodes captured
          </p>
        </div>

        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="p-2 space-y-1"
        >
          {topologyState.nodes.map((node) => {
            const Icon = classIcons[node.class as keyof typeof classIcons] || Server;
            const colors = NODE_CLASS_COLORS[node.class as keyof typeof NODE_CLASS_COLORS];

            return (
              <motion.div key={node.id} variants={staggerItemVariants}>
                <Link
                  to={ROUTES.NODES + '/' + node.id}
                  className="flex items-center gap-3 rounded-lg p-2 hover:bg-muted transition-colors"
                >
                  <div className={cn('rounded-lg p-1.5', colors?.bg || 'bg-muted')}>
                    <Icon className="h-4 w-4 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{node.id}</div>
                    <div className="text-xs text-muted-foreground capitalize">
                      {node.class} • {node.kind}
                    </div>
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </div>
  );
}
