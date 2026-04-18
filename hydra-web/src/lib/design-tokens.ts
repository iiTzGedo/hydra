import { cva, type VariantProps } from 'class-variance-authority';

/**
 * Hydra design tokens — CVA-based variant maps for shared semantic concepts.
 *
 * These are intentionally NOT React components. They return Tailwind class
 * strings so callers can compose them with their own layout or ref handling.
 *
 * Every variant maps to a semantic CSS variable defined in `src/index.css`
 * (see `--event-*`, `--severity-*`, `--surface-*`, etc.). If you catch yourself
 * reaching for a raw Tailwind color like `bg-emerald-500`, add or reuse a token
 * here instead so the result is theme-aware.
 */

// ---------- Node class tokens (compute / networking / iot) ----------

export const nodeClassToken = cva('inline-flex items-center gap-1.5', {
  variants: {
    nodeClass: {
      compute: 'text-compute',
      networking: 'text-network',
      iot: 'text-iot',
      unknown: 'text-muted-foreground',
    },
    surface: {
      solid: '',
      soft: '',
      outline: '',
      none: '',
    },
  },
  compoundVariants: [
    { nodeClass: 'compute', surface: 'solid', class: 'bg-compute text-compute-foreground' },
    { nodeClass: 'networking', surface: 'solid', class: 'bg-network text-network-foreground' },
    { nodeClass: 'iot', surface: 'solid', class: 'bg-iot text-iot-foreground' },
    { nodeClass: 'compute', surface: 'soft', class: 'bg-compute/10 text-compute border border-compute/20' },
    { nodeClass: 'networking', surface: 'soft', class: 'bg-network/10 text-network border border-network/20' },
    { nodeClass: 'iot', surface: 'soft', class: 'bg-iot/10 text-iot border border-iot/20' },
    { nodeClass: 'compute', surface: 'outline', class: 'border border-compute/40 text-compute' },
    { nodeClass: 'networking', surface: 'outline', class: 'border border-network/40 text-network' },
    { nodeClass: 'iot', surface: 'outline', class: 'border border-iot/40 text-iot' },
    { nodeClass: 'unknown', surface: 'soft', class: 'bg-muted text-muted-foreground' },
  ],
  defaultVariants: {
    nodeClass: 'unknown',
    surface: 'none',
  },
});

export type NodeClassTokenProps = VariantProps<typeof nodeClassToken>;

// ---------- Status tokens (active / running / stopped / failed / etc.) ----------

export const statusToken = cva('inline-flex items-center gap-1.5', {
  variants: {
    status: {
      active: 'text-success',
      running: 'text-success',
      online: 'text-success',
      inactive: 'text-muted-foreground',
      stopped: 'text-muted-foreground',
      exited: 'text-muted-foreground',
      unknown: 'text-muted-foreground',
      pending: 'text-warning',
      paused: 'text-warning',
      restarting: 'text-warning',
      failed: 'text-destructive',
      archived: 'text-destructive',
      offline: 'text-destructive',
    },
    surface: {
      solid: '',
      soft: '',
      outline: '',
      none: '',
    },
  },
  compoundVariants: [
    // Soft (tinted) surface
    { status: 'active', surface: 'soft', class: 'bg-success/10 text-success' },
    { status: 'running', surface: 'soft', class: 'bg-success/10 text-success' },
    { status: 'online', surface: 'soft', class: 'bg-success/10 text-success' },
    { status: 'inactive', surface: 'soft', class: 'bg-muted text-muted-foreground' },
    { status: 'stopped', surface: 'soft', class: 'bg-muted text-muted-foreground' },
    { status: 'exited', surface: 'soft', class: 'bg-muted text-muted-foreground' },
    { status: 'unknown', surface: 'soft', class: 'bg-muted text-muted-foreground' },
    { status: 'pending', surface: 'soft', class: 'bg-warning/10 text-warning' },
    { status: 'paused', surface: 'soft', class: 'bg-warning/10 text-warning' },
    { status: 'restarting', surface: 'soft', class: 'bg-warning/10 text-warning' },
    { status: 'failed', surface: 'soft', class: 'bg-destructive/10 text-destructive' },
    { status: 'archived', surface: 'soft', class: 'bg-destructive/10 text-destructive' },
    { status: 'offline', surface: 'soft', class: 'bg-destructive/10 text-destructive' },
  ],
  defaultVariants: {
    status: 'unknown',
    surface: 'none',
  },
});

