/**
 * Tests for dashboard-store.ts
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useDashboardStore } from '@/stores/dashboard-store';
import type { WidgetConfig } from '@/stores/dashboard-store';

describe('dashboard-store', () => {
  beforeEach(() => {
    // Reset store to initial state
    useDashboardStore.setState({
      timeRange: 'last24h',
      customTimeRange: null,
      widgetLayout: [
        { id: 'stats', type: 'stats', x: 0, y: 0, w: 12, h: 2, visible: true },
        { id: 'services', type: 'services', x: 0, y: 2, w: 6, h: 4, visible: true },
        { id: 'notifications', type: 'notifications', x: 6, y: 2, w: 6, h: 4, visible: true },
        { id: 'capacity', type: 'capacity', x: 0, y: 6, w: 12, h: 4, visible: true },
        { id: 'topology-mini', type: 'topology-mini', x: 0, y: 10, w: 12, h: 4, visible: true },
        { id: 'activity', type: 'activity', x: 0, y: 14, w: 12, h: 4, visible: true },
      ],
      isEditMode: false,
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const state = useDashboardStore.getState();
      expect(state.timeRange).toBe('last24h');
      expect(state.customTimeRange).toBeNull();
      expect(state.isEditMode).toBe(false);
    });

    it('should have 6 default widgets', () => {
      const state = useDashboardStore.getState();
      expect(state.widgetLayout).toHaveLength(6);
    });

    it('should have all widgets visible by default', () => {
      const state = useDashboardStore.getState();
      expect(state.widgetLayout.every((w) => w.visible)).toBe(true);
    });
  });

  describe('setTimeRange', () => {
    it('should set timeRange to last1h', () => {
      const { setTimeRange } = useDashboardStore.getState();
      setTimeRange('last1h');
      expect(useDashboardStore.getState().timeRange).toBe('last1h');
    });

    it('should set timeRange to last24h', () => {
      const { setTimeRange } = useDashboardStore.getState();
      setTimeRange('last24h');
      expect(useDashboardStore.getState().timeRange).toBe('last24h');
    });

    it('should set timeRange to last7d', () => {
      const { setTimeRange } = useDashboardStore.getState();
      setTimeRange('last7d');
      expect(useDashboardStore.getState().timeRange).toBe('last7d');
    });

    it('should set timeRange to last30d', () => {
      const { setTimeRange } = useDashboardStore.getState();
      setTimeRange('last30d');
      expect(useDashboardStore.getState().timeRange).toBe('last30d');
    });
  });

  describe('setCustomTimeRange', () => {
    it('should set customTimeRange and change timeRange to custom', () => {
      const { setCustomTimeRange } = useDashboardStore.getState();
      const customRange = {
        from: new Date('2024-01-01T00:00:00Z'),
        to: new Date('2024-01-31T23:59:59Z'),
      };

      setCustomTimeRange(customRange);

      const state = useDashboardStore.getState();
      expect(state.timeRange).toBe('custom');
      expect(state.customTimeRange).toEqual(customRange);
    });
  });

  describe('updateWidgetLayout', () => {
    it('should replace entire widget layout', () => {
      const { updateWidgetLayout } = useDashboardStore.getState();
      const newLayout: WidgetConfig[] = [
        { id: 'stats', type: 'stats', x: 0, y: 0, w: 6, h: 2, visible: true },
      ];

      updateWidgetLayout(newLayout);

      const state = useDashboardStore.getState();
      expect(state.widgetLayout).toEqual(newLayout);
      expect(state.widgetLayout).toHaveLength(1);
    });
  });

  describe('updateWidgetPosition', () => {
    it('should update widget position by id', () => {
      const { updateWidgetPosition } = useDashboardStore.getState();
      updateWidgetPosition('stats', 5, 10);

      const state = useDashboardStore.getState();
      const statsWidget = state.widgetLayout.find((w) => w.id === 'stats');
      expect(statsWidget?.x).toBe(5);
      expect(statsWidget?.y).toBe(10);
    });

    it('should not affect other widgets when updating position', () => {
      const { updateWidgetPosition } = useDashboardStore.getState();
      const initialLayout = useDashboardStore.getState().widgetLayout;
      updateWidgetPosition('stats', 5, 10);

      const state = useDashboardStore.getState();
      const servicesWidget = state.widgetLayout.find((w) => w.id === 'services');
      const initialServicesWidget = initialLayout.find((w) => w.id === 'services');
      expect(servicesWidget).toEqual(initialServicesWidget);
    });

    it('should handle non-existent widget id gracefully', () => {
      const { updateWidgetPosition } = useDashboardStore.getState();
      const initialLayout = useDashboardStore.getState().widgetLayout;
      updateWidgetPosition('non-existent-id', 5, 10);

      const state = useDashboardStore.getState();
      expect(state.widgetLayout).toEqual(initialLayout);
    });
  });

  describe('updateWidgetSize', () => {
    it('should update widget size by id', () => {
      const { updateWidgetSize } = useDashboardStore.getState();
      updateWidgetSize('capacity', 8, 6);

      const state = useDashboardStore.getState();
      const capacityWidget = state.widgetLayout.find((w) => w.id === 'capacity');
      expect(capacityWidget?.w).toBe(8);
      expect(capacityWidget?.h).toBe(6);
    });

    it('should not affect other properties when updating size', () => {
      const { updateWidgetSize } = useDashboardStore.getState();
      const initialLayout = useDashboardStore.getState().widgetLayout;
      const initialWidget = initialLayout.find((w) => w.id === 'capacity');

      updateWidgetSize('capacity', 8, 6);

      const state = useDashboardStore.getState();
      const updatedWidget = state.widgetLayout.find((w) => w.id === 'capacity');
      expect(updatedWidget?.x).toBe(initialWidget?.x);
      expect(updatedWidget?.y).toBe(initialWidget?.y);
      expect(updatedWidget?.visible).toBe(initialWidget?.visible);
    });
  });

  describe('toggleWidgetVisibility', () => {
    it('should toggle widget from visible to hidden', () => {
      const { toggleWidgetVisibility } = useDashboardStore.getState();
      toggleWidgetVisibility('stats');

      const state = useDashboardStore.getState();
      const statsWidget = state.widgetLayout.find((w) => w.id === 'stats');
      expect(statsWidget?.visible).toBe(false);
    });

    it('should toggle widget from hidden to visible', () => {
      const { toggleWidgetVisibility } = useDashboardStore.getState();
      toggleWidgetVisibility('stats');
      toggleWidgetVisibility('stats');

      const state = useDashboardStore.getState();
      const statsWidget = state.widgetLayout.find((w) => w.id === 'stats');
      expect(statsWidget?.visible).toBe(true);
    });
  });

  describe('resetLayout', () => {
    it('should reset widget layout to default', () => {
      const { updateWidgetPosition, resetLayout } = useDashboardStore.getState();

      updateWidgetPosition('stats', 5, 10);
      const modifiedState = useDashboardStore.getState();
      expect(modifiedState.widgetLayout.find((w) => w.id === 'stats')?.x).toBe(5);

      resetLayout();

      const state = useDashboardStore.getState();
      expect(state.widgetLayout).toHaveLength(6);
      expect(state.widgetLayout.find((w) => w.id === 'stats')?.x).toBe(0);
      expect(state.widgetLayout.find((w) => w.id === 'stats')?.y).toBe(0);
    });

    it('should reset all widgets to visible', () => {
      const { toggleWidgetVisibility, resetLayout } = useDashboardStore.getState();

      toggleWidgetVisibility('stats');
      toggleWidgetVisibility('services');

      resetLayout();

      const state = useDashboardStore.getState();
      expect(state.widgetLayout.every((w) => w.visible)).toBe(true);
    });
  });

  describe('setEditMode', () => {
    it('should set isEditMode to true', () => {
      const { setEditMode } = useDashboardStore.getState();
      setEditMode(true);
      expect(useDashboardStore.getState().isEditMode).toBe(true);
    });

    it('should set isEditMode to false', () => {
      const { setEditMode } = useDashboardStore.getState();
      setEditMode(true);
      setEditMode(false);
      expect(useDashboardStore.getState().isEditMode).toBe(false);
    });
  });

  describe('getTimeRangeLabel', () => {
    it('should return "Last Hour" for last1h', () => {
      const { setTimeRange, getTimeRangeLabel } = useDashboardStore.getState();
      setTimeRange('last1h');
      expect(getTimeRangeLabel()).toBe('Last Hour');
    });

    it('should return "Last 24 Hours" for last24h', () => {
      const { setTimeRange, getTimeRangeLabel } = useDashboardStore.getState();
      setTimeRange('last24h');
      expect(getTimeRangeLabel()).toBe('Last 24 Hours');
    });

    it('should return "Last 7 Days" for last7d', () => {
      const { setTimeRange, getTimeRangeLabel } = useDashboardStore.getState();
      setTimeRange('last7d');
      expect(getTimeRangeLabel()).toBe('Last 7 Days');
    });

    it('should return "Last 30 Days" for last30d', () => {
      const { setTimeRange, getTimeRangeLabel } = useDashboardStore.getState();
      setTimeRange('last30d');
      expect(getTimeRangeLabel()).toBe('Last 30 Days');
    });

    it('should return formatted date range for custom with customTimeRange set', () => {
      const { setCustomTimeRange, getTimeRangeLabel } = useDashboardStore.getState();
      const customRange = {
        from: new Date('2024-01-01T00:00:00Z'),
        to: new Date('2024-01-31T23:59:59Z'),
      };
      setCustomTimeRange(customRange);

      const label = getTimeRangeLabel();
      expect(label).toContain('-');
    });

    it('should return "Custom Range" for custom without customTimeRange set', () => {
      const { getTimeRangeLabel } = useDashboardStore.getState();
      useDashboardStore.setState({ timeRange: 'custom', customTimeRange: null });
      expect(getTimeRangeLabel()).toBe('Custom Range');
    });
  });

  describe('getEffectiveTimeRange', () => {
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-15T12:00:00Z'));
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should return correct range for last1h', () => {
      const { setTimeRange, getEffectiveTimeRange } = useDashboardStore.getState();
      setTimeRange('last1h');

      const range = getEffectiveTimeRange();
      const now = new Date('2024-01-15T12:00:00Z');
      const expectedFrom = new Date(now.getTime() - 60 * 60 * 1000);

      expect(range.to).toEqual(now);
      expect(range.from).toEqual(expectedFrom);
    });

    it('should return correct range for last24h', () => {
      const { setTimeRange, getEffectiveTimeRange } = useDashboardStore.getState();
      setTimeRange('last24h');

      const range = getEffectiveTimeRange();
      const now = new Date('2024-01-15T12:00:00Z');
      const expectedFrom = new Date(now.getTime() - 24 * 60 * 60 * 1000);

      expect(range.to).toEqual(now);
      expect(range.from).toEqual(expectedFrom);
    });

    it('should return correct range for last7d', () => {
      const { setTimeRange, getEffectiveTimeRange } = useDashboardStore.getState();
      setTimeRange('last7d');

      const range = getEffectiveTimeRange();
      const now = new Date('2024-01-15T12:00:00Z');
      const expectedFrom = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

      expect(range.to).toEqual(now);
      expect(range.from).toEqual(expectedFrom);
    });

    it('should return correct range for last30d', () => {
      const { setTimeRange, getEffectiveTimeRange } = useDashboardStore.getState();
      setTimeRange('last30d');

      const range = getEffectiveTimeRange();
      const now = new Date('2024-01-15T12:00:00Z');
      const expectedFrom = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

      expect(range.to).toEqual(now);
      expect(range.from).toEqual(expectedFrom);
    });

    it('should return custom range when set', () => {
      const { setCustomTimeRange, getEffectiveTimeRange } = useDashboardStore.getState();
      const customRange = {
        from: new Date('2024-01-01T00:00:00Z'),
        to: new Date('2024-01-31T23:59:59Z'),
      };
      setCustomTimeRange(customRange);

      const range = getEffectiveTimeRange();
      expect(range).toEqual(customRange);
    });

    it('should fallback to last24h when custom is set but customTimeRange is null', () => {
      useDashboardStore.setState({ timeRange: 'custom', customTimeRange: null });

      const range = useDashboardStore.getState().getEffectiveTimeRange();
      const now = new Date('2024-01-15T12:00:00Z');
      const expectedFrom = new Date(now.getTime() - 24 * 60 * 60 * 1000);

      expect(range.to).toEqual(now);
      expect(range.from).toEqual(expectedFrom);
    });
  });

  describe('Persistence', () => {
    it('should persist timeRange to localStorage', () => {
      const { setTimeRange } = useDashboardStore.getState();
      setTimeRange('last7d');

      const stored = localStorage.getItem('hydra-dashboard-storage');
      expect(stored).toBeTruthy();

      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.timeRange).toBe('last7d');
      }
    });

    it('should persist widgetLayout to localStorage', () => {
      const { updateWidgetPosition } = useDashboardStore.getState();
      updateWidgetPosition('stats', 3, 5);

      const stored = localStorage.getItem('hydra-dashboard-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        const statsWidget = parsed.state.widgetLayout.find((w: WidgetConfig) => w.id === 'stats');
        expect(statsWidget.x).toBe(3);
        expect(statsWidget.y).toBe(5);
      }
    });

    it('should not persist isEditMode to localStorage', () => {
      const { setEditMode } = useDashboardStore.getState();
      setEditMode(true);

      const stored = localStorage.getItem('hydra-dashboard-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.isEditMode).toBeUndefined();
      }
    });
  });
});
