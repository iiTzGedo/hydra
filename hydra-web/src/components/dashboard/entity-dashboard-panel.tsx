/**
 * EntityDashboardPanel — renders a collapsible mini-dashboard panel on entity
 * detail pages (node, service, network).
 *
 * Fetches the entity panel board via the Phase 4 API
 * (GET /dashboards/panel/:entityType) and resolves {{entity.id}} /
 * {{entity.type}} template variables before rendering each widget.
 *
 * "Customize panel…" creates a user override board and navigates to it in
 * edit mode.
 */

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDown, ChevronRight, Settings } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { useEmbeddedPanel } from '@/hooks/use-embedded-panel';
import { useCustomizeEntityPanel } from '@/api/dashboards';
import { useAuthStore } from '@/stores/auth-store';
import { useWidgetData } from '@/hooks/use-widget-data';
import { getWidgetComponent } from '@/components/dashboard/widgets';
import {
  Widget,
  WidgetGrid,
  widgetTypeLabel,
} from '@/components/dashboard/widget-grid';
import { getErrorMessage } from '@/lib/api-client';
import type { EntityPanelType, DashboardWidgetInstance, DashboardDataBinding } from '@/types/dashboard';

// ── Inline widget content ───────────────────────────────────────────

interface WidgetContentProps {
  widget: DashboardWidgetInstance;
  onNavigate: (path: string) => void;
  onExecuteCommand: (
    commandId: string,
    target: Record<string, unknown>,
    params: Record<string, unknown>,
  ) => Promise<void>;
}

function EmbeddedWidgetContent({ widget, onNavigate, onExecuteCommand }: WidgetContentProps) {
  const { data, isLoading, error } = useWidgetData(
    widget.dataBinding as DashboardDataBinding | null | undefined,
  );
  const Component = getWidgetComponent(widget.widgetType);

  if (Component) {
    return (
      <Component
        config={{ ...widget.config, __widgetType: widget.widgetType }}
        data={data}
        isEditing={false}
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
      Unknown widget: {widget.widgetType}
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────

interface EntityDashboardPanelProps {
  entityType: EntityPanelType;
  entityId: string;
  /** Optional node ID for command targeting when rendering a service panel. */
  nodeId?: string;
}

export function EntityDashboardPanel({ entityType, entityId, nodeId: _nodeId }: EntityDashboardPanelProps) {
  const router = useRouter();
  const [open, setOpen] = useState(true);

  const { data: panel, isLoading, isError } = useEmbeddedPanel(entityType, entityId);
  const customize = useCustomizeEntityPanel(entityType);
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const canCustomize = hasPermission('dashboards:write');

  const handleNavigate = useCallback((path: string) => router.push(path), [router]);

  const handleExecuteCommand = useCallback(
    async (
      _commandId: string,
      _target: Record<string, unknown>,
      _params: Record<string, unknown>,
    ) => {
      // Command execution is handled by the full dashboard page; the embedded
      // panel is read-only so we simply acknowledge the call.
    },
    [],
  );

  const handleCustomize = useCallback(async () => {
    try {
      const override = await customize.mutateAsync();
      router.push(`/dashboards/${override.boardId}?edit=1`);
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to create panel customization'));
    }
  }, [customize, router]);

  if (isLoading) {
    return (
      <div className="p-4 text-sm text-muted-foreground">Loading panel…</div>
    );
  }

  if (isError) {
    return (
      <section className="border border-destructive/30 rounded-md bg-destructive/5 p-4">
        <p className="text-sm text-destructive">Panel unavailable. The server could not load the panel for this entity.</p>
      </section>
    );
  }

  if (!panel) {
    return null;
  }

  const widgets = panel.widgets ?? [];
  if (widgets.length === 0) return null;

  return (
    <section className="border rounded-md bg-card">
      <header className="flex items-center gap-2 px-4 py-2 border-b">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1 text-sm font-medium"
          aria-expanded={open}
          aria-controls={`entity-panel-${entityType}-content`}
        >
          {open ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          {panel.name}
        </button>
        <div className="flex-1" />
        {canCustomize && (
          <Button
            size="sm"
            variant="ghost"
            onClick={handleCustomize}
            disabled={customize.isPending}
            data-testid="customize-panel-button"
          >
            <Settings className="w-4 h-4 mr-1" />
            Customize panel…
          </Button>
        )}
      </header>

      {open && (
        <div className="p-2" id={`entity-panel-${entityType}-content`}>
          <WidgetGrid
            widgets={widgets}
            layout={panel.layout}
            layoutMode={panel.layoutMode}
            isEditMode={false}
            rowHeight={
              panel.layout.mode === 'grid' ? panel.layout.grid.rowHeight : 80
            }
          >
            {widgets.map((widget: DashboardWidgetInstance) => (
              <Widget
                key={widget.instanceId}
                id={widget.instanceId}
                title={
                  typeof widget.config?.title === 'string'
                    ? widget.config.title
                    : widgetTypeLabel(widget.widgetType)
                }
                isEditMode={false}
              >
                <EmbeddedWidgetContent
                  widget={widget}
                  onNavigate={handleNavigate}
                  onExecuteCommand={handleExecuteCommand}
                />
              </Widget>
            ))}
          </WidgetGrid>
        </div>
      )}
    </section>
  );
}