export type StatusTokenProps = VariantProps<typeof statusToken>;

// ---------- Event-type tokens (Time Machine / audit) ----------

export const eventToken = cva('inline-flex items-center gap-1.5', {
  variants: {
    event: {
      profile_submitted: 'text-event-profile',
      service_discovered: 'text-event-service-added',
      service_removed: 'text-event-service-removed',
      topology_generated: 'text-event-topology',
      node_registered: 'text-event-node-added',
      node_archived: 'text-event-node-removed',
      network_created: 'text-event-network',
      group_created: 'text-event-group',
    },
    surface: {
      solid: '',
      soft: '',
      dot: '',
      none: '',
    },
  },
  compoundVariants: [
    // Solid — used for glyphs/pills
    { event: 'profile_submitted', surface: 'solid', class: 'bg-event-profile text-event-profile-foreground' },
    { event: 'service_discovered', surface: 'solid', class: 'bg-event-service-added text-event-service-added-foreground' },
    { event: 'service_removed', surface: 'solid', class: 'bg-event-service-removed text-event-service-removed-foreground' },
    { event: 'topology_generated', surface: 'solid', class: 'bg-event-topology text-event-topology-foreground' },
    { event: 'node_registered', surface: 'solid', class: 'bg-event-node-added text-event-node-added-foreground' },
    { event: 'node_archived', surface: 'solid', class: 'bg-event-node-removed text-event-node-removed-foreground' },
    { event: 'network_created', surface: 'solid', class: 'bg-event-network text-event-network-foreground' },
    { event: 'group_created', surface: 'solid', class: 'bg-event-group text-event-group-foreground' },
    // Soft — used for chips and hover rows
    { event: 'profile_submitted', surface: 'soft', class: 'bg-event-profile/10 text-event-profile border border-event-profile/20' },
    { event: 'service_discovered', surface: 'soft', class: 'bg-event-service-added/10 text-event-service-added border border-event-service-added/20' },
    { event: 'service_removed', surface: 'soft', class: 'bg-event-service-removed/10 text-event-service-removed border border-event-service-removed/20' },
    { event: 'topology_generated', surface: 'soft', class: 'bg-event-topology/10 text-event-topology border border-event-topology/20' },
    { event: 'node_registered', surface: 'soft', class: 'bg-event-node-added/10 text-event-node-added border border-event-node-added/20' },
    { event: 'node_archived', surface: 'soft', class: 'bg-event-node-removed/10 text-event-node-removed border border-event-node-removed/20' },
    { event: 'network_created', surface: 'soft', class: 'bg-event-network/10 text-event-network border border-event-network/20' },
    { event: 'group_created', surface: 'soft', class: 'bg-event-group/10 text-event-group border border-event-group/20' },
    // Dot — used for timeline/legend markers
    { event: 'profile_submitted', surface: 'dot', class: 'bg-event-profile' },
    { event: 'service_discovered', surface: 'dot', class: 'bg-event-service-added' },
    { event: 'service_removed', surface: 'dot', class: 'bg-event-service-removed' },
    { event: 'topology_generated', surface: 'dot', class: 'bg-event-topology' },
    { event: 'node_registered', surface: 'dot', class: 'bg-event-node-added' },
    { event: 'node_archived', surface: 'dot', class: 'bg-event-node-removed' },
    { event: 'network_created', surface: 'dot', class: 'bg-event-network' },
    { event: 'group_created', surface: 'dot', class: 'bg-event-group' },
  ],
  defaultVariants: {
    surface: 'none',
  },
});

