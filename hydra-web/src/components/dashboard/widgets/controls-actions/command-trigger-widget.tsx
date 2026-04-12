/**
 * CommandTriggerWidget -- displays a command trigger button with parameter
 * input fields. Placeholder for Wave 3 command execution integration.
 *
 * Config: { label: string; commandId: string; params?: Record<string, string> }
 *
 * Currently renders a disabled form indicating that command triggers require
 * the Wave 3 command execution infrastructure.
 */

import { Terminal } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface CommandTriggerConfig extends Record<string, unknown> {
  label?: string;
  commandId?: string;
  params?: Record<string, string>;
}

export function CommandTriggerWidget({
  config,
  isLoading,
  error,
}: WidgetComponentProps<unknown, CommandTriggerConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const label = config.label ?? 'Command Trigger';
  const params = config.params ?? {};
  const paramKeys = Object.keys(params);

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-1">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Terminal className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold">{label}</span>
        <span className="ml-auto rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-600">
          Wave 3
        </span>
      </div>

      {/* Parameter fields */}
      {paramKeys.length > 0 && (
        <div className="space-y-2">
          {paramKeys.map((key) => (
            <div key={key} className="space-y-1">
              <label className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                {key}
              </label>
              <input
                type="text"
                disabled
                placeholder={params[key] ?? ''}
                className="w-full rounded-md border border-border/60 bg-muted/30 px-2 py-1 text-xs text-muted-foreground placeholder:text-muted-foreground/50"
              />
            </div>
          ))}
        </div>
      )}

      {/* Trigger button */}
      <div className="mt-auto">
        <button
          type="button"
          disabled
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-border/60 bg-muted/30 px-3 py-2 text-xs font-medium text-muted-foreground"
          title="Command execution required"
        >
          <Terminal className="h-3.5 w-3.5" />
          Command trigger — Wave 3
        </button>
      </div>

      {config.commandId && (
        <span className="text-center text-[10px] text-muted-foreground/60">
          cmd: {config.commandId}
        </span>
      )}
    </div>
  );
}
