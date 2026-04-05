/**
 * Topology layout utilities using ELK for automatic graph layout.
 *
 * ELK (Eclipse Layout Kernel) provides hierarchical layout algorithms that
 * prevent node overlapping and create clean, readable graph visualizations.
 * It's ESM-compatible and works well with Vite.
 */

import ELK, { ElkNode, ElkExtendedEdge } from 'elkjs/lib/elk.bundled.js';
import { Node, Edge } from '@xyflow/react';

const elk = new ELK();

export interface LayoutOptions {
  /** Layout direction: DOWN (top-bottom), RIGHT (left-right), UP, LEFT */
  direction?: 'DOWN' | 'RIGHT' | 'UP' | 'LEFT';
  /** Horizontal spacing between nodes */
  nodeWidth?: number;
  /** Vertical spacing between nodes */
  nodeHeight?: number;
  /** Separation between nodes */
  nodeSep?: number;
  /** Separation between layers (ranks) */
  layerSep?: number;
  /** Layout algorithm: layered, force, stress, mrtree */
  algorithm?: 'layered' | 'force' | 'stress' | 'mrtree';
}

const DEFAULT_OPTIONS: Required<LayoutOptions> = {
  direction: 'DOWN',
  nodeWidth: 180,
  nodeHeight: 80,
  nodeSep: 60,
  layerSep: 100,
  algorithm: 'layered',
};

/**
 * Apply ELK layout to ReactFlow nodes and edges.
 *
 * @param nodes - ReactFlow nodes to layout
 * @param edges - ReactFlow edges connecting nodes
 * @param options - Layout configuration options
 * @returns Promise of layouted nodes and edges with computed positions
 */
export async function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {}
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  if (nodes.length === 0) {
    return { nodes: [], edges: [] };
  }

  const opts = { ...DEFAULT_OPTIONS, ...options };

  // Build ELK graph structure
  const elkGraph: ElkNode = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': opts.algorithm,
      'elk.direction': opts.direction,
      'elk.spacing.nodeNode': String(opts.nodeSep),
      'elk.layered.spacing.nodeNodeBetweenLayers': String(opts.layerSep),
      'elk.layered.spacing.baseValue': String(opts.nodeSep),
    },
    children: nodes.map((node) => ({
      id: node.id,
      width: opts.nodeWidth,
      height: opts.nodeHeight,
    })),
    edges: edges
      .filter((edge) => {
        // Only include edges where both nodes exist
        const hasSource = nodes.some((n) => n.id === edge.source);
        const hasTarget = nodes.some((n) => n.id === edge.target);
        return hasSource && hasTarget;
      })
      .map((edge) => ({
        id: edge.id,
        sources: [edge.source],
        targets: [edge.target],
      })) as ElkExtendedEdge[],
  };

  // Run the layout algorithm
  const layoutedGraph = await elk.layout(elkGraph);

  // Create a map of node positions from ELK result
  const nodePositions = new Map<string, { x: number; y: number }>();
  layoutedGraph.children?.forEach((elkNode) => {
    if (elkNode.x !== undefined && elkNode.y !== undefined) {
      nodePositions.set(elkNode.id, {
        x: elkNode.x,
        y: elkNode.y,
      });
    }
  });

  // Apply computed positions to nodes
  const layoutedNodes = nodes.map((node) => {
    const position = nodePositions.get(node.id);
    if (!position) {
      return node;
    }

    return {
      ...node,
      position: {
        x: position.x,
        y: position.y,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

/**
 * Synchronous wrapper that returns nodes with a simple grid layout
 * as a fallback while async layout is computed.
 *
 * @param nodes - ReactFlow nodes to layout
 * @param options - Layout configuration options
 * @returns Nodes with grid positions
 */
export function getGridLayout(
  nodes: Node[],
  options: LayoutOptions = {}
): Node[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const cols = Math.ceil(Math.sqrt(nodes.length));

  return nodes.map((node, index) => ({
    ...node,
    position: {
      x: (index % cols) * (opts.nodeWidth + opts.nodeSep),
      y: Math.floor(index / cols) * (opts.nodeHeight + opts.layerSep),
    },
  }));
}

/**
 * Get optimal layout direction based on topology mode.
 *
 * @param mode - Topology mode (infrastructure, network, service)
 * @returns Recommended layout direction
 */
export function getLayoutDirectionForMode(
  mode: 'infrastructure' | 'network' | 'service'
): 'DOWN' | 'RIGHT' {
  switch (mode) {
    case 'infrastructure':
      // Top-down hierarchy for parent-child relationships
      return 'DOWN';
    case 'network':
      // Left-right for network topology flow
      return 'RIGHT';
    case 'service':
      // Top-down for service-host relationships
      return 'DOWN';
    default:
      return 'DOWN';
  }
}

/**
 * Get layout options optimized for different topology modes.
 *
 * @param mode - Topology mode
 * @param nodeCount - Number of nodes in the graph
 * @returns Optimized layout options
 */
export function getLayoutOptionsForMode(
  mode: 'infrastructure' | 'network' | 'service',
  nodeCount: number
): LayoutOptions {
  const baseOptions: LayoutOptions = {
    direction: getLayoutDirectionForMode(mode),
    nodeWidth: 180,
    nodeHeight: 80,
    algorithm: 'layered',
  };

  // Adjust spacing based on node count
  if (nodeCount <= 10) {
    return {
      ...baseOptions,
      nodeSep: 80,
      layerSep: 120,
    };
  } else if (nodeCount <= 30) {
    return {
      ...baseOptions,
      nodeSep: 60,
      layerSep: 100,
    };
  } else if (nodeCount <= 50) {
    return {
      ...baseOptions,
      nodeSep: 50,
      layerSep: 80,
    };
  } else {
    // Large graphs need tighter spacing
    return {
      ...baseOptions,
      nodeSep: 40,
      layerSep: 60,
    };
  }
}
