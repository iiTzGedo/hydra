/**
 * Tests for topology-store.ts
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useTopologyStore } from '@/stores/topology-store';
import type { TopologyMode, ViewportState } from '@/stores/topology-store';

describe('topology-store', () => {
  beforeEach(() => {
    // Reset store to initial state
    useTopologyStore.setState({
      selectedNodeId: null,
      selectedGroupId: null,
      highlightedNodeIds: [],
      isSubgraphPanelOpen: false,
      viewports: {
        infrastructure: null,
        network: null,
        service: null,
      },
    });
  });

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const state = useTopologyStore.getState();
      expect(state.selectedNodeId).toBeNull();
      expect(state.selectedGroupId).toBeNull();
      expect(state.highlightedNodeIds).toEqual([]);
      expect(state.isSubgraphPanelOpen).toBe(false);
    });

    it('should have null viewports for all modes initially', () => {
      const state = useTopologyStore.getState();
      expect(state.viewports.infrastructure).toBeNull();
      expect(state.viewports.network).toBeNull();
      expect(state.viewports.service).toBeNull();
    });
  });

  describe('setSelectedNodeId', () => {
    it('should set selectedNodeId and open subgraph panel when nodeId is provided', () => {
      const { setSelectedNodeId } = useTopologyStore.getState();
      setSelectedNodeId('node-123');

      const state = useTopologyStore.getState();
      expect(state.selectedNodeId).toBe('node-123');
      expect(state.isSubgraphPanelOpen).toBe(true);
    });

    it('should clear selectedNodeId and close subgraph panel when null is provided', () => {
      const { setSelectedNodeId } = useTopologyStore.getState();
      setSelectedNodeId('node-123');
      setSelectedNodeId(null);

      const state = useTopologyStore.getState();
      expect(state.selectedNodeId).toBeNull();
      expect(state.isSubgraphPanelOpen).toBe(false);
    });

    it('should update selectedNodeId when changing from one node to another', () => {
      const { setSelectedNodeId } = useTopologyStore.getState();
      setSelectedNodeId('node-123');
      setSelectedNodeId('node-456');

      const state = useTopologyStore.getState();
      expect(state.selectedNodeId).toBe('node-456');
      expect(state.isSubgraphPanelOpen).toBe(true);
    });
  });

  describe('setSelectedGroupId', () => {
    it('should set selectedGroupId', () => {
      const { setSelectedGroupId } = useTopologyStore.getState();
      setSelectedGroupId('group-abc');

      const state = useTopologyStore.getState();
      expect(state.selectedGroupId).toBe('group-abc');
    });

    it('should clear selectedGroupId when null is provided', () => {
      const { setSelectedGroupId } = useTopologyStore.getState();
      setSelectedGroupId('group-abc');
      setSelectedGroupId(null);

      const state = useTopologyStore.getState();
      expect(state.selectedGroupId).toBeNull();
    });
  });

  describe('setHighlightedNodeIds', () => {
    it('should set highlightedNodeIds array', () => {
      const { setHighlightedNodeIds } = useTopologyStore.getState();
      const nodeIds = ['node-1', 'node-2', 'node-3'];
      setHighlightedNodeIds(nodeIds);

      const state = useTopologyStore.getState();
      expect(state.highlightedNodeIds).toEqual(nodeIds);
    });

    it('should clear highlightedNodeIds when empty array is provided', () => {
      const { setHighlightedNodeIds } = useTopologyStore.getState();
      setHighlightedNodeIds(['node-1', 'node-2']);
      setHighlightedNodeIds([]);

      const state = useTopologyStore.getState();
      expect(state.highlightedNodeIds).toEqual([]);
    });
  });

  describe('toggleSubgraphPanel', () => {
    it('should toggle isSubgraphPanelOpen from false to true', () => {
      const { toggleSubgraphPanel } = useTopologyStore.getState();
      toggleSubgraphPanel();

      const state = useTopologyStore.getState();
      expect(state.isSubgraphPanelOpen).toBe(true);
    });

    it('should toggle isSubgraphPanelOpen from true to false', () => {
      const { toggleSubgraphPanel } = useTopologyStore.getState();
      useTopologyStore.setState({ isSubgraphPanelOpen: true });
      toggleSubgraphPanel();

      const state = useTopologyStore.getState();
      expect(state.isSubgraphPanelOpen).toBe(false);
    });
  });

  describe('setSubgraphPanelOpen', () => {
    it('should set isSubgraphPanelOpen to true', () => {
      const { setSubgraphPanelOpen } = useTopologyStore.getState();
      setSubgraphPanelOpen(true);

      const state = useTopologyStore.getState();
      expect(state.isSubgraphPanelOpen).toBe(true);
    });

    it('should set isSubgraphPanelOpen to false', () => {
      const { setSubgraphPanelOpen } = useTopologyStore.getState();
      useTopologyStore.setState({ isSubgraphPanelOpen: true });
      setSubgraphPanelOpen(false);

      const state = useTopologyStore.getState();
      expect(state.isSubgraphPanelOpen).toBe(false);
    });
  });

  describe('clearSelection', () => {
    it('should reset all selection state', () => {
      const { setSelectedNodeId, setSelectedGroupId, setHighlightedNodeIds, clearSelection } =
        useTopologyStore.getState();

      setSelectedNodeId('node-123');
      setSelectedGroupId('group-abc');
      setHighlightedNodeIds(['node-1', 'node-2']);

      clearSelection();

      const state = useTopologyStore.getState();
      expect(state.selectedNodeId).toBeNull();
      expect(state.selectedGroupId).toBeNull();
      expect(state.highlightedNodeIds).toEqual([]);
      expect(state.isSubgraphPanelOpen).toBe(false);
    });

    it('should close subgraph panel when clearing selection', () => {
      const { setSelectedNodeId, clearSelection } = useTopologyStore.getState();
      setSelectedNodeId('node-123');

      expect(useTopologyStore.getState().isSubgraphPanelOpen).toBe(true);

      clearSelection();

      expect(useTopologyStore.getState().isSubgraphPanelOpen).toBe(false);
    });
  });

  describe('setViewport', () => {
    it('should set viewport for infrastructure mode', () => {
      const { setViewport } = useTopologyStore.getState();
      const viewport: ViewportState = { x: 100, y: 200, zoom: 1.5 };

      setViewport('infrastructure', viewport);

      const state = useTopologyStore.getState();
      expect(state.viewports.infrastructure).toEqual(viewport);
    });

    it('should set viewport for network mode', () => {
      const { setViewport } = useTopologyStore.getState();
      const viewport: ViewportState = { x: 50, y: 75, zoom: 2.0 };

      setViewport('network', viewport);

      const state = useTopologyStore.getState();
      expect(state.viewports.network).toEqual(viewport);
    });

    it('should set viewport for service mode', () => {
      const { setViewport } = useTopologyStore.getState();
      const viewport: ViewportState = { x: 0, y: 0, zoom: 1.0 };

      setViewport('service', viewport);

      const state = useTopologyStore.getState();
      expect(state.viewports.service).toEqual(viewport);
    });

    it('should maintain separate viewports for different modes', () => {
      const { setViewport } = useTopologyStore.getState();
      const infraViewport: ViewportState = { x: 100, y: 200, zoom: 1.5 };
      const networkViewport: ViewportState = { x: 50, y: 75, zoom: 2.0 };

      setViewport('infrastructure', infraViewport);
      setViewport('network', networkViewport);

      const state = useTopologyStore.getState();
      expect(state.viewports.infrastructure).toEqual(infraViewport);
      expect(state.viewports.network).toEqual(networkViewport);
      expect(state.viewports.service).toBeNull();
    });

    it('should update viewport when called multiple times for same mode', () => {
      const { setViewport } = useTopologyStore.getState();
      const viewport1: ViewportState = { x: 100, y: 200, zoom: 1.0 };
      const viewport2: ViewportState = { x: 150, y: 250, zoom: 1.5 };

      setViewport('infrastructure', viewport1);
      setViewport('infrastructure', viewport2);

      const state = useTopologyStore.getState();
      expect(state.viewports.infrastructure).toEqual(viewport2);
    });
  });

  describe('getViewport', () => {
    it('should return null for mode with no viewport set', () => {
      const { getViewport } = useTopologyStore.getState();
      const viewport = getViewport('infrastructure');
      expect(viewport).toBeNull();
    });

    it('should return viewport for infrastructure mode', () => {
      const { setViewport, getViewport } = useTopologyStore.getState();
      const viewport: ViewportState = { x: 100, y: 200, zoom: 1.5 };

      setViewport('infrastructure', viewport);
      const retrieved = getViewport('infrastructure');

      expect(retrieved).toEqual(viewport);
    });

    it('should return viewport for network mode', () => {
      const { setViewport, getViewport } = useTopologyStore.getState();
      const viewport: ViewportState = { x: 50, y: 75, zoom: 2.0 };

      setViewport('network', viewport);
      const retrieved = getViewport('network');

      expect(retrieved).toEqual(viewport);
    });

    it('should return viewport for service mode', () => {
      const { setViewport, getViewport } = useTopologyStore.getState();
      const viewport: ViewportState = { x: 0, y: 0, zoom: 1.0 };

      setViewport('service', viewport);
      const retrieved = getViewport('service');

      expect(retrieved).toEqual(viewport);
    });

    it('should return correct viewport for each mode independently', () => {
      const { setViewport, getViewport } = useTopologyStore.getState();
      const infraViewport: ViewportState = { x: 100, y: 200, zoom: 1.5 };
      const networkViewport: ViewportState = { x: 50, y: 75, zoom: 2.0 };

      setViewport('infrastructure', infraViewport);
      setViewport('network', networkViewport);

      expect(getViewport('infrastructure')).toEqual(infraViewport);
      expect(getViewport('network')).toEqual(networkViewport);
      expect(getViewport('service')).toBeNull();
    });
  });

  describe('Integration scenarios', () => {
    it('should handle node selection and highlight together', () => {
      const { setSelectedNodeId, setHighlightedNodeIds } = useTopologyStore.getState();

      setSelectedNodeId('node-123');
      setHighlightedNodeIds(['node-1', 'node-2', 'node-3']);

      const state = useTopologyStore.getState();
      expect(state.selectedNodeId).toBe('node-123');
      expect(state.highlightedNodeIds).toEqual(['node-1', 'node-2', 'node-3']);
      expect(state.isSubgraphPanelOpen).toBe(true);
    });

    it('should handle group selection and node highlights together', () => {
      const { setSelectedGroupId, setHighlightedNodeIds } = useTopologyStore.getState();

      setSelectedGroupId('group-abc');
      setHighlightedNodeIds(['node-1', 'node-2']);

      const state = useTopologyStore.getState();
      expect(state.selectedGroupId).toBe('group-abc');
      expect(state.highlightedNodeIds).toEqual(['node-1', 'node-2']);
    });

    it('should persist viewport state across selection changes', () => {
      const { setViewport, setSelectedNodeId } = useTopologyStore.getState();
      const viewport: ViewportState = { x: 100, y: 200, zoom: 1.5 };

      setViewport('infrastructure', viewport);
      setSelectedNodeId('node-123');

      const state = useTopologyStore.getState();
      expect(state.viewports.infrastructure).toEqual(viewport);
      expect(state.selectedNodeId).toBe('node-123');
    });
  });
});
