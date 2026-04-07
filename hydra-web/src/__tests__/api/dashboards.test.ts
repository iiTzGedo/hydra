import { act, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  useCreateDashboard,
  useDashboard,
  useDashboards,
  useUpdateDashboard,
  useWidgetRegistry,
} from '@/api/dashboards';
import { renderWithQuery } from '../msw/test-utils';

describe('Dashboards API Hooks', () => {
  it('should fetch a paginated list of dashboards with id aliases', async () => {
    const { result } = renderWithQuery(() => useDashboards());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].id).toBe('board-001');
    expect(result.current.data?.items[0].boardId).toBe('board-001');
  });

  it('should fetch a single dashboard detail with widgets', async () => {
    const { result } = renderWithQuery(() => useDashboard('board-001'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.boardId).toBe('board-001');
    expect(result.current.data?.id).toBe('board-001');
    expect(result.current.data?.widgets).toHaveLength(6);
  });

  it('should create a dashboard board', async () => {
    const { result } = renderWithQuery(() => useCreateDashboard());

    await act(async () => {
      await result.current.mutateAsync({
        name: 'Created From Test',
        visibility: 'private',
        widgets: [],
      });
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data?.name).toBe('Created From Test');
    expect(result.current.data?.boardId).toBeTruthy();
  });

  it('should update a dashboard board widget state', async () => {
    const { result } = renderWithQuery(() => useUpdateDashboard('board-001'));

    await act(async () => {
      await result.current.mutateAsync({
        widgets: [
          {
            instanceId: 'wi_stats',
            widgetType: 'hydra::stats-cards',
            position: { x: 0, y: 0, w: 12, h: 2 },
            config: { hidden: true },
            dataBinding: null,
          },
        ],
      });
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data?.widgets[0].config).toEqual({ hidden: true });
    expect(result.current.data?.version).toBeGreaterThan(1);
  });

  it('should fetch widget registry capabilities and config schema', async () => {
    const { result } = renderWithQuery(() => useWidgetRegistry());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.total).toBe(6);
    expect(result.current.data?.widgets[0].capabilities.configurable).toBe(true);
    expect(result.current.data?.widgets[0].configSchema[0].key).toBe('title');
  });
});
