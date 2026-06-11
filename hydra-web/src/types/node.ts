import { ListParams } from './api';
import type { IconDescriptor } from './icons';

// Node class
export type NodeClass = 'compute' | 'networking' | 'iot';

// Node type
export type NodeType = 'physical' | 'logical';

// Node kind (specific types within classes)
export type NodeKind =
  // Compute kinds
  | 'bare-metal'
  | 'vm'
  | 'lxc'
  | 'docker'
  | 'kubernetes-pod'
  // Networking kinds
  | 'router'
  | 'switch'
  | 'access-point'
  | 'firewall'
  | 'load-balancer'
  // IoT kinds
  | 'sensor'
  | 'actuator'
  | 'controller'
  | 'hub'
  | 'bridge'
  | 'appliance'
  // Generic
  | 'other';

// Node status
export type NodeStatus = 'active' | 'inactive' | 'pending' | 'archived';

// Agent tier
export type AgentTier = 'lite' | 'normal' | 'max';

// Node location
export interface NodeLocation {
  site?: string;
  building?: string;
  floor?: string;
  room?: string;
  rack?: string;
  position?: string;
}

// Control-server configuration for a max-tier agent (null for non-max nodes)
export interface AgentServerConfig {
  enabled: boolean;
  bindAddress?: string | null;
  advertiseAddress?: string | null;
  port?: number | null;
  tlsEnabled?: boolean | null;
}

// Runtime reachability status for a max-tier agent's control server
export interface AgentServerStatus {
  isReachable?: boolean | null;
  lastDirectContact?: string | null;
  failedDirectAttempts?: number | null;
  lastPollContact?: string | null;
}

// Nested agent metadata attached to a node (spec §3.4)
export interface NodeAgentInfo {
  tier?: AgentTier | null;
  serverConfig?: AgentServerConfig | null;
  serverStatus?: AgentServerStatus | null;
  credentialRotatedAt?: string | null;
}

// Node summary (for list views)
export interface NodeSummary {
  nodeId: string;
  id?: string; // Alias for nodeId for component convenience
  displayName: string;
  class: NodeClass;
  type: NodeType;
  kind?: NodeKind;
  status: NodeStatus;
  tags: string[];
  lastProfileAt?: string;
  lastSeenAt?: string;
  registeredBy?: string;
  agent?: NodeAgentInfo | null;
  icon?: IconDescriptor | null;
}

// Full node details
export interface Node extends NodeSummary {
  description?: string;
  parentNodeId?: string;
  networkIds: string[];
  registeredBy?: string;
  registeredAt: string;
  lastUpdated: string;
}

// Node list params
export interface NodeListParams extends ListParams {
  class?: NodeClass;
  type?: NodeType;
  kind?: NodeKind;
  status?: NodeStatus;
  agentTier?: AgentTier;
  tags?: string[];
  parentNodeId?: string;
  networkId?: string;
}

// Update node request
export interface UpdateNodeRequest {
  displayName?: string;
  description?: string;
  kind?: NodeKind;
  tags?: string[];
  parentNodeId?: string;
  status?: NodeStatus;
}

// Node registration agent block (nested; matches API contract)
export interface NodeRegistrationAgent {
  tier?: AgentTier;
  serverConfig?: {
    enabled?: boolean;
    advertiseAddress?: string;
    bindAddress?: string;
    port?: number;
    tlsEnabled?: boolean;
  };
}

// Node registration
export interface NodeRegistrationRequest {
  nodeId: string;
  class: NodeClass;
  type: NodeType;
  kind?: NodeKind;
  displayName?: string;
  description?: string;
  tags?: string[];
  parentNodeId?: string;
  location?: NodeLocation;
  agent?: NodeRegistrationAgent;
}

export interface NodeRegistrationResponse {
  nodeId: string;
  apiKey: string;
  apiKeyId: string;
  registeredBy: string;
  registeredAt: string;
  status: NodeStatus;
  agentServerSecret?: string;
}
