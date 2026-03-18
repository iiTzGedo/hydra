import {
  GitBranch,
  Globe,
  Layers,
  Network,
  Server,
  type LucideIcon,
} from 'lucide-react';
import type { ColumnConfig } from '@/components/common/entity-list-page';
import type { FilterConfig } from '@/components/common/filter-bar';
import { NETWORK_TYPE_LABELS } from '@/lib/constants';
import type { NetworkType } from '@/types/network';

export interface NetworkTypeConfig {
  icon: LucideIcon;
  color: string;
  bgColor: string;
  label: string;
}

export const NETWORK_TYPE_CONFIG: Record<NetworkType, NetworkTypeConfig> = {
  physical: {
    icon: Server,
    color: 'text-network',
    bgColor: 'bg-network/10',
    label: 'Physical',
  },
  virtual: {
    icon: Globe,
    color: 'text-compute',
    bgColor: 'bg-compute/10',
    label: 'Virtual',
  },
  overlay: {
    icon: Layers,
    color: 'text-primary',
    bgColor: 'bg-primary/10',
    label: 'Overlay',
  },
  vlan: {
    icon: GitBranch,
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    label: 'VLAN',
  },
  vxlan: {
    icon: GitBranch,
    color: 'text-info',
    bgColor: 'bg-info/10',
    label: 'VXLAN',
  },
  bridge: {
    icon: Network,
    color: 'text-iot',
    bgColor: 'bg-iot/10',
    label: 'Bridge',
  },
  tunnel: {
    icon: Network,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
    label: 'Tunnel',
  },
};

export const NETWORK_FILTER_CONFIG: FilterConfig[] = [
  {
    type: 'search',
    key: 'search',
    placeholder: 'Search networks by name or CIDR...',
    className: 'flex-1',
  },
  {
    type: 'select',
    key: 'type',
    label: 'Types',
    options: Object.entries(NETWORK_TYPE_LABELS).map(([value, label]) => ({ value, label })),
  },
];

export const NETWORK_COLUMNS: ColumnConfig[] = [
  { key: 'network', label: 'Network' },
  { key: 'type', label: 'Type' },
  { key: 'cidr', label: 'CIDR' },
  { key: 'gateway', label: 'Gateway' },
  { key: 'nodes', label: 'Nodes' },
  { key: 'actions', label: 'Actions' },
];
