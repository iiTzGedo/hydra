import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useParams } from 'next/navigation';
import type { Layout } from 'react-grid-layout';
import {
  ArrowLeft,
  ArrowRight,
  Copy,
  Download,
  Home,
  LayoutGrid,
  LayoutTemplate,
  Maximize2,
  MoreHorizontal,
  PanelsTopLeft,
  Pin,
  PinOff,
  Plus,
  Save,
  Share2,
  Trash2,
  Upload,
  X,
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
  useExportDashboard,
  useImportDashboard,
  useSetHomeDashboard,
  useUpdateDashboard,
  useWidgetRegistry,
} from '@/api/dashboards';
import { useCreateCommand } from '@/api/commands';
import { useUpdateUserSettings, useUserSettings } from '@/api/settings';
import { BoardTemplates } from '@/components/dashboard/board-templates';
import { ShareDialog } from '@/components/dashboard/share-dialog';
import { TimeRangeSelector } from '@/components/dashboard/time-range-selector';
import { getWidgetComponent } from '@/components/dashboard/widgets';
import {
  Widget,
  WidgetCustomizerContent,
  WidgetGrid,
  applyLayoutToWidgets,
  widgetTypeLabel,
} from '@/components/dashboard/widget-grid';
import { HydraIcon } from '@/components/icons/hydra-icon';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
import { useWidgetData } from '@/hooks/use-widget-data';
import { getErrorMessage } from '@/lib/api-client';
import { ROUTES } from '@/lib/constants';
import { useDashboardStore } from '@/stores/dashboard-store';
import { normalizeDashboardLayout } from '@/types/dashboard';
import type {
  CreateDashboardRequest,
  DashboardBoard,
  DashboardBoardLayout,
  DashboardBoardSettings,
  DashboardCreateWidgetRequest,
  DashboardDataBinding,
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
  mode: 'grid',
  grid: {
    columns: 12,
    rowHeight: 80,
    breakpoints: {
      xl: { columns: 12, width: 1536 },
      lg: { columns: 12, width: 1200 },
      md: { columns: 8, width: 996 },
      sm: { columns: 4, width: 480 },
      xs: { columns: 2, width: 0 },
    },
    compaction: 'vertical',
    margin: [16, 16],
    padding: [0, 0],
  },
};

const STARTER_BOARD_SETTINGS: DashboardBoardSettings = {
  theme: 'inherit',
  autoRefresh: true,
  refreshInterval: 30,
  showHeader: true,
  kioskMode: false,
  kioskAutoScroll: false,
  kioskScrollSpeed: 30,
  backgroundImage: null,
  customCss: null,
};

function getBoardDisplayName(board?: { isHome?: boolean; name: string } | null) {
  if (!board) {
    return 'Dashboard';
  }

  return board.isHome ? 'Dashboard' : board.name;
}

