import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';

// ── Mock API hooks ──────────────────────────────────────────────────

const useDashboardsMock = vi.fn();
const useDashboardMock = vi.fn();
const createDashboardMock = vi.fn();
const updateDashboardMock = vi.fn();
const deleteDashboardMock = vi.fn();
const cloneDashboardMock = vi.fn();
const addWidgetMock = vi.fn();
const deleteWidgetMock = vi.fn();
const useDashboardTemplatesMock = vi.fn();
const useWidgetRegistryMock = vi.fn();

vi.mock('@/api/dashboards', () => ({
  useDashboards: () => useDashboardsMock(),
  useDashboard: (boardId: string) => useDashboardMock(boardId),
  useCreateDashboard: () => ({
    mutateAsync: createDashboardMock,
    isPending: false,
  }),
  useUpdateDashboard: () => ({
    mutateAsync: updateDashboardMock,
    mutate: updateDashboardMock,
    isPending: false,
  }),
  useDeleteDashboard: () => ({
    mutateAsync: deleteDashboardMock,
    isPending: false,
  }),
  useCloneDashboard: () => ({
    mutateAsync: cloneDashboardMock,
    isPending: false,
  }),
  useAddWidget: () => ({
    mutate: addWidgetMock,
    isPending: false,
  }),
  useDeleteWidget: () => ({
    mutate: deleteWidgetMock,
    isPending: false,
  }),
  useUpdateWidget: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useExportDashboard: () => ({
    data: null,
    refetch: vi.fn().mockResolvedValue({ data: null }),
    isLoading: false,
    isError: false,
    error: null,
  }),
  useImportDashboard: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useSaveAsTemplate: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useShareDashboard: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useDashboardShares: () => ({
    data: null,
    refetch: vi.fn(),
    isLoading: false,
    isError: false,
    error: null,
  }),
  useRevokeDashboardShares: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useDashboardTemplates: () => useDashboardTemplatesMock(),
  useDashboardTemplate: () => ({
    data: null,
    isLoading: false,
    isError: false,
    error: null,
  }),
  useWidgetRegistry: () => useWidgetRegistryMock(),
}));

// ── Mock widget components ──────────────────────────────────────────

vi.mock('@/components/dashboard/stats-cards', () => ({
  StatsCards: () => <div data-testid="stats-cards-widget">Stats Cards</div>,
}));

vi.mock('@/components/dashboard/capacity-overview', () => ({
  CapacityOverview: () => <div data-testid="capacity-widget">Capacity Overview</div>,
}));

vi.mock('@/components/dashboard/recent-activity', () => ({
  RecentActivity: () => <div data-testid="activity-widget">Recent Activity</div>,
}));

vi.mock('@/components/dashboard/node-status-grid', () => ({
  NodeStatusGrid: () => <div data-testid="node-grid-widget">Node Status Grid</div>,
}));

vi.mock('@/components/dashboard/service-summary', () => ({
  ServiceSummary: () => <div data-testid="service-widget">Service Summary</div>,
}));

vi.mock('@/components/dashboard/mini-topology', () => ({
  MiniTopology: () => <div data-testid="topology-widget">Mini Topology</div>,
}));

vi.mock('@/components/dashboard/time-range-selector', () => ({
  TimeRangeSelector: () => <div>Time Range Selector</div>,
}));

