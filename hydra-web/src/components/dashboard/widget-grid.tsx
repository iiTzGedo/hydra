import React, { ReactNode, useState, useMemo, useCallback, useEffect } from 'react';
import {
  ResponsiveGridLayout,
  useContainerWidth,
  type Layout,
  type LayoutItem,
  type ResponsiveLayouts,
} from 'react-grid-layout';
import { Settings2, Eye, EyeOff, RotateCcw, Maximize2, Minimize2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import {
  normalizeDashboardLayout,
  type DashboardBoardLayout,
  type DashboardWidgetInstance,
  type FreeformPosition,
  type LayoutMode,
  type WidgetTypeDefinition,
} from '@/types/dashboard';
import { WidgetConfiguratorPopover } from '@/components/dashboard/widget-configurator-popover';
import { FreeformCanvas } from '@/components/dashboard/freeform-canvas';
import { gridToFreeform } from '@/lib/freeform-layout';
import { useIsMobile } from '@/hooks/use-media-query';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const WIDGET_TYPE_LABELS: Record<string, string> = {
  // Existing composites
  'hydra::stats-cards': 'Stats Cards',
  'hydra::capacity-overview': 'Capacity Overview',
  'hydra::recent-activity': 'Recent Activities',
  'hydra::node-status-grid': 'Node Status Grid',
  'hydra::mini-topology': 'Mini Topology',
  'hydra::service-summary': 'Service Summary',
  // Data Display
  'hydra::metric-card': 'Metric Card',
  'hydra::gauge': 'Gauge',
  'hydra::progress-bar': 'Progress Bar',
  'hydra::sparkline': 'Sparkline',
  'hydra::stat-group': 'Stat Group',
  'hydra::donut-chart': 'Donut Chart',
  // Status & Health
  'hydra::status-grid': 'Status Grid',
  'hydra::health-matrix': 'Health Matrix',
  'hydra::node-status-card': 'Node Status Card',
  'hydra::service-status-bar': 'Service Status Bar',
  'hydra::uptime-bar': 'Uptime Bar',
  // Tables & Lists
  'hydra::entity-table': 'Entity Table',
  'hydra::service-list': 'Service List',
  'hydra::activity-feed': 'Activity Feed',
  'hydra::alert-list': 'Alert List',
  'hydra::log-viewer': 'Log Viewer',
  // Charts & Graphs
  'hydra::line-chart': 'Line Chart',
  'hydra::bar-chart': 'Bar Chart',
  'hydra::area-chart': 'Area Chart',
  'hydra::heatmap': 'Heatmap',
  // Topology & Maps
  'hydra::network-map': 'Network Map',
  // Controls & Actions
  'hydra::quick-action': 'Quick Action',
  'hydra::command-trigger': 'Command Trigger',
  'hydra::service-control': 'Service Control',
  'hydra::workflow-trigger': 'Workflow Trigger',
  // Infrastructure
  'hydra::node-summary': 'Node Summary',
  'hydra::capacity-panel': 'Capacity Panel',
  'hydra::network-summary': 'Network Summary',
  'hydra::profile-diff': 'Profile Diff',
  // Time & History
  'hydra::time-machine-scrubber': 'Time Machine',
  'hydra::change-log': 'Change Log',
  'hydra::profile-timeline': 'Profile Timeline',
  // External & Embed
  'hydra::clock': 'Clock',
  'hydra::rss-feed': 'RSS Feed',
  'hydra::bookmark-grid': 'Bookmark Grid',
  'hydra::iframe': 'Embed',
  'hydra::markdown': 'Markdown',
  'hydra::weather': 'Weather',
  'hydra::html-block': 'HTML Block',
  // System & Meta
  'hydra::integration-health': 'Integration Health',
  'hydra::agent-grid': 'Agent Grid',
  'hydra::audit-stream': 'Audit Stream',
  'hydra::api-status': 'API Status',
  'hydra::mcp-query': 'MCP Query',
  'hydra::execution-queue': 'Execution Queue',
};

export function widgetTypeLabel(widgetType: string): string {
  return WIDGET_TYPE_LABELS[widgetType] ?? widgetType;
}

/** Map API widget instances to react-grid-layout LayoutItem array for a breakpoint */
export function widgetsToLayout(
  widgets: DashboardWidgetInstance[],
  breakpoint: 'xs' | 'sm' | 'md' | 'lg' | 'xl' = 'lg',
): LayoutItem[] {
  return widgets.map((w) => {
    const placement = w.placements?.[breakpoint] ?? w.placements?.lg ?? w.position;
    return {
      i: w.instanceId,
      x: placement?.x ?? 0,
      y: placement?.y ?? 0,
      w: placement?.w ?? 12,
      h: placement?.h ?? 4,
    };
  });
}

/** Apply RGL layout changes back onto existing widget instances */
export function applyLayoutToWidgets(
  widgets: DashboardWidgetInstance[],
  layout: Layout
): DashboardWidgetInstance[] {
  const positionMap = new Map(
    layout.map((item) => [item.i, { x: item.x, y: item.y, w: item.w, h: item.h }])
  );
  return widgets.map((widget) => {
    const pos = positionMap.get(widget.instanceId);
    if (!pos) return widget;
    return {
      ...widget,
      position: pos,
      placements: {
        ...(widget.placements ?? {}),
        lg: pos,
      },
    };
  });
}

// ── Configurator callbacks passed in from the dashboard page ──────

export interface WidgetConfiguratorCallbacks {
  /** Map of widgetType → WidgetTypeDefinition, for looking up configSchema */
  widgetDefinitions: Map<string, WidgetTypeDefinition>;
  /** Update a config key on a widget */
  onWidgetConfigChange: (instanceId: string, key: string, value: unknown) => void;
  /** Resize a widget to a preset w × h */
  onWidgetSizeChange: (instanceId: string, w: number, h: number) => void;
  /** Change widget refresh interval */
  onWidgetRefreshChange?: (instanceId: string, seconds: number) => void;
  /** Duplicate a widget */
  onWidgetDuplicate: (instanceId: string) => void;
  /** Open the data binding editor for a widget */
  onWidgetOpenDataBinding: (instanceId: string) => void;
}

// ── WidgetGrid props ───────────────────────────────────────────────

interface WidgetGridProps {
  widgets: DashboardWidgetInstance[];
  layout: DashboardBoardLayout;
  /**
   * Overrides layout mode for rendering. When `'freeform'`, the grid uses
   * `FreeformCanvas` instead of RGL, regardless of the `layout.mode` field.
   */
  layoutMode?: LayoutMode;
  isEditMode: boolean;
  onLayoutChange?: (layout: Layout) => void;
  onRemoveWidget?: (instanceId: string) => void;
  /** Called when a widget's freeform position changes (move/resize). */
  onFreeformPositionChange?: (instanceId: string, position: FreeformPosition) => void;
  rowHeight?: number;
  children: ReactNode;
  /** When provided, clicking a widget in edit mode opens the configurator popover */
  configurator?: WidgetConfiguratorCallbacks;
}

export function WidgetGrid({
  widgets,
  layout,
  layoutMode,
  isEditMode,
  onLayoutChange,
  onRemoveWidget,
  onFreeformPositionChange,
  rowHeight = 80,
  children,
  configurator,
}: WidgetGridProps) {
  const [selectedWidgetId, setSelectedWidgetId] = useState<string | null>(null);
  const { width, containerRef, mounted } = useContainerWidth({ initialWidth: 1200 });
  const isMobile = useIsMobile();

  useEffect(() => {
    if (!isEditMode) {
      setSelectedWidgetId(null);
    }
  }, [isEditMode]);
  const childArray = React.Children.toArray(children);
  const normalizedLayout = normalizeDashboardLayout(layout);

  const layouts: ResponsiveLayouts = useMemo(() => {
    if (normalizedLayout.mode !== 'grid') {
      return { lg: widgetsToLayout(widgets, 'lg') };
    }
    const breakpointKeys = Object.keys(normalizedLayout.grid.breakpoints) as Array<
      'xs' | 'sm' | 'md' | 'lg' | 'xl'
    >;
    return breakpointKeys.reduce<ResponsiveLayouts>((acc, key) => {
      acc[key] = widgetsToLayout(widgets, key);
      return acc;
    }, {});
  }, [widgets, normalizedLayout]);

  const handleLayoutChange = useCallback(
    (currentLayout: Layout) => {
      if (isEditMode && onLayoutChange) {
        onLayoutChange(currentLayout);
      }
    },
    [isEditMode, onLayoutChange]
  );

  const toggleSelection = useCallback(
    (instanceId: string) => {
      setSelectedWidgetId((prev) => (prev === instanceId ? null : instanceId));
    },
    [],
  );

  /**
   * Render a single widget wrapper — shared by both grid and columns modes.
   * Handles configurator popover (click to select), drag handle, and remove button.
   */
  const renderWidgetWrapper = useCallback(
    (widget: DashboardWidgetInstance, child: React.ReactNode) => {
      const isSelected = selectedWidgetId === widget.instanceId;
      const typeDef = configurator?.widgetDefinitions.get(widget.widgetType);
      const hasConfigurator = isEditMode && !!configurator && !!typeDef;

      const handleClick = (e: React.MouseEvent) => {
        if (!hasConfigurator) return;
        // Ignore clicks on drag handles and remove buttons
        const target = e.target as HTMLElement;
        if (
          target.closest('.widget-drag-handle') ||
          target.closest('[data-widget-remove]')
        )
          return;
        e.stopPropagation();
        toggleSelection(widget.instanceId);
      };

      const handleKeyDown = (e: React.KeyboardEvent) => {
        if (!hasConfigurator) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          e.stopPropagation();
          toggleSelection(widget.instanceId);
        }
      };

      const handleContextMenu = (e: React.MouseEvent) => {
        if (!hasConfigurator) return;
        e.preventDefault();
        e.stopPropagation();
        setSelectedWidgetId(widget.instanceId);
      };

      const closePopover = () => setSelectedWidgetId(null);

      const widgetEl = (
        <div
          className={cn(
            'relative h-full',
            hasConfigurator && 'cursor-pointer',
            isSelected && 'ring-2 ring-primary ring-offset-1 rounded-xl',
          )}
          role={hasConfigurator ? 'button' : undefined}
          tabIndex={hasConfigurator ? 0 : undefined}
          aria-label={hasConfigurator ? `Configure ${widgetTypeLabel(widget.widgetType)}` : undefined}
          aria-pressed={hasConfigurator ? isSelected : undefined}
          onClick={handleClick}
          onKeyDown={hasConfigurator ? handleKeyDown : undefined}
          onContextMenu={handleContextMenu}
        >
          {isEditMode && onRemoveWidget && (
            <button
              type="button"
              data-widget-remove
              className="absolute -top-2 -right-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow-md hover:bg-destructive/90 transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                onRemoveWidget(widget.instanceId);
                closePopover();
              }}
              aria-label={`Remove ${widgetTypeLabel(widget.widgetType)}`}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          {isEditMode && (
            <div className="widget-drag-handle absolute top-0 left-0 right-0 h-8 cursor-grab z-10" />
          )}
          {child}
        </div>
      );

      if (hasConfigurator && typeDef) {
        return (
          <WidgetConfiguratorPopover
            key={widget.instanceId}
            typeDef={typeDef}
            instance={widget}
            open={isSelected}
            onOpenChange={(open) => {
              if (!open) closePopover();
            }}
            trigger={widgetEl}
            onConfigChange={(key, value) => {
              configurator.onWidgetConfigChange(widget.instanceId, key, value);
            }}
            onSizeChange={({ w, h }) => {
              configurator.onWidgetSizeChange(widget.instanceId, w, h);
            }}
            onRefreshChange={
              configurator.onWidgetRefreshChange
                ? (seconds) => configurator.onWidgetRefreshChange!(widget.instanceId, seconds)
                : undefined
            }
            onDelete={() => {
              onRemoveWidget?.(widget.instanceId);
              closePopover();
            }}
            onDuplicate={() => {
              configurator.onWidgetDuplicate(widget.instanceId);
              closePopover();
            }}
            onOpenDataBinding={() => {
              configurator.onWidgetOpenDataBinding(widget.instanceId);
              closePopover();
            }}
          />
        );
      }

      return widgetEl;
    },
    [
      configurator,
      isEditMode,
      onRemoveWidget,
      selectedWidgetId,
      toggleSelection,
    ],
  );

  // ── Freeform rendering path ────────────────────────────────────

  const effectiveMode = layoutMode ?? normalizedLayout.mode;

  if (effectiveMode === 'freeform') {
    // Mobile fallback: vertical stack sorted by freeformPosition.y
    if (isMobile) {
      const sorted = [...widgets].sort(
        (a, b) => (a.freeformPosition?.y ?? 0) - (b.freeformPosition?.y ?? 0),
      );
      return (
        <div className="flex flex-col gap-2">
          {/* m5: hint that the freeform layout stacks vertically on mobile */}
          <p className="px-1 text-xs text-muted-foreground">
            Freeform layout — widgets stacked on mobile
          </p>
          {sorted.map((widget) => {
            // I1: match child by instanceId rather than by sorted array index.
            // Using the sorted index would mismatch child elements when the
            // sort order differs from the original widgets array order.
            const origIndex = widgets.findIndex((w) => w.instanceId === widget.instanceId);
            const child = origIndex >= 0 ? childArray[origIndex] : null;
            return (
              <div key={widget.instanceId}>
                {renderWidgetWrapper(widget, child)}
              </div>
            );
          })}
        </div>
      );
    }

    // Ensure every widget has a freeformPosition by falling back to
    // gridToFreeform conversion when none is set.
    const freeformParams = {
      cols: 12,
      rowHeight: rowHeight,
      gap: 8,
      canvasWidth: width,
    };
    const widgetsWithFF = widgets.map((w) => {
      if (w.freeformPosition) return w;
      const grid = w.placements?.lg ?? w.position ?? { x: 0, y: 0, w: 4, h: 2 };
      const ff = gridToFreeform(grid, freeformParams);
      return { ...w, freeformPosition: ff };
    });

    return (
      <div
        ref={containerRef as React.RefObject<HTMLDivElement>}
        className={cn('widget-grid', isEditMode && 'widget-grid--editing')}
        onClick={() => setSelectedWidgetId(null)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setSelectedWidgetId(null);
        }}
        role="presentation"
      >
        <FreeformCanvas
          widgets={widgetsWithFF}
          editable={isEditMode}
          canvasWidth={mounted ? width : 1200}
          renderWidget={(w) => {
            const origIndex = widgets.findIndex((orig) => orig.instanceId === w.instanceId);
            return renderWidgetWrapper(w, childArray[origIndex] ?? null);
          }}
          onPositionChange={(id, pos) => onFreeformPositionChange?.(id, pos)}
        />
      </div>
    );
  }

  // ── Grid / columns rendering path (existing) ───────────────────

  return (
    <div
      ref={containerRef as React.RefObject<HTMLDivElement>}
      className={cn('widget-grid', isEditMode && 'widget-grid--editing')}
      // Clicking/pressing outside any widget collapses the selection
      onClick={() => setSelectedWidgetId(null)}
      onKeyDown={(e) => {
        if (e.key === 'Escape') setSelectedWidgetId(null);
      }}
      role="presentation"
    >
      {normalizedLayout.mode === 'columns' ? (
        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: normalizedLayout.columnsLayout.columns.map((column) => `${column.ratio}fr`).join(' '),
          }}
        >
          {normalizedLayout.columnsLayout.columns.map((column) => {
            const columnWidgets = widgets
              .filter((widget) => (widget.column ?? normalizedLayout.columnsLayout.columns[0]?.id) === column.id)
              .sort((left, right) => (left.order ?? 0) - (right.order ?? 0));

            return (
              <div key={column.id} className="space-y-4">
                {column.title ? (
                  <div className="px-1 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    {column.title}
                  </div>
                ) : null}
                {columnWidgets.map((widget) => {
                  const childIndex = widgets.findIndex((entry) => entry.instanceId === widget.instanceId);
                  return (
                    <div key={widget.instanceId}>
                      {renderWidgetWrapper(widget, childArray[childIndex] ?? null)}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      ) : mounted ? (
        <ResponsiveGridLayout
          className="layout"
          width={width}
          layouts={layouts}
          breakpoints={Object.fromEntries(
            Object.entries(normalizedLayout.grid.breakpoints).map(([key, value]) => [key, value.width])
          )}
          cols={Object.fromEntries(
            Object.entries(normalizedLayout.grid.breakpoints).map(([key, value]) => [key, value.columns])
          )}
          rowHeight={rowHeight}
          dragConfig={{ enabled: isEditMode, handle: '.widget-drag-handle' }}
          resizeConfig={{ enabled: isEditMode }}
          onLayoutChange={handleLayoutChange}
          margin={normalizedLayout.grid.margin}
          containerPadding={normalizedLayout.grid.padding}
        >
          {widgets.map((widget, index) => (
            <div key={widget.instanceId}>
              {renderWidgetWrapper(widget, childArray[index] ?? null)}
            </div>
          ))}
        </ResponsiveGridLayout>
      ) : null}
    </div>
  );
}

interface WidgetProps {
  id: string;
  children: ReactNode;
  className?: string;
  title?: string;
  description?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  isEditMode?: boolean;
}

export function Widget({
  id,
  children,
  className = '',
  title,
  description,
  icon,
  actions,
  collapsible = false,
  defaultCollapsed = false,
  isEditMode = false,
}: WidgetProps) {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  const hasHeader = Boolean(title || icon || collapsible || actions);

  return (
    <div
      className={cn(
        'relative flex h-full min-h-0 flex-col rounded-xl border border-border bg-card overflow-hidden',
        isEditMode && 'ring-2 ring-dashed ring-muted-foreground/30',
        className
      )}
    >
      {hasHeader && (
        <div className="flex flex-none items-center justify-between px-4 py-3 border-b border-border/50">
          <div className="flex min-w-0 items-center gap-2">
            {icon ? (
              <div className="p-1.5 rounded-lg bg-muted">
                {icon}
              </div>
            ) : null}
            <div className="min-w-0">
              {title && (
                <h3 className="truncate font-semibold text-sm text-foreground">{title}</h3>
              )}
              {description && (
                <p className="truncate text-xs text-muted-foreground">{description}</p>
              )}
            </div>
          </div>

          <div className="flex flex-none items-center gap-2">
            {actions}
            {collapsible && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                onClick={() => setIsCollapsed(!isCollapsed)}
                aria-label={isCollapsed ? 'Expand widget' : 'Collapse widget'}
              >
                {isCollapsed ? (
                  <Maximize2 className="h-3.5 w-3.5" />
                ) : (
                  <Minimize2 className="h-3.5 w-3.5" />
                )}
              </Button>
            )}
          </div>
        </div>
      )}

      {isEditMode && !title && !icon && (
        <div className="pointer-events-none absolute top-1 left-1 z-10 rounded border border-border bg-card/90 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
          {id}
        </div>
      )}

      {!isCollapsed && (
        <div className="flex min-h-0 flex-1 flex-col overflow-auto p-4">
          {children}
        </div>
      )}
    </div>
  );
}

interface WidgetCustomizerContentProps {
  widgetLayout: {
    id: string;
    type: string;
    visible: boolean;
    configurable?: boolean;
    supportsVisibilityToggle?: boolean;
  }[];
  isEditMode: boolean;
  setEditMode: (editing: boolean) => void;
  onToggleWidget: (id: string) => void;
  onConfigureWidget?: (id: string) => void;
  onResetLayout: () => void;
  isSaving?: boolean;
}

export function WidgetCustomizerContent({
  widgetLayout,
  isEditMode,
  setEditMode,
  onToggleWidget,
  onConfigureWidget,
  onResetLayout,
  isSaving = false,
}: WidgetCustomizerContentProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="bg-card border-border text-foreground hover:bg-muted gap-2"
        >
          <Settings2 className="h-4 w-4" />
          <span className="hidden sm:inline">Customize</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 bg-card border-border" align="end">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-foreground">Dashboard Widgets</h4>
          </div>

          <div className="space-y-3">
            {widgetLayout.map((widget) => (
              <div key={widget.id} className="flex items-center justify-between">
                <Label
                  htmlFor={`widget-${widget.id}`}
                  className="text-sm text-foreground cursor-pointer"
                >
                  {WIDGET_TYPE_LABELS[widget.type] || widget.id}
                </Label>
                <div className="flex items-center gap-2">
                  {widget.configurable && onConfigureWidget && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-foreground"
                      disabled={isSaving}
                      onClick={() => onConfigureWidget(widget.id)}
                      aria-label={`Configure ${widgetTypeLabel(widget.type)}`}
                      data-testid={`customizer-configure-${widget.id}`}
                    >
                      <Settings2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  {widget.visible ? (
                    <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                  <Switch
                    id={`widget-${widget.id}`}
                    checked={widget.visible}
                    disabled={isSaving || widget.supportsVisibilityToggle === false}
                    onCheckedChange={() => onToggleWidget(widget.id)}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-border pt-3 space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="edit-mode" className="text-sm text-foreground cursor-pointer">
                Edit Mode
              </Label>
              <Switch
                id="edit-mode"
                checked={isEditMode}
                onCheckedChange={setEditMode}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Enable to drag, resize, and manage widgets
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            disabled={isSaving}
            onClick={onResetLayout}
            className="w-full gap-2 border-border text-foreground hover:bg-muted"
          >
            <RotateCcw className="h-4 w-4" />
            Reset to Default
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
