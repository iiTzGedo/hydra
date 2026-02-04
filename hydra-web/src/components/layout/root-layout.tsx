import { Outlet, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './sidebar';
import { Header } from './header';
import { ToastContainer, subscribeToToasts, removeToast, type Toast } from '@/components/ui/toast-container';
import { KeyboardShortcutsModal } from '@/components/modals/keyboard-shortcuts-modal';
import { useKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { SkipLinks } from '@/components/a11y/skip-link';
import { ROUTES } from '@/lib/constants';
import { useQueryClient } from '@tanstack/react-query';
import { useNotificationsSocket } from '@/hooks/use-notifications-socket';

interface RootLayoutProps {
  children?: React.ReactNode;
}

/**
 * RootLayout - Main application layout with sidebar and header
 * 
 * Features:
 * - Toast notifications
 * - Keyboard shortcuts
 * - Skip links for accessibility
 * - Global navigation shortcuts
 */
export function RootLayout({ children }: RootLayoutProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [showShortcuts, setShowShortcuts] = useState(false);

  useNotificationsSocket();

  // Subscribe to toast updates
  useEffect(() => {
    const unsubscribe = subscribeToToasts(setToasts);
    return unsubscribe;
  }, []);

  // Refresh current page data
  const refreshData = useCallback(() => {
    queryClient.invalidateQueries();
  }, [queryClient]);

  // Global keyboard shortcuts
  useKeyboardShortcuts([
    // Navigation
    {
      key: 'g',
      ctrl: true,
      shift: true,
      handler: () => navigate(ROUTES.DASHBOARD),
      description: 'Go to Dashboard',
    },
    {
      key: 'n',
      ctrl: true,
      shift: true,
      handler: () => navigate(ROUTES.NODES),
      description: 'Go to Nodes',
    },
    {
      key: 's',
      ctrl: true,
      shift: true,
      handler: () => navigate(ROUTES.SERVICES),
      description: 'Go to Services',
    },
    {
      key: 'w',
      ctrl: true,
      shift: true,
      handler: () => navigate(ROUTES.NETWORKS),
      description: 'Go to Networks',
    },
    {
      key: 't',
      ctrl: true,
      shift: true,
      handler: () => navigate(ROUTES.TOPOLOGY),
      description: 'Go to Topology',
    },
    // Actions
    {
      key: 'r',
      ctrl: true,
      handler: refreshData,
      description: 'Refresh data',
    },
    // Help
    {
      key: '?',
      handler: () => setShowShortcuts(true),
      description: 'Show keyboard shortcuts',
    },
  ]);

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Skip Links for Accessibility */}
      <SkipLinks
        links={[
          { href: '#main-content', label: 'Skip to main content' },
          { href: '#sidebar-nav', label: 'Skip to navigation' },
        ]}
      />

      {/* Sidebar */}
      <aside id="sidebar-nav">
        <Sidebar />
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />

        <main 
          id="main-content"
          className="flex-1 overflow-auto bg-background p-4 sm:p-6"
          tabIndex={-1}
        >
          {children || <Outlet />}
        </main>
      </div>

      {/* Toast Notifications */}
      <ToastContainer
        toasts={toasts}
        onDismiss={removeToast}
        position="bottom-right"
      />

      {/* Keyboard Shortcuts Help Modal */}
      <KeyboardShortcutsModal
        isOpen={showShortcuts}
        onClose={() => setShowShortcuts(false)}
      />
    </div>
  );
}