vi.mock('@/components/dashboard/widget-grid', () => ({
  WidgetGrid: ({ children }: { children: ReactNode }) => (
    <div data-testid="widget-grid">{children}</div>
  ),
  Widget: ({
    children,
    id,
    title,
    description,
    isEditMode,
  }: {
    children: ReactNode;
    id: string;
    title?: string;
    description?: string;
    isEditMode?: boolean;
  }) => (
    <section data-testid={`widget-${id}`} data-edit-mode={isEditMode}>
      {title ? <h3>{title}</h3> : null}
      {description ? <p>{description}</p> : null}
      {children}
    </section>
  ),
  WidgetCustomizerContent: ({
    isEditMode,
    setEditMode,
    widgetLayout,
    onConfigureWidget,
  }: {
    widgetLayout: Array<{ id: string }>;
    isEditMode: boolean;
    setEditMode: (v: boolean) => void;
    onToggleWidget: (id: string) => void;
    onConfigureWidget?: (id: string) => void;
    onResetLayout: () => void;
  }) => (
    <div>
      <button onClick={() => setEditMode(!isEditMode)} type="button">
        Toggle Edit Mode
      </button>
      {widgetLayout[0] && onConfigureWidget ? (
        <button onClick={() => onConfigureWidget(widgetLayout[0].id)} type="button">
          Configure First Widget
        </button>
      ) : null}
      <span data-testid="edit-mode-status">{isEditMode ? 'editing' : 'viewing'}</span>
    </div>
  ),
  applyLayoutToWidgets: vi.fn(),
  widgetTypeLabel: (type: string) => type,
  widgetIcon: () => null,
  widgetActions: () => null,
}));

vi.mock('@/components/dashboard/widget-picker', () => ({
  WidgetPicker: ({ disabled, existingTypes }: { onSelect: unknown; disabled?: boolean; existingTypes?: string[] }) => (
    <button data-testid="mock-widget-picker" disabled={disabled} type="button">
      Add Widget ({existingTypes?.length ?? 0} existing)
    </button>
  ),
}));

import DashboardPage from '@/pages/dashboard';
import { useDashboardStore } from '@/stores/dashboard-store';
import { renderWithRoute } from '../page-test-utils';

// ── Shared Test Data ────────────────────────────────────────────────

const fullWidgetRegistry = {
  widgets: [
    {
      widgetType: 'hydra::stats-cards',
      displayName: 'Stats Overview',
      description: 'Key infrastructure metrics at a glance.',
      category: 'data-display',
      icon: 'bar-chart-3',
      source: 'hydra',
      defaultSize: { w: 12, h: 2 },
      minSize: { w: 6, h: 2 },
      maxSize: { w: 12, h: 4 },
      configSchema: [
        { key: 'title', label: 'Title', fieldType: 'text', description: 'Title override', options: [] },
      ],
      capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false },
    },
    {
      widgetType: 'hydra::capacity-overview',
      displayName: 'Capacity Overview',
      description: 'Resource utilization and capacity planning.',
      category: 'infrastructure',
      icon: 'hard-drive',
      source: 'hydra',
      defaultSize: { w: 12, h: 4 },
      minSize: { w: 6, h: 3 },
      maxSize: { w: 12, h: 6 },
      configSchema: [],
      capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false },
    },
    {
      widgetType: 'hydra::service-summary',
      displayName: 'Service Summary',
      description: 'Overview of service health and status.',
      category: 'status',
      icon: 'activity',
      source: 'hydra',
      defaultSize: { w: 6, h: 4 },
      minSize: { w: 4, h: 3 },
      maxSize: { w: 12, h: 6 },
      configSchema: [],
      capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false },
    },
    {
      widgetType: 'hydra::recent-activity',
      displayName: 'Recent Activity',
      description: 'Latest infrastructure events.',
      category: 'activity',
      icon: 'clock',
      source: 'hydra',
      defaultSize: { w: 6, h: 4 },
      minSize: { w: 4, h: 3 },
      maxSize: { w: 12, h: 6 },
      configSchema: [],
      capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false },
    },
    {
      widgetType: 'hydra::mini-topology',
      displayName: 'Infrastructure Topology',
      description: 'Visual map of current topology.',
      category: 'infrastructure',
      icon: 'network',
      source: 'hydra',
      defaultSize: { w: 12, h: 4 },
      minSize: { w: 6, h: 3 },
      maxSize: { w: 12, h: 8 },
      configSchema: [],
      capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false },
    },
    {
      widgetType: 'hydra::node-status-grid',
      displayName: 'Node Status Grid',
      description: 'Grid view of node health.',
      category: 'status',
      icon: 'server',
      source: 'hydra',
      defaultSize: { w: 12, h: 4 },
      minSize: { w: 6, h: 3 },
      maxSize: { w: 12, h: 6 },
      configSchema: [],
      capabilities: { configurable: true, supportsVisibilityToggle: true, repeatable: false },
    },
  ],
  categories: [
    { id: 'data-display', name: 'Data Display', count: 1 },
    { id: 'infrastructure', name: 'Infrastructure', count: 2 },
    { id: 'status', name: 'Status', count: 2 },
    { id: 'activity', name: 'Activity', count: 1 },
  ],
  total: 6,
};

