/**
 * Tests for ui-store.ts
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useUiStore } from '@/stores/ui-store';
import type { ViewPreferences } from '@/stores/ui-store';

describe('ui-store', () => {
  beforeEach(() => {
    // Reset store to initial state
    useUiStore.setState({
      sidebarCollapsed: false,
      sidebarMobileOpen: false,
      theme: 'system',
      topologyMode: 'infrastructure',
      timeMachineTimestamp: null,
      nodesView: { layout: 'list', sortField: 'displayName', sortDirection: 'asc' },
      networksView: { layout: 'list', sortField: 'displayName', sortDirection: 'asc' },
      servicesView: { layout: 'list', sortField: 'displayName', sortDirection: 'asc' },
      groupsView: { layout: 'list', sortField: 'displayName', sortDirection: 'asc' },
      profilesView: { layout: 'list', sortField: 'submittedAt', sortDirection: 'desc' },
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const state = useUiStore.getState();
      expect(state.sidebarCollapsed).toBe(false);
      expect(state.sidebarMobileOpen).toBe(false);
      expect(state.theme).toBe('system');
      expect(state.topologyMode).toBe('infrastructure');
      expect(state.timeMachineTimestamp).toBeNull();
    });

    it('should have correct default view preferences for nodes', () => {
      const state = useUiStore.getState();
      expect(state.nodesView).toEqual({
        layout: 'list',
        sortField: 'displayName',
        sortDirection: 'asc',
      });
    });

    it('should have correct default view preferences for profiles', () => {
      const state = useUiStore.getState();
      expect(state.profilesView).toEqual({
        layout: 'list',
        sortField: 'submittedAt',
        sortDirection: 'desc',
      });
    });
  });

  describe('toggleSidebar', () => {
    it('should toggle sidebarCollapsed from false to true', () => {
      const { toggleSidebar } = useUiStore.getState();
      toggleSidebar();
      expect(useUiStore.getState().sidebarCollapsed).toBe(true);
    });

    it('should toggle sidebarCollapsed from true to false', () => {
      const { toggleSidebar } = useUiStore.getState();
      useUiStore.setState({ sidebarCollapsed: true });
      toggleSidebar();
      expect(useUiStore.getState().sidebarCollapsed).toBe(false);
    });
  });

  describe('setSidebarCollapsed', () => {
    it('should set sidebarCollapsed to true', () => {
      const { setSidebarCollapsed } = useUiStore.getState();
      setSidebarCollapsed(true);
      expect(useUiStore.getState().sidebarCollapsed).toBe(true);
    });

    it('should set sidebarCollapsed to false', () => {
      const { setSidebarCollapsed } = useUiStore.getState();
      useUiStore.setState({ sidebarCollapsed: true });
      setSidebarCollapsed(false);
      expect(useUiStore.getState().sidebarCollapsed).toBe(false);
    });
  });

  describe('setSidebarMobileOpen', () => {
    it('should set sidebarMobileOpen to true', () => {
      const { setSidebarMobileOpen } = useUiStore.getState();
      setSidebarMobileOpen(true);
      expect(useUiStore.getState().sidebarMobileOpen).toBe(true);
    });

    it('should set sidebarMobileOpen to false', () => {
      const { setSidebarMobileOpen } = useUiStore.getState();
      useUiStore.setState({ sidebarMobileOpen: true });
      setSidebarMobileOpen(false);
      expect(useUiStore.getState().sidebarMobileOpen).toBe(false);
    });
  });

  describe('setTheme', () => {
    it('should set theme to light', () => {
      const { setTheme } = useUiStore.getState();
      setTheme('light');
      expect(useUiStore.getState().theme).toBe('light');
    });

    it('should set theme to dark', () => {
      const { setTheme } = useUiStore.getState();
      setTheme('dark');
      expect(useUiStore.getState().theme).toBe('dark');
    });

    it('should set theme to system', () => {
      const { setTheme } = useUiStore.getState();
      setTheme('system');
      expect(useUiStore.getState().theme).toBe('system');
    });
  });

  describe('setTopologyMode', () => {
    it('should set topologyMode to infrastructure', () => {
      const { setTopologyMode } = useUiStore.getState();
      setTopologyMode('infrastructure');
      expect(useUiStore.getState().topologyMode).toBe('infrastructure');
    });

    it('should set topologyMode to network', () => {
      const { setTopologyMode } = useUiStore.getState();
      setTopologyMode('network');
      expect(useUiStore.getState().topologyMode).toBe('network');
    });

    it('should set topologyMode to service', () => {
      const { setTopologyMode } = useUiStore.getState();
      setTopologyMode('service');
      expect(useUiStore.getState().topologyMode).toBe('service');
    });
  });

  describe('setTimeMachineTimestamp', () => {
    it('should set timeMachineTimestamp to an ISO string', () => {
      const { setTimeMachineTimestamp } = useUiStore.getState();
      const timestamp = '2024-01-15T10:30:00Z';
      setTimeMachineTimestamp(timestamp);
      expect(useUiStore.getState().timeMachineTimestamp).toBe(timestamp);
    });

    it('should set timeMachineTimestamp to null', () => {
      const { setTimeMachineTimestamp } = useUiStore.getState();
      setTimeMachineTimestamp('2024-01-15T10:30:00Z');
      setTimeMachineTimestamp(null);
      expect(useUiStore.getState().timeMachineTimestamp).toBeNull();
    });
  });

  describe('setNodesView', () => {
    it('should merge partial preferences with existing nodesView', () => {
      const { setNodesView } = useUiStore.getState();
      setNodesView({ layout: 'grid' });
      const state = useUiStore.getState();
      expect(state.nodesView).toEqual({
        layout: 'grid',
        sortField: 'displayName',
        sortDirection: 'asc',
      });
    });

    it('should update multiple fields at once', () => {
      const { setNodesView } = useUiStore.getState();
      setNodesView({ sortField: 'status', sortDirection: 'desc' });
      const state = useUiStore.getState();
      expect(state.nodesView).toEqual({
        layout: 'list',
        sortField: 'status',
        sortDirection: 'desc',
      });
    });

    it('should allow setting compact layout', () => {
      const { setNodesView } = useUiStore.getState();
      setNodesView({ layout: 'compact' });
      expect(useUiStore.getState().nodesView.layout).toBe('compact');
    });
  });

  describe('setNetworksView', () => {
    it('should merge partial preferences with existing networksView', () => {
      const { setNetworksView } = useUiStore.getState();
      setNetworksView({ layout: 'grid' });
      const state = useUiStore.getState();
      expect(state.networksView.layout).toBe('grid');
      expect(state.networksView.sortField).toBe('displayName');
    });

    it('should update sort direction only', () => {
      const { setNetworksView } = useUiStore.getState();
      setNetworksView({ sortDirection: 'desc' });
      expect(useUiStore.getState().networksView.sortDirection).toBe('desc');
    });
  });

  describe('setServicesView', () => {
    it('should merge partial preferences with existing servicesView', () => {
      const { setServicesView } = useUiStore.getState();
      setServicesView({ sortField: 'name' });
      const state = useUiStore.getState();
      expect(state.servicesView.sortField).toBe('name');
      expect(state.servicesView.layout).toBe('list');
    });
  });

  describe('setGroupsView', () => {
    it('should merge partial preferences with existing groupsView', () => {
      const { setGroupsView } = useUiStore.getState();
      setGroupsView({ layout: 'grid', sortDirection: 'desc' });
      const state = useUiStore.getState();
      expect(state.groupsView).toEqual({
        layout: 'grid',
        sortField: 'displayName',
        sortDirection: 'desc',
      });
    });
  });

  describe('setProfilesView', () => {
    it('should merge partial preferences with existing profilesView', () => {
      const { setProfilesView } = useUiStore.getState();
      setProfilesView({ layout: 'grid' });
      const state = useUiStore.getState();
      expect(state.profilesView).toEqual({
        layout: 'grid',
        sortField: 'submittedAt',
        sortDirection: 'desc',
      });
    });

    it('should preserve default sort preferences for profiles', () => {
      const state = useUiStore.getState();
      expect(state.profilesView.sortField).toBe('submittedAt');
      expect(state.profilesView.sortDirection).toBe('desc');
    });
  });

  describe('Persistence', () => {
    it('should persist sidebar state to localStorage', () => {
      const { setSidebarCollapsed } = useUiStore.getState();
      setSidebarCollapsed(true);

      const stored = localStorage.getItem('hydra-ui-storage');
      expect(stored).toBeTruthy();

      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.sidebarCollapsed).toBe(true);
      }
    });

    it('should persist theme to localStorage', () => {
      const { setTheme } = useUiStore.getState();
      setTheme('dark');

      const stored = localStorage.getItem('hydra-ui-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.theme).toBe('dark');
      }
    });

    it('should persist view preferences to localStorage', () => {
      const { setNodesView } = useUiStore.getState();
      setNodesView({ layout: 'grid', sortField: 'status' });

      const stored = localStorage.getItem('hydra-ui-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.nodesView.layout).toBe('grid');
        expect(parsed.state.nodesView.sortField).toBe('status');
      }
    });

    it('should not persist sidebarMobileOpen to localStorage', () => {
      const { setSidebarMobileOpen } = useUiStore.getState();
      setSidebarMobileOpen(true);

      const stored = localStorage.getItem('hydra-ui-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.sidebarMobileOpen).toBeUndefined();
      }
    });

    it('should not persist timeMachineTimestamp to localStorage', () => {
      const { setTimeMachineTimestamp } = useUiStore.getState();
      setTimeMachineTimestamp('2024-01-15T10:30:00Z');

      const stored = localStorage.getItem('hydra-ui-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.timeMachineTimestamp).toBeUndefined();
      }
    });
  });

  describe('View preference independence', () => {
    it('should maintain independent preferences for each view type', () => {
      const { setNodesView, setServicesView, setProfilesView } = useUiStore.getState();

      setNodesView({ layout: 'grid', sortDirection: 'desc' });
      setServicesView({ layout: 'compact', sortField: 'runtime' });
      setProfilesView({ layout: 'list' });

      const state = useUiStore.getState();
      expect(state.nodesView.layout).toBe('grid');
      expect(state.servicesView.layout).toBe('compact');
      expect(state.profilesView.layout).toBe('list');
    });
  });
});
