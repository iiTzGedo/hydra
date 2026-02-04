import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type TimeRangePreset = 'last1h' | 'last24h' | 'last7d' | 'last30d' | 'custom';

export interface CustomTimeRange {
  from: Date;
  to: Date;
}

export interface WidgetConfig {
  id: string;
  type: 'stats' | 'capacity' | 'notifications' | 'activity' | 'topology-mini' | 'services';
  x: number;
  y: number;
  w: number;
  h: number;
  visible: boolean;
}

// Default widget layout for the dashboard grid
const defaultWidgetLayout: WidgetConfig[] = [
  { id: 'stats', type: 'stats', x: 0, y: 0, w: 12, h: 2, visible: true },
  { id: 'services', type: 'services', x: 0, y: 2, w: 6, h: 4, visible: true },
  { id: 'notifications', type: 'notifications', x: 6, y: 2, w: 6, h: 4, visible: true },
  { id: 'capacity', type: 'capacity', x: 0, y: 6, w: 12, h: 4, visible: true },
  { id: 'topology-mini', type: 'topology-mini', x: 0, y: 10, w: 12, h: 4, visible: true },
  { id: 'activity', type: 'activity', x: 0, y: 14, w: 12, h: 4, visible: true },
];

interface DashboardState {
  // Time range selection
  timeRange: TimeRangePreset;
  customTimeRange: CustomTimeRange | null;

  // Widget layout
  widgetLayout: WidgetConfig[];
  isEditMode: boolean;

  // Actions
  setTimeRange: (range: TimeRangePreset) => void;
  setCustomTimeRange: (range: CustomTimeRange) => void;
  updateWidgetLayout: (layout: WidgetConfig[]) => void;
  updateWidgetPosition: (id: string, x: number, y: number) => void;
  updateWidgetSize: (id: string, w: number, h: number) => void;
  toggleWidgetVisibility: (id: string) => void;
  resetLayout: () => void;
  setEditMode: (editing: boolean) => void;

  // Computed helpers
  getTimeRangeLabel: () => string;
  getEffectiveTimeRange: () => { from: Date; to: Date };
}

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set, get) => ({
      timeRange: 'last24h',
      customTimeRange: null,
      widgetLayout: [...defaultWidgetLayout],
      isEditMode: false,

      setTimeRange: (range) => set({ timeRange: range }),

      setCustomTimeRange: (range) =>
        set({ timeRange: 'custom', customTimeRange: range }),

      updateWidgetLayout: (layout) => set({ widgetLayout: layout }),

      updateWidgetPosition: (id, x, y) =>
        set((state) => ({
          widgetLayout: state.widgetLayout.map((w) =>
            w.id === id ? { ...w, x, y } : w
          ),
        })),

      updateWidgetSize: (id, w, h) =>
        set((state) => ({
          widgetLayout: state.widgetLayout.map((widget) =>
            widget.id === id ? { ...widget, w, h } : widget
          ),
        })),

      toggleWidgetVisibility: (id) =>
        set((state) => ({
          widgetLayout: state.widgetLayout.map((w) =>
            w.id === id ? { ...w, visible: !w.visible } : w
          ),
        })),

      resetLayout: () => set({ widgetLayout: [...defaultWidgetLayout] }),

      setEditMode: (editing) => set({ isEditMode: editing }),

      getTimeRangeLabel: () => {
        const { timeRange, customTimeRange } = get();
        switch (timeRange) {
          case 'last1h':
            return 'Last Hour';
          case 'last24h':
            return 'Last 24 Hours';
          case 'last7d':
            return 'Last 7 Days';
          case 'last30d':
            return 'Last 30 Days';
          case 'custom':
            if (customTimeRange) {
              const from = customTimeRange.from.toLocaleDateString();
              const to = customTimeRange.to.toLocaleDateString();
              return `${from} - ${to}`;
            }
            return 'Custom Range';
          default:
            return 'Last 24 Hours';
        }
      },

      getEffectiveTimeRange: () => {
        const { timeRange, customTimeRange } = get();
        const now = new Date();

        switch (timeRange) {
          case 'last1h':
            return { from: new Date(now.getTime() - 60 * 60 * 1000), to: now };
          case 'last24h':
            return { from: new Date(now.getTime() - 24 * 60 * 60 * 1000), to: now };
          case 'last7d':
            return { from: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000), to: now };
          case 'last30d':
            return { from: new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000), to: now };
          case 'custom':
            if (customTimeRange) {
              return customTimeRange;
            }
            // Fallback to last 24h if custom range not set
            return { from: new Date(now.getTime() - 24 * 60 * 60 * 1000), to: now };
          default:
            return { from: new Date(now.getTime() - 24 * 60 * 60 * 1000), to: now };
        }
      },
    }),
    {
      name: 'hydra-dashboard-storage',
      partialize: (state) => ({
        timeRange: state.timeRange,
        customTimeRange: state.customTimeRange,
        widgetLayout: state.widgetLayout,
      }),
      merge: (persisted, current) => {
        const persistedState = persisted as Partial<DashboardState>;
        
        // Start with current (has latest defaults for positions/sizing)
        const merged: DashboardState = { ...current };
        
        // Apply persisted preferences for existing widgets
        if (persistedState?.widgetLayout) {
          const persistedIds = new Set(persistedState.widgetLayout.map((w) => w.id));
          
          merged.widgetLayout = current.widgetLayout.map((defaultWidget) => {
            const persistedWidget = persistedState.widgetLayout?.find(
              (p) => p.id === defaultWidget.id
            );
            return persistedWidget
              ? { 
                  ...defaultWidget, // Use defaults for position/size
                  visible: persistedWidget.visible, // Use persisted visibility
                }
              : defaultWidget; // New widget uses defaults
          });
          
          // Add any new default widgets that aren't in persisted state
          const missing = defaultWidgetLayout.filter(
            (w) => !persistedIds.has(w.id)
          );
          if (missing.length > 0) {
            merged.widgetLayout = [...merged.widgetLayout, ...missing];
          }
        }
        
        // Apply other persisted state
        if (persistedState?.timeRange) merged.timeRange = persistedState.timeRange;
        if (persistedState?.customTimeRange) merged.customTimeRange = persistedState.customTimeRange;
        
        return merged;
      },
    }
  )
);
