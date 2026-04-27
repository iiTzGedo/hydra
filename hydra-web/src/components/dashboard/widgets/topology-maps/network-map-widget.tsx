/**
 * NetworkMapWidget
 *
 * Displays a compact card grid of networks. Each card shows the
 * network name, CIDR range, node count badge, and a type-based icon.
 * Designed for at-a-glance network topology awareness.
 *
 * Data binding:
 *   source: hydra::networks
 *   endpoint: /networks
 *
 * Accepts two data shapes:
 *   1. Envelope: { networks: NetworkEntry[] }
 *   2. Raw array: NetworkSummary[] from /networks API (auto-normalized)
 *      Maps: networkId, name, type (physical/virtual/overlay/etc), cidr, nodeCount
 *
 * Config options:
 *   layoutAlgorithm: "force" | "grid" | "hierarchical" (visual hint, currently grid)
 *   showLabels: boolean
 */

import { useMemo } from 'react';
import {
  Network,
  Wifi,
  Globe,
  Shield,
  Server,
  Router,
} from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface NetworkEntry {
  networkId: string;
  name: string;
  cidr: string;
  nodeCount: number;
  type?: string;
}

interface NetworkMapData {
  networks: NetworkEntry[];
}

interface NetworkMapConfig extends Record<string, unknown> {
  layoutAlgorithm?: string;
  showLabels?: boolean;
}

/**
 * Map NetworkSummary.type (physical/virtual/vlan/tunnel/etc.) to a display type.
 * NetworkEntry uses simplified types; map the extended API types to the closest
 * display variant.
 */
function mapNetworkType(apiType: string | undefined): string | undefined {
  if (!apiType) return undefined;
  switch (apiType.toLowerCase()) {
    case 'vlan': return 'vlan';
    case 'vxlan':
    case 'overlay': return 'vlan';
    case 'tunnel': return 'vpn';
    case 'bridge': return 'bridge';
    case 'physical': return undefined; // default icon
    case 'virtual': return undefined;
    default: return apiType;
  }
}

/**
 * Normalize incoming data to NetworkMapData envelope.
 * Handles both explicit envelope and raw NetworkSummary[] from the API.
 */
function normalizeNetworkMapData(raw: unknown): NetworkMapData | null {
  if (raw == null) return null;

  // Envelope shape
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.networks)) {
      return { networks: obj.networks as NetworkEntry[] };
    }
  }

  // Raw array of NetworkSummary
  if (Array.isArray(raw)) {
    return {
      networks: (raw as Record<string, unknown>[]).map((n) => ({
        networkId: String(n.networkId ?? n.id ?? ''),
        name: String(n.name ?? ''),
        cidr: String(n.cidr ?? n.cidrV4 ?? ''),
        nodeCount: Number(n.nodeCount ?? 0),
        type: mapNetworkType(
          typeof n.type === 'string' ? n.type : undefined,
        ),
      })),
    };
  }

  return null;
}

/**
 * Return an icon component based on network type.
 */
function getNetworkIcon(type?: string) {
  switch (type?.toLowerCase()) {
    case 'wifi':
    case 'wireless':
      return <Wifi className="h-4 w-4" />;
    case 'wan':
    case 'internet':
      return <Globe className="h-4 w-4" />;
    case 'vpn':
    case 'tunnel':
      return <Shield className="h-4 w-4" />;
    case 'vlan':
    case 'bridge':
      return <Router className="h-4 w-4" />;
    case 'management':
    case 'mgmt':
      return <Server className="h-4 w-4" />;
    default:
      return <Network className="h-4 w-4" />;
  }
}

/**
 * Return a subtle background tint based on network type.
 */
function getNetworkAccent(type?: string): string {
  switch (type?.toLowerCase()) {
    case 'wifi':
    case 'wireless':
      return 'border-l-violet-500';
    case 'wan':
    case 'internet':
      return 'border-l-blue-500';
    case 'vpn':
    case 'tunnel':
      return 'border-l-emerald-500';
    case 'vlan':
    case 'bridge':
      return 'border-l-amber-500';
    case 'management':
    case 'mgmt':
      return 'border-l-cyan-500';
    default:
      return 'border-l-slate-400';
  }
}

export function NetworkMapWidget({
  data: rawData,
  config,
  isLoading,
  error,
  onNavigate,
}: WidgetComponentProps<unknown, NetworkMapConfig>) {
  const data = useMemo(() => normalizeNetworkMapData(rawData), [rawData]);
  const typedConfig = config as NetworkMapConfig;
  const showLabels = typedConfig.showLabels !== false;

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Network className="h-5 w-5" />
        <div className="text-sm">No network data</div>
      </div>
    );
  }

  if (!data.networks || data.networks.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Network className="h-5 w-5" />
        <div className="text-sm">No networks discovered</div>
      </div>
    );
  }

  return (
    <div className="grid h-full auto-rows-min gap-2 overflow-y-auto sm:grid-cols-2">
      {data.networks.map((net) => (
        <button
          key={net.networkId}
          type="button"
          className={`flex items-start gap-3 rounded-lg border border-border/60 border-l-2 bg-card p-3 text-left transition-colors hover:bg-muted/40 ${getNetworkAccent(net.type)}`}
          onClick={() => onNavigate?.(`/networks/${net.networkId}`)}
        >
          {/* Icon */}
          <div className="mt-0.5 flex-shrink-0 text-muted-foreground">
            {getNetworkIcon(net.type)}
          </div>

          {/* Content */}
          <div className="min-w-0 flex-1">
            {showLabels && (
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium text-foreground">
                  {net.name}
                </span>
                {net.type && (
                  <span className="flex-shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                    {net.type}
                  </span>
                )}
              </div>
            )}
            {!showLabels && (
              <div className="truncate text-sm font-medium text-foreground">
                {net.name}
              </div>
            )}

            <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
              {/* CIDR */}
              <span className="font-mono tabular-nums">{net.cidr}</span>

              {/* Node count badge */}
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                <Server className="h-2.5 w-2.5" />
                {net.nodeCount}
              </span>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
