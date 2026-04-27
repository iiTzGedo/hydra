/**
 * ServiceControlWidget -- three action buttons (Start, Stop, Restart)
 * for controlling a service. Executes commands via the onExecuteCommand callback.
 *
 * Config: { serviceId: string; nodeId: string }
 */

import { useState } from 'react';
import { Loader2, Play, Square, RotateCw, Power } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ServiceControlConfig extends Record<string, unknown> {
  serviceId?: string;
  nodeId?: string;
}

const ACTIONS = [
  { label: 'Start', registryId: 'reg::service::start', Icon: Play, color: 'text-emerald-500', hoverBg: 'hover:bg-emerald-500/10', borderColor: 'border-emerald-500/30' },
  { label: 'Stop', registryId: 'reg::service::stop', Icon: Square, color: 'text-red-500', hoverBg: 'hover:bg-red-500/10', borderColor: 'border-red-500/30' },
  { label: 'Restart', registryId: 'reg::service::restart', Icon: RotateCw, color: 'text-blue-500', hoverBg: 'hover:bg-blue-500/10', borderColor: 'border-blue-500/30' },
] as const;

export function ServiceControlWidget({
  config,
  isLoading,
  isEditing,
  error,
  readonly,
  onExecuteCommand,
}: WidgetComponentProps<unknown, ServiceControlConfig>) {
  const [executingAction, setExecutingAction] = useState<string | null>(null);

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const serviceId = config.serviceId;
  const nodeId = config.nodeId;
  const canExecute = !!serviceId && !!nodeId && !!onExecuteCommand && !isEditing && !readonly;

  async function handleAction(registryId: string) {
    if (!canExecute) return;
    setExecutingAction(registryId);
    try {
      await onExecuteCommand!(registryId, { nodeId: nodeId!, serviceId }, {});
    } finally {
      setExecutingAction(null);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 p-1">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Power className="h-4 w-4 text-muted-foreground" />
        <span className="truncate text-sm font-semibold">Service Control</span>
      </div>

      {/* Service ID */}
      <div className="rounded-md bg-muted/30 px-2 py-1">
        <span className="font-mono text-xs text-muted-foreground">
          {serviceId ?? 'No service configured'}
        </span>
      </div>

      {/* Action buttons */}
      <div className="flex flex-1 items-center justify-center gap-3">
        {ACTIONS.map(({ label, registryId, Icon, color, hoverBg, borderColor }) => {
          const isExecuting = executingAction === registryId;
          return (
            <button
              key={label}
              type="button"
              disabled={!canExecute || !!executingAction}
              onClick={() => void handleAction(registryId)}
              title={readonly ? 'Read-only in kiosk mode' : canExecute ? label : 'Configure serviceId and nodeId in widget settings'}
              className={`flex flex-col items-center gap-1.5 rounded-xl border ${borderColor} px-4 py-3 transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${hoverBg}`}
            >
              {isExecuting ? (
                <Loader2 className={`h-5 w-5 animate-spin ${color}`} />
              ) : (
                <Icon className={`h-5 w-5 ${color}`} />
              )}
              <span className="text-[10px] font-medium text-muted-foreground">
                {isExecuting ? '...' : label}
              </span>
            </button>
          );
        })}
      </div>

      {!serviceId && (
        <div className="text-center text-[10px] text-amber-600">
          Configure serviceId and nodeId in widget settings
        </div>
      )}
    </div>
  );
}
