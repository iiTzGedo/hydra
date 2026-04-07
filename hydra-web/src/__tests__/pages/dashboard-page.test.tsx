import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';

const useDashboardsMock = vi.fn();
const useDashboardMock = vi.fn();
const createDashboardMock = vi.fn();
const updateDashboardMock = vi.fn();
const deleteDashboardMock = vi.fn();
const cloneDashboardMock = vi.fn();
const addWidgetMock = vi.fn();
const deleteWidgetMock = vi.fn();

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
  useWidgetRegistry: () => ({
    data: {
      widgets: [
        {
          widgetType: 'hydra::stats-cards',
          displayName: 'Stats Overview',
          description: 'Key metrics',
          category: 'data-display',
          icon: 'bar-chart-3',
          source: 'hydra',
          defaultSize: { w: 12, h: 2 },
          minSize: { w: 6, h: 2 },
          maxSize: { w: 12, h: 4 },
          configSchema: [
            {
              key: 'title',
              label: 'Title',
              fieldType: 'text',
              description: 'Optional display title override for the widget header.',
              placeholder: 'Leave blank to use the default title',
              options: [],
            },
            {
              key: 'subtitle',
              label: 'Subtitle',
              fieldType: 'text',
              description: 'Short supporting text shown under the title.',
              placeholder: 'Optional supporting context',
              options: [],
            },
            {
              key: 'collapsible',
              label: 'Collapsible',
              fieldType: 'boolean',
              description: 'Allow the widget body to be collapsed from the header.',
              options: [],
            },
            {
              key: 'defaultCollapsed',
              label: 'Start collapsed',
              fieldType: 'boolean',
              description: 'Collapse the widget body when the board first loads.',
              options: [],
            },
          ],
          capabilities: {
            configurable: true,
            supportsVisibilityToggle: true,
            repeatable: false,
          },
        },
      ],
      categories: [{ id: 'data-display', name: 'Data Display', count: 1 }],
      total: 1,
    },
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

vi.mock('@/components/dashboard/stats-cards', () => ({
  StatsCards: () => <div>Stats Cards</div>,
}));

vi.mock('@/components/dashboard/capacity-overview', () => ({
  CapacityOverview: () => <div>Capacity Overview</div>,
}));

vi.mock('@/components/dashboard/recent-activity', () => ({
  RecentActivity: () => <div>Recent Activity</div>,
}));

vi.mock('@/components/dashboard/node-status-grid', () => ({
  NodeStatusGrid: () => <div>Node Status Grid</div>,
}));

vi.mock('@/components/dashboard/service-summary', () => ({
  ServiceSummary: () => <div>Service Summary</div>,
}));

vi.mock('@/components/dashboard/mini-topology', () => ({
  MiniTopology: () => <div>Mini Topology</div>,
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

const starterBoard = {
  boardId: 'board-001',
  id: 'board-001',
  name: 'Operations Overview',
  description: 'Primary infrastructure dashboard',
  icon: 'layout-dashboard',
  ownerId: 'user-001',
  boardType: 'home',
  visibility: 'private',
  widgetCount: 6,
  tags: ['starter'],
  isHome: true,
  version: 1,
  createdAt: '2026-03-09T12:00:00Z',
  updatedAt: '2026-03-09T12:00:00Z',
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
      dataBinding: null,
    },
    {
      instanceId: 'wi_services',
      widgetType: 'hydra::service-summary',
      position: { x: 0, y: 2, w: 6, h: 4 },
      config: { hidden: false },
      dataBinding: null,
    },
    {
      instanceId: 'wi_notifications',
      widgetType: 'hydra::recent-activity',
      position: { x: 6, y: 2, w: 6, h: 4 },
      config: { hidden: false },
      dataBinding: null,
    },
    {
      instanceId: 'wi_capacity',
      widgetType: 'hydra::capacity-overview',
      position: { x: 0, y: 6, w: 12, h: 4 },
      config: { hidden: false },
      dataBinding: null,
    },
    {
      instanceId: 'wi_topology',
      widgetType: 'hydra::mini-topology',
      position: { x: 0, y: 10, w: 12, h: 4 },
      config: { hidden: false },
      dataBinding: null,
    },
    {
      instanceId: 'wi_activity',
      widgetType: 'hydra::node-status-grid',
      position: { x: 0, y: 14, w: 12, h: 4 },
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

const secondBoard = {
  boardId: 'board-002',
  id: 'board-002',
  name: 'Secondary Board',
  description: 'Another board',
  icon: null,
  ownerId: 'user-001',
  boardType: 'custom',
  visibility: 'private',
  widgetCount: 1,
  tags: [],
  isHome: false,
  version: 1,
  createdAt: '2026-03-10T12:00:00Z',
  updatedAt: '2026-03-10T12:00:00Z',
};

function setupWithBoards(boards: Array<{ boardId: string; name: string; description?: string | null }> = [starterBoard], selectedBoard = starterBoard) {
  useDashboardsMock.mockReturnValue({
    data: {
      items: boards.map((b) => ({
        boardId: b.boardId,
        id: b.boardId,
        name: b.name,
        description: b.description,
      })),
      total: boards.length,
      limit: 50,
      offset: 0,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  useDashboardMock.mockReturnValue({
    data: selectedBoard,
    isLoading: false,
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
}

describe('Dashboard Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDashboardStore.setState({
      timeRange: 'last24h',
      customTimeRange: null,
      activeBoardId: null,
      isEditMode: false,
    });
    createDashboardMock.mockResolvedValue(starterBoard);
    updateDashboardMock.mockResolvedValue(starterBoard);
    deleteDashboardMock.mockResolvedValue(undefined);
    cloneDashboardMock.mockResolvedValue({ ...starterBoard, boardId: 'board-clone', name: 'Operations Overview (Copy)' });
  });

  it('shows the starter-board empty state and creates a board on demand', async () => {
    const user = userEvent.setup();
    setupEmpty();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboard',
        route: '/dashboard',
      });
    });

    expect(await screen.findByText('No dashboard boards yet')).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Create Starter Board' }));
    });

    await waitFor(() => expect(createDashboardMock).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(useDashboardStore.getState().activeBoardId).toBe('board-001')
    );
    expect(createDashboardMock.mock.calls[0][0]).toMatchObject({
      name: 'My Dashboard',
      boardType: 'home',
      visibility: 'private',
    });
  });

  it('renders the board switcher with all boards listed', async () => {
    setupWithBoards([starterBoard, secondBoard]);

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboard',
        route: '/dashboard',
      });
    });

    // The select trigger should show the active board name
    expect(await screen.findByText('Operations Overview')).toBeInTheDocument();
  });

  it('renders all visible widgets from the board', async () => {
    setupWithBoards();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboard',
        route: '/dashboard',
      });
    });

    // Should render all 6 widgets (none hidden)
    expect(await screen.findByTestId('widget-grid')).toBeInTheDocument();
    expect(await screen.findByText('Stats Cards')).toBeInTheDocument();
    expect(await screen.findByText('Service Summary')).toBeInTheDocument();
  });

  it('shows edit mode controls when edit mode is enabled', async () => {
    const user = userEvent.setup();
    setupWithBoards();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboard',
        route: '/dashboard',
      });
    });

    await waitFor(() =>
      expect(useDashboardStore.getState().activeBoardId).toBe('board-001')
    );

    // Toggle edit mode
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Toggle Edit Mode' }));
    });

    await waitFor(() => {
      expect(screen.getByTestId('edit-mode-status')).toHaveTextContent('editing');
    });

    // Edit mode shows Add Widget, Clone, Delete buttons
    expect(screen.getByRole('button', { name: /Add Widget/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Clone/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Delete/i })).toBeInTheDocument();
  });

  it('passes isEditMode to widget components', async () => {
    const user = userEvent.setup();
    setupWithBoards();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboard',
        route: '/dashboard',
      });
    });

    await waitFor(() =>
      expect(useDashboardStore.getState().activeBoardId).toBe('board-001')
    );

    // Enter edit mode
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Toggle Edit Mode' }));
    });

    await waitFor(() => {
      const widgets = screen.getAllByTestId(/^widget-/);
      // Filter out widget-grid itself
      const widgetElements = widgets.filter((el) => el.tagName === 'SECTION');
      for (const widget of widgetElements) {
        expect(widget).toHaveAttribute('data-edit-mode', 'true');
      }
    });
  });

  it('persists activeBoardId in store when board is selected', async () => {
    setupWithBoards();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboard',
        route: '/dashboard',
      });
    });

    // The store should have been updated with the first board's ID
    await waitFor(() =>
      expect(useDashboardStore.getState().activeBoardId).toBe('board-001')
    );
  });

  it('persists widget settings through dashboard updates', async () => {
    const user = userEvent.setup();
    setupWithBoards();

    await act(async () => {
      renderWithRoute(<DashboardPage />, {
        path: '/dashboard',
        route: '/dashboard',
      });
    });

    await waitFor(() =>
      expect(useDashboardStore.getState().activeBoardId).toBe('board-001')
    );

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Configure First Widget' }));
    });
    const dialog = await screen.findByRole('dialog');
    const titleInput = within(dialog).getByLabelText('Title');
    await act(async () => {
      fireEvent.change(titleInput, {
        target: { value: 'Executive Summary' },
      });
    });
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Save Settings' }));
    });

    await waitFor(() => expect(updateDashboardMock).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByLabelText('Title')).not.toBeInTheDocument()
    );

    const latestUpdate = updateDashboardMock.mock.calls.at(-1)?.[0];
    expect(latestUpdate).toMatchObject({
      widgets: expect.arrayContaining([
        expect.objectContaining({
          instanceId: 'wi_stats',
          config: expect.objectContaining({
            hidden: false,
            title: 'Executive Summary',
          }),
        }),
      ]),
    });
  });
});
