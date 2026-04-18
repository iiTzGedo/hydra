import { forwardRef, useCallback } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  AlertTriangle,
  Check,
  CheckCircle,
  ChevronRight,
  Info,
  Server,
  ShieldAlert,
  Trash2,
  XCircle,
} from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { Notification, NotificationTier } from '@/types/notification';
import { ACKNOWLEDGE_MIN_TIER, DETAILS_MODAL_MIN_TIER, INFO_MAX_TIER, RESOLVE_MIN_TIER, TIER_COLORS } from '@/types/notification';

const tierIcons: Record<NotificationTier, React.ElementType> = {
  1: Info,
  2: CheckCircle,
  3: AlertTriangle,
  4: ShieldAlert,
  5: XCircle,
};

interface NotificationItemProps {
  notification: Notification;
  compact?: boolean;
  onMarkRead?: (id: string) => void;
  onAcknowledge?: (id: string) => void;
  onResolve?: (id: string) => void;
  onDelete?: (id: string) => void;
  /**
   * Called when a tier 4-5 notification is clicked to show details modal
   */
  onViewDetails?: (notification: Notification) => void;
  /**
   * Called when the notification is clicked (for navigation)
   */
  onClick?: () => void;
  /**
   * Whether to auto-focus this item (for keyboard navigation)
   */
  autoFocus?: boolean;
  /**
   * Whether the user has write permission (can acknowledge/resolve)
   */
  canWrite?: boolean;
}

/**
 * NotificationItem - Displays a single notification
 *
 * Features:
 * - Click to navigate to related entity
 * - Mark as read action
 * - Visual indicators for tier and read status
 * - Compact mode for notification panel
 * - Keyboard accessible
 *
 * @example
 * // In notification panel
 * <NotificationItem
 *   notification={notification}
 *   compact
 *   onMarkRead={handleMarkRead}
 *   onClick={() => setPanelOpen(false)}
 * />
 */
