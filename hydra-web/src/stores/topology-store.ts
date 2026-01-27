import { create } from 'zustand';

export type TopologyMode = 'infrastructure' | 'network' | 'service';

export interface ViewportState {
  x: number;
  y: number;
  zoom: number;
}

interface TopologyState {
  // Selected node for subgraph panel
  selectedNodeId: string | null;

  // Selected group for highlighting
  selectedGroupId: string | null;

  // Node IDs to highlight (computed from selected group)
  highlightedNodeIds: string[];

  // Panel visibility
  isSubgraphPanelOpen: boolean;

  // Viewport states per mode
  viewports: Record<TopologyMode, ViewportState | null>;

  // Actions
  setSelectedNodeId: (nodeId: string | null) => void;
  setSelectedGroupId: (groupId: string | null) => void;
  setHighlightedNodeIds: (nodeIds: string[]) => void;
  toggleSubgraphPanel: () => void;
  setSubgraphPanelOpen: (open: boolean) => void;
  clearSelection: () => void;
  setViewport: (mode: TopologyMode, viewport: ViewportState) => void;
  getViewport: (mode: TopologyMode) => ViewportState | null;
}

export const useTopologyStore = create<TopologyState>()((set, get) => ({
  selectedNodeId: null,
  selectedGroupId: null,
  highlightedNodeIds: [],
  isSubgraphPanelOpen: false,
  viewports: {
    infrastructure: null,
    network: null,
    service: null,
  },

  setSelectedNodeId: (nodeId) =>
    set({
      selectedNodeId: nodeId,
      isSubgraphPanelOpen: nodeId !== null,
    }),

  setSelectedGroupId: (groupId) =>
    set({ selectedGroupId: groupId }),

  setHighlightedNodeIds: (nodeIds) =>
    set({ highlightedNodeIds: nodeIds }),

  toggleSubgraphPanel: () =>
    set((state) => ({ isSubgraphPanelOpen: !state.isSubgraphPanelOpen })),

  setSubgraphPanelOpen: (open) =>
    set({ isSubgraphPanelOpen: open }),

  clearSelection: () =>
    set({
      selectedNodeId: null,
      selectedGroupId: null,
      highlightedNodeIds: [],
      isSubgraphPanelOpen: false,
    }),

  setViewport: (mode, viewport) =>
    set((state) => ({
      viewports: {
        ...state.viewports,
        [mode]: viewport,
      },
    })),

  getViewport: (mode) => get().viewports[mode],
}));
