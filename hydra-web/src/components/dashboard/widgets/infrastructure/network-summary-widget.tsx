/**
 * NetworkSummaryWidget -- info card displaying a single network's identity,
 * addressing details, and associated node count.
 *
 * Data shape:
 *   { networkId: string; name: string; cidr: string; gateway?: string;
 *     nodeCount: number; type?: string; vlan?: number }
 *
 * Config: { networkId: string }
 */

import { Network, Globe, Router, Server, Hash } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface NetworkSummaryData {
  networkId: string;
  name: string;
  cidr: string;
  gateway?: string;
  nodeCount: number;
  type?: string;
  vlan?: number;
}

interface NetworkSummaryConfig extends Record<string, unknown> {
  networkId?: string;
}

export function NetworkSummaryWidget({
  data,
  config,
  isLoading,
  error,
}: WidgetComponentProps<NetworkSummaryData, NetworkSummaryConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Network className="h-5 w-5" />
        <div className="text-sm font-medium">{config.networkId ?? 'Network'}</div>
        <div className="text-xs">Loading network data...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-1">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Network className="h-5 w-5 text-muted-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{data.name}</div>
          <div className="text-xs text-muted-foreground">{data.networkId}</div>
        </div>
      </div>

      {/* Details */}
      <div className="space-y-2 rounded-lg border border-border/60 bg-muted/20 p-2.5">
        {/* CIDR */}
        <div className="flex items-center gap-2">
          <Globe className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">CIDR</span>
          <span className="ml-auto rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono font-medium text-primary">
            {data.cidr}
          </span>
        </div>

        {/* Gateway */}
        {data.gateway && (
          <div className="flex items-center gap-2">
            <Router className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Gateway</span>
            <span className="ml-auto text-xs font-mono font-medium">
              {data.gateway}
            </span>
          </div>
        )}

        {/* Node count */}
        <div className="flex items-center gap-2">
          <Server className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Nodes</span>
          <span className="ml-auto text-xs font-medium">
            {data.nodeCount}
          </span>
        </div>

        {/* Type */}
        {data.type && (
          <div className="flex items-center gap-2">
            <Network className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Type</span>
            <span className="ml-auto text-xs font-medium capitalize">
              {data.type}
            </span>
          </div>
        )}

        {/* VLAN */}
        {data.vlan != null && (
          <div className="flex items-center gap-2">
            <Hash className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">VLAN</span>
            <span className="ml-auto text-xs font-mono font-medium">
              {data.vlan}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
