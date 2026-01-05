import { ListParams } from './api';

// Network type
export type NetworkType = 'L2' | 'L3' | 'vlan' | 'vxlan' | 'overlay' | 'physical';

// DHCP configuration
export interface DhcpConfig {
  enabled: boolean;
  rangeStart?: string;
  rangeEnd?: string;
  leaseTime?: number;
  server?: string;
}

// DNS configuration
export interface DnsConfig {
  servers: string[];
  domain?: string;
  search?: string[];
}

// Network summary (for list views)
export interface NetworkSummary {
  networkId: string;
  id?: string; // Alias for networkId for component convenience
  name: string;
  type: NetworkType;
  cidr: string;
  gateway?: string;
  vlanId?: number;
  nodeCount: number;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

// Full network details
export interface Network extends NetworkSummary {
  description?: string;
  parentNetworkId?: string;
  routerNodeId?: string;
  dhcp?: DhcpConfig;
  dns?: DnsConfig;
  domain?: string; // Convenience alias for dns.domain
  mtu?: number;
  metadata?: Record<string, unknown>;
}

// Network list params
export interface NetworkListParams extends ListParams {
  type?: NetworkType;
  parentNetworkId?: string;
  routerNodeId?: string;
  cidr?: string;
  tags?: string[];
}

// Create network request
export interface CreateNetworkRequest {
  networkId?: string;
  name: string;
  type: NetworkType;
  cidr: string;
  gateway?: string;
  vlanId?: number;
  description?: string;
  parentNetworkId?: string;
  routerNodeId?: string;
  dhcp?: DhcpConfig;
  dns?: DnsConfig;
  tags?: string[];
}

// Update network request
export interface UpdateNetworkRequest {
  name?: string;
  description?: string;
  gateway?: string;
  dhcp?: DhcpConfig;
  dns?: DnsConfig;
  tags?: string[];
}
