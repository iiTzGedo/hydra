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

/** Tier color mapping for UI rendering. */
export const TIER_COLORS: Record<NotificationTier, { bg: string; text: string; border: string; dot: string; label: string }> = {
  1: { bg: 'bg-blue-50 dark:bg-blue-950/30', text: 'text-blue-700 dark:text-blue-400', border: 'border-blue-200 dark:border-blue-800', dot: 'bg-blue-500', label: 'Info' },
  2: { bg: 'bg-green-50 dark:bg-green-950/30', text: 'text-green-700 dark:text-green-400', border: 'border-green-200 dark:border-green-800', dot: 'bg-green-500', label: 'System' },
  3: { bg: 'bg-yellow-50 dark:bg-yellow-950/30', text: 'text-yellow-700 dark:text-yellow-400', border: 'border-yellow-200 dark:border-yellow-800', dot: 'bg-yellow-500', label: 'Warning' },
  4: { bg: 'bg-orange-50 dark:bg-orange-950/30', text: 'text-orange-700 dark:text-orange-400', border: 'border-orange-200 dark:border-orange-800', dot: 'bg-orange-500', label: 'High' },
  5: { bg: 'bg-red-50 dark:bg-red-950/30', text: 'text-red-700 dark:text-red-400', border: 'border-red-200 dark:border-red-800', dot: 'bg-red-500', label: 'Critical' },
};

/** Tier label to tier number mapping. */
export const TIER_LABEL_MAP: Record<TierLabel, NotificationTier> = {
  low_user: 1,
  low_system: 2,
  warning: 3,
  high: 4,
  critical: 5,
};
