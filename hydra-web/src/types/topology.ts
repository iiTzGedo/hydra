import { ListParams } from './api';

// Topology mode
export type TopologyMode = 'infrastructure' | 'services';

// Topology node type
export interface TopologyNode {
  id: string;
  type: 'network' | 'node' | 'service';
  label: string;
  data: {
    nodeId?: string;
    networkId?: string;
    serviceId?: string;
    class?: string;
    kind?: string;
    status?: string;
    runtime?: string;
    [key: string]: unknown;
  };
  position?: {
    x: number;
    y: number;
  };
}

// Topology edge type
export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  type: 'network' | 'parent-child' | 'service';
  label?: string;
  data?: {
    interface?: string;
    bandwidth?: number;
    [key: string]: unknown;
  };
}

// Topology graph
export interface TopologyGraph {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

// Topology summary (for list views)
export interface TopologySummary {
  topologyId: string;
  mode: TopologyMode;
  validFrom: string;
  validUntil?: string;
  nodeCount: number;
  edgeCount: number;
  createdAt: string;
}

// Full topology
export interface Topology extends TopologySummary {
  graph?: TopologyGraph;
  generatedAt: string;
  metadata?: {
    generationDuration?: number;
    layoutAlgorithm?: string;
  };
}

// Topology list params
export interface TopologyListParams extends ListParams {
  mode?: TopologyMode;
  since?: string;
  until?: string;
}

// Generate topology request
export interface GenerateTopologyRequest {
  mode: TopologyMode;
  forceRegenerate?: boolean;
}

// Topology diff
export interface TopologyDiff {
  fromTopologyId?: string;
  toTopologyId?: string;
  mode: TopologyMode;
  changes: {
    nodesAdded: TopologyNode[];
    nodesRemoved: TopologyNode[];
    nodesChanged: Array<{
      node: TopologyNode;
      changes: string[];
    }>;
    edgesAdded: TopologyEdge[];
    edgesRemoved: TopologyEdge[];
  };
  summary: {
    totalChanges: number;
    nodesAdded: number;
    nodesRemoved: number;
    nodesChanged: number;
    edgesAdded: number;
    edgesRemoved: number;
  };
}
