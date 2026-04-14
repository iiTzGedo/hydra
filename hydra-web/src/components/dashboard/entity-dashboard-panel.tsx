/**
 * EntityDashboardPanel — renders a compact mini-dashboard for an entity detail
 * page (node, service, or network). Shows widgets from a tagged dashboard board
 * matching the entity, or falls back to sensible default widgets.
 */

import { useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { LayoutDashboard } from 'lucide-react';
import { toast } from 'sonner';
import { useDashboard, useDashboards } from '@/api/dashboards';
import { useCreateCommand, type CreateCommandRequest } from '@/api/commands';
import { getErrorMessage } from '@/lib/api-client';
import { getWidgetComponent } from '@/components/dashboard/widgets';
import { useWidgetData } from '@/hooks/use-widget-data';
import type { DashboardDataBinding, DashboardWidgetInstance } from '@/types/dashboard';

interface EntityDashboardPanelProps {
  entityType: 'node' | 'service' | 'network';
  entityId: string;
  nodeId?: string;
}

function InlineWidget({
  widget,
  onNavigate,
  onExecuteCommand,
}: {
  widget: DashboardWidgetInstance;
  onNavigate: (path: string) => void;
  onExecuteCommand: (
    commandId: string,
    target: Record<string, unknown>,
    params: Record<string, unknown>,
  ) => Promise<void>;
}) {
  const { data, isLoading, error } = useWidgetData(widget.dataBinding as DashboardDataBinding | null | undefined);
  const Component = getWidgetComponent(widget.widgetType);

  if (!Component) return null;

  return (
    <div className="rounded-xl border border-border/60 bg-card p-4">
      <Component
        config={widget.config}
        data={data}
        isEditing={false}
        isLoading={isLoading}
        error={error}
        dimensions={{ width: 0, height: 0 }}
        onNavigate={onNavigate}
        onExecuteCommand={onExecuteCommand}
      />
    </div>
  );
}

export function EntityDashboardPanel({ entityType, entityId, nodeId }: EntityDashboardPanelProps) {
  const router = useRouter();
  const createCommand = useCreateCommand();

  // Find boards tagged for this entity type and ID; fetch the full board to get widgets
  const dashboardsQuery = useDashboards({ limit: 1, tags: [entityType], search: entityId });
  const taggedBoardId = dashboardsQuery.data?.items?.[0]?.boardId;
  const fullBoardQuery = useDashboard(taggedBoardId ?? '');
  const fullBoard = taggedBoardId ? fullBoardQuery.data : null;

  const widgets = useMemo(() => {
    if (fullBoard?.widgets && fullBoard.widgets.length > 0) {
      return (fullBoard.widgets as DashboardWidgetInstance[]).slice(0, 4);
    }
    // No tagged board found — don't render default widgets since data
    // bindings require matching board configuration to resolve correctly.
    return [];
  }, [fullBoard]);

  const handleNavigate = useCallback(
    (path: string) => router.push(path),
    [router],
  );

  const handleExecuteCommand = useCallback(
    async (
      registryId: string,
      target: Record<string, unknown>,
      params: Record<string, unknown>,
    ) => {
      const targetNodeId = (target.nodeId as string) ?? nodeId;
      if (!registryId || !targetNodeId) {
        toast.error('Missing command or target node');
        return;
      }
      try {
        const req: CreateCommandRequest = {
          registryId,
          target: {
            nodeId: targetNodeId,
            serviceId: (target.serviceId as string) ?? undefined,
          },
          parameters: Object.keys(params).length > 0 ? params : undefined,
        };
        const result = await createCommand.mutateAsync(req);
        if (result.requiresConfirmation) {
          toast.warning('Command requires confirmation', {
            description: result.confirmationMessage ?? `Confirm command ${registryId}`,
          });
        } else {
          toast.success('Command submitted', { description: `Status: ${result.status}` });
        }
      } catch (err) {
        toast.error(getErrorMessage(err, 'Command execution failed'));
      }
    },
    [createCommand, nodeId],
  );

  if (widgets.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <LayoutDashboard className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">Dashboard Widgets</h3>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {widgets.map((widget) => (
          <InlineWidget
            key={widget.instanceId}
            widget={widget}
            onNavigate={handleNavigate}
            onExecuteCommand={handleExecuteCommand}
          />
        ))}
      </div>
    </div>
  );
}