export const NotificationItem = forwardRef<HTMLButtonElement, NotificationItemProps>(
  function NotificationItem(
    {
      notification,
      compact = false,
      onMarkRead,
      onAcknowledge,
      onResolve,
      onDelete,
      onViewDetails,
      onClick,
      autoFocus,
      canWrite = true,
    },
    ref
  ) {
    const router = useRouter();
    const tier = notification.tier as NotificationTier;
    const colors = TIER_COLORS[tier];
    const Icon = tierIcons[tier];
    const isUnread = !notification.readAt;
    const isActive = notification.status === 'active';

    const timeAgo = formatDistanceToNow(new Date(notification.createdAt), {
      addSuffix: true,
    });

    const occurrenceCount = notification.event?.occurrenceCount ?? 1;

    // Find the first link to use as a deep link
    const primaryLink = notification.links?.[0];

    // Handle click on notification item
    const handleClick = useCallback(() => {
      // Open details modal for tier 4-5 (Orange/Red) notifications
      if (tier >= DETAILS_MODAL_MIN_TIER && onViewDetails) {
        onViewDetails(notification);
        onClick?.();
        return;
      }
      // Navigate to the primary link if available (validate relative path to prevent open redirect)
      if (primaryLink && primaryLink.href.startsWith('/') && !primaryLink.href.startsWith('//')) {
        router.push(primaryLink.href);
      }
      onClick?.();
    }, [router, primaryLink, onClick, tier, onViewDetails, notification]);

    // Handle mark read without triggering navigation
    const handleMarkRead = useCallback(
      (e: React.MouseEvent) => {
        e.stopPropagation();
        onMarkRead?.(notification.notificationId);
      },
      [onMarkRead, notification.notificationId]
    );

    // Compact mode for notification panel
    if (compact) {
      return (
        <button
          ref={ref}
          onClick={handleClick}
          className={cn(
            'w-full text-left transition-colors focus:outline-none focus:bg-muted',
            'hover:bg-muted/60',
            isUnread ? 'bg-primary/5' : 'opacity-70',
            'p-3'
          )}
          autoFocus={autoFocus}
          aria-label={`${notification.title}. ${isUnread ? 'Unread' : 'Read'}`}
        >
          <div className="flex gap-3">
            {/* Tier icon */}
            <div className={cn('mt-0.5 flex-shrink-0 rounded-full p-1.5', colors.bg)}>
              <Icon className={cn('h-4 w-4', colors.text)} />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p
                  className={cn(
                    'text-sm leading-tight',
                    isUnread ? 'font-medium text-foreground' : 'text-muted-foreground'
                  )}
                >
                  {notification.title}
                  {occurrenceCount > 1 && (
                    <span className={cn('ml-1.5 text-xs', colors.text)}>
                      ({occurrenceCount}x)
                    </span>
                  )}
                </p>
              </div>

              <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                {notification.message}
              </p>

              {/* Footer: time and actions */}
              <div className="flex items-center gap-3 mt-2">
                <span className="text-xs text-muted-foreground">{timeAgo}</span>

                {/* Mark read in compact mode: only for informational tiers (1-2) */}
                {isUnread && onMarkRead && tier <= INFO_MAX_TIER && (
                  <>
                    <span className="text-border">•</span>
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={handleMarkRead}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleMarkRead(e as unknown as React.MouseEvent); } }}
                      className="text-xs text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-primary/20 rounded px-1 cursor-pointer"
                    >
                      Mark read
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Unread indicator */}
            {isUnread && (
              <div className={cn('mt-2 h-2 w-2 flex-shrink-0 rounded-full', colors.dot)} />
            )}
          </div>
        </button>
      );
    }

    // Full mode for notification list page
    return (
      <div
        className={cn(
          'flex items-start gap-3 rounded-lg border p-3 transition-colors',
          isUnread
            ? `${colors.bg} ${colors.border}`
            : 'border-border/50 bg-background'
        )}
      >
        {/* Tier indicator */}
        <div className={cn('mt-0.5 flex-shrink-0 rounded-full p-1.5', colors.bg)}>
          <Icon className={cn('h-4 w-4', colors.text)} />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p
                className={cn(
                  'text-sm font-medium leading-tight',
                  isUnread ? '' : 'text-muted-foreground'
                )}
              >
                {notification.title}
                {occurrenceCount > 1 && (
                  <span className={cn('ml-1.5 text-xs font-normal', colors.text)}>
                    ({occurrenceCount}x)
                  </span>
                )}
              </p>

              <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                {notification.message}
              </p>
            </div>

            {/* Time */}
            <span className="flex-shrink-0 text-xs text-muted-foreground whitespace-nowrap">
              {timeAgo}
            </span>
          </div>

          {/* Source + Actions row */}
          <div className="mt-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Server className="h-3 w-3" />
              <span>{notification.source.component}</span>
              {notification.source.nodeId && (
                <>
                  <span className="text-border">/</span>
                  <span>{notification.source.nodeId}</span>
                </>
              )}
              {notification.acknowledgedAt && notification.status === 'active' && (
                <span className="flex items-center gap-1 text-success">
                  <Check className="h-3 w-3" />
                  Acknowledged
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              {/* Mark read: only for informational tiers (1-2) */}
              {isUnread && onMarkRead && tier <= INFO_MAX_TIER && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => onMarkRead(notification.notificationId)}
                >
                  Mark read
                </Button>
              )}
              {/* Acknowledge: tier 3+ — only if user has write permission */}
              {canWrite && isActive && !notification.acknowledgedAt && onAcknowledge && tier >= ACKNOWLEDGE_MIN_TIER && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => onAcknowledge(notification.notificationId)}
                >
                  Acknowledge
                </Button>
              )}
              {/* Resolve: tier 3+ — only if user has write permission */}
              {canWrite && isActive && onResolve && tier >= RESOLVE_MIN_TIER && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => onResolve(notification.notificationId)}
                >
                  Resolve
                </Button>
              )}
              {primaryLink && (
                <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" asChild>
                  <button onClick={handleClick}>
                    {primaryLink.label}
                    <ChevronRight className="ml-0.5 h-3 w-3" />
                  </button>
                </Button>
              )}
              {/* Delete: available to all users */}
              {onDelete && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(notification.notificationId);
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Unread dot */}
        {isUnread && <div className={cn('mt-2 h-2 w-2 flex-shrink-0 rounded-full', colors.dot)} />}
      </div>
    );
  }
);

export type { NotificationItemProps };
