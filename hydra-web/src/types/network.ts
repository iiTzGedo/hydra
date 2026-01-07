import { ListParams } from './api';

// Network type
export type NetworkType =
  | 'physical'
  | 'virtual'
  | 'overlay'
  | 'vlan'
  | 'vxlan'
  | 'bridge'
  | 'tunnel';

// DHCP configuration
export interface DhcpConfig {
  enabled: boolean;
  rangeStart?: string;
  rangeEnd?: string;
  serverNodeId?: string;
}

// DNS configuration
export interface DnsConfig {
  servers: string[];
  domain?: string;
  searchDomains?: string[];
}

// Network summary (for list views)
export interface NetworkSummary {
  networkId: string;
  id?: string; // Alias for networkId for component convenience
  name: string;
  type: NetworkType;
  cidr?: string | null;
  gatewayV4?: string;
  gatewayV6?: string;
  vlanId?: number;
  routerNodeId?: string;
  nodeCount: number;
  tags: string[];
}

// Full network details
export interface Network extends NetworkSummary {
  description?: string;
  cidrV6?: string | null;
  parentNetworkId?: string;
  subnetIds?: string[];
  dhcp?: DhcpConfig;
  dns?: DnsConfig;
  origin?: {
    createdBy: string;
    sourceNodeId?: string;
    sourceProfileId?: string;
  };
  mtu?: number;
  createdAt?: string;
  updatedAt?: string;
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
  networkId: string;
  name: string;
  type: NetworkType;
  cidr?: string;
  cidrV6?: string;
  gatewayV4?: string;
  gatewayV6?: string;
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
  gatewayV4?: string;
  gatewayV6?: string;
  routerNodeId?: string;
  dhcp?: DhcpConfig;
  dns?: DnsConfig;
  tags?: string[];
}
