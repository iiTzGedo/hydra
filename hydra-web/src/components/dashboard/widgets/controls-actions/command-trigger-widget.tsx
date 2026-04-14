/**
 * CommandTriggerWidget -- displays a command trigger button with parameter
 * input fields. Executes commands via the onExecuteCommand callback.
 *
 * Config: { label: string; commandId: string; nodeId: string; params?: Record<string, string> }
 */

import { useState } from 'react';
import { Loader2, Terminal } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface CommandTriggerConfig extends Record<string, unknown> {
  label?: string;
  commandId?: string;
  nodeId?: string;
  params?: Record<string, string>;
}

export function CommandTriggerWidget({
  config,
  isLoading,
  isEditing,
  error,
  onExecuteCommand,
}: WidgetComponentProps<unknown, CommandTriggerConfig>) {
  const paramDefaults = config.params ?? {};
  const [paramValues, setParamValues] = useState<Record<string, string>>(() => ({ ...paramDefaults }));
  const [executing, setExecuting] = useState(false);

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const label = config.label ?? 'Command Trigger';
  const paramKeys = Object.keys(paramDefaults);
  const canExecute = !!config.commandId && !!config.nodeId && !!onExecuteCommand && !isEditing;

  async function handleExecute() {
    if (!canExecute) return;
    setExecuting(true);
    try {
      await onExecuteCommand!(
        config.commandId!,
        { nodeId: config.nodeId! },
        paramValues,
      );
    } finally {
      setExecuting(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-1">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Terminal className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold">{label}</span>
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
                value={paramValues[key] ?? ''}
                disabled={!canExecute || executing}
                placeholder={paramDefaults[key] ?? ''}
                onChange={(e) => setParamValues((prev) => ({ ...prev, [key]: e.target.value }))}
                className="w-full rounded-md border border-border/60 bg-muted/30 px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground/50 disabled:opacity-50"
              />
            </div>
          ))}
        </div>
      )}

      {/* Trigger button */}
      <div className="mt-auto">
        <button
          type="button"
          disabled={!canExecute || executing}
          onClick={() => void handleExecute()}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {executing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Terminal className="h-3.5 w-3.5" />
          )}
          {executing ? 'Executing...' : 'Execute'}
        </button>
      </div>

      {config.commandId && (
        <span className="text-center text-[10px] text-muted-foreground/60">
          cmd: {config.commandId}
        </span>
      )}

      {!config.commandId && (
        <span className="text-center text-[10px] text-amber-600">
          Configure a commandId in widget settings
        </span>
      )}
    </div>
  );
}