function buildStarterBoardRequest(name: string, isHome: boolean): CreateDashboardRequest {
  return {
    name,
    description: 'Overview of your infrastructure',
    boardType: 'user',
    visibility: { scope: 'private', sharedWith: { roles: [], users: [] } },
    layout: DEFAULT_BOARD_LAYOUT,
    settings: STARTER_BOARD_SETTINGS,
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

function cloneBoardState<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
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

function WidgetContent({
  widgetType,
  config,
  dataBinding,
  isEditing,
  onNavigate,
  onExecuteCommand,
}: {
  widgetType: string;
  config: Record<string, unknown>;
  dataBinding?: DashboardDataBinding | null;
  isEditing: boolean;
  onNavigate: (path: string) => void;
  onExecuteCommand: (
    commandId: string,
    target: Record<string, unknown>,
    params: Record<string, unknown>,
  ) => Promise<void>;
}) {
  const { data, isLoading, error } = useWidgetData(dataBinding);

  const Component = getWidgetComponent(widgetType);
  if (Component) {
    return (
      <Component
        config={{ ...config, __widgetType: widgetType }}
        data={data}
        isEditing={isEditing}
        isLoading={isLoading}
        error={error}
        dimensions={{ width: 0, height: 0 }}
        onNavigate={onNavigate}
        onExecuteCommand={onExecuteCommand}
      />
    );
  }
  return (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      Unknown widget: {widgetType}
    </div>
  );
}

function widgetActions(widgetType: string) {
  switch (widgetType) {
    case 'hydra::service-summary':
      return (
        <Link href={ROUTES.SERVICES}>
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      );
    case 'hydra::recent-activity':
      return (
        <Link href={`${ROUTES.SETTINGS}?bottom=audit`}>
          <Button variant="ghost" size="sm" className="group/btn text-muted-foreground">
            View all
            <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover/btn:translate-x-0.5" />
          </Button>
        </Link>
      );
    case 'hydra::mini-topology':
      return (
        <Link href={ROUTES.TOPOLOGY}>
          <Button variant="outline" size="sm">
            <Maximize2 className="mr-2 h-4 w-4" />
            Full view
          </Button>
        </Link>
      );
    case 'hydra::node-status-grid':
      return (
        <Link href={ROUTES.NODES}>
          <Button variant="outline" size="sm" className="group/btn">
            View all
            <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover/btn:translate-x-0.5" />
          </Button>
        </Link>
      );
    default:
      return null;
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const pathname = usePathname() ?? '/';
  const { boardId: routeBoardId } = useParams<{ boardId?: string }>()!
  const isInlineLegacyDashboard = pathname === ROUTES.DASHBOARD && !routeBoardId;

  const {
    activeBoardId,
    setActiveBoardId,
    isEditMode,
    setEditMode,
  } = useDashboardStore();
  const [configWidgetId, setConfigWidgetId] = useState<string | null>(null);
  const [widgetConfigDraft, setWidgetConfigDraft] = useState<Record<string, unknown>>({});
  const [draftBoard, setDraftBoard] = useState<DashboardBoard | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const dashboardsQuery = useDashboards({ limit: 50, sortBy: 'updatedAt', sortOrder: 'desc' });
  const settingsQuery = useUserSettings();
  const widgetRegistry = useWidgetRegistry().data;

  const createDashboard = useCreateDashboard();
  const updateSettings = useUpdateUserSettings();

  const boards = useMemo(() => dashboardsQuery.data?.items ?? [], [dashboardsQuery.data?.items]);
  const settings = settingsQuery.data;
  const pinnedBoardIds = useMemo(
    () => settings?.dashboard?.pinnedBoardIds ?? [],
    [settings?.dashboard?.pinnedBoardIds],
  );
  const lastOpenedBoardId = settings?.dashboard?.lastOpenedBoardId ?? null;
  const resolvedLegacyBoardId = useMemo(() => {
    if (!isInlineLegacyDashboard) {
      return null;
    }

    if (activeBoardId && boards.some((board) => board.boardId === activeBoardId)) {
      return activeBoardId;
    }

    const homeBoard = boards.find((board) => board.isHome);
    if (homeBoard) {
      return homeBoard.boardId;
    }

    if (lastOpenedBoardId && boards.some((board) => board.boardId === lastOpenedBoardId)) {
      return lastOpenedBoardId;
    }

    const pinnedBoard = boards.find((board) => pinnedBoardIds.includes(board.boardId));
    return pinnedBoard?.boardId ?? boards[0]?.boardId ?? null;
  }, [activeBoardId, boards, isInlineLegacyDashboard, lastOpenedBoardId, pinnedBoardIds]);
  const effectiveBoardId = routeBoardId ?? resolvedLegacyBoardId ?? undefined;
  const isBoardBrowser = !effectiveBoardId && !isInlineLegacyDashboard;

  const selectedBoardQuery = useDashboard(effectiveBoardId ?? '');
  const selectedBoard = effectiveBoardId ? selectedBoardQuery.data : null;
  const workingBoard = isEditMode ? draftBoard ?? selectedBoard ?? null : selectedBoard ?? null;
  const normalizedWorkingLayout = useMemo(
    () => normalizeDashboardLayout(workingBoard?.layout as DashboardBoardLayout | undefined),
    [workingBoard?.layout],
  );
  useDocumentTitle(
    isBoardBrowser
      ? 'Dashboards'
      : getBoardDisplayName(selectedBoard),
  );

  const updateDashboard = useUpdateDashboard(effectiveBoardId ?? '');
  const deleteDashboard = useDeleteDashboard();
  const cloneDashboard = useCloneDashboard(effectiveBoardId ?? '');
  const addWidget = useAddWidget(effectiveBoardId ?? '');
  const deleteWidget = useDeleteWidget(effectiveBoardId ?? '');
  const exportQuery = useExportDashboard(effectiveBoardId ?? '');
  const importDashboard = useImportDashboard();
  const setHomeBoard = useSetHomeDashboard();
  const createCommand = useCreateCommand();

  const handleExecuteCommand = useCallback(
    async (
      registryId: string,
      target: Record<string, unknown>,
      params: Record<string, unknown>,
    ) => {
      const nodeId = target.nodeId as string | undefined;
      if (!registryId || !nodeId) {
        toast.error('Missing command or target node');
        return;
      }
      try {
        const result = await createCommand.mutateAsync({
          registryId,
          target: {
            nodeId,
            serviceId: (target.serviceId as string) ?? undefined,
          },
          parameters: Object.keys(params).length > 0 ? params : undefined,
        });
        if (result.requiresConfirmation) {
          toast.warning('Command requires confirmation', {
            description: result.confirmationMessage ?? `Confirm command ${registryId} (${result.dangerLevel ?? 'unknown'} risk)`,
          });
        } else if (result.status === 'queued') {
          toast.info('Command queued', { description: `Position: ${result.queuePosition ?? '—'}` });
        } else {
          toast.success('Command submitted', { description: `Status: ${result.status}` });
        }
      } catch (err) {
        toast.error(getErrorMessage(err, 'Command execution failed'));
      }
    },
    [createCommand],
  );

  const widgetDefinitions = useMemo(
    () =>
      new Map<string, WidgetTypeDefinition>(
        (widgetRegistry?.widgets ?? []).map((widget) => [widget.widgetType, widget]),
      ),
    [widgetRegistry],
  );

  useEffect(() => {
    if (effectiveBoardId) {
      if (activeBoardId !== effectiveBoardId) {
        setActiveBoardId(effectiveBoardId);
      }
      if (lastOpenedBoardId !== effectiveBoardId) {
        updateSettings.mutate({ dashboard: { lastOpenedBoardId: effectiveBoardId } });
      }
    }
  }, [activeBoardId, effectiveBoardId, lastOpenedBoardId, setActiveBoardId, updateSettings]);

  useEffect(() => {
    if (!isEditMode) {
      setDraftBoard(null);
      setConfigWidgetId(null);
    }
  }, [isEditMode]);

  const configWidget = useMemo(
    () => workingBoard?.widgets.find((widget) => widget.instanceId === configWidgetId) ?? null,
    [configWidgetId, workingBoard],
  );
  const configWidgetDefinition = useMemo(
    () => (configWidget ? widgetDefinitions.get(configWidget.widgetType) ?? null : null),
    [configWidget, widgetDefinitions],
  );

  useEffect(() => {
    if (!configWidget) {
      setWidgetConfigDraft({});
      return;
    }
    setWidgetConfigDraft({ ...(configWidget.config ?? {}) });
  }, [configWidget]);

  const isMutating =
    createDashboard.isPending ||
    updateDashboard.isPending ||
    deleteDashboard.isPending ||
    cloneDashboard.isPending ||
    addWidget.isPending ||
    deleteWidget.isPending ||
    importDashboard.isPending ||
    updateSettings.isPending;

  const visibleWidgets = useMemo(
    () =>
      (workingBoard?.widgets ?? []).filter((widget) => !(widget.config as { hidden?: boolean })?.hidden),
    [workingBoard],
  );

  const boardPath = useCallback(
    (boardId: string) => ROUTES.DASHBOARD_BOARD.replace(':boardId', boardId),
    [],
  );

  const openBoard = useCallback(
    (boardId: string) => {
      setEditMode(false);
      setDraftBoard(null);
      setActiveBoardId(boardId);
      if (isInlineLegacyDashboard) {
        return;
      }
      router.push(boardPath(boardId));
    },
    [boardPath, isInlineLegacyDashboard, router, setActiveBoardId, setEditMode],
  );

  const beginEditing = useCallback(() => {
    if (!selectedBoard) {
      return;
    }
    setDraftBoard({
      ...cloneBoardState(selectedBoard),
      layout: normalizeDashboardLayout(selectedBoard.layout as DashboardBoardLayout | undefined),
    });
    setEditMode(true);
  }, [selectedBoard, setEditMode]);

  const exitEditing = useCallback(() => {
    setDraftBoard(null);
    setEditMode(false);
  }, [setEditMode]);

  const handleLayoutChange = useCallback(
    (layout: Layout) => {
      if (!isEditMode || !workingBoard) {
        return;
      }

      setDraftBoard({
        ...workingBoard,
        widgets: applyLayoutToWidgets(workingBoard.widgets, layout),
      });
    },
    [isEditMode, workingBoard],
  );

  const handleRemoveWidget = useCallback(
    (instanceId: string) => {
      if (!workingBoard) {
        return;
      }

      if (isEditMode) {
        setDraftBoard({
          ...workingBoard,
          widgets: workingBoard.widgets.filter((widget) => widget.instanceId !== instanceId),
        });
        return;
      }

      deleteWidget.mutate(instanceId, {
        onError: (error) => {
          toast.error(getErrorMessage(error, 'Failed to remove widget'));
        },
      });
    },
    [deleteWidget, isEditMode, workingBoard],
  );

  const handleAddWidget = useCallback(
    (widgetType: string, defaultSize?: WidgetSize) => {
      const size = defaultSize ?? widgetDefinitions.get(widgetType)?.defaultSize;
      if (!size || !workingBoard) {
        return;
      }

      const maxY = workingBoard.widgets.reduce((max, widget) => {
        const position = widget.position ?? widget.placements?.lg;
        return Math.max(max, (position?.y ?? 0) + (position?.h ?? 0));
      }, 0);

      const request: DashboardCreateWidgetRequest = {
        widgetType,
        position: { x: 0, y: maxY, ...size },
        config: {},
        dataBinding: null,
      };

      if (isEditMode) {
        setDraftBoard({
          ...workingBoard,
          widgets: [
            ...workingBoard.widgets,
            {
              instanceId: `draft_${Date.now()}`,
              widgetType,
              position: request.position,
              placements: request.position ? { lg: request.position } : null,
              config: {},
              dataBinding: null,
            },
          ],
        });
        return;
      }

      addWidget.mutate(request, {
        onError: (error) => {
          toast.error(getErrorMessage(error, 'Failed to add widget'));
        },
      });
    },
    [addWidget, isEditMode, widgetDefinitions, workingBoard],
  );

  const handleToggleWidget = useCallback(
    async (instanceId: string) => {
      if (!workingBoard) {
        return;
      }

      const nextWidgets = workingBoard.widgets.map((widget) => {
        if (widget.instanceId !== instanceId) {
          return widget;
        }
        const hidden = Boolean((widget.config as { hidden?: boolean })?.hidden);
        return { ...widget, config: { ...widget.config, hidden: !hidden } };
      });

      if (isEditMode) {
        setDraftBoard({ ...workingBoard, widgets: nextWidgets });
        return;
      }

      try {
        await updateDashboard.mutateAsync({ widgets: nextWidgets });
      } catch (error) {
        toast.error(getErrorMessage(error, 'Failed to update widget visibility'));
      }
    },
    [isEditMode, updateDashboard, workingBoard],
  );

  const handleConfigureWidget = useCallback(
    (instanceId: string) => {
      const widget = workingBoard?.widgets.find((entry) => entry.instanceId === instanceId);
      if (!widget) {
        return;
      }

      const definition = widgetDefinitions.get(widget.widgetType);
      if (!definition?.capabilities.configurable) {
        return;
      }

      setConfigWidgetId(instanceId);
    },
    [widgetDefinitions, workingBoard],
  );

  const handleResetLayout = useCallback(() => {
    if (!workingBoard) {
      return;
    }

    const starter = buildStarterBoardRequest(workingBoard.name, workingBoard.isHome);
    setDraftBoard({
      ...workingBoard,
      layout: starter.layout ?? DEFAULT_BOARD_LAYOUT,
      widgets: (starter.widgets ?? []) as DashboardWidgetInstance[],
    });
  }, [workingBoard]);

  const handleSaveBoard = useCallback(async () => {
    if (!effectiveBoardId || !draftBoard) {
      return;
    }

    try {
      await updateDashboard.mutateAsync({
        layout: draftBoard.layout,
        widgets: draftBoard.widgets,
      });
      toast.success('Dashboard saved');
      exitEditing();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to save dashboard'));
    }
  }, [draftBoard, effectiveBoardId, exitEditing, updateDashboard]);

  const handleSaveWidgetConfig = useCallback(async () => {
    if (!workingBoard || !configWidget || !configWidgetDefinition) {
      return;
    }

    const nextConfig = sanitizeWidgetConfig(widgetConfigDraft, configWidgetDefinition.configSchema);
    const updatedWidgets = workingBoard.widgets.map((widget) =>
      widget.instanceId === configWidget.instanceId
        ? { ...widget, config: nextConfig }
        : widget,
    );

    if (isEditMode) {
      setDraftBoard({ ...workingBoard, widgets: updatedWidgets });
      setConfigWidgetId(null);
      return;
    }

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
    isEditMode,
    updateDashboard,
    widgetConfigDraft,
    workingBoard,
  ]);

  const handleCreateBoard = useCallback(async () => {
    try {
      const board = await createDashboard.mutateAsync(
        buildStarterBoardRequest(
          boards.length === 0 ? 'Dashboard' : `Dashboard ${boards.length + 1}`,
          boards.length === 0,
        ),
      );
      toast.success('Dashboard board created');
      openBoard(board.boardId);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to create dashboard board'));
    }
  }, [boards.length, createDashboard, openBoard]);

  const handleCloneBoard = useCallback(async () => {
    try {
      const board = await cloneDashboard.mutateAsync();
      toast.success('Dashboard board cloned');
      openBoard(board.boardId);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to clone dashboard board'));
    }
  }, [cloneDashboard, openBoard]);

  const handleDeleteBoard = useCallback(async () => {
    if (!effectiveBoardId) {
      return;
    }
    try {
      await deleteDashboard.mutateAsync(effectiveBoardId);
      exitEditing();
      setShowDeleteConfirm(false);
      toast.success('Dashboard board deleted');
      router.push(ROUTES.DASHBOARDS);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to delete dashboard board'));
    }
  }, [deleteDashboard, effectiveBoardId, exitEditing, router]);

  const handleExportBoard = useCallback(async () => {
    if (!effectiveBoardId) {
      return;
    }
    try {
      const { data } = await exportQuery.refetch();
      if (!data) {
        return;
      }
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `dashboard-${selectedBoard?.name?.replace(/\s+/g, '-').toLowerCase() ?? 'export'}.json`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success('Dashboard exported');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to export dashboard'));
    }
  }, [effectiveBoardId, exportQuery, selectedBoard?.name]);

  const handleImportBoard = useCallback(async (file: File) => {
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const result = await importDashboard.mutateAsync({ board: parsed });
      if (result.warnings.length > 0) {
        toast.warning(
          `Dashboard imported with ${result.warnings.length} warning(s): ${result.warnings[0].message}`,
        );
      } else {
        toast.success('Dashboard imported');
      }
      openBoard(result.board.boardId);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to import dashboard'));
    }
  }, [importDashboard, openBoard]);

  const handleTemplateUsed = useCallback((boardId: string) => {
    openBoard(boardId);
  }, [openBoard]);

  const handleTogglePin = useCallback(async (boardId: string) => {
    const currentPins = pinnedBoardIds.includes(boardId)
      ? pinnedBoardIds.filter((id) => id !== boardId)
      : [...pinnedBoardIds, boardId].slice(0, 5);

    try {
      await updateSettings.mutateAsync({ dashboard: { pinnedBoardIds: currentPins } });
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to update pinned dashboards'));
    }
  }, [pinnedBoardIds, updateSettings]);

  const handleMakeHome = useCallback(async (boardId: string) => {
    try {
      await setHomeBoard.mutateAsync(boardId);
      toast.success('Home dashboard updated');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to update home dashboard'));
    }
  }, [setHomeBoard]);

  const customizerWidgets = useMemo(() => {
    if (!workingBoard) {
      return [];
    }
    return workingBoard.widgets.map((widget) => ({
      id: widget.instanceId,
      type: widget.widgetType,
      visible: !(widget.config as { hidden?: boolean })?.hidden,
      configurable: widgetDefinitions.get(widget.widgetType)?.capabilities.configurable ?? false,
      supportsVisibilityToggle:
        widgetDefinitions.get(widget.widgetType)?.capabilities.supportsVisibilityToggle ?? true,
    }));
  }, [widgetDefinitions, workingBoard]);

  const loadError = dashboardsQuery.error || (effectiveBoardId ? selectedBoardQuery.error : null);
  const hasNoBoards = !dashboardsQuery.isLoading && boards.length === 0;

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="visible" className="space-y-6">
      <motion.div variants={itemVariants}>
        <PageHeaderLayout
          title={
            isBoardBrowser
              ? 'Dashboards'
              : getBoardDisplayName(selectedBoard)
          }
          subtitle={
            isBoardBrowser
              ? 'Browse saved boards, manage pins, and choose your home dashboard.'
              : workingBoard?.description ?? 'Editable board surface with persistent save and discard flow.'
          }
          showBackButton={false}
          actions={
            isBoardBrowser ? (
              <>
                <Button size="sm" variant="outline" onClick={() => setShowTemplates(true)} disabled={isMutating}>
                  <LayoutTemplate className="mr-2 h-4 w-4" />
                  Templates
                </Button>
                <Button size="sm" onClick={() => void handleCreateBoard()} disabled={isMutating}>
                  {createDashboard.isPending ? <LoadingSpinner size="sm" className="mr-2 text-current" /> : <Plus className="mr-2 h-4 w-4" />}
                  New Board
                </Button>
              </>
            ) : (
              <>
                <Button variant="outline" size="sm" onClick={() => router.push(ROUTES.DASHBOARDS)}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  All Dashboards
                </Button>
                <Select value={effectiveBoardId} onValueChange={openBoard}>
                  <SelectTrigger className="w-[220px] bg-card border-border text-foreground">
                    <SelectValue placeholder="Select board" />
                  </SelectTrigger>
                  <SelectContent>
                    {boards.map((board) => (
                      <SelectItem key={board.boardId} value={board.boardId}>
                        {getBoardDisplayName(board)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <TimeRangeSelector />
                {isEditMode ? (
                  <>
                    <WidgetCustomizerContent
                      widgetLayout={customizerWidgets}
                      isEditMode={isEditMode}
                      setEditMode={(editing) => {
                        if (editing) {
                          beginEditing();
                        } else {
                          exitEditing();
                        }
                      }}
                      onToggleWidget={handleToggleWidget}
                      onConfigureWidget={handleConfigureWidget}
                      onResetLayout={handleResetLayout}
                      isSaving={isMutating}
                    />
                    <WidgetPicker
                      onSelect={handleAddWidget}
                      disabled={isMutating}
                      existingTypes={workingBoard?.widgets.map((widget) => widget.widgetType) ?? []}
                    />
                    <Button variant="outline" size="sm" onClick={exitEditing} disabled={isMutating}>
                      <X className="mr-2 h-4 w-4" />
                      Discard
                    </Button>
                    <Button size="sm" onClick={() => void handleSaveBoard()} disabled={isMutating}>
                      <Save className="mr-2 h-4 w-4" />
                      Save Layout
                    </Button>
                  </>
                ) : (
                  <Button size="sm" onClick={beginEditing} disabled={!selectedBoard || isMutating}>
                    <LayoutGrid className="mr-2 h-4 w-4" />
                    Edit Board
                  </Button>
                )}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      disabled={!selectedBoard || isMutating}
                      aria-label="Board actions"
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuLabel>Board actions</DropdownMenuLabel>
                    <DropdownMenuItem
                      onClick={() => void handleCloneBoard()}
                      disabled={isMutating}
                    >
                      <Copy className="mr-2 h-4 w-4" />
                      Clone
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setShowShare(true)}
                      disabled={isMutating || isEditMode}
                    >
                      <Share2 className="mr-2 h-4 w-4" />
                      Share
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => void handleExportBoard()}
                      disabled={isMutating || isEditMode}
                    >
                      <Download className="mr-2 h-4 w-4" />
                      Export
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.accept = '.json';
                        input.onchange = (event) => {
                          const file = (event.target as HTMLInputElement).files?.[0];
                          if (file) {
                            void handleImportBoard(file);
                          }
                        };
                        input.click();
                      }}
                      disabled={isMutating || isEditMode}
                    >
                      <Upload className="mr-2 h-4 w-4" />
                      Import
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => setShowDeleteConfirm(true)}
                      disabled={isMutating || selectedBoard?.isHome}
                      className="text-destructive focus:text-destructive"
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )
          }
        />
      </motion.div>

      {loadError ? (
        <motion.div variants={itemVariants}>
          <EmptyState
            icon={PanelsTopLeft}
            title="Dashboard unavailable"
            description={getErrorMessage(loadError, 'Unable to load dashboards right now.')}
            action={{ label: 'Try Again', onClick: () => void dashboardsQuery.refetch() }}
          />
        </motion.div>
      ) : hasNoBoards ? (
        <motion.div variants={itemVariants}>
          <EmptyState
            icon={PanelsTopLeft}
            title="No dashboard boards yet"
            description="Create a starter board seeded with the core Hydra widgets and we’ll persist your board state on the server."
            action={{
              label: createDashboard.isPending ? 'Creating...' : 'Create Starter Board',
              onClick: () => void handleCreateBoard(),
            }}
          />
        </motion.div>
      ) : isBoardBrowser ? (
        <motion.div variants={itemVariants} className="grid gap-4 xl:grid-cols-2">
          {boards.map((board) => {
            const pinned = pinnedBoardIds.includes(board.boardId);
            return (
              <Card key={board.boardId} className="overflow-hidden border-border/70">
                <CardHeader className="border-b border-border/60 bg-muted/20">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-border/60 bg-card">
                        <HydraIcon fallback={board.icon ?? 'dashboard'} size={22} />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{getBoardDisplayName(board)}</CardTitle>
                        <CardDescription className="mt-1">
                          {board.description ?? 'Customizable board with persisted widget layout.'}
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {board.isHome ? <Badge variant="info">Home</Badge> : null}
                      {pinned ? <Badge variant="secondary">Pinned</Badge> : null}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 p-6">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">{board.widgetCount} widgets</Badge>
                    <Badge variant="outline">{board.visibility.scope}</Badge>
                    <Badge variant="outline">{board.boardType}</Badge>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <Button onClick={() => openBoard(board.boardId)}>
                      Open Board
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => void handleTogglePin(board.boardId)}
                      disabled={isMutating}
                    >
                      {pinned ? (
                        <>
                          <PinOff className="mr-2 h-4 w-4" />
                          Unpin
                        </>
                      ) : (
                        <>
                          <Pin className="mr-2 h-4 w-4" />
                          Pin
                        </>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => void handleMakeHome(board.boardId)}
                      disabled={board.isHome || isMutating}
                    >
                      <Home className="mr-2 h-4 w-4" />
                      Make Home
                    </Button>
                    <Button variant="outline" onClick={() => router.push(boardPath(board.boardId))}>
                      <LayoutGrid className="mr-2 h-4 w-4" />
                      Customize
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </motion.div>
      ) : boards.length === 0 ? (
        <motion.div variants={itemVariants}>
          <EmptyState
            icon={PanelsTopLeft}
            title="No dashboard boards yet"
            description="Create a starter board seeded with the core Hydra widgets and we’ll persist your board state on the server."
            action={{
              label: createDashboard.isPending ? 'Creating...' : 'Create Starter Board',
              onClick: () => void handleCreateBoard(),
            }}
          />
        </motion.div>
      ) : !selectedBoard ? (
        <motion.div variants={itemVariants}>
          <EmptyState
            icon={PanelsTopLeft}
            title="Board not found"
            description="The requested dashboard board could not be loaded."
            action={{ label: 'Back to Dashboards', onClick: () => router.push(ROUTES.DASHBOARDS) }}
          />
        </motion.div>
      ) : (
        <>
          {visibleWidgets.length === 0 ? (
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
                layout={normalizedWorkingLayout}
                isEditMode={isEditMode}
                onLayoutChange={handleLayoutChange}
                onRemoveWidget={handleRemoveWidget}
                rowHeight={normalizedWorkingLayout.mode === 'grid' ? normalizedWorkingLayout.grid.rowHeight : 80}
              >
                {visibleWidgets.map((widget) => (
                  <Widget
                    key={widget.instanceId}
                    id={widget.instanceId}
                    title={getTextConfig(widget.config, 'title') ?? widgetTypeLabel(widget.widgetType)}
                    description={getTextConfig(widget.config, 'subtitle')}
                    icon={<HydraIcon fallback={widget.widgetType.replace('hydra::', '')} size={16} />}
                    actions={widgetActions(widget.widgetType)}
                    collapsible={getBooleanConfig(widget.config, 'collapsible')}
                    defaultCollapsed={getBooleanConfig(widget.config, 'defaultCollapsed')}
                    isEditMode={isEditMode}
                  >
                    <WidgetContent
                      widgetType={widget.widgetType}
                      config={widget.config}
                      dataBinding={widget.dataBinding}
                      isEditing={isEditMode}
                      onNavigate={(path) => router.push(path)}
                      onExecuteCommand={handleExecuteCommand}
                    />
                  </Widget>
                ))}
              </WidgetGrid>
            </motion.div>
          )}
        </>
      )}

      <BoardTemplates open={showTemplates} onOpenChange={setShowTemplates} onTemplateUsed={handleTemplateUsed} />

      {effectiveBoardId && selectedBoard ? (
        <ShareDialog
          open={showShare}
          onOpenChange={setShowShare}
          boardId={effectiveBoardId}
          boardName={getBoardDisplayName(selectedBoard)}
        />
      ) : null}

      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this dashboard?</AlertDialogTitle>
            <AlertDialogDescription>
              {selectedBoard
                ? `"${getBoardDisplayName(selectedBoard)}" and its widget layout will be permanently removed. This cannot be undone.`
                : 'This dashboard and its widget layout will be permanently removed. This cannot be undone.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteDashboard.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault();
                void handleDeleteBoard();
              }}
              disabled={deleteDashboard.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteDashboard.isPending ? 'Deleting…' : 'Delete dashboard'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={Boolean(configWidget && configWidgetDefinition)}
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
                    <div key={field.key} className="flex items-center justify-between gap-4 rounded-lg border border-border/60 p-3">
                      <div className="space-y-1">
                        <Label htmlFor={`widget-config-${field.key}`}>{field.label}</Label>
                        {field.description ? <p className="text-xs text-muted-foreground">{field.description}</p> : null}
                      </div>
                      <Switch
                        id={`widget-config-${field.key}`}
                        checked={getBooleanConfig(widgetConfigDraft, field.key)}
                        onCheckedChange={(checked) =>
                          setWidgetConfigDraft((current) => ({ ...current, [field.key]: checked }))
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
                      {field.description ? <p className="text-xs text-muted-foreground">{field.description}</p> : null}
                      <Select
                        value={selectValue}
                        onValueChange={(value) =>
                          setWidgetConfigDraft((current) => ({
                            ...current,
                            [field.key]: value === '__default__' ? '' : value,
                          }))
                        }
                      >
                        <SelectTrigger id={`widget-config-${field.key}`} className="bg-card border-border">
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
                  <div key={field.key} className="space-y-2">
                    <Label htmlFor={`widget-config-${field.key}`}>{field.label}</Label>
                    {field.description ? <p className="text-xs text-muted-foreground">{field.description}</p> : null}
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
                  </div>
                );
              })}
            </div>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfigWidgetId(null)} disabled={isMutating}>
              Cancel
            </Button>
            <Button type="button" onClick={() => void handleSaveWidgetConfig()} disabled={isMutating}>
              Save Settings
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
