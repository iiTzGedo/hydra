import { ReactNode, useState } from 'react';
import { Settings2, Eye, EyeOff, RotateCcw, Maximize2, Minimize2, LucideIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { useDashboardStore, type WidgetConfig } from '@/stores/dashboard-store';

const WIDGET_LABELS: Record<WidgetConfig['type'], string> = {
  stats: 'Stats Cards',
  capacity: 'Capacity Overview',
  notifications: 'Recent Activities',
  activity: 'Recent Activity',
  'topology-mini': 'Mini Topology',
  services: 'Services Status',
};

interface WidgetGridProps {
  children: ReactNode;
}

export function WidgetGrid({ children }: WidgetGridProps) {
  return (
    <div className="space-y-4">
      {children}
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
  defaultCollapsed = false
}: WidgetProps) {
  const { widgetLayout, isEditMode } = useDashboardStore();
  const config = widgetLayout.find((w) => w.id === id);
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  if (!config?.visible) {
    return null;
  }

  return (
    <div
      className={cn(
        'relative rounded-xl border border-border bg-card overflow-hidden',
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
              <span className="text-xs text-muted-foreground">
                {WIDGET_LABELS[config.type] || id}
              </span>
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
          {WIDGET_LABELS[config.type] || id}
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

export function WidgetCustomizer() {
  const { widgetLayout, toggleWidgetVisibility, resetLayout, isEditMode, setEditMode } =
    useDashboardStore();

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
                  {WIDGET_LABELS[widget.type] || widget.id}
                </Label>
                <div className="flex items-center gap-2">
                  {widget.visible ? (
                    <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                  <Switch
                    id={`widget-${widget.id}`}
                    checked={widget.visible}
                    onCheckedChange={() => toggleWidgetVisibility(widget.id)}
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
              Enable to see widget boundaries
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={resetLayout}
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
