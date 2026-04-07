import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Layout } from 'react-grid-layout';
import {
  ArrowRight,
  Bell,
  Boxes,
  Copy,
  History,
  LayoutGrid,
  Maximize2,
  MessageSquare,
  Network,
  PanelsTopLeft,
  Plus,
  Trash2,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  useAddWidget,
  useCloneDashboard,
  useCreateDashboard,
  useDashboard,
  useDashboards,
  useDeleteDashboard,
  useDeleteWidget,
  useUpdateDashboard,
  useWidgetRegistry,
} from '@/api/dashboards';
import { TimeRangeSelector } from '@/components/dashboard/time-range-selector';
import { getWidgetComponent } from '@/components/dashboard/widgets';
import {
  Widget,
  WidgetCustomizerContent,
  WidgetGrid,
  applyLayoutToWidgets,
  widgetTypeLabel,
} from '@/components/dashboard/widget-grid';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { WidgetPicker } from '@/components/dashboard/widget-picker';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { getErrorMessage } from '@/lib/api-client';
import { ROUTES } from '@/lib/constants';
import { useDashboardStore } from '@/stores/dashboard-store';
import type {
  CreateDashboardRequest,
  DashboardBoardLayout,
  DashboardBoardSettings,
  DashboardCreateWidgetRequest,
  DashboardWidgetInstance,
  WidgetConfigField,
  WidgetSize,
  WidgetTypeDefinition,
} from '@/types/dashboard';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

const DEFAULT_BOARD_LAYOUT: DashboardBoardLayout = {
  columns: 12,
  rowHeight: 80,
  breakpoints: {
    lg: { columns: 12, width: 1200 },
    md: { columns: 8, width: 996 },
    sm: { columns: 4, width: 768 },
  },
};

const DEFAULT_BOARD_SETTINGS: DashboardBoardSettings = {
  theme: 'inherit',
  autoRefresh: true,
  refreshInterval: 30,
  showHeader: true,
  kioskMode: false,
};

function buildStarterBoardRequest(
  name: string,
  isHome: boolean
): CreateDashboardRequest {
  return {
    name,
    description: 'Overview of your infrastructure',
    boardType: isHome ? 'home' : 'custom',
    visibility: 'private',
    layout: DEFAULT_BOARD_LAYOUT,
    settings: DEFAULT_BOARD_SETTINGS,
    tags: ['starter'],
    isHome,
    widgets: [
      { widgetType: 'hydra::stats-cards', position: { x: 0, y: 0, w: 12, h: 2 }, config: {}, dataBinding: null },
      { widgetType: 'hydra::service-summary', position: { x: 0, y: 2, w: 6, h: 4 }, config: {}, dataBinding: null },
      { widgetType: 'hydra::recent-activity', position: { x: 6, y: 2, w: 6, h: 4 }, config: {}, dataBinding: null },
      { widgetType: 'hydra::capacity-overview', position: { x: 0, y: 6, w: 12, h: 4 }, config: {}, dataBinding: null },
      { widgetType: 'hydra::mini-topology', position: { x: 0, y: 10, w: 12, h: 4 }, config: {}, dataBinding: null },
      { widgetType: 'hydra::node-status-grid', position: { x: 0, y: 14, w: 12, h: 4 }, config: {}, dataBinding: null },
    ],
  };
}