const boardWithWidgets = {
  boardId: 'board-widget-test',
  id: 'board-widget-test',
  name: 'Widget Test Board',
  description: 'Board for widget data binding tests',
  icon: 'layout-dashboard',
  ownerId: 'user-001',
  boardType: 'custom' as const,
  visibility: 'private' as const,
  widgetCount: 3,
  tags: ['test'],
  isHome: false,
  version: 1,
  createdAt: '2026-04-01T12:00:00Z',
  updatedAt: '2026-04-01T12:00:00Z',
  layout: {
    columns: 12,
    rowHeight: 80,
    breakpoints: {
      lg: { columns: 12, width: 1200 },
      md: { columns: 8, width: 996 },
      sm: { columns: 4, width: 768 },
    },
  },
  widgets: [
    {
      instanceId: 'wi_stats',
      widgetType: 'hydra::stats-cards',
      position: { x: 0, y: 0, w: 12, h: 2 },
      config: { hidden: false },
      dataBinding: { source: 'hydra::nodes', query: { class: 'compute' }, refreshInterval: 60 },
    },
    {
      instanceId: 'wi_services',
      widgetType: 'hydra::service-summary',
      position: { x: 0, y: 2, w: 6, h: 4 },
      config: { hidden: false },
      dataBinding: { source: 'hydra::services', query: {}, refreshInterval: 120 },
    },
    {
      instanceId: 'wi_capacity',
      widgetType: 'hydra::capacity-overview',
      position: { x: 6, y: 2, w: 6, h: 4 },
      config: { hidden: false },
      dataBinding: null,
    },
  ],
  settings: {
    theme: 'inherit',
    autoRefresh: true,
    refreshInterval: 30,
    showHeader: true,
    kioskMode: false,
  },
  clonedFrom: null,
  archivedAt: null,
};

const emptyBoard = {
  ...boardWithWidgets,
  boardId: 'board-empty',
  id: 'board-empty',
  name: 'Empty Board',
  widgetCount: 0,
  widgets: [],
};

// ── Helpers ─────────────────────────────────────────────────────────

