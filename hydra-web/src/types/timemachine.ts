import { TopologyGraph, TopologyMode } from './topology';
import { ProfileSections } from './profile';

// Timeline event type
export type TimelineEventType =
  | 'profile_submitted'
  | 'service_discovered'
  | 'service_removed'
  | 'topology_generated'
  | 'node_registered'
  | 'node_archived'
  | 'network_created'
  | 'group_created';

// Timeline event
export interface TimelineEvent {
  eventId: string;
  eventType: TimelineEventType;
  timestamp: string;
  entityType: string;
  entityId: string;
  description: string;
  metadata?: Record<string, unknown>;
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
  version: number;
  generatedAt: string;
  graph?: TopologyGraph;
  stats?: Record<string, unknown>;
  note?: string;
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