function getTextConfig(config: Record<string, unknown>, key: string): string | undefined {
  const value = config[key];
  if (typeof value !== 'string') {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function getBooleanConfig(
  config: Record<string, unknown>,
  key: string,
  fallback = false,
): boolean {
  const value = config[key];
  return typeof value === 'boolean' ? value : fallback;
}

function sanitizeWidgetConfig(
  draft: Record<string, unknown>,
  schema: WidgetConfigField[],
): Record<string, unknown> {
  const nextConfig = { ...draft };

  for (const field of schema) {
    const rawValue = nextConfig[field.key];

    if (field.fieldType === 'text' || field.fieldType === 'select') {
      if (typeof rawValue !== 'string' || rawValue.trim() === '') {
        delete nextConfig[field.key];
        continue;
      }

      nextConfig[field.key] = rawValue.trim();
      continue;
    }

    if (field.fieldType === 'number') {
      if (rawValue === '' || rawValue === null || rawValue === undefined) {
        delete nextConfig[field.key];
        continue;
      }

      const parsed = typeof rawValue === 'number' ? rawValue : Number(rawValue);
      if (Number.isNaN(parsed)) {
        delete nextConfig[field.key];
        continue;
      }

      let clamped = parsed;
      if (typeof field.minValue === 'number') {
        clamped = Math.max(field.minValue, clamped);
      }
      if (typeof field.maxValue === 'number') {
        clamped = Math.min(field.maxValue, clamped);
      }
      nextConfig[field.key] = clamped;
      continue;
    }

    nextConfig[field.key] = Boolean(rawValue);
  }

  if (!getBooleanConfig(nextConfig, 'collapsible', false)) {
    delete nextConfig.defaultCollapsed;
  }

  return nextConfig;
}

/** Render the inner content of a widget based on its type */
function WidgetContent({
  widgetType,
  config,
}: {
  widgetType: string;
  config: Record<string, unknown>;
}) {
  const Component = getWidgetComponent(widgetType);
  if (Component) {
    return <Component config={{ ...config, __widgetType: widgetType }} />;
  }
  return (
    <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
      Unknown widget: {widgetType}
    </div>
  );
}

/** Icon for a widget type */
function widgetIcon(widgetType: string): typeof LayoutGrid {
  switch (widgetType) {
    case 'hydra::service-summary':
      return Boxes;
    case 'hydra::mini-topology':
      return Network;
    case 'hydra::recent-activity':
      return Bell;
    default:
      return LayoutGrid;
  }
}

/** Extra link actions per widget type */
function widgetActions(widgetType: string) {
  switch (widgetType) {
    case 'hydra::service-summary':
      return (
        <Link to={ROUTES.SERVICES}>
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      );
    case 'hydra::recent-activity':
      return (
        <Link to={`${ROUTES.SETTINGS}?bottom=audit`}>
          <Button variant="ghost" size="sm" className="group/btn text-muted-foreground">
            View all
            <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover/btn:translate-x-0.5" />
          </Button>
        </Link>
      );
    case 'hydra::mini-topology':
      return (
        <Link to={ROUTES.TOPOLOGY}>
          <Button variant="outline" size="sm">
            <Maximize2 className="mr-2 h-4 w-4" />
            Full view
          </Button>
        </Link>
      );
    case 'hydra::node-status-grid':
      return (
        <Link to={ROUTES.NODES}>
          <Button variant="outline" size="sm" className="group/btn">
            View All
            <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover/btn:translate-x-0.5" />
          </Button>
        </Link>
      );
    default:
      return null;
  }
}

export default function DashboardPage() {
  useDocumentTitle('Dashboard');

  const {
    activeBoardId,
    setActiveBoardId,
    isEditMode,
    setEditMode,
  } = useDashboardStore();
  const [configWidgetId, setConfigWidgetId] = useState<string | null>(null);
  const [widgetConfigDraft, setWidgetConfigDraft] = useState<Record<string, unknown>>({});

  const dashboardsQuery = useDashboards({ limit: 50, sortBy: 'updatedAt', sortOrder: 'desc' });
  const widgetRegistry = useWidgetRegistry().data;
  const dashboardItems = dashboardsQuery.data?.items;
  const dashboards = dashboardItems ?? [];
  const widgetDefinitions = useMemo(
    () =>
      new Map<string, WidgetTypeDefinition>(
        (widgetRegistry?.widgets ?? []).map((widget) => [widget.widgetType, widget])
      ),
    [widgetRegistry]
  );

  // Resolve selected board ID: prefer store's activeBoardId, fall back to first board
  const selectedBoardId = useMemo(() => {
    if (!dashboardItems?.length) return '';
    if (activeBoardId && dashboardItems.some((b) => b.boardId === activeBoardId)) {
      return activeBoardId;
    }
    return dashboardItems[0].boardId;
  }, [dashboardItems, activeBoardId]);

  // Sync store when selectedBoardId resolves differently from activeBoardId
  useEffect(() => {
    if (selectedBoardId && selectedBoardId !== activeBoardId) {
      setActiveBoardId(selectedBoardId);
    }
  }, [selectedBoardId, activeBoardId, setActiveBoardId]);

  const selectedBoardQuery = useDashboard(selectedBoardId);
  const selectedBoard = selectedBoardQuery.data;
  const configWidget = useMemo(
    () =>
      selectedBoard?.widgets.find((widget) => widget.instanceId === configWidgetId) ?? null,
    [selectedBoard, configWidgetId]
  );
  const configWidgetDefinition = useMemo(
    () =>
      configWidget ? widgetDefinitions.get(configWidget.widgetType) ?? null : null,
    [configWidget, widgetDefinitions]
  );

  const createDashboard = useCreateDashboard();
  const updateDashboard = useUpdateDashboard(selectedBoardId);
  const deleteDashboard = useDeleteDashboard();
  const cloneDashboard = useCloneDashboard(selectedBoardId);
  const addWidget = useAddWidget(selectedBoardId);
  const deleteWidget = useDeleteWidget(selectedBoardId);

  const isMutating =
    createDashboard.isPending ||
    updateDashboard.isPending ||
    deleteDashboard.isPending ||
    cloneDashboard.isPending ||
    addWidget.isPending ||
    deleteWidget.isPending;

  // Track whether a layout-change save is in-flight to debounce
  const layoutSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up debounce timer on unmount to prevent stale mutations
  useEffect(() => {
    return () => {
      if (layoutSaveRef.current) {
        clearTimeout(layoutSaveRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!configWidget) {
      setWidgetConfigDraft({});
      return;
    }

    setWidgetConfigDraft({ ...(configWidget.config ?? {}) });
  }, [configWidget]);

  const handleBoardChange = useCallback(
    (boardId: string) => {
      setActiveBoardId(boardId);
      setEditMode(false);
    },
    [setActiveBoardId, setEditMode]
  );

  const handleLayoutChange = useCallback(
    (layout: Layout) => {
      if (!selectedBoard) return;

      // Debounce saves: react-grid-layout fires this frequently during drags
      if (layoutSaveRef.current) {
        clearTimeout(layoutSaveRef.current);
      }

      layoutSaveRef.current = setTimeout(() => {
        const updatedWidgets = applyLayoutToWidgets(selectedBoard.widgets, layout);

        // If lengths differ the grid changed structurally — always save
        if (updatedWidgets.length !== selectedBoard.widgets.length) {
          updateDashboard.mutate(
            { widgets: updatedWidgets },
            {
              onError: (error) => {
                toast.error(getErrorMessage(error, 'Failed to save layout'));
              },
            }
          );
          return;
        }

        // Only save if positions actually changed
        const changed = updatedWidgets.some((w, i) => {
          const orig = selectedBoard.widgets[i];
          if (!orig) return true;
          return (
            w.position.x !== orig.position.x ||
            w.position.y !== orig.position.y ||
            w.position.w !== orig.position.w ||
            w.position.h !== orig.position.h
          );
        });

        if (changed) {
          updateDashboard.mutate(
            { widgets: updatedWidgets },
            {
              onError: (error) => {
                toast.error(getErrorMessage(error, 'Failed to save layout'));
              },
            }
          );
        }
      }, 500);
    },
    [selectedBoard, updateDashboard]
  );

  const handleRemoveWidget = useCallback(
    (instanceId: string) => {
      deleteWidget.mutate(instanceId, {
        onError: (error) => {
          toast.error(getErrorMessage(error, 'Failed to remove widget'));
        },
      });
    },
    [deleteWidget]
  );

  const handleAddWidget = useCallback(
    (widgetType: string, defaultSize?: WidgetSize) => {
      const size = defaultSize ?? widgetDefinitions.get(widgetType)?.defaultSize;
      if (!size) return;

      // Place at the bottom of the current grid
      const maxY = selectedBoard?.widgets.reduce(
        (max, w) => Math.max(max, w.position.y + w.position.h),
        0
      ) ?? 0;

      const request: DashboardCreateWidgetRequest = {
        widgetType,
        position: { x: 0, y: maxY, ...size },
        config: {},
        dataBinding: null,
      };

      addWidget.mutate(request, {
        onError: (error) => {
          toast.error(getErrorMessage(error, 'Failed to add widget'));
        },
      });
    },
    [selectedBoard, addWidget, widgetDefinitions]
  );

  const handleCreateBoard = useCallback(async () => {
    try {
      const board = await createDashboard.mutateAsync(
        buildStarterBoardRequest(
          dashboards.length === 0 ? 'My Dashboard' : `Dashboard ${dashboards.length + 1}`,
          dashboards.length === 0
        )
      );
      setActiveBoardId(board.boardId);
      setEditMode(false);
      toast.success('Dashboard board created');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to create dashboard board'));
    }
  }, [dashboards.length, createDashboard, setActiveBoardId, setEditMode]);

  const handleCloneBoard = useCallback(async () => {
    try {
      const board = await cloneDashboard.mutateAsync();
      setActiveBoardId(board.boardId);
      toast.success('Dashboard board cloned');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to clone dashboard board'));
    }
  }, [cloneDashboard, setActiveBoardId]);

  const handleDeleteBoard = useCallback(async () => {
    if (!selectedBoardId) return;
    try {
      await deleteDashboard.mutateAsync(selectedBoardId);
      setActiveBoardId(null);
      setEditMode(false);
      toast.success('Dashboard board deleted');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to delete dashboard board'));
    }
  }, [selectedBoardId, deleteDashboard, setActiveBoardId, setEditMode]);

  const handleToggleWidget = useCallback(
    async (instanceId: string) => {
      if (!selectedBoard) return;
      const widget = selectedBoard.widgets.find((w) => w.instanceId === instanceId);
      if (!widget) return;

      const isHidden = (widget.config as { hidden?: boolean })?.hidden ?? false;
      const updatedWidgets = selectedBoard.widgets.map((w) =>
        w.instanceId === instanceId
          ? { ...w, config: { ...w.config, hidden: !isHidden } }
          : w
      );

      try {
        await updateDashboard.mutateAsync({ widgets: updatedWidgets });
      } catch (error) {
        toast.error(getErrorMessage(error, 'Failed to update widget'));
      }
    },
    [selectedBoard, updateDashboard]
  );

  const handleResetLayout = useCallback(async () => {
    if (!selectedBoard) return;
    const request = buildStarterBoardRequest(selectedBoard.name, selectedBoard.isHome);
    try {
      await updateDashboard.mutateAsync({ widgets: request.widgets as DashboardWidgetInstance[] });
      toast.success('Layout reset to default');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to reset layout'));
    }
  }, [selectedBoard, updateDashboard]);

  const handleConfigureWidget = useCallback(
    (instanceId: string) => {
      if (!selectedBoard) return;

      const widget = selectedBoard.widgets.find((entry) => entry.instanceId === instanceId);
      if (!widget) return;

      const definition = widgetDefinitions.get(widget.widgetType);
      if (!definition?.capabilities.configurable) return;

      setConfigWidgetId(instanceId);
    },
    [selectedBoard, widgetDefinitions]
  );

  const handleSaveWidgetConfig = useCallback(async () => {
    if (!selectedBoard || !configWidget || !configWidgetDefinition) return;

    const nextConfig = sanitizeWidgetConfig(
      widgetConfigDraft,
      configWidgetDefinition.configSchema
    );
    const updatedWidgets = selectedBoard.widgets.map((widget) =>
      widget.instanceId === configWidget.instanceId
        ? { ...widget, config: nextConfig }
        : widget
    );

    try {
      await updateDashboard.mutateAsync({ widgets: updatedWidgets });
      setConfigWidgetId(null);
      toast.success('Widget settings saved');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to save widget settings'));
    }
  }, [
    configWidget,
    configWidgetDefinition,
    selectedBoard,
    updateDashboard,
    widgetConfigDraft,
  ]);

  // Build the customizer widget list from the board's actual widgets
  const customizerWidgets = useMemo(() => {
    if (!selectedBoard) return [];
    return selectedBoard.widgets.map((w) => ({
      id: w.instanceId,
      type: w.widgetType,
      visible: !(w.config as { hidden?: boolean })?.hidden,
      configurable: widgetDefinitions.get(w.widgetType)?.capabilities.configurable ?? false,
      supportsVisibilityToggle:
        widgetDefinitions.get(w.widgetType)?.capabilities.supportsVisibilityToggle ?? true,
    }));
  }, [selectedBoard, widgetDefinitions]);

  const hasBoards = dashboards.length > 0;
  const isInitialLoading = dashboardsQuery.isLoading && !dashboardsQuery.data;
  const isBoardLoading =
    selectedBoardId !== '' && selectedBoardQuery.isLoading && !selectedBoardQuery.data;
  const loadError = dashboardsQuery.error || selectedBoardQuery.error;

  // Filter to visible widgets for rendering
  const visibleWidgets = useMemo(() => {
    if (!selectedBoard) return [];
    return selectedBoard.widgets.filter(
      (w) => !(w.config as { hidden?: boolean })?.hidden
    );
  }, [selectedBoard]);

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      <motion.div variants={itemVariants}>
        <PageHeaderLayout
          title="Dashboard"
          subtitle={
            selectedBoard?.description ||
            (hasBoards
              ? `${dashboards.length} saved board${dashboards.length === 1 ? '' : 's'}`
              : 'Create a starter board to persist your dashboard layout')
          }
          showBreadcrumbs={false}
          showBackButton={false}
          actions={
            hasBoards ? (
              <>
                <Select value={selectedBoardId} onValueChange={handleBoardChange}>
                  <SelectTrigger className="w-[220px] bg-card border-border text-foreground">
                    <SelectValue placeholder="Select board" />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-border">
                    {dashboards.map((board) => (
                      <SelectItem key={board.boardId} value={board.boardId}>
                        {board.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {/* Time range selector — persisted in store. Widgets will
                    consume the selected range for data queries once data
                    binding is implemented in a future wave. */}
                <TimeRangeSelector />
                <WidgetCustomizerContent
                  widgetLayout={customizerWidgets}
                  isEditMode={isEditMode}
                  setEditMode={setEditMode}
                  onToggleWidget={handleToggleWidget}
                  onConfigureWidget={handleConfigureWidget}
                  onResetLayout={() => void handleResetLayout()}
                  isSaving={isMutating}
                />

                {isEditMode && (
                  <>
                    <WidgetPicker
                      onSelect={handleAddWidget}
                      disabled={isMutating}
                      existingTypes={selectedBoard?.widgets.map((w) => w.widgetType) ?? []}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void handleCloneBoard()}
                      disabled={isMutating}
                    >
                      <Copy className="mr-2 h-4 w-4" />
                      Clone
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => void handleDeleteBoard()}
                      disabled={isMutating}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </Button>
                  </>
                )}
                <Button size="sm" onClick={() => void handleCreateBoard()} disabled={isMutating}>
                  {createDashboard.isPending ? (
                    <LoadingSpinner size="sm" className="mr-2 text-current" />
                  ) : (
                    <Plus className="mr-2 h-4 w-4" />
                  )}
                  New Board
                </Button>
              </>
            ) : undefined
          }
        />
      </motion.div>

      {isInitialLoading ? (
        <motion.div
          variants={itemVariants}
          className="flex min-h-[320px] items-center justify-center rounded-xl border border-border bg-card"
        >
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <LoadingSpinner />
            Loading dashboards...
          </div>
        </motion.div>
      ) : loadError ? (
        <motion.div variants={itemVariants}>
          <EmptyState
            icon={PanelsTopLeft}
            title="Dashboard unavailable"
            description={getErrorMessage(loadError, 'Unable to load dashboard boards right now.')}
            action={{ label: 'Try Again', onClick: () => void dashboardsQuery.refetch() }}
          />
        </motion.div>
      ) : !hasBoards ? (
        <motion.div variants={itemVariants}>
          <EmptyState
            icon={PanelsTopLeft}
            title="No dashboard boards yet"
            description="Create a starter board seeded with the core Hydra widgets and we'll persist your board state on the server."
            action={{
              label: createDashboard.isPending ? 'Creating...' : 'Create Starter Board',
              onClick: () => void handleCreateBoard(),
            }}
          />
        </motion.div>
      ) : (
        <>
          <motion.div variants={itemVariants} className="flex flex-wrap gap-2">
            <Link to={ROUTES.TOPOLOGY}>
              <Button variant="outline" size="sm" className="group">
                <Network className="mr-2 h-4 w-4 text-primary transition-transform group-hover:scale-110" />
                Topology
              </Button>
            </Link>
            <Link to={ROUTES.TIME_MACHINE}>
              <Button variant="outline" size="sm" className="group">
                <History className="mr-2 h-4 w-4 text-info transition-transform group-hover:scale-110" />
                Time Machine
              </Button>
            </Link>
            <Link to={ROUTES.CHAT}>
              <Button variant="outline" size="sm" className="group">
                <MessageSquare className="mr-2 h-4 w-4 text-compute transition-transform group-hover:scale-110" />
                AI Chat
              </Button>
            </Link>
            <Link to={ROUTES.SERVICES}>
              <Button variant="outline" size="sm" className="group">
                <Boxes className="mr-2 h-4 w-4 text-purple-500 transition-transform group-hover:scale-110" />
                Services
              </Button>
            </Link>
            <Link to={ROUTES.NOTIFICATIONS}>
              <Button variant="outline" size="sm" className="group">
                <Bell className="mr-2 h-4 w-4 text-amber-500 transition-transform group-hover:scale-110" />
                Notifications
              </Button>
            </Link>
          </motion.div>

          {isBoardLoading ? (
            <motion.div
              variants={itemVariants}
              className="flex min-h-[280px] items-center justify-center rounded-xl border border-border bg-card"
            >
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <LoadingSpinner />
                Loading board...
              </div>
            </motion.div>
          ) : visibleWidgets.length === 0 ? (
            <motion.div variants={itemVariants}>
              <EmptyState
                icon={LayoutGrid}
                title="No visible widgets"
                description="All widgets are hidden or none have been added. Use the Customize panel or Add Widget button to configure your board."
              />
            </motion.div>
          ) : (
            <motion.div variants={itemVariants}>
              <WidgetGrid
                widgets={visibleWidgets}
                isEditMode={isEditMode}
                onLayoutChange={handleLayoutChange}
                onRemoveWidget={handleRemoveWidget}
                rowHeight={selectedBoard?.layout.rowHeight ?? 80}
              >
                {visibleWidgets.map((widget) => (
                  <Widget
                    key={widget.instanceId}
                    id={widget.instanceId}
                    title={getTextConfig(widget.config, 'title') ?? widgetTypeLabel(widget.widgetType)}
                    description={getTextConfig(widget.config, 'subtitle')}
                    icon={widgetIcon(widget.widgetType)}
                    actions={widgetActions(widget.widgetType)}
                    collapsible={getBooleanConfig(widget.config, 'collapsible')}
                    defaultCollapsed={getBooleanConfig(widget.config, 'defaultCollapsed')}
                    isEditMode={isEditMode}
                  >
                    <WidgetContent widgetType={widget.widgetType} config={widget.config} />
                  </Widget>
                ))}
              </WidgetGrid>
            </motion.div>
          )}
        </>
      )}

      <Dialog
        open={!!configWidget && !!configWidgetDefinition}
        onOpenChange={(open) => {
          if (!open) {
            setConfigWidgetId(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-[560px] bg-card border-border">
          <DialogHeader>
            <DialogTitle>Widget Settings</DialogTitle>
            <DialogDescription>
              {configWidgetDefinition
                ? `Customize ${configWidgetDefinition.displayName} on this board.`
                : 'Customize this widget.'}
            </DialogDescription>
          </DialogHeader>

          {configWidget && configWidgetDefinition ? (
            <div className="space-y-4">
              {configWidgetDefinition.configSchema.map((field) => {
                if (field.fieldType === 'boolean') {
                  return (
                    <div
                      key={field.key}
                      className="flex items-center justify-between gap-4 rounded-lg border border-border/60 p-3"
                    >
                      <div className="space-y-1">
                        <Label htmlFor={`widget-config-${field.key}`}>{field.label}</Label>
                        {field.description && (
                          <p className="text-xs text-muted-foreground">{field.description}</p>
                        )}
                      </div>
                      <Switch
                        id={`widget-config-${field.key}`}
                        checked={getBooleanConfig(widgetConfigDraft, field.key)}
                        onCheckedChange={(checked) =>
                          setWidgetConfigDraft((current) => ({
                            ...current,
                            [field.key]: checked,
                          }))
                        }
                      />
                    </div>
                  );
                }

                if (field.fieldType === 'select') {
                  const currentValue = widgetConfigDraft[field.key];
                  const selectValue =
                    typeof currentValue === 'string' && currentValue.length > 0
                      ? currentValue
                      : '__default__';

                  return (
                    <div key={field.key} className="space-y-2">
                      <Label htmlFor={`widget-config-${field.key}`}>{field.label}</Label>
                      {field.description && (
                        <p className="text-xs text-muted-foreground">{field.description}</p>
                      )}
                      <Select
                        value={selectValue}
                        onValueChange={(value) =>
                          setWidgetConfigDraft((current) => ({
                            ...current,
                            [field.key]: value === '__default__' ? '' : value,
                          }))
                        }
                      >
                        <SelectTrigger
                          id={`widget-config-${field.key}`}
                          className="bg-card border-border"
                          aria-label={field.label}
                        >
                          <SelectValue placeholder={field.placeholder ?? 'Select an option'} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__default__">Default</SelectItem>
                          {field.options.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  );
                }

                return (
                  <div key={field.key} className="space-y-2">
                    <Label htmlFor={`widget-config-${field.key}`}>{field.label}</Label>
                    {field.description && (
                      <p className="text-xs text-muted-foreground">{field.description}</p>
                    )}
                    {(() => {
                      const draftValue = widgetConfigDraft[field.key];
                      const inputValue =
                        field.fieldType === 'number'
                          ? typeof draftValue === 'number'
                            ? String(draftValue)
                            : typeof draftValue === 'string'
                              ? draftValue
                              : ''
                          : typeof draftValue === 'string'
                            ? draftValue
                            : '';

                      return (
                        <Input
                          id={`widget-config-${field.key}`}
                          type={field.fieldType === 'number' ? 'number' : 'text'}
                          value={inputValue}
                          placeholder={field.placeholder ?? undefined}
                          min={field.minValue ?? undefined}
                          max={field.maxValue ?? undefined}
                          onChange={(event) =>
                            setWidgetConfigDraft((current) => ({
                              ...current,
                              [field.key]:
                                field.fieldType === 'number'
                                  ? event.target.value === ''
                                    ? ''
                                    : Number(event.target.value)
                                  : event.target.value,
                            }))
                          }
                        />
                      );
                    })()}
                  </div>
                );
              })}
            </div>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfigWidgetId(null)}
              disabled={isMutating}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void handleSaveWidgetConfig()}
              disabled={isMutating || !configWidget || !configWidgetDefinition}
            >
              Save Settings
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
