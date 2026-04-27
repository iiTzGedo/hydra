/**
 * Tests for useEmbeddedPanel hook.
 *
 * Uses the MSW server (set up in __tests__/setup.ts) and overrides the
 * entity-panel GET handler per test where needed.
 */

import { describe, it, expect } from 'vitest';
import { waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { renderWithQuery } from '../msw/test-utils';
import { useEmbeddedPanel } from '@/hooks/use-embedded-panel';

// Must match BASE_URL in src/__tests__/msw/handlers.ts (127.0.0.1, not localhost)
const BASE_URL = 'http://127.0.0.1:8080/api/v1';

function apiResponse<T>(data: T) {
  return { success: true, data };
}

function makeDefaultBoard(entityType: string) {
  return {
    boardId: `panel-default-${entityType}`,
    name: `Default ${entityType} Panel`,
    description: null,
    icon: null,
    ownerId: 'system',
    ownerType: 'system' as const,
    boardType: 'user' as const,
    visibility: { scope: 'public' as const, sharedWith: { roles: [], users: [] } },
    widgetCount: 0,
    tags: [],
    isHome: false,
    version: 1,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    layoutMode: 'grid' as const,
    scope: 'entity-panel' as const,
    entityTypeFilter: entityType,
    isSystemDefault: true,
    layout: {
      mode: 'grid' as const,
      grid: {
        columns: 12,
        rowHeight: 80,
        breakpoints: {},
        compaction: 'vertical' as const,
        margin: [16, 16] as [number, number],
        padding: [0, 0] as [number, number],
      },
    },
    widgets: [] as unknown[],
    settings: {
      theme: 'inherit',
      autoRefresh: true,
      refreshInterval: 30,
      showHeader: true,
      kioskMode: false,
      kioskAutoScroll: false,
      kioskScrollSpeed: 30,
      backgroundImage: null,
      customCss: null,
    },
    clonedFrom: null,
    archivedAt: null,
  };
}

describe('useEmbeddedPanel', () => {
  it('returns null while loading', () => {
    const { result } = renderWithQuery(() => useEmbeddedPanel('node', 'node-abc'));
    // Before the fetch resolves, data should be null and loading should be true
    expect(result.current.data).toBeNull();
    expect(result.current.isLoading).toBe(true);
  });

  it('returns the board with id alias after loading (no templates)', async () => {
    const { result } = renderWithQuery(() => useEmbeddedPanel('node', 'node-abc'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data).not.toBeNull();
    expect(result.current.data?.boardId).toBe('panel-default-node');
    // withBoardId adds id alias
    expect(result.current.data?.id).toBe('panel-default-node');
    expect(result.current.isError).toBe(false);
  });

  it('resolves {{entity.id}} in widget dataBinding.query.endpoint', async () => {
    const entityId = 'entity-abc';
    const board = {
      ...makeDefaultBoard('node'),
      widgets: [
        {
          instanceId: 'w1',
          widgetType: 'hydra::metric-card',
          position: { x: 0, y: 0, w: 4, h: 2 },
          config: { title: 'My Widget' },
          dataBinding: {
            source: 'api',
            query: {
              endpoint: '/nodes/{{entity.id}}/profiles/latest',
            },
          },
        },
      ],
    };

    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );

    const { result } = renderWithQuery(() => useEmbeddedPanel('node', entityId));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const widget = result.current.data?.widgets[0];
    expect(widget?.dataBinding?.query?.endpoint).toBe(`/nodes/${entityId}/profiles/latest`);
  });

  it('resolves {{entity.type}} in widget config fields', async () => {
    const entityId = 'svc-nginx-a1b2';
    const board = {
      ...makeDefaultBoard('service'),
      widgets: [
        {
          instanceId: 'w1',
          widgetType: 'hydra::metric-card',
          config: { title: 'Type: {{entity.type}}', subtitle: '{{entity.id}}' },
          dataBinding: null,
        },
      ],
    };

    server.use(
      http.get(`${BASE_URL}/dashboards/panel/service`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );

    const { result } = renderWithQuery(() => useEmbeddedPanel('service', entityId));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const widget = result.current.data?.widgets[0];
    expect(widget?.config?.title).toBe('Type: service');
    expect(widget?.config?.subtitle).toBe(entityId);
  });

  it('resolves templates in deeply nested widget config', async () => {
    const entityId = 'net-lan-001';
    const board = {
      ...makeDefaultBoard('network'),
      widgets: [
        {
          instanceId: 'w1',
          widgetType: 'hydra::entity-table',
          config: {
            nested: {
              deep: {
                query: '/networks/{{entity.id}}/nodes',
              },
            },
            items: ['{{entity.id}}', '{{entity.type}}'],
          },
          dataBinding: null,
        },
      ],
    };

    server.use(
      http.get(`${BASE_URL}/dashboards/panel/network`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );

    const { result } = renderWithQuery(() => useEmbeddedPanel('network', entityId));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const widget = result.current.data?.widgets[0];
    expect((widget?.config?.nested as { deep: { query: string } })?.deep?.query).toBe(
      `/networks/${entityId}/nodes`,
    );
    expect(widget?.config?.items).toEqual([entityId, 'network']);
  });

  it('returns isError=true when the API fails', async () => {
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json({ success: false, detail: 'Not found' }, { status: 404 }),
      ),
    );

    const { result } = renderWithQuery(() => useEmbeddedPanel('node', 'node-xyz'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.isError).toBe(true);
    expect(result.current.data).toBeNull();
  });

  it('re-resolves when entityId changes', async () => {
    const entityId = 'node-first';

    const board = (_id: string) => ({
      ...makeDefaultBoard('node'),
      boardId: 'panel-default-node',
      widgets: [
        {
          instanceId: 'w1',
          widgetType: 'hydra::metric-card',
          config: {},
          dataBinding: {
            source: 'api',
            query: { endpoint: '/nodes/{{entity.id}}' },
          },
        },
      ],
    });
    // The MSW handler is static but we change entityId to verify client-side re-resolution
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json(apiResponse(board(entityId))),
      ),
    );

    const { result, rerender } = renderWithQuery(
      ({ id }: { id: string }) => useEmbeddedPanel('node', id),
      { initialProps: { id: 'node-first' } },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data?.widgets[0]?.dataBinding?.query?.endpoint).toBe(
      '/nodes/node-first',
    );

    // Re-render with a different entityId — template resolution should update
    rerender({ id: 'node-second' });

    await waitFor(() => {
      expect(result.current.data?.widgets[0]?.dataBinding?.query?.endpoint).toBe(
        '/nodes/node-second',
      );
    });
  });
});
