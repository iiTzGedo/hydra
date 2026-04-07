import React, { ReactNode, useState, useMemo, useCallback } from 'react';
import {
  ResponsiveGridLayout,
  useContainerWidth,
  type Layout,
  type LayoutItem,
  type ResponsiveLayouts,
} from 'react-grid-layout';
import { Settings2, Eye, EyeOff, RotateCcw, Maximize2, Minimize2, X, LucideIcon } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import type { DashboardWidgetInstance } from '@/types/dashboard';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const WIDGET_TYPE_LABELS: Record<string, string> = {
  'hydra::stats-cards': 'Stats Cards',
  'hydra::capacity-overview': 'Capacity Overview',
  'hydra::recent-activity': 'Recent Activities',
  'hydra::node-status-grid': 'Node Status Grid',
  'hydra::mini-topology': 'Mini Topology',
  'hydra::service-summary': 'Service Summary',
};

export function widgetTypeLabel(widgetType: string): string {
  return WIDGET_TYPE_LABELS[widgetType] ?? widgetType;
}

/** Map API widget instances to react-grid-layout LayoutItem array */
export function widgetsToLayout(widgets: DashboardWidgetInstance[]): LayoutItem[] {
  return widgets.map((w) => ({
    i: w.instanceId,
    x: w.position.x,
    y: w.position.y,
    w: w.position.w,
    h: w.position.h,
  }));
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
    };
  });
}

interface WidgetGridProps {
  widgets: DashboardWidgetInstance[];
  isEditMode: boolean;
  onLayoutChange?: (layout: Layout) => void;
  onRemoveWidget?: (instanceId: string) => void;
  rowHeight?: number;
  children: ReactNode;
}

export function WidgetGrid({
  widgets,
  isEditMode,
  onLayoutChange,
  onRemoveWidget,
  rowHeight = 80,
  children,
}: WidgetGridProps) {
  const { width, containerRef, mounted } = useContainerWidth({ initialWidth: 1200 });

  const layouts: ResponsiveLayouts = useMemo(
    () => ({ lg: widgetsToLayout(widgets) }),
    [widgets]
  );

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
      {mounted && (
        <ResponsiveGridLayout
          className="layout"
          width={width}
          layouts={layouts}
          breakpoints={{ lg: 1200, md: 996, sm: 768 }}
          cols={{ lg: 12, md: 8, sm: 4 }}
          rowHeight={rowHeight}
          dragConfig={{ enabled: isEditMode, handle: '.widget-drag-handle' }}
          resizeConfig={{ enabled: isEditMode }}
          onLayoutChange={handleLayoutChange}
          margin={[16, 16]}
          containerPadding={[0, 0]}
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
              {Array.isArray(children) ? children[index] : index === 0 ? children : null}
            </div>
          ))}
        </ResponsiveGridLayout>
      )}
    </div>
  );
}

interface WidgetProps {
  id: string;
  children: ReactNode;
  className?: string;
  title?: string;
  description?: string;
  icon?: LucideIcon;
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
  icon: Icon,
  actions,
  collapsible = false,
  defaultCollapsed = false,
  isEditMode = false,
}: WidgetProps) {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  return (
    <div
      className={cn(
        'relative h-full rounded-xl border border-border bg-card overflow-hidden',
        isEditMode && 'ring-2 ring-dashed ring-muted-foreground/30',
        className
      )}
    >
      {/* Widget Header */}
      {(title || Icon || isEditMode) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
          <div className="flex items-center gap-2">
            {Icon && (
              <div className="p-1.5 rounded-lg bg-muted">
                <Icon className="h-4 w-4 text-primary" />
              </div>
            )}
            <div>
              {title && (
                <h3 className="font-semibold text-sm text-foreground">{title}</h3>
              )}
              {description && (
                <p className="text-xs text-muted-foreground">{description}</p>
              )}
            </div>
            {isEditMode && !title && (
              <span className="text-xs text-muted-foreground">{id}</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {actions}
            {collapsible && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                onClick={() => setIsCollapsed(!isCollapsed)}
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

      {/* Edit Mode Label (when no header) */}
      {isEditMode && !title && !Icon && (
        <div className="absolute -top-3 left-2 bg-card px-2 py-0.5 text-xs text-muted-foreground rounded border border-border z-10">
          {id}
        </div>
      )}

      {/* Widget Content */}
      <AnimatePresence initial={false}>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="p-4">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
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
