import { useMemo, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
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
import { motion } from 'framer-motion';
import { Server, Wifi, Cpu } from 'lucide-react';
import { useLatestTopology } from '@/api/topologies';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';

// Node class icons
const classIcons: Record<string, React.ElementType> = {
  compute: Cpu,
  networking: Wifi,
  iot: Server,
};

// Node class colors using CSS variables
const classColors: Record<string, string> = {
  compute: 'bg-compute',
  networking: 'bg-network',
  iot: 'bg-iot',
};

const classBorderColors: Record<string, string> = {
  compute: 'border-compute',
  networking: 'border-network',
  iot: 'border-iot',
};

/**
 * Custom node component for topology graph
 */
function TopologyNode({
  data,
}: {
  data: {
    label: string;
    class: string;
    type: string;
    nodeId: string;
    onClick: (nodeId: string) => void;
  };
}) {
  const colorClass = classColors[data.class] || 'bg-muted-foreground';
  const borderColorClass = classBorderColors[data.class] || 'border-border';
  const Icon = classIcons[data.class] || Server;

  return (
    <button
      onClick={() => data.onClick(data.nodeId)}
      className={cn(
        'rounded-lg border-2 px-3 py-2 text-xs font-medium shadow-sm',
        'bg-card hover:bg-muted',
        'transition-all duration-200 hover:shadow-md hover:scale-105',
        'min-w-[100px] text-center group',
        borderColorClass,
        'focus:outline-none focus:ring-2 focus:ring-primary/30'
      )}
    >
      <div className={cn('mx-auto mb-1.5 h-2.5 w-2.5 rounded-full', colorClass)} />
      <Icon className="h-4 w-4 mx-auto mb-1 text-muted-foreground group-hover:text-foreground transition-colors" />
      <div className="truncate text-foreground max-w-[120px]" title={data.label}>
        {data.label}
      </div>
      <div className="text-[10px] text-muted-foreground capitalize truncate max-w-[100px]" title={data.type}>
        {data.type}
      </div>
    </button>
  );
}

const nodeTypes = {
  topology: TopologyNode,
};

/**
 * Calculate optimal layout positions for nodes
 * Uses a simple grid layout that adapts to node count
 */
function calculateLayout(index: number, total: number): { x: number; y: number } {
  // Adaptive grid based on total nodes
  let columns = 4;
  if (total <= 4) columns = 2;
  else if (total <= 6) columns = 3;
  else if (total <= 12) columns = 4;
  else columns = 5;

  const col = index % columns;
  const row = Math.floor(index / columns);

  // Spacing
  const xSpacing = 180;
  const ySpacing = 120;

  // Center the grid
  const totalCols = Math.min(columns, total);
  const startX = (totalCols - 1) * xSpacing * 0.5;

  return {
    x: col * xSpacing - startX + 100, // +100 for padding
    y: row * ySpacing + 50, // +50 for padding
  };
}

/**
 * MiniTopology - Dashboard widget showing infrastructure topology
 *
 * Features:
 * - Clickable nodes that navigate to node detail
 * - Zoom and pan controls
 * - Shows up to 12 nodes with truncation indicator
 * - Responsive sizing
 * - Links to full topology view
 *
 * @example
 * <MiniTopology />
 */
export function MiniTopology() {
  const navigate = useNavigate();
  const { data: topology, isLoading, error } = useLatestTopology();

  const totalNodes = topology?.graph?.nodes?.length ?? 0;
  const allNodes = topology?.graph?.nodes ?? [];
  const displayedNodes = allNodes.slice(0, 12);
  const hasMoreNodes = totalNodes > 12;

  // Handle node click - navigate to node detail
  const handleNodeClick = useCallback(
    (nodeId: string) => {
      navigate(`${ROUTES.NODES}/${nodeId}`);
    },
    [navigate]
  );

  // Build ReactFlow nodes
  const { initialNodes, initialEdges } = useMemo(() => {
    if (!displayedNodes.length) {
      return { initialNodes: [], initialEdges: [] };
    }

    const nodes: Node[] = displayedNodes.map((node, index) => ({
      id: node.id,
      type: 'topology',
      position: calculateLayout(index, displayedNodes.length),
      data: {
        label: node.label || node.id,
        class: node.data?.class || 'compute',
        type: node.type || 'unknown',
        nodeId: node.id,
        onClick: handleNodeClick,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }));

    // Filter edges to only include visible nodes
    const topologyEdges = topology?.graph?.edges ?? [];
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
        style: { stroke: 'hsl(var(--border))', strokeWidth: 1.5 },
      }));

    return { initialNodes: nodes, initialEdges: edges };
  }, [displayedNodes, topology?.graph?.edges, handleNodeClick]);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  // Loading state
  if (isLoading) {
    return (
      <div className="h-full min-h-[220px] animate-pulse rounded-lg bg-muted" />
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-full min-h-[220px] items-center justify-center rounded-lg bg-muted/60 border border-dashed border-border">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">Failed to load topology</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    );
  }

  // Empty state
  if (!totalNodes) {
    return (
      <div className="flex h-full min-h-[220px] items-center justify-center rounded-lg bg-muted/60 border border-dashed border-border">
        <div className="text-center">
          <Server className="h-10 w-10 text-muted-foreground/50 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No topology data available</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            Nodes will appear here once registered
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="h-full min-h-[220px] flex-1 rounded-lg overflow-hidden border border-border"
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.3}
            maxZoom={1.5}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            panOnDrag={true}
            zoomOnScroll={true}
            zoomOnPinch={true}
            zoomOnDoubleClick={false}
            preventScrolling={false}
          >
            <Background color="hsl(var(--border))" gap={20} size={1} />
            <Controls showInteractive={false} className="!bg-card !border-border" />
          </ReactFlow>
        </motion.div>

        {/* Legend and truncation indicator */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2 text-xs">
              <div className="h-2.5 w-2.5 rounded-full bg-compute" />
              <span className="text-muted-foreground">Compute</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="h-2.5 w-2.5 rounded-full bg-network" />
              <span className="text-muted-foreground">Networking</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="h-2.5 w-2.5 rounded-full bg-iot" />
              <span className="text-muted-foreground">IoT</span>
            </div>
          </div>

          {hasMoreNodes && (
            <div className="text-xs text-muted-foreground">
              Showing {displayedNodes.length} of {totalNodes} nodes
              <Link
                to={ROUTES.TOPOLOGY}
                className="ml-2 text-primary hover:underline font-medium"
              >
                View all
              </Link>
            </div>
          )}
        </div>
    </div>
  );
}
