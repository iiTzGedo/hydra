import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Command, CornerDownLeft, ArrowUp, ArrowDown } from 'lucide-react';
import { formatShortcut, GLOBAL_SHORTCUTS, type ShortcutDisplayConfig } from '@/hooks/use-keyboard-shortcuts';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ShortcutGroup {
  title: string;
  shortcuts: ShortcutDisplayConfig[];
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: 'Navigation',
    shortcuts: [
      GLOBAL_SHORTCUTS.GO_TO_DASHBOARD,
      GLOBAL_SHORTCUTS.GO_TO_NODES,
      GLOBAL_SHORTCUTS.GO_TO_SERVICES,
      GLOBAL_SHORTCUTS.GO_TO_NETWORKS,
      GLOBAL_SHORTCUTS.GO_TO_TOPOLOGY,
    ],
  },
  {
    title: 'Actions',
    shortcuts: [
      GLOBAL_SHORTCUTS.OPEN_SEARCH,
      GLOBAL_SHORTCUTS.REFRESH_DATA,
      GLOBAL_SHORTCUTS.CREATE_NEW,
      GLOBAL_SHORTCUTS.FOCUS_SEARCH,
    ],
  },
  {
    title: 'General',
    shortcuts: [
      GLOBAL_SHORTCUTS.SHOW_SHORTCUTS,
      GLOBAL_SHORTCUTS.CLOSE_MODAL,
    ],
  },
];

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsModal({ isOpen, onClose }: KeyboardShortcutsModalProps) {
  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl z-50 p-4"
          >
            <div className="bg-card border border-border rounded-2xl shadow-2xl overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-border">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-primary/10">
                    <Command className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">Keyboard Shortcuts</h2>
                    <p className="text-sm text-muted-foreground">
                      Press <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">?</kbd> anytime to show this help
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {/* Content */}
              <div className="p-6 max-h-[60vh] overflow-y-auto">
                <div className="grid gap-8 sm:grid-cols-2">
                  {SHORTCUT_GROUPS.map((group) => (
                    <div key={group.title}>
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                        {group.title}
                      </h3>
                      <div className="space-y-2">
                        {group.shortcuts.map((shortcut, index) => (
                          <div
                            key={index}
                            className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
                          >
                            <span className="text-sm text-foreground">{shortcut.description}</span>
                            <kbd className="flex items-center gap-1 px-2 py-1 bg-muted rounded-lg text-xs font-mono text-muted-foreground whitespace-nowrap">
                              {formatShortcut(shortcut)}
                            </kbd>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Tips */}
                <div className="mt-6 p-4 rounded-xl bg-muted/50 border border-border">
                  <h4 className="text-sm font-medium text-foreground mb-2">Pro Tips</h4>
                  <ul className="space-y-1.5 text-sm text-muted-foreground">
                    <li className="flex items-center gap-2">
                      <CornerDownLeft className="h-3.5 w-3.5" />
                      Shortcuts work anywhere except when typing in form fields
                    </li>
                    <li className="flex items-center gap-2">
                      <ArrowUp className="h-3.5 w-3.5" />
                      <ArrowDown className="h-3.5 w-3.5" />
                      Use arrow keys to navigate within lists and tables
                    </li>
                  </ul>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between p-4 border-t border-border bg-muted/30">
                <span className="text-xs text-muted-foreground">
                  {navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'} = Command/Control key
                </span>
                <Button onClick={onClose} size="sm">
                  Got it
                </Button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
