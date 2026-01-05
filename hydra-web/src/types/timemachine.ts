import { TopologyGraph, TopologyMode } from './topology';
import { ProfileSections } from './profile';

// Timeline event type
export type TimelineEventType =
  | 'node_registered'
  | 'node_updated'
  | 'node_archived'
  | 'profile_submitted'
  | 'service_added'
  | 'service_removed'
  | 'service_changed'
  | 'topology_generated'
  | 'network_created'
  | 'network_updated';

// Timeline event
export interface TimelineEvent {
  id: string;
  type: TimelineEventType;
  timestamp: string;
  nodeId?: string;
  serviceId?: string;
  networkId?: string;
  summary: string;
  details?: Record<string, unknown>;
}

// Timeline response
export interface TimelineResponse {
  events: TimelineEvent[];
  since: string;
  until: string;
  total: number;
}

// Node state at a point in time
export interface HistoricalNodeState {
  nodeId: string;
  timestamp: string;
  displayName: string;
  status: string;
  class: string;
  type: string;
  kind?: string;
  profile?: {
    profileId: string;
    version: string;
    sections: ProfileSections;
  };
  services?: Array<{
    serviceId: string;
    name: string;
    runtime: string;
    status: string;
  }>;
}

// Historical topology
export interface HistoricalTopology {
  timestamp: string;
  mode: TopologyMode;
  topologyId: string;
  validFrom: string;
  validUntil?: string;
  graph: TopologyGraph;
}

// Time machine query params
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
