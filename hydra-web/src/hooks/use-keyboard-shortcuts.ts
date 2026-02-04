import { useEffect, useCallback, useRef } from 'react';

type ShortcutHandler = (e: KeyboardEvent) => void;

interface ShortcutConfig {
  key: string;
  handler: ShortcutHandler;
  description: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;
  preventDefault?: boolean;
  disabled?: boolean;
}

/**
 * useKeyboardShortcuts - Hook for registering keyboard shortcuts
 * 
 * Usage:
 * useKeyboardShortcuts([
 *   { key: 'k', ctrl: true, handler: openSearch, description: 'Open search' },
 *   { key: '?', handler: showHelp, description: 'Show keyboard shortcuts' },
 * ]);
 */
export function useKeyboardShortcuts(shortcuts: ShortcutConfig[]) {
  const shortcutsRef = useRef(shortcuts);
  shortcutsRef.current = shortcuts;

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Ignore shortcuts when user is typing in an input
    if (
      e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement ||
      e.target instanceof HTMLSelectElement ||
      (e.target as HTMLElement)?.isContentEditable
    ) {
      return;
    }

    shortcutsRef.current.forEach((shortcut) => {
      if (shortcut.disabled) return;

      const keyMatch = e.key.toLowerCase() === shortcut.key.toLowerCase();
      const ctrlMatch = !!shortcut.ctrl === (e.ctrlKey || e.metaKey);
      const shiftMatch = !!shortcut.shift === e.shiftKey;
      const altMatch = !!shortcut.alt === e.altKey;

      if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
        if (shortcut.preventDefault !== false) {
          e.preventDefault();
        }
        shortcut.handler(e);
      }
    });
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

/**
 * useShortcut - Register a single keyboard shortcut
 */
export function useShortcut(
  key: string,
  handler: ShortcutHandler,
  options?: Omit<ShortcutConfig, 'key' | 'handler'>
) {
  useKeyboardShortcuts([{ key, handler, ...options }]);
}

/**
 * Global shortcut definitions
 */
export const GLOBAL_SHORTCUTS = {
  // Navigation
  GO_TO_DASHBOARD: { key: 'g', ctrl: true, shift: true, description: 'Go to Dashboard' },
  GO_TO_NODES: { key: 'n', ctrl: true, shift: true, description: 'Go to Nodes' },
  GO_TO_SERVICES: { key: 's', ctrl: true, shift: true, description: 'Go to Services' },
  GO_TO_NETWORKS: { key: 'w', ctrl: true, shift: true, description: 'Go to Networks' },
  GO_TO_TOPOLOGY: { key: 't', ctrl: true, shift: true, description: 'Go to Topology' },
  
  // Actions
  OPEN_SEARCH: { key: 'k', ctrl: true, description: 'Open command palette' },
  REFRESH_DATA: { key: 'r', ctrl: true, description: 'Refresh current page data' },
  CREATE_NEW: { key: 'n', ctrl: true, description: 'Create new item' },
  
  // Help
  SHOW_SHORTCUTS: { key: '?', description: 'Show keyboard shortcuts' },
  CLOSE_MODAL: { key: 'Escape', description: 'Close modal/dialog' },
  
  // Focus
  FOCUS_SEARCH: { key: '/', description: 'Focus search input' },
  FOCUS_NEXT: { key: 'j', ctrl: true, description: 'Focus next item' },
  FOCUS_PREV: { key: 'k', ctrl: true, description: 'Focus previous item' },
} as const;

export interface ShortcutDisplayConfig {
  key: string;
  description: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;
}

export type ShortcutDefinition = typeof GLOBAL_SHORTCUTS[keyof typeof GLOBAL_SHORTCUTS];

/**
 * Format shortcut for display
 */
export function formatShortcut(shortcut: ShortcutDisplayConfig): string {
  const parts: string[] = [];
  
  if (shortcut.ctrl || shortcut.meta) parts.push('⌘');
  if (shortcut.alt) parts.push('⌥');
  if (shortcut.shift) parts.push('⇧');
  
  const keyMap: Record<string, string> = {
    'ArrowUp': '↑',
    'ArrowDown': '↓',
    'ArrowLeft': '←',
    'ArrowRight': '→',
    'Escape': 'Esc',
    'Enter': '↵',
    'Tab': '⇥',
  };
  
  parts.push(keyMap[shortcut.key] || shortcut.key.toUpperCase());
  
  return parts.join(' ');
}
