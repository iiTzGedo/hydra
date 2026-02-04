import { useEffect, useRef, useMemo } from 'react';
import { Bell } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useNotificationStats } from '@/api/notifications';
import { useNotificationStore } from '@/stores/notification-store';
import { NotificationPanel } from './notification-panel';
import { useMediaQuery } from '@/hooks/use-media-query';
import { cn } from '@/lib/utils';

interface NotificationBellProps {
  className?: string;
}

/**
 * NotificationBell - Header notification indicator with popup panel
 *
 * Features:
 * - Responsive Popover that works on all screen sizes
 * - Unread badge with tier-based coloring (red for critical, orange for high)
 * - Animated badge entrance/exit
 * - Keyboard accessible (Escape to close)
 * - Returns focus to trigger on close
 * - Proper collision detection for popover positioning
 *
 * @example
 * <NotificationBell />
 */
export function NotificationBell({ className }: NotificationBellProps) {
  const { data: stats } = useNotificationStats();
  const { panelOpen, setPanelOpen } = useNotificationStore();
  const triggerRef = useRef<HTMLButtonElement>(null);
  
  // Use media query to adjust panel size on mobile
  const isMobile = useMediaQuery('(max-width: 640px)');

  // Use API stats as source of truth
  const unreadCount = stats?.unread ?? 0;

  // Determine badge color based on severity
  const badgeColor = useMemo(() => {
    const hasCritical = (stats?.byTier?.critical ?? 0) > 0;
    const hasHigh = (stats?.byTier?.high ?? 0) > 0;
    
    if (hasCritical) return 'bg-red-500 text-white';
    if (hasHigh) return 'bg-orange-500 text-white';
    return 'bg-primary text-primary-foreground';
  }, [stats]);

  // Close on escape key (handled by Popover, but also add global handler)
  useEffect(() => {
    if (!panelOpen) return;
    
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPanelOpen(false);
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [panelOpen, setPanelOpen]);

  // Return focus to trigger when panel closes
  useEffect(() => {
    if (!panelOpen && triggerRef.current) {
      triggerRef.current.focus();
    }
  }, [panelOpen]);

  return (
    <Popover open={panelOpen} onOpenChange={setPanelOpen}>
      <PopoverTrigger asChild>
        <Button
          ref={triggerRef}
          variant="ghost"
          size="icon"
          className={cn(
            'relative h-9 w-9 text-muted-foreground hover:text-foreground',
            className
          )}
          aria-label={`${unreadCount} unread notifications`}
          aria-haspopup="dialog"
          aria-expanded={panelOpen}
        >
          <Bell className="h-5 w-5" aria-hidden="true" />
          <AnimatePresence>
            {unreadCount > 0 && (
              <motion.span
                key="badge"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ 
                  scale: 1, 
                  opacity: 1,
                  transition: {
                    type: 'spring',
                    stiffness: 500,
                    damping: 15,
                  }
                }}
                exit={{ scale: 0, opacity: 0 }}
                className={cn(
                  'absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold',
                  badgeColor
                )}
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </motion.span>
            )}
          </AnimatePresence>
        </Button>
      </PopoverTrigger>
      
      <PopoverContent 
        align="end" 
        className={cn(
          "p-0",
          isMobile ? "w-[calc(100vw-2rem)]" : "w-[380px]"
        )} 
        sideOffset={8}
        collisionPadding={16}
        onOpenAutoFocus={(e) => e.preventDefault()} // Prevent auto-scroll on open
        aria-describedby="notification-panel-description"
      >
        <span id="notification-panel-description" className="sr-only">
          Notification panel with recent alerts and messages
        </span>
        <NotificationPanel 
          onClose={() => setPanelOpen(false)} 
          mobile={isMobile}
          triggerRef={triggerRef}
        />
      </PopoverContent>
    </Popover>
  );
}
