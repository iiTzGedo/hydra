import { useRef, useEffect, useCallback } from 'react';
import { Bell, CheckCheck, Loader2, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import {
  useNotifications,
  useMarkAllRead,
  useMarkNotificationRead,
} from '@/api/notifications';
import { NotificationItem } from './notification-item';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';

interface NotificationPanelProps {
  /**
   * Callback when panel should close (item click, mark all read, etc.)
   */
  onClose?: () => void;
  /**
   * Whether this is the mobile version (inside Sheet)
   */
  mobile?: boolean;
  /**
   * Reference to the trigger button for focus management
   */
  triggerRef?: React.RefObject<HTMLButtonElement>;
}

/**
 * NotificationPanel - Displays list of notifications with actions
 *
 * Features:
 * - Keyboard navigation (Tab cycles through items, Enter opens, Escape closes)
 * - Focus trap within panel
 * - Focus returns to trigger on close
 * - Loading and empty states
 * - Mark individual or all as read
 * - Responsive sizing for mobile/desktop
 *
 * @example
 * // Desktop (inside Popover)
 * <NotificationPanel onClose={() => setOpen(false)} triggerRef={triggerRef} />
 *
 * // Mobile (inside Sheet)
 * <NotificationPanel onClose={() => setOpen(false)} mobile />
 */
export function NotificationPanel({
  onClose,
  mobile = false,
  triggerRef,
}: NotificationPanelProps) {
  const { data, isLoading } = useNotifications({
    limit: mobile ? 20 : 10,
    status: 'active',
  });
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllRead();
  const panelRef = useRef<HTMLDivElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);

  const notifications = data?.data ?? [];
  const total = data?.meta?.total ?? 0;

  // Handle mark single notification as read
  const handleMarkRead = useCallback(
    (id: string) => {
      markRead.mutate(id);
    },
    [markRead]
  );

  // Handle mark all as read
  const handleMarkAllRead = useCallback(() => {
    markAllRead.mutate({});
    onClose?.();
  }, [markAllRead, onClose]);

  // Focus trap and keyboard navigation
  useEffect(() => {
    if (!panelRef.current) return;

    const panel = panelRef.current;
    
    // Focus first item when panel opens
    if (notifications.length > 0 && firstItemRef.current) {
      firstItemRef.current.focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const focusableElements = panel.querySelectorAll<HTMLElement>(
        'button, a[href], [tabindex]:not([tabindex="-1"])'
      );
      
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    };

    panel.addEventListener('keydown', handleKeyDown);
    return () => panel.removeEventListener('keydown', handleKeyDown);
  }, [notifications.length]);

  // Animation variants
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.03,
        delayChildren: 0.05,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, x: -10 },
    visible: { 
      opacity: 1, 
      x: 0,
      transition: { duration: 0.15 }
    },
  };

  return (
    <div
      ref={panelRef}
      className={cn(
        'flex flex-col bg-popover',
        !mobile && 'rounded-lg border shadow-lg'
      )}
      role="dialog"
      aria-label="Notifications"
      aria-modal="true"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3 bg-muted/30">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-foreground">Notifications</h3>
          {total > 0 && (
            <Badge variant="secondary" className="text-xs">
              {total}
            </Badge>
          )}
        </div>
        {notifications.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-xs"
            onClick={handleMarkAllRead}
            disabled={markAllRead.isPending}
          >
            {markAllRead.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <CheckCheck className="h-3.5 w-3.5" />
            )}
            Mark all read
          </Button>
        )}
      </div>

      {/* Content */}
      <ScrollArea
        className={cn(
          'overflow-y-auto',
          mobile ? 'max-h-[calc(100vh-180px)]' : 'max-h-[400px]'
        )}
      >
        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : notifications.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <div className="rounded-full bg-muted p-4">
              <Bell className="h-8 w-8 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">No notifications</p>
              <p className="text-xs text-muted-foreground mt-1">
                You&apos;re all caught up
              </p>
            </div>
          </div>
        ) : (
          <motion.div
            className="divide-y"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            {notifications.map((notification, index) => (
              <motion.div key={notification.notificationId} variants={itemVariants}>
                <NotificationItem
                  notification={notification}
                  compact
                  onMarkRead={handleMarkRead}
                  onClick={onClose}
                  autoFocus={index === 0}
                  ref={index === 0 ? firstItemRef : undefined}
                />
              </motion.div>
            ))}
          </motion.div>
        )}
      </ScrollArea>

      {/* Footer */}
      {total > 0 && (
        <div className="border-t px-4 py-3 bg-muted/30">
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-xs group"
            asChild
            onClick={onClose}
          >
            <Link to={ROUTES.NOTIFICATIONS}>
              View all notifications
              <span className="ml-1 text-muted-foreground">
                ({total})
              </span>
              <ChevronRight className="h-3 w-3 ml-auto transition-transform group-hover:translate-x-0.5" />
            </Link>
          </Button>
        </div>
      )}
    </div>
  );
}
