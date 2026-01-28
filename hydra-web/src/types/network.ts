import { ListParams } from './api';

export type NetworkType =
  | 'physical'
  | 'virtual'
  | 'overlay'
  | 'vlan'
  | 'vxlan'
  | 'bridge'
  | 'tunnel';

export interface DhcpConfig {
  enabled: boolean;
  rangeStart?: string;
  rangeEnd?: string;
  serverNodeId?: string;
}

export interface DnsConfig {
  servers: string[];
  domain?: string;
  searchDomains?: string[];
}

export interface NetworkSummary {
  networkId: string;
  id?: string;
  name: string;
  type: NetworkType;
  cidr?: string | null;
  gatewayV4?: string;
  routerNodeId?: string;
  nodeCount: number;
  tags: string[];
}

export interface Network extends NetworkSummary {
  description?: string;
  cidrV6?: string | null;
  gatewayV6?: string;
  vlanId?: number;
  parentNetworkId?: string;
  subnetIds?: string[];
  dhcp?: DhcpConfig;
  dns?: DnsConfig;
  origin?: {
    createdBy: string;
    sourceNodeId?: string;
    sourceProfileId?: string;
  };
  createdAt?: string;
  updatedAt?: string;
}

export interface NetworkNodeInfo {
  nodeId: string;
  displayName: string;
  class: string;
  ipAddresses: string[];
}

export interface NetworkListParams extends ListParams {
  type?: NetworkType;
  parentNetworkId?: string;
  routerNodeId?: string;
  cidr?: string;
  tags?: string[];
}

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