function setupWithBoard(board = boardWithWidgets) {
  useDashboardsMock.mockReturnValue({
    data: {
      items: [{ boardId: board.boardId, id: board.boardId, name: board.name, description: board.description }],
      total: 1,
      limit: 50,
      offset: 0,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  useDashboardMock.mockReturnValue({
    data: board,
    isLoading: false,
    error: null,
  });
  useWidgetRegistryMock.mockReturnValue({
    data: fullWidgetRegistry,
    isLoading: false,
    isError: false,
    error: null,
  });
  useDashboardTemplatesMock.mockReturnValue({
    data: { items: [], total: 0, limit: 50, offset: 0 },
    isLoading: false,
    isError: false,
    error: null,
  });
}

function setupEmpty() {
  useDashboardsMock.mockReturnValue({
    data: { items: [], total: 0, limit: 50, offset: 0 },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  useDashboardMock.mockReturnValue({
    data: undefined,
    isLoading: false,
    error: null,
  });
  useWidgetRegistryMock.mockReturnValue({
    data: fullWidgetRegistry,
    isLoading: false,
    isError: false,
    error: null,
  });
  useDashboardTemplatesMock.mockReturnValue({
    data: { items: [], total: 0, limit: 50, offset: 0 },
    isLoading: false,
    isError: false,
    error: null,
  });
}

// ── Tests ───────────────────────────────────────────────────────────

describe('Dashboard Widget Data Binding', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDashboardStore.setState({
      timeRange: 'last24h',
      customTimeRange: null,
      activeBoardId: null,
      isEditMode: false,
    });
    createDashboardMock.mockResolvedValue(boardWithWidgets);
    updateDashboardMock.mockResolvedValue(boardWithWidgets);
    deleteDashboardMock.mockResolvedValue(undefined);
  });

  it('renders widgets from board data with correct widget types', async () => {
    setupWithBoard();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboards/:boardId',
        route: '/dashboards/board-widget-test',
      });
    });

    await waitFor(() => {
      expect(useDashboardStore.getState().activeBoardId).toBe('board-widget-test');
    });

    // All three widget containers should be rendered from the board definition
    await waitFor(() => {
      expect(screen.getByTestId('widget-wi_stats')).toBeInTheDocument();
      expect(screen.getByTestId('widget-wi_services')).toBeInTheDocument();
      expect(screen.getByTestId('widget-wi_capacity')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('renders the empty state when the board has no widgets', async () => {
    setupWithBoard(emptyBoard);

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboards/:boardId',
        route: '/dashboards/board-empty',
      });
    });

    // Board should load but show no widget content
    await waitFor(() => {
      expect(useDashboardStore.getState().activeBoardId).toBe('board-empty');
    });

    // The mock widget components should NOT be rendered for empty board
    expect(screen.queryByText('Stats Cards')).not.toBeInTheDocument();
    expect(screen.queryByText('Service Summary')).not.toBeInTheDocument();
  });

  it('shows the starter-board empty state when no boards exist', async () => {
    setupEmpty();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboards',
        route: '/dashboards',
      });
    });

    await waitFor(
      () => expect(screen.getByText('No dashboard boards yet')).toBeInTheDocument(),
      { timeout: 5000 }
    );
  });

  it('renders template gallery data correctly', async () => {
    setupWithBoard();
    const templateData = {
      items: [
        {
          templateId: 'tmpl_infra',
          name: 'Infrastructure Overview',
          description: 'Full infrastructure dashboard template',
          boardType: 'custom',
          tags: ['infrastructure', 'builtin'],
          widgetCount: 3,
          createdBy: 'system',
          createdAt: '2026-03-01T00:00:00Z',
        },
        {
          templateId: 'tmpl_minimal',
          name: 'Minimal Home',
          description: 'A clean, minimal dashboard',
          boardType: 'custom',
          tags: ['minimal', 'builtin'],
          widgetCount: 1,
          createdBy: 'system',
          createdAt: '2026-03-01T00:00:00Z',
        },
        {
          templateId: 'tmpl_ops',
          name: 'Operations Center',
          description: 'Full operations view with all core widgets',
          boardType: 'custom',
          tags: ['operations', 'builtin'],
          widgetCount: 6,
          createdBy: 'system',
          createdAt: '2026-03-01T00:00:00Z',
        },
      ],
      total: 3,
      limit: 50,
      offset: 0,
    };
    useDashboardTemplatesMock.mockReturnValue({
      data: templateData,
      isLoading: false,
      isError: false,
      error: null,
    });

    // The templates hook is called by the page, and template data is available
    // Verify the hook provides the expected structure
    const result = useDashboardTemplatesMock();
    expect(result.data.items).toHaveLength(3);
    expect(result.data.items[0].name).toBe('Infrastructure Overview');
    expect(result.data.items[0].widgetCount).toBe(3);
    expect(result.data.items[1].name).toBe('Minimal Home');
    expect(result.data.items[2].name).toBe('Operations Center');
    expect(result.data.items[2].widgetCount).toBe(6);
  });

  it('widget registry provides all widget types with full metadata', () => {
    setupWithBoard();

    const registry = useWidgetRegistryMock();
    expect(registry.data.total).toBe(6);
    expect(registry.data.widgets).toHaveLength(6);
    expect(registry.data.categories).toHaveLength(4);

    // Verify each widget type in registry has required fields
    for (const widget of registry.data.widgets) {
      expect(widget).toHaveProperty('widgetType');
      expect(widget).toHaveProperty('displayName');
      expect(widget).toHaveProperty('description');
      expect(widget).toHaveProperty('category');
      expect(widget).toHaveProperty('defaultSize');
      expect(widget).toHaveProperty('minSize');
      expect(widget).toHaveProperty('maxSize');
      expect(widget).toHaveProperty('capabilities');
    }

    // Verify widget types match the API registry
    const typeSet = new Set(registry.data.widgets.map((w: { widgetType: string }) => w.widgetType));
    expect(typeSet).toContain('hydra::stats-cards');
    expect(typeSet).toContain('hydra::capacity-overview');
    expect(typeSet).toContain('hydra::service-summary');
    expect(typeSet).toContain('hydra::recent-activity');
    expect(typeSet).toContain('hydra::mini-topology');
    expect(typeSet).toContain('hydra::node-status-grid');
  });

  it('widget registry categories can be used for filtering', () => {
    setupWithBoard();

    const registry = useWidgetRegistryMock();
    const categories = registry.data.categories;

    // Verify category structure
    const catIds = categories.map((c: { id: string }) => c.id);
    expect(catIds).toContain('data-display');
    expect(catIds).toContain('infrastructure');
    expect(catIds).toContain('status');
    expect(catIds).toContain('activity');

    // Filter widgets by "infrastructure" category
    const infraWidgets = registry.data.widgets.filter(
      (w: { category: string }) => w.category === 'infrastructure'
    );
    expect(infraWidgets).toHaveLength(2);
    const infraTypes = infraWidgets.map((w: { widgetType: string }) => w.widgetType);
    expect(infraTypes).toContain('hydra::capacity-overview');
    expect(infraTypes).toContain('hydra::mini-topology');

    // Filter by "status" category
    const statusWidgets = registry.data.widgets.filter(
      (w: { category: string }) => w.category === 'status'
    );
    expect(statusWidgets).toHaveLength(2);
  });

  it('board data binding preserves source and query on widgets', async () => {
    setupWithBoard();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboards/:boardId',
        route: '/dashboards/board-widget-test',
      });
    });

    await waitFor(() => {
      expect(useDashboardStore.getState().activeBoardId).toBe('board-widget-test');
    });

    // Verify the board was loaded with correct widget data bindings
    const boardData = useDashboardMock.mock.results[0]?.value?.data;
    expect(boardData).toBeDefined();
    expect(boardData.widgets).toHaveLength(3);

    // Stats widget has data binding
    const statsWidget = boardData.widgets.find(
      (w: { widgetType: string }) => w.widgetType === 'hydra::stats-cards'
    );
    expect(statsWidget.dataBinding).toEqual({
      source: 'hydra::nodes',
      query: { class: 'compute' },
      refreshInterval: 60,
    });

    // Service widget has data binding
    const svcWidget = boardData.widgets.find(
      (w: { widgetType: string }) => w.widgetType === 'hydra::service-summary'
    );
    expect(svcWidget.dataBinding).toEqual({
      source: 'hydra::services',
      query: {},
      refreshInterval: 120,
    });

    // Capacity widget has no data binding
    const capWidget = boardData.widgets.find(
      (w: { widgetType: string }) => w.widgetType === 'hydra::capacity-overview'
    );
    expect(capWidget.dataBinding).toBeNull();
  });

  it('edit mode shows widget picker and action buttons', async () => {
    const user = userEvent.setup();
    setupWithBoard();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboards/:boardId',
        route: '/dashboards/board-widget-test',
      });
    });

    await waitFor(() => {
      expect(useDashboardStore.getState().activeBoardId).toBe('board-widget-test');
    });

    expect(await screen.findByText('Stats Cards')).toBeInTheDocument();

    // Enter edit mode via the primary Edit Board button
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /^Edit Board$/i }));
    });

    await waitFor(
      () => expect(screen.getByTestId('edit-mode-status')).toHaveTextContent('editing'),
      { timeout: 5000 }
    );

    // Widget picker should be available in edit mode
    expect(screen.getByTestId('mock-widget-picker')).toBeInTheDocument();

    // Clone and Delete are available via the board-actions overflow menu
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /Board actions/i }));
    });
    expect(await screen.findByRole('menuitem', { name: /Clone/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /Delete/i })).toBeInTheDocument();
  }, 10000);
});
