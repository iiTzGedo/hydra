import { TopologyGraph, TopologyMode } from './topology';

export type TimelineEventType =
  | 'profile_submitted'
  | 'service_discovered'
  | 'service_removed'
  | 'topology_generated'
  | 'node_registered'
  | 'node_archived'
  | 'network_created'
  | 'group_created';

export interface TimelineEvent {
  eventId: string;
  eventType: TimelineEventType;
  timestamp: string;
  entityType: string;
  entityId: string;
  description: string;
  metadata?: Record<string, unknown>;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  since: string;
  until: string;
  total: number;
}

export interface NodeStateSnapshot {
  nodeId: string;
  displayName: string;
  class: string;
  type: string;
  kind?: string;
  status: string;
  tags?: string[];
  registeredAt: string;
}

export interface ProfileStateSnapshot {
  profileId: string;
  version: string;
  submittedAt: string;
  hardware?: Record<string, unknown>;
  network?: Record<string, unknown>;
  storage?: Record<string, unknown>;
  software?: Record<string, unknown>;
}

export interface ServiceStateSnapshot {
  serviceId: string;
  name: string;
  runtime: string;
  status: string;
  version?: string;
}

export interface NodeTimeMachineState {
  node?: NodeStateSnapshot;
  profile?: ProfileStateSnapshot;
  services: ServiceStateSnapshot[];
}

export interface ClosestSnapshot {
  profileAt?: string | null;
  deltaMinutes: number;
}

export interface NodeTimeMachineResponse {
  nodeId: string;
  timestamp: string;
  state: NodeTimeMachineState;
  closestSnapshot: ClosestSnapshot;
}

export interface HistoricalTopology {
  timestamp: string;
  mode: TopologyMode;
  topologyId: string;
  version: number;
  generatedAt: string;
  graph?: TopologyGraph;
  stats: Record<string, unknown>;
  note?: string;
}

export interface NodeStateParams {
  timestamp: string;
  sections?: string[];
}

export interface TopologyStateParams {
  timestamp: string;
  mode?: TopologyMode;
}

export interface TimelineParams {
  since?: string;
  until?: string;
  nodeId?: string;
  eventTypes?: TimelineEventType[];
  limit?: number;
  offset?: number;
}
