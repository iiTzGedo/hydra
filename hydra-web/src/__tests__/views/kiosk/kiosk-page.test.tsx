/**
 * Tests for KioskPage view.
 *
 * Verifies token authentication flow:
 *   - Missing token → "Missing kiosk token" Deauthorized screen
 *   - Invalid token → "Kiosk unavailable" Deauthorized screen
 *   - Valid token → board is rendered
 *   - Board with readonly widget → readonly flag is passed through
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from '../../msw/server';
import KioskPage from '@/views/kiosk/index';

// Must match BASE_URL in src/__tests__/msw/handlers.ts
const BASE_URL = 'http://127.0.0.1:8080/api/v1';

// ── Mocks ──────────────────────────────────────────────────────────

// react-grid-layout is browser-layout-dependent and unnecessary here
vi.mock('react-grid-layout', () => ({
  ResponsiveGridLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="rgl">{children}</div>
  ),
  useContainerWidth: () => ({ width: 1200, containerRef: { current: null }, mounted: true }),
}));

// useWidgetData always returns empty data in these tests
vi.mock('@/hooks/use-widget-data', () => ({
  useWidgetData: () => ({
    data: null,
    isLoading: false,
    error: null,
    isStale: false,
    isFetching: false,
  }),
}));

// Stub widget components to avoid rendering complexity
vi.mock('@/components/dashboard/widgets', () => ({
  getWidgetComponent:
    () =>
    ({ config, readonly }: { config: Record<string, unknown>; readonly?: boolean }) =>
      (
        <div data-testid="widget-content" data-readonly={readonly ? 'true' : 'false'}>
          {JSON.stringify(config)}
        </div>
      ),
}));

// useCreateCommand — not needed for read-only kiosk tests
vi.mock('@/api/commands', () => ({
  useCreateCommand: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

// ── Helpers ────────────────────────────────────────────────────────

// Access the shared mock navigation state from global setup
const mockNavState = (globalThis as Record<string, unknown>).__mockNavState as {
  params: Record<string, string>;
  searchParams: URLSearchParams;
};

function setRoute(boardId: string, token: string | null) {
  mockNavState.params = { boardId };
  mockNavState.searchParams = new URLSearchParams(token ? `token=${token}` : '');
}

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderKioskPage() {
  const qc = createTestQueryClient();
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <KioskPage />
      </QueryClientProvider>,
    ),
  };
}

// ── Tests ──────────────────────────────────────────────────────────

beforeEach(() => {
  mockNavState.params = {};
  mockNavState.searchParams = new URLSearchParams();
});

describe('KioskPage', () => {
  it('shows "Missing kiosk token" when no token is present', () => {
    setRoute('board-001', null);
    renderKioskPage();

    expect(screen.getByText('Kiosk unavailable')).toBeInTheDocument();
    expect(screen.getByText('Missing kiosk token')).toBeInTheDocument();
  });

  it('shows "Kiosk unavailable" when the token is invalid (API returns 401)', async () => {
    setRoute('board-001', 'invalid');
    renderKioskPage();

    // MSW handler returns 401 for token === 'invalid'
    await waitFor(() =>
      expect(screen.getByText('Kiosk unavailable')).toBeInTheDocument(),
    );
    expect(screen.getByText('This display has been deauthorized')).toBeInTheDocument();
  });

  it('renders the board when a valid token is provided', async () => {
    setRoute('board-001', 'valid-token-xyz');
    renderKioskPage();

    // Loading state first
    await waitFor(() =>
      expect(screen.queryByText('Kiosk unavailable')).not.toBeInTheDocument(),
    );
  });

  it('renders widgets when the board has widgets', async () => {
    const boardId = 'board-with-widgets';

    server.use(
      http.get(`${BASE_URL}/dashboards/kiosk/${boardId}`, ({ request }) => {
        const url = new URL(request.url);
        const token = url.searchParams.get('token');
        if (!token || token === 'invalid') {
          return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }
        return HttpResponse.json({
          success: true,
          data: {
            boardId,
            name: 'Widget Board',
            description: null,
            icon: null,
            ownerId: 'user-001',
            ownerType: 'user',
            boardType: 'kiosk',
            visibility: { scope: 'public', sharedWith: { roles: [], users: [] } },
            widgetCount: 1,
            tags: [],
            isHome: false,
            version: 1,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            layoutMode: 'grid',
            scope: 'standalone',
            entityTypeFilter: null,
            isSystemDefault: false,
            layout: {
              mode: 'grid',
              grid: {
                columns: 12,
                rowHeight: 80,
                breakpoints: {},
                compaction: 'vertical',
                margin: [16, 16],
                padding: [0, 0],
              },
            },
            widgets: [
              {
                instanceId: 'widget-001',
                widgetType: 'hydra::metric-card',
                position: { x: 0, y: 0, w: 4, h: 2 },
                config: { title: 'CPU Usage' },
                dataBinding: null,
                readonly: false,
              },
            ],
            settings: {
              theme: 'inherit',
              autoRefresh: true,
              refreshInterval: 30,
              showHeader: false,
              kioskMode: true,
              kioskAutoScroll: false,
              kioskScrollSpeed: 30,
              backgroundImage: null,
              customCss: null,
            },
            clonedFrom: null,
            archivedAt: null,
          },
        });
      }),
    );

    setRoute(boardId, 'valid-token-for-widgets');
    renderKioskPage();

    await waitFor(() => expect(screen.getByTestId('widget-content')).toBeInTheDocument());
  });

  it('passes readonly=true to widgets that have readonly set on the instance', async () => {
    const boardId = 'board-with-readonly-widget';

    server.use(
      http.get(`${BASE_URL}/dashboards/kiosk/${boardId}`, ({ request }) => {
        const url = new URL(request.url);
        const token = url.searchParams.get('token');
        if (!token || token === 'invalid') {
          return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }
        return HttpResponse.json({
          success: true,
          data: {
            boardId,
            name: 'Readonly Test Board',
            description: null,
            icon: null,
            ownerId: 'user-001',
            ownerType: 'user',
            boardType: 'kiosk',
            visibility: { scope: 'public', sharedWith: { roles: [], users: [] } },
            widgetCount: 1,
            tags: [],
            isHome: false,
            version: 1,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            layoutMode: 'grid',
            scope: 'standalone',
            entityTypeFilter: null,
            isSystemDefault: false,
            layout: {
              mode: 'grid',
              grid: {
                columns: 12,
                rowHeight: 80,
                breakpoints: {},
                compaction: 'vertical',
                margin: [16, 16],
                padding: [0, 0],
              },
            },
            widgets: [
              {
                instanceId: 'widget-ro',
                widgetType: 'hydra::quick-action',
                position: { x: 0, y: 0, w: 4, h: 2 },
                config: { title: 'Action' },
                dataBinding: null,
                readonly: true,
              },
            ],
            settings: {
              theme: 'inherit',
              autoRefresh: true,
              refreshInterval: 30,
              showHeader: false,
              kioskMode: true,
              kioskAutoScroll: false,
              kioskScrollSpeed: 30,
              backgroundImage: null,
              customCss: null,
            },
            clonedFrom: null,
            archivedAt: null,
          },
        });
      }),
    );

    setRoute(boardId, 'valid-readonly-token');
    renderKioskPage();

    await waitFor(() => {
      const widgetEl = screen.getByTestId('widget-content');
      expect(widgetEl.getAttribute('data-readonly')).toBe('true');
    });
  });

  it('shows deauthorized screen when token is revoked mid-session (re-fetch returns 401)', async () => {
    const boardId = 'board-revoke-test';
    const token = 'short-lived-token';
    let callCount = 0;

    server.use(
      http.get(`${BASE_URL}/dashboards/kiosk/${boardId}`, ({ request }) => {
        const url = new URL(request.url);
        const reqToken = url.searchParams.get('token');
        if (!reqToken || reqToken === 'invalid') {
          return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }
        callCount += 1;
        if (callCount === 1) {
          // First call — success
          return HttpResponse.json({
            success: true,
            data: {
              boardId,
              name: 'Revoke Board',
              description: null,
              icon: null,
              ownerId: 'user-001',
              ownerType: 'user',
              boardType: 'kiosk',
              visibility: { scope: 'public', sharedWith: { roles: [], users: [] } },
              widgetCount: 0,
              tags: [],
              isHome: false,
              version: 1,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              layoutMode: 'grid',
              scope: 'standalone',
              entityTypeFilter: null,
              isSystemDefault: false,
              layout: {
                mode: 'grid',
                grid: {
                  columns: 12,
                  rowHeight: 80,
                  breakpoints: {},
                  compaction: 'vertical',
                  margin: [16, 16],
                  padding: [0, 0],
                },
              },
              widgets: [],
              settings: {
                theme: 'inherit',
                autoRefresh: true,
                refreshInterval: 30,
                showHeader: false,
                kioskMode: true,
                kioskAutoScroll: false,
                kioskScrollSpeed: 30,
                backgroundImage: null,
                customCss: null,
              },
              clonedFrom: null,
              archivedAt: null,
            },
          });
        }
        // Subsequent calls — token revoked
        return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 });
      }),
    );

    setRoute(boardId, token);
    const { qc } = renderKioskPage();

    // Initially loads fine (no deauthorized screen)
    await waitFor(() =>
      expect(screen.queryByText('Missing kiosk token')).not.toBeInTheDocument(),
    );
    expect(screen.queryByText('Kiosk unavailable')).not.toBeInTheDocument();

    // Simulate a mid-session refetch where the server now returns 401 (token revoked)
    // The kiosk query key is ['kiosk', boardId, token] per src/lib/query-client.ts
    await qc.invalidateQueries({ queryKey: ['kiosk', boardId, token] });

    await waitFor(() =>
      expect(screen.getByText('Kiosk unavailable')).toBeInTheDocument(),
    );
  });
});
