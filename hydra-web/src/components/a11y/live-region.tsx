import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

type LiveRegionPriority = 'polite' | 'assertive';

interface LiveRegionProps {
  id: string;
  priority?: LiveRegionPriority;
  className?: string;
}

/**
 * LiveRegion - Screen reader announcement container
 * 
 * Use for dynamic content updates that should be announced to screen readers.
 * 
 * Usage:
 * <LiveRegion id="notifications" priority="polite" />
 * 
 * Then announce with:
 * announce('Item saved successfully', 'polite');
 */
export function LiveRegion({ id, priority = 'polite', className }: LiveRegionProps) {
  return (
    <div
      id={id}
      role="status"
      aria-live={priority}
      aria-atomic="true"
      className={cn('sr-only', className)}
    />
  );
}

/**
 * Announce message to screen readers
 */
export function announce(message: string, priority: LiveRegionPriority = 'polite') {
  const regionId = `live-region-${priority}`;
  const region = document.getElementById(regionId);
  
  if (region) {
    region.textContent = message;
    // Clear after announcement (screen readers typically read within 100ms)
    setTimeout(() => {
      region.textContent = '';
    }, 1000);
  }
}

/**
 * LiveRegionProvider - Creates both polite and assertive live regions
 */
export function LiveRegionProvider({ children }: { children: React.ReactNode }) {
  return (
    <>
      <LiveRegion id="live-region-polite" priority="polite" />
      <LiveRegion id="live-region-assertive" priority="assertive" />
      {children}
    </>
  );
}

/**
 * useAnnouncer - Hook for making announcements
 */
export function useAnnouncer() {
  return {
    announce: (message: string) => announce(message, 'polite'),
    announceAssertive: (message: string) => announce(message, 'assertive'),
  };
}
