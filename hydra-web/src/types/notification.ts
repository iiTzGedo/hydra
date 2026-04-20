/** Notification tier (1=blue/user, 2=green/system, 3=yellow/warning, 4=orange/high, 5=red/critical). */
export type NotificationTier = 1 | 2 | 3 | 4 | 5;

export type TierLabel = 'low_user' | 'low_system' | 'warning' | 'high' | 'critical';

export type NotificationStatus = 'active' | 'resolved' | 'expired';

export type SourceComponent = 'hydra-api' | 'hydra-agent' | 'hydra-mcp' | 'hydra-web' | 'system';

export interface NotificationSource {
  component: SourceComponent;
  service: string;
  nodeId?: string;
  serviceId?: string;
}

export interface NotificationLink {
  label: string;
  entityType: string;
  entityId: string;
  href: string;
}

export interface NotificationActor {
  type: 'system' | 'user' | 'agent';
  id: string;
  ip?: string;
  userAgent?: string;
}

export interface NotificationEvent {
  firstSeenAt: string;
  lastSeenAt: string;
  occurrenceCount: number;
}

export interface Notification {
  notificationId: string;
  type: string;
  tier: NotificationTier;
  tierLabel: TierLabel;
  source: NotificationSource;
  title: string;
  message: string;
  details?: Record<string, unknown>;
  links?: NotificationLink[];
  actor?: NotificationActor;
  event?: NotificationEvent;
  targetUserId?: string;
  targetRoles: string[];
  groupKey: string;
  correlationId?: string;
  auditEntryId?: string | null;
  status: NotificationStatus;
  readAt?: string | null;
  createdAt: string;
  expiresAt?: string | null;
  acknowledgedAt?: string | null;
  acknowledgedBy?: string | null;
  resolvedAt?: string | null;
  resolvedBy?: string | null;
}

export interface NotificationStats {
  total: number;
  unread: number;
  needsAttention: number;
  acknowledgedPending: number;
  byTier: Record<string, number>;
  byStatus: Record<string, number>;
  bySource: Record<string, number>;
}

export interface NotificationListParams {
  tier?: NotificationTier;
  tierMin?: NotificationTier;
  tierMax?: NotificationTier;
  status?: NotificationStatus;
  read?: boolean;
  acknowledged?: boolean;
  source?: SourceComponent;
  nodeId?: string;
  type?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

export interface NotificationBulkActionRequest {
  tier?: NotificationTier;
  tierMin?: NotificationTier;
  status?: NotificationStatus;
  source?: SourceComponent;
  nodeId?: string;
}

export interface NotificationBulkActionResponse {
  affectedCount: number;
}

export interface NotificationBulkDeleteRequest {
  notificationIds?: string[];
  status?: NotificationStatus;
  tier?: NotificationTier;
  before?: string;
}

/** Minimum tier required for acknowledge action (Yellow+). */
export const ACKNOWLEDGE_MIN_TIER: NotificationTier = 3;

/** Minimum tier required for resolve action (Warning+). */
export const RESOLVE_MIN_TIER: NotificationTier = 3;

/** Maximum tier for informational notifications (Blue/Green). */
export const INFO_MAX_TIER: NotificationTier = 2;

/** Minimum tier that shows a details modal on click (Orange+). */
export const DETAILS_MODAL_MIN_TIER: NotificationTier = 4;

/**
 * Tier color mapping for UI rendering.
 * Uses semantic severity tokens from tailwind config (see `src/index.css` and
 * `src/lib/design-tokens.ts`) so colours respond to light/dark themes.
 *
 * Tier 1 (low user) → low severity (blue)
 * Tier 2 (low system) → success (green)
 * Tier 3 (warning) → medium severity (amber/warning)
 * Tier 4 (high) → high severity (orange)
 * Tier 5 (critical) → critical severity (red)
 */
export const TIER_COLORS: Record<NotificationTier, { bg: string; text: string; border: string; dot: string; label: string }> = {
  1: {
    bg: 'bg-severity-low/10',
    text: 'text-severity-low',
    border: 'border-severity-low/20',
    dot: 'bg-severity-low',
    label: 'Info',
  },
  2: {
    bg: 'bg-success/10',
    text: 'text-success',
    border: 'border-success/20',
    dot: 'bg-success',
    label: 'System',
  },
  3: {
    bg: 'bg-severity-medium/10',
    text: 'text-severity-medium',
    border: 'border-severity-medium/20',
    dot: 'bg-severity-medium',
    label: 'Warning',
  },
  4: {
    bg: 'bg-severity-high/10',
    text: 'text-severity-high',
    border: 'border-severity-high/20',
    dot: 'bg-severity-high',
    label: 'High',
  },
  5: {
    bg: 'bg-severity-critical/10',
    text: 'text-severity-critical',
    border: 'border-severity-critical/20',
    dot: 'bg-severity-critical',
    label: 'Critical',
  },
};

/** Tier label to tier number mapping. */
export const TIER_LABEL_MAP: Record<TierLabel, NotificationTier> = {
  low_user: 1,
  low_system: 2,
  warning: 3,
  high: 4,
  critical: 5,
};
