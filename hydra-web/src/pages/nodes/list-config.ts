import { Cpu, Server, Wifi, type LucideIcon } from 'lucide-react';
import type { ColumnConfig } from '@/components/common/entity-list-page';
import type { FilterConfig } from '@/components/common/filter-bar';

export const nodeClassIcons: Record<string, LucideIcon> = {
  compute: Server,
  networking: Wifi,
  iot: Cpu,
};

export const nodeClassColors: Record<string, string> = {
  compute: 'text-compute',
  networking: 'text-network',
  iot: 'text-iot',
};

export const NODE_FILTER_CONFIG: FilterConfig[] = [
  {
    type: 'search',
    key: 'search',
    placeholder: 'Search by hostname, IP, or tag...',
    className: 'flex-1',
  },
  {
    type: 'select',
    key: 'class',
    label: 'Class',
    options: [
      { value: 'compute', label: 'Compute' },
      { value: 'networking', label: 'Networking' },
      { value: 'iot', label: 'IoT' },
    ],
    allLabel: 'All Classes',
    className: 'w-[130px]',
  },
  {
    type: 'select',
    key: 'status',
    label: 'Status',
    options: [
      { value: 'active', label: 'Online' },
      { value: 'pending', label: 'Warning' },
      { value: 'inactive', label: 'Offline' },
      { value: 'archived', label: 'Archived' },
    ],
    allLabel: 'All Status',
    className: 'w-[120px]',
  },
];

export const NODE_COLUMNS: ColumnConfig[] = [
  { key: 'node', label: 'Node' },
  { key: 'class', label: 'Class' },
  { key: 'type', label: 'Type' },
  { key: 'tier', label: 'Tier' },
  { key: 'status', label: 'Status' },
  { key: 'lastProfile', label: 'Last Profile' },
];
