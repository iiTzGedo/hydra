import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type TimeRangePreset = 'last1h' | 'last24h' | 'last7d' | 'last30d' | 'custom';

export interface CustomTimeRange {
  from: Date;
  to: Date;
}

interface DashboardState {
  // Time range selection
  timeRange: TimeRangePreset;
  customTimeRange: CustomTimeRange | null;

  // Active board
  activeBoardId: string | null;

  // Edit mode
  isEditMode: boolean;

  // Actions
  setTimeRange: (range: TimeRangePreset) => void;
  setCustomTimeRange: (range: CustomTimeRange) => void;
  setActiveBoardId: (id: string | null) => void;
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
      activeBoardId: null,
      isEditMode: false,

      setTimeRange: (range) => set({ timeRange: range }),

      setCustomTimeRange: (range) =>
        set({ timeRange: 'custom', customTimeRange: range }),

      setActiveBoardId: (id) => set({ activeBoardId: id }),

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
        activeBoardId: state.activeBoardId,
      }),
    }
  )
);