export type EventTokenProps = VariantProps<typeof eventToken>;

// ---------- Severity tokens (notification tiers 1-5) ----------

export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low' | 'info';

export const severityToken = cva('inline-flex items-center gap-1.5', {
  variants: {
    severity: {
      critical: 'text-severity-critical',
      high: 'text-severity-high',
      medium: 'text-severity-medium',
      low: 'text-severity-low',
      info: 'text-muted-foreground',
    },
    surface: {
      solid: '',
      soft: '',
      dot: '',
      none: '',
    },
  },
  compoundVariants: [
    { severity: 'critical', surface: 'solid', class: 'bg-severity-critical text-severity-critical-foreground' },
    { severity: 'high', surface: 'solid', class: 'bg-severity-high text-severity-high-foreground' },
    { severity: 'medium', surface: 'solid', class: 'bg-severity-medium text-severity-medium-foreground' },
    { severity: 'low', surface: 'solid', class: 'bg-severity-low text-severity-low-foreground' },
    { severity: 'info', surface: 'solid', class: 'bg-muted text-muted-foreground' },

    { severity: 'critical', surface: 'soft', class: 'bg-severity-critical/10 text-severity-critical border border-severity-critical/20' },
    { severity: 'high', surface: 'soft', class: 'bg-severity-high/10 text-severity-high border border-severity-high/20' },
    { severity: 'medium', surface: 'soft', class: 'bg-severity-medium/10 text-severity-medium border border-severity-medium/20' },
    { severity: 'low', surface: 'soft', class: 'bg-severity-low/10 text-severity-low border border-severity-low/20' },
    { severity: 'info', surface: 'soft', class: 'bg-muted text-muted-foreground border border-border' },

    { severity: 'critical', surface: 'dot', class: 'bg-severity-critical' },
    { severity: 'high', surface: 'dot', class: 'bg-severity-high' },
    { severity: 'medium', surface: 'dot', class: 'bg-severity-medium' },
    { severity: 'low', surface: 'dot', class: 'bg-severity-low' },
    { severity: 'info', surface: 'dot', class: 'bg-muted-foreground' },
  ],
  defaultVariants: {
    severity: 'info',
    surface: 'none',
  },
});

export type SeverityTokenProps = VariantProps<typeof severityToken>;

/** Map notification tier (1-5) to severity level. */
export function tierToSeverity(tier: number): SeverityLevel {
  if (tier >= 5) return 'critical';
  if (tier === 4) return 'high';
  if (tier === 3) return 'medium';
  if (tier === 2) return 'low';
  return 'info';
}

// ---------- Surface elevation tokens ----------

export const surfaceToken = cva('', {
  variants: {
    level: {
      1: 'bg-surface-1',
      2: 'bg-surface-2',
      3: 'bg-surface-3',
      4: 'bg-surface-4',
    },
    border: {
      none: '',
      default: 'border border-border',
      strong: 'border border-border/80',
    },
    shadow: {
      none: '',
      xs: 'shadow-hydra-xs',
      sm: 'shadow-hydra-sm',
      md: 'shadow-hydra-md',
      lg: 'shadow-hydra-lg',
    },
    radius: {
      none: 'rounded-none',
      sm: 'rounded-sm',
      md: 'rounded-md',
      lg: 'rounded-lg',
      xl: 'rounded-xl',
    },
  },
  defaultVariants: {
    level: 2,
    border: 'default',
    shadow: 'sm',
    radius: 'lg',
  },
});

export type SurfaceTokenProps = VariantProps<typeof surfaceToken>;

// ---------- Focus / keyboard tokens ----------

export const focusRing =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background';

export const interactive =
  'transition-colors duration-150 hover:bg-accent hover:text-accent-foreground';

export const interactiveCard =
  'transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 hover:border-foreground/10 active:translate-y-0 active:shadow-sm';
