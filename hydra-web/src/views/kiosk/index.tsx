/**
 * KioskPage — renders a dashboard board in full-screen kiosk mode without
 * sidebar, header, or edit controls. Authenticates via a ?token= query
 * parameter — no session cookie required.
 *
 * Features preserved from authenticated kiosk:
 *   - Auto-scroll (bounce) when kioskAutoScroll is true
 *   - Screen wake lock to prevent display sleep
 *   - Background image / custom CSS from board settings
 *   - Deauthorized fallback on missing or invalid token
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useKioskBoard } from '@/api/dashboards';
import { useCreateCommand } from '@/api/commands';
import { getErrorMessage } from '@/lib/api-client';
import { getWidgetComponent } from '@/components/dashboard/widgets';
import {
  WidgetGrid,
  Widget,
  widgetTypeLabel,
} from '@/components/dashboard/widget-grid';
import { useWidgetData } from '@/hooks/use-widget-data';
import { HydraIcon } from '@/components/icons/hydra-icon';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { toast } from 'sonner';
import type {
  DashboardBoardLayout,
  DashboardBoardSettings,
  DashboardDataBinding,
  DashboardWidgetInstance,
} from '@/types/dashboard';

function normalizeBoardLayout(layout: DashboardBoardLayout | undefined): DashboardBoardLayout {
  if (!layout) {
    return {
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
        padding: [16, 16],
      },
    };
  }
  return layout;
}

function getTextConfig(config: Record<string, unknown>, key: string): string | undefined {
  const value = config[key];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

/** Shown when the token is missing or the API rejects it. */
function Deauthorized({ reason }: { reason: string }) {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center gap-4 bg-background text-foreground">
      <h1 className="text-2xl font-semibold">Kiosk unavailable</h1>
      <p className="text-muted-foreground">{reason}</p>
    </div>
  );
}

function KioskWidgetContent({
  widgetType,
  config,
  dataBinding,
  readonly,
  onExecuteCommand,
}: {
  widgetType: string;
  config: Record<string, unknown>;
  dataBinding?: DashboardDataBinding | null;
  readonly?: boolean;
  onExecuteCommand: (
    commandId: string,
    target: Record<string, unknown>,
    params: Record<string, unknown>,
  ) => Promise<void>;
}) {
  const { data, isLoading, error } = useWidgetData(dataBinding);
  const Component = getWidgetComponent(widgetType);

  if (!Component) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Unknown widget: {widgetType}
      </div>
    );
  }

  return (
    <Component
      config={{ ...config, __widgetType: widgetType }}
      data={data}
      isEditing={false}
      isLoading={isLoading}
      error={error}
      dimensions={{ width: 0, height: 0 }}
      readonly={readonly}
      onExecuteCommand={onExecuteCommand}
    />
  );
}

export default function KioskPage() {
  const { boardId } = useParams<{ boardId: string }>()!;
  const searchParams = useSearchParams();
  const scrollRef = useRef<HTMLDivElement>(null);
  const animationRef = useRef<number | null>(null);

  const token = searchParams?.get('token') ?? null;

  const { data: board, isLoading, isError } = useKioskBoard(boardId ?? '', token);
  const createCommand = useCreateCommand();

  const settings = (board?.settings ?? {}) as DashboardBoardSettings;
  const autoScroll = settings.kioskAutoScroll ?? false;
  const scrollSpeed = settings.kioskScrollSpeed ?? 30; // px/s

  const layout = useMemo(
    () => normalizeBoardLayout(board?.layout as DashboardBoardLayout | undefined),
    [board?.layout],
  );

  const visibleWidgets = useMemo(
    () =>
      ((board?.widgets ?? []) as DashboardWidgetInstance[]).filter(
        (w) => !(w.config as { hidden?: boolean })?.hidden,
      ),
    [board?.widgets],
  );

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
          target: { nodeId, serviceId: (target.serviceId as string) ?? undefined },
          parameters: Object.keys(params).length > 0 ? params : undefined,
        });
        if (result.requiresConfirmation) {
          toast.warning('Command requires confirmation');
        } else {
          toast.success(`Command: ${result.status}`);
        }
      } catch (err) {
        toast.error(getErrorMessage(err, 'Command failed'));
      }
    },
    [createCommand],
  );

  // Auto-scroll effect (bounce between top and bottom)
  useEffect(() => {
    if (!autoScroll || !scrollRef.current) return;

    const container = scrollRef.current;
    let lastTime = performance.now();
    let direction = 1; // 1 = down, -1 = up

    function step(now: number) {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      container.scrollTop += direction * scrollSpeed * dt;

      const maxScroll = container.scrollHeight - container.clientHeight;
      if (container.scrollTop >= maxScroll) {
        direction = -1;
      } else if (container.scrollTop <= 0) {
        direction = 1;
      }

      animationRef.current = requestAnimationFrame(step);
    }

    animationRef.current = requestAnimationFrame(step);

    return () => {
      if (animationRef.current !== null) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [autoScroll, scrollSpeed]);

  // Request wake lock to prevent display sleep on kiosk screens
  useEffect(() => {
    let wakeLock: WakeLockSentinel | null = null;

    async function requestWakeLock() {
      try {
        if ('wakeLock' in navigator) {
          wakeLock = await navigator.wakeLock.request('screen');
        }
      } catch {
        // Wake lock not supported or denied — non-critical
      }
    }

    void requestWakeLock();

    return () => {
      void wakeLock?.release();
    };
  }, []);

  // Guard: token must be present in the URL
  if (!token) {
    return <Deauthorized reason="Missing kiosk token" />;
  }

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (isError || !board) {
    return <Deauthorized reason="This display has been deauthorized" />;
  }

  return (
    <div
      ref={scrollRef}
      className="h-screen w-screen overflow-auto bg-background text-foreground"
      style={{
        backgroundImage: settings.backgroundImage ? `url(${settings.backgroundImage})` : undefined,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {settings.customCss && (
        <style dangerouslySetInnerHTML={{ __html: settings.customCss }} />
      )}

      <div className="mx-auto max-w-[1920px] p-4">
        <WidgetGrid
          widgets={visibleWidgets}
          layout={layout}
          isEditMode={false}
          rowHeight={layout.mode === 'grid' ? layout.grid.rowHeight : 80}
        >
          {visibleWidgets.map((widget) => (
            <Widget
              key={widget.instanceId}
              id={widget.instanceId}
              title={getTextConfig(widget.config, 'title') ?? widgetTypeLabel(widget.widgetType)}
              description={getTextConfig(widget.config, 'subtitle')}
              icon={<HydraIcon fallback={widget.widgetType.replace('hydra::', '')} size={16} />}
              isEditMode={false}
            >
              <KioskWidgetContent
                widgetType={widget.widgetType}
                config={widget.config}
                dataBinding={widget.dataBinding as DashboardDataBinding | null | undefined}
                readonly={widget.readonly}
                onExecuteCommand={handleExecuteCommand}
              />
            </Widget>
          ))}
        </WidgetGrid>
      </div>
    </div>
  );
}
