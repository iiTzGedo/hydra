import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ViewLayout = 'list' | 'grid' | 'compact';
export type SortDirection = 'asc' | 'desc';

export interface ViewPreferences {
  layout: ViewLayout;
  sortField: string;
  sortDirection: SortDirection;
}

const defaultViewPrefs: ViewPreferences = {
  layout: 'list',
  sortField: 'displayName',
  sortDirection: 'asc',
};

interface UiState {
  sidebarCollapsed: boolean;
  sidebarMobileOpen: boolean;
  theme: 'light' | 'dark' | 'system';
  topologyMode: 'infrastructure' | 'network' | 'service';
  timeMachineTimestamp: string | null;
  nodesView: ViewPreferences;
  networksView: ViewPreferences;
  servicesView: ViewPreferences;
  groupsView: ViewPreferences;
  profilesView: ViewPreferences;

  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setSidebarMobileOpen: (open: boolean) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  setTopologyMode: (mode: 'infrastructure' | 'network' | 'service') => void;
  setTimeMachineTimestamp: (timestamp: string | null) => void;
  setNodesView: (prefs: Partial<ViewPreferences>) => void;
  setNetworksView: (prefs: Partial<ViewPreferences>) => void;
  setServicesView: (prefs: Partial<ViewPreferences>) => void;
  setGroupsView: (prefs: Partial<ViewPreferences>) => void;
  setProfilesView: (prefs: Partial<ViewPreferences>) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      sidebarMobileOpen: false,
      theme: 'system',
      topologyMode: 'infrastructure',
      timeMachineTimestamp: null,
      nodesView: { ...defaultViewPrefs },
      networksView: { ...defaultViewPrefs },
      servicesView: { ...defaultViewPrefs },
      groupsView: { ...defaultViewPrefs },
      profilesView: { ...defaultViewPrefs, sortField: 'submittedAt', sortDirection: 'desc' },

      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      setSidebarMobileOpen: (open) => set({ sidebarMobileOpen: open }),

      setTheme: (theme) => set({ theme }),

      setTopologyMode: (mode) => set({ topologyMode: mode }),

      setTimeMachineTimestamp: (timestamp) =>
        set({ timeMachineTimestamp: timestamp }),

      setNodesView: (prefs) =>
        set((state) => ({ nodesView: { ...state.nodesView, ...prefs } })),

      setNetworksView: (prefs) =>
        set((state) => ({ networksView: { ...state.networksView, ...prefs } })),

      setServicesView: (prefs) =>
        set((state) => ({ servicesView: { ...state.servicesView, ...prefs } })),

      setGroupsView: (prefs) =>
        set((state) => ({ groupsView: { ...state.groupsView, ...prefs } })),

      setProfilesView: (prefs) =>
        set((state) => ({ profilesView: { ...state.profilesView, ...prefs } })),
    }),
    {
      name: 'hydra-ui-storage',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        theme: state.theme,
        topologyMode: state.topologyMode,
        nodesView: state.nodesView,
        networksView: state.networksView,
        servicesView: state.servicesView,
        groupsView: state.groupsView,
        profilesView: state.profilesView,
      }),
    }
  )
);
