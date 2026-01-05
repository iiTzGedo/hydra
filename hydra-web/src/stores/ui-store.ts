import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiState {
  // Sidebar
  sidebarCollapsed: boolean;
  sidebarMobileOpen: boolean;

  // Theme (handled by theme-provider, but stored here for convenience)
  theme: 'light' | 'dark' | 'system';

  // Topology view
  topologyMode: 'infrastructure' | 'services';

  // Time machine
  timeMachineTimestamp: string | null;

  // Actions
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setSidebarMobileOpen: (open: boolean) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  setTopologyMode: (mode: 'infrastructure' | 'services') => void;
  setTimeMachineTimestamp: (timestamp: string | null) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      sidebarMobileOpen: false,
      theme: 'system',
      topologyMode: 'infrastructure',
      timeMachineTimestamp: null,

      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      setSidebarMobileOpen: (open) => set({ sidebarMobileOpen: open }),

      setTheme: (theme) => set({ theme }),

      setTopologyMode: (mode) => set({ topologyMode: mode }),

      setTimeMachineTimestamp: (timestamp) =>
        set({ timeMachineTimestamp: timestamp }),
    }),
    {
      name: 'hydra-ui-storage',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        theme: state.theme,
        topologyMode: state.topologyMode,
      }),
    }
  )
);
