import { ListParams } from './api';

export type TopologyMode = 'network' | 'infrastructure' | 'service';

export interface TopologyNode {
  id: string;
  type: string;
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

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label?: string;
  data?: {
    interface?: string;
    bandwidth?: number;
    [key: string]: unknown;
  };
}

export interface TopologyGraph {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface TopologyStats {
  nodeCount: number;
  edgeCount: number;
  networkCount?: number;
  serviceCount?: number;
  computeTimeMs?: number;
}

export interface TopologyScope {
  networkIds?: string[];
  groupIds?: string[];
  nodeIds?: string[];
}

export interface TopologySummary {
  topologyId: string;
  mode: TopologyMode;
  version: number;
  generatedAt: string;
  validFrom: string;
  validUntil?: string;
  stats: TopologyStats;
}

export interface Topology extends TopologySummary {
  scope?: TopologyScope;
  graph?: TopologyGraph;
  previousTopologyId?: string;
  diff?: TopologyDiff;
}

export interface TopologyListParams extends ListParams {
  mode?: TopologyMode;
  since?: string;
  until?: string;
}

export interface GenerateTopologyRequest {
  mode: TopologyMode;
  scope?: TopologyScope;
}

export interface TopologyDiff {
  nodesAdded: string[];
  nodesRemoved: string[];
  nodesModified: string[];
  edgesAdded: string[];
  edgesRemoved: string[];
}

export interface TopologyDiffResponse {
  from: TopologySummary;
  to: TopologySummary;
  diff: TopologyDiff;
  summary: Record<string, number>;
}

export interface SubgraphStats {
  nodeCount: number;
  edgeCount: number;
  serviceCount: number;
  networkCount: number;
}

export interface SubgraphResponse {
  centerNodeId: string;
  depth: number;
  graph: TopologyGraph;
  stats: SubgraphStats;
}
