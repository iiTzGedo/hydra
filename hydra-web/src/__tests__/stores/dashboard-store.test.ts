/**
 * Tests for dashboard-store.ts
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useDashboardStore } from '@/stores/dashboard-store';

describe('dashboard-store', () => {
  beforeEach(() => {
    // Reset store to initial state
    useDashboardStore.setState({
      timeRange: 'last24h',
      customTimeRange: null,
      activeBoardId: null,
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
      expect(state.activeBoardId).toBeNull();
      expect(state.isEditMode).toBe(false);
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

  describe('setActiveBoardId', () => {
    it('should set the active board id', () => {
      const { setActiveBoardId } = useDashboardStore.getState();
      setActiveBoardId('board-123');
      expect(useDashboardStore.getState().activeBoardId).toBe('board-123');
    });

    it('should allow clearing the active board id', () => {
      const { setActiveBoardId } = useDashboardStore.getState();
      setActiveBoardId('board-123');
      setActiveBoardId(null);
      expect(useDashboardStore.getState().activeBoardId).toBeNull();
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

    it('should persist activeBoardId to localStorage', () => {
      const { setActiveBoardId } = useDashboardStore.getState();
      setActiveBoardId('board-persist-test');

      const stored = localStorage.getItem('hydra-dashboard-storage');
      expect(stored).toBeTruthy();

      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.activeBoardId).toBe('board-persist-test');
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
