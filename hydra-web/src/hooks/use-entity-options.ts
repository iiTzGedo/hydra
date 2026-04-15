import { useMemo } from 'react';
import { Server, Boxes, Network, FolderTree, type LucideIcon } from 'lucide-react';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';
import { useGroups } from '@/api/groups';

export type EntityType = 'node' | 'service' | 'network' | 'group';

export interface EntityOption {
  id: string;
  label: string;
  sublabel?: string;
  icon: LucideIcon;
  iconColorClass: string;
}

interface UseEntityOptionsParams {
  limit?: number;
  excludeIds?: string[];
  /** Pass-through query params for the underlying API hook (e.g. { class: 'networking' }) */
  queryParams?: Record<string, unknown>;
}

interface UseEntityOptionsResult {
  options: EntityOption[];
  isLoading: boolean;
}

function useNodeOptions(
  params: UseEntityOptionsParams,
  enabled: boolean,
): UseEntityOptionsResult {
  const { data, isLoading } = useNodes(
    enabled ? { limit: params.limit ?? 200, ...params.queryParams } : undefined,
  );

  const options = useMemo(() => {
    if (!data?.items) return [];
    const items = params.excludeIds?.length
      ? data.items.filter((n) => !params.excludeIds!.includes(n.nodeId))
      : data.items;
    return items.map((n) => ({
      id: n.nodeId,
      label: n.displayName,
      sublabel: [n.class, n.kind ?? n.type, n.status].filter(Boolean).join(' / '),
      icon: Server,
      iconColorClass:
        n.class === 'compute'
          ? 'text-compute'
          : n.class === 'networking'
            ? 'text-network'
            : 'text-warning',
    }));
  }, [data, params.excludeIds]);

  return { options, isLoading: enabled ? isLoading : false };
}

function useServiceOptions(
  params: UseEntityOptionsParams,
  enabled: boolean,
): UseEntityOptionsResult {
  const { data, isLoading } = useServices(
    enabled ? { limit: params.limit ?? 200, ...params.queryParams } : undefined,
  );

  const options = useMemo(() => {
    if (!data?.items) return [];
    const items = params.excludeIds?.length
      ? data.items.filter((s) => !params.excludeIds!.includes(s.serviceId))
      : data.items;
    return items.map((s) => ({
      id: s.serviceId,
      label: s.displayName || s.name,
      sublabel: [s.runtime, s.status, `on ${s.nodeId}`].join(' / '),
      icon: Boxes,
      iconColorClass: 'text-success',
    }));
  }, [data, params.excludeIds]);

  return { options, isLoading: enabled ? isLoading : false };
}

function useNetworkOptions(
  params: UseEntityOptionsParams,
  enabled: boolean,
): UseEntityOptionsResult {
  const { data, isLoading } = useNetworks(
    enabled ? { limit: params.limit ?? 200, ...params.queryParams } : undefined,
  );

  const options = useMemo(() => {
    if (!data?.items) return [];
    const items = params.excludeIds?.length
      ? data.items.filter((n) => !params.excludeIds!.includes(n.networkId))
      : data.items;
    return items.map((n) => ({
      id: n.networkId,
      label: n.name,
      sublabel: [n.type, n.cidr].filter(Boolean).join(' / '),
      icon: Network,
      iconColorClass: 'text-network',
    }));
  }, [data, params.excludeIds]);

  return { options, isLoading: enabled ? isLoading : false };
}

function useGroupOptions(
  params: UseEntityOptionsParams,
  enabled: boolean,
): UseEntityOptionsResult {
  const { data, isLoading } = useGroups(
    enabled ? { limit: params.limit ?? 200, ...params.queryParams } : undefined,
  );

  const options = useMemo(() => {
    if (!data?.items) return [];
    const items = params.excludeIds?.length
      ? data.items.filter((g) => !params.excludeIds!.includes(g.groupId))
      : data.items;
    return items.map((g) => ({
      id: g.groupId,
      label: g.name,
      sublabel: `${(g.memberCount?.nodes ?? 0) + (g.memberCount?.services ?? 0)} members`,
      icon: FolderTree,
      iconColorClass: 'text-warning',
    }));
  }, [data, params.excludeIds]);

  return { options, isLoading: enabled ? isLoading : false };
}

/**
 * Hook that fetches entity data and transforms it into a uniform EntityOption[] shape
 * for use with EntityCombobox and EntityMultiSelect components.
 */
export function useEntityOptions(
  entityType: EntityType,
  params: UseEntityOptionsParams = {},
): UseEntityOptionsResult {
  const nodeResult = useNodeOptions(params, entityType === 'node');
  const serviceResult = useServiceOptions(params, entityType === 'service');
  const networkResult = useNetworkOptions(params, entityType === 'network');
  const groupResult = useGroupOptions(params, entityType === 'group');

  switch (entityType) {
    case 'node':
      return nodeResult;
    case 'service':
      return serviceResult;
    case 'network':
      return networkResult;
    case 'group':
      return groupResult;
  }
}
