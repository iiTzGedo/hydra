import { useEffect, useRef, useCallback } from 'react';

interface FocusTrapOptions {
  enabled?: boolean;
  onEscape?: () => void;
  returnFocus?: boolean;
}

/**
 * useFocusTrap - Hook to trap focus within an element
 * 
 * Usage:
 * const ref = useFocusTrap({ enabled: isOpen, onEscape: closeModal });
 * return <div ref={ref}>...</div>
 */
export function useFocusTrap({ enabled = true, onEscape, returnFocus = true }: FocusTrapOptions = {}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const getFocusableElements = useCallback(() => {
    const container = containerRef.current;
    if (!container) return [];

    return Array.from(
      container.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
    ).filter((el) => {
      const isDisabled = (el as HTMLButtonElement | HTMLInputElement).disabled;
      return !isDisabled && !el.getAttribute('aria-hidden');
    });
  }, []);

  // Save previous focus and focus first element
  useEffect(() => {
    if (!enabled) return;

    previousFocusRef.current = document.activeElement as HTMLElement;
    
    // Focus first focusable element after a short delay to ensure DOM is ready
    const timer = setTimeout(() => {
      const focusable = getFocusableElements();
      if (focusable.length > 0) {
        focusable[0].focus();
      }
    }, 50);

    return () => {
      clearTimeout(timer);
      if (returnFocus && previousFocusRef.current) {
        previousFocusRef.current.focus();
      }
    };
  }, [enabled, returnFocus, getFocusableElements]);

  // Handle tab and shift+tab
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const focusable = getFocusableElements();
      if (focusable.length === 0) return;

      const firstElement = focusable[0];
      const lastElement = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    };

    // Handle escape
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onEscape) {
        onEscape();
      }
    };

    const container = containerRef.current;
    if (container) {
      container.addEventListener('keydown', handleKeyDown);
      container.addEventListener('keydown', handleEscape);
    }

    return () => {
      if (container) {
        container.removeEventListener('keydown', handleKeyDown);
        container.removeEventListener('keydown', handleEscape);
      }
    };
  }, [enabled, onEscape, getFocusableElements]);

  return containerRef;
}

/**
 * FocusTrap - Component wrapper for focus trapping
 */
interface FocusTrapProps {
  children: React.ReactNode;
  enabled?: boolean;
  onEscape?: () => void;
  returnFocus?: boolean;
  className?: string;
}

export function FocusTrap({ 
  children, 
  enabled = true, 
  onEscape, 
  returnFocus = true,
  className 
}: FocusTrapProps) {
  const ref = useFocusTrap({ enabled, onEscape, returnFocus });
  
  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
