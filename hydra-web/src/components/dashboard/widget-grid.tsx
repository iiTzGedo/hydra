import React, { ReactNode, useState, useMemo, useCallback } from 'react';
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
import { normalizeDashboardLayout, type DashboardBoardLayout, type DashboardWidgetInstance } from '@/types/dashboard';

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

interface WidgetGridProps {
  widgets: DashboardWidgetInstance[];
  layout: DashboardBoardLayout;
  isEditMode: boolean;
  onLayoutChange?: (layout: Layout) => void;
  onRemoveWidget?: (instanceId: string) => void;
  rowHeight?: number;
  children: ReactNode;
}

export function WidgetGrid({
  widgets,
  layout,
  isEditMode,
  onLayoutChange,
  onRemoveWidget,
  rowHeight = 80,
  children,
}: WidgetGridProps) {
  const { width, containerRef, mounted } = useContainerWidth({ initialWidth: 1200 });
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

  return (
    <div ref={containerRef as React.RefObject<HTMLDivElement>} className={cn('widget-grid', isEditMode && 'widget-grid--editing')}>
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
                    <div key={widget.instanceId} className="relative">
                      {isEditMode && onRemoveWidget ? (
                        <button
                          type="button"
                          className="absolute -right-2 -top-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow-md transition-colors hover:bg-destructive/90"
                          onClick={() => onRemoveWidget(widget.instanceId)}
                          aria-label={`Remove ${widgetTypeLabel(widget.widgetType)}`}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      ) : null}
                      {childArray[childIndex] ?? null}
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
            <div key={widget.instanceId} className="relative">
              {isEditMode && onRemoveWidget && (
                <button
                  type="button"
                  className="absolute -top-2 -right-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow-md hover:bg-destructive/90 transition-colors"
                  onClick={() => onRemoveWidget(widget.instanceId)}
                  aria-label={`Remove ${widgetTypeLabel(widget.widgetType)}`}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
              {isEditMode && (
                <div className="widget-drag-handle absolute top-0 left-0 right-0 h-8 cursor-grab z-10" />
              )}
              {/* Render the corresponding child by index.
                 INVARIANT: parent must pass children in the same order as
                 the `widgets` array so that index-based lookup is correct. */}
              {childArray[index] ?? null}
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
