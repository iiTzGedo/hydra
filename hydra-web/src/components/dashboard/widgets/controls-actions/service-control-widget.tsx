/**
 * ServiceControlWidget -- three action buttons (Start, Stop, Restart)
 * for controlling a service. Placeholder for Wave 3 command execution.
 *
 * Config: { serviceId: string }
 *
 * All buttons are disabled with a tooltip explaining that command execution
 * infrastructure is required.
 */

import { Play, Square, RotateCw, Power } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ServiceControlConfig extends Record<string, unknown> {
  serviceId?: string;
}

const ACTIONS = [
  { label: 'Start', Icon: Play, color: 'text-emerald-500', hoverBg: 'hover:bg-emerald-500/5' },
  { label: 'Stop', Icon: Square, color: 'text-red-500', hoverBg: 'hover:bg-red-500/5' },
  { label: 'Restart', Icon: RotateCw, color: 'text-blue-500', hoverBg: 'hover:bg-blue-500/5' },
] as const;

export function ServiceControlWidget({
  config,
  isLoading,
  error,
}: WidgetComponentProps<unknown, ServiceControlConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const serviceId = config.serviceId ?? 'No service configured';

  return (
    <div className="flex h-full flex-col gap-3 p-1">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Power className="h-4 w-4 text-muted-foreground" />
        <span className="truncate text-sm font-semibold">Service Control</span>
      </div>

      {/* Service ID */}
      <div className="rounded-md bg-muted/30 px-2 py-1">
        <span className="font-mono text-xs text-muted-foreground">{serviceId}</span>
      </div>

      {/* Action buttons */}
      <div className="flex flex-1 items-center justify-center gap-3">
        {ACTIONS.map(({ label, Icon, color, hoverBg }) => (
          <button
            key={label}
            type="button"
            disabled
            title="Command execution required"
            className={`flex flex-col items-center gap-1.5 rounded-xl border border-border/60 px-4 py-3 transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${hoverBg}`}
          >
            <Icon className={`h-5 w-5 ${color}`} />
            <span className="text-[10px] font-medium text-muted-foreground">
              {label}
            </span>
          </button>
        ))}
      </div>

      {/* Wave 3 notice */}
      <div className="text-center text-[10px] text-muted-foreground/60">
        Available after command integration
      </div>
    </div>
  );
}
