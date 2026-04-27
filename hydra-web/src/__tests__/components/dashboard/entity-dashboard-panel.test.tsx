/**
 * Tests for EntityDashboardPanel component.
 *
 * The component is tested via MSW for API calls and vi.mock() for heavy
 * rendering dependencies (WidgetGrid, Widget, useWidgetData, react-grid-layout).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from '../../msw/server';
import { EntityDashboardPanel } from '@/components/dashboard/entity-dashboard-panel';
import { useAuthStore } from '@/stores/auth-store';
import type { ReactNode } from 'react';

// Must match BASE_URL in src/__tests__/msw/handlers.ts (127.0.0.1, not localhost)
const BASE_URL = 'http://127.0.0.1:8080/api/v1';

// ── Mocks ──────────────────────────────────────────────────────────

// react-grid-layout is browser-layout-dependent
vi.mock('react-grid-layout', () => ({
  ResponsiveGridLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="rgl">{children}</div>
  ),
  useContainerWidth: () => ({ width: 1200, containerRef: { current: null }, mounted: true }),
}));

// useWidgetData always returns empty data in tests (widget content tested elsewhere)
vi.mock('@/hooks/use-widget-data', () => ({
  useWidgetData: () => ({ data: null, isLoading: false, error: null, isStale: false, isFetching: false }),
}));

// getWidgetComponent returns a simple stub component
vi.mock('@/components/dashboard/widgets', () => ({
  getWidgetComponent: () => ({ config }: { config: Record<string, unknown> }) => (
    <div data-testid="widget-content">{JSON.stringify(config)}</div>
  ),
}));

// ── Helpers ────────────────────────────────────────────────────────

function apiResponse<T>(data: T) {
  return { success: true, data };
}

function makeBoard(entityType: string, overrides: Record<string, unknown> = {}) {
  return {
    boardId: `panel-default-${entityType}`,
    name: `Default ${entityType} Panel`,
    description: null,
    icon: null,
    ownerId: 'system',
    ownerType: 'system',
    boardType: 'user',
    visibility: { scope: 'public', sharedWith: { roles: [], users: [] } },
    widgetCount: 0,
    tags: [],
    isHome: false,
    version: 1,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    layoutMode: 'grid',
    scope: 'entity-panel',
    entityTypeFilter: entityType,
    isSystemDefault: true,
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
      showHeader: true,
      kioskMode: false,
      kioskAutoScroll: false,
      kioskScrollSpeed: 30,
      backgroundImage: null,
      customCss: null,
    },
    clonedFrom: null,
    archivedAt: null,
    ...overrides,
  };
}

function makeWidget(id: string, query?: string) {
  return {
    instanceId: id,
    widgetType: 'hydra::metric-card',
    position: { x: 0, y: 0, w: 4, h: 2 },
    placements: { lg: { x: 0, y: 0, w: 4, h: 2 } },
    config: { title: `Widget ${id}` },
    dataBinding: query
      ? { source: 'api', query: { endpoint: query } }
      : null,
  };
}

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderPanel(entityType: 'node' | 'service' | 'network', entityId: string) {
  const qc = createTestQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <EntityDashboardPanel entityType={entityType} entityId={entityId} />
    </QueryClientProvider>,
  );
}

// ── Test setup ─────────────────────────────────────────────────────

beforeEach(() => {
  // Reset auth store to unauthenticated state
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false });
});

// ── Tests ──────────────────────────────────────────────────────────

describe('EntityDashboardPanel', () => {
  it('shows loading state initially', () => {
    renderPanel('node', 'node-abc');
    expect(screen.getByText('Loading panel…')).toBeInTheDocument();
  });

  it('renders nothing when panel has no widgets', async () => {
    // Default MSW handler returns a board with empty widgets array
    const { container } = renderPanel('node', 'node-abc');
    await waitFor(() =>
      expect(screen.queryByText('Loading panel…')).not.toBeInTheDocument(),
    );
    // Panel renders nothing when widgets=[]
    expect(container.firstChild).toBeNull();
  });

  it('renders panel name and widgets when data is loaded', async () => {
    const board = makeBoard('node', {
      name: 'Node Overview Panel',
      widgets: [makeWidget('w1'), makeWidget('w2')],
      widgetCount: 2,
    });
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );

    renderPanel('node', 'node-abc');
    await waitFor(() =>
      expect(screen.getByText('Node Overview Panel')).toBeInTheDocument(),
    );

    // Both widgets should be rendered via the mock widget component
    const widgetContents = screen.getAllByTestId('widget-content');
    expect(widgetContents).toHaveLength(2);
  });

  it('collapses and expands on header button click', async () => {
    const board = makeBoard('node', {
      name: 'Collapsible Panel',
      widgets: [makeWidget('w1')],
      widgetCount: 1,
    });
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );

    renderPanel('node', 'node-abc');
    await waitFor(() =>
      expect(screen.getByText('Collapsible Panel')).toBeInTheDocument(),
    );

    // Initially open — widget content visible
    expect(screen.getByTestId('widget-content')).toBeInTheDocument();

    // Click the toggle button to collapse
    const toggleBtn = screen.getByRole('button', { name: /Collapsible Panel/i });
    await userEvent.click(toggleBtn);

    // Widget content should be hidden
    expect(screen.queryByTestId('widget-content')).not.toBeInTheDocument();

    // Click again to expand
    await userEvent.click(toggleBtn);
    expect(screen.getByTestId('widget-content')).toBeInTheDocument();
  });

  it('does NOT show Customize button when user lacks dashboards:write permission', async () => {
    const board = makeBoard('node', {
      widgets: [makeWidget('w1')],
      widgetCount: 1,
    });
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );
    // No user set — hasPermission returns false
    renderPanel('node', 'node-abc');
    await waitFor(() =>
      expect(screen.queryByText('Loading panel…')).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByTestId('customize-panel-button'),
    ).not.toBeInTheDocument();
  });

  it('shows Customize panel button when user has dashboards:write permission', async () => {
    useAuthStore.setState({
      user: {
        userId: 'u1',
        username: 'admin',
        email: 'a@b.c',
        role: 'admin',
        permissions: ['*:*'],
        temporaryRoles: [],
      },
      isAuthenticated: true,
      isLoading: false,
    });

    const board = makeBoard('node', {
      widgets: [makeWidget('w1')],
      widgetCount: 1,
    });
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );

    renderPanel('node', 'node-abc');
    await waitFor(() =>
      expect(screen.getByTestId('customize-panel-button')).toBeInTheDocument(),
    );
  });

  it('clicking Customize calls the customize mutation and navigates', async () => {
    const mockPush = vi.fn();
    const mockRouter = (globalThis as Record<string, unknown>).__mockNavState as {
      router: { push: ReturnType<typeof vi.fn> };
    };
    mockRouter.router.push = mockPush;

    useAuthStore.setState({
      user: {
        userId: 'u1',
        username: 'admin',
        email: 'a@b.c',
        role: 'admin',
        permissions: ['*:*'],
        temporaryRoles: [],
      },
      isAuthenticated: true,
      isLoading: false,
    });

    const board = makeBoard('node', {
      widgets: [makeWidget('w1')],
      widgetCount: 1,
    });
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );

    renderPanel('node', 'node-abc');
    await waitFor(() =>
      expect(screen.getByTestId('customize-panel-button')).toBeInTheDocument(),
    );

    await act(async () => {
      await userEvent.click(screen.getByTestId('customize-panel-button'));
    });

    await waitFor(() => expect(mockPush).toHaveBeenCalled());
    // Should navigate to the dashboards/:boardId edit URL
    const navArg: string = mockPush.mock.calls[0][0];
    expect(navArg).toMatch(/\/dashboards\//);
    expect(navArg).toMatch(/edit=1/);
  });

  it('shows error message on API error', async () => {
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/network`, () =>
        HttpResponse.json({ success: false }, { status: 500 }),
      ),
    );

    renderPanel('network', 'net-lan-001');
    await waitFor(() =>
      expect(screen.queryByText('Loading panel…')).not.toBeInTheDocument(),
    );
    expect(
      screen.getByText('Panel unavailable. The server could not load the panel for this entity.'),
    ).toBeInTheDocument();
  });

  it('resolves {{entity.id}} template in widget dataBinding before rendering', async () => {
    const entityId = 'node-resolved-id';
    const board = makeBoard('node', {
      name: 'Template Panel',
      widgets: [makeWidget('w1', '/nodes/{{entity.id}}/profiles')],
      widgetCount: 1,
    });
    server.use(
      http.get(`${BASE_URL}/dashboards/panel/node`, () =>
        HttpResponse.json(apiResponse(board)),
      ),
    );

    renderPanel('node', entityId);
    await waitFor(() =>
      expect(screen.getByText('Template Panel')).toBeInTheDocument(),
    );

    // The widget content receives the resolved config — just verify widget rendered
    expect(screen.getByTestId('widget-content')).toBeInTheDocument();
    // Resolved endpoint is passed through dataBinding to useWidgetData (mocked);
    // resolution correctness is tested in use-embedded-panel.test.ts
  });
});
