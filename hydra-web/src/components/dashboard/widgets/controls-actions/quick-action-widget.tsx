/**
 * QuickActionWidget -- displays a styled action button with icon and label.
 * Executes commands via the onExecuteCommand callback.
 *
 * Config: { label: string; icon?: string; commandId: string; nodeId: string }
 */

import { useState } from 'react';
import { Loader2, Zap } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface QuickActionConfig extends Record<string, unknown> {
  label?: string;
  icon?: string;
  commandId?: string;
  nodeId?: string;
}

export function QuickActionWidget({
  config,
  isLoading,
  isEditing,
  error,
  onExecuteCommand,
}: WidgetComponentProps<unknown, QuickActionConfig>) {
  const [executing, setExecuting] = useState(false);

  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const label = config.label ?? 'Quick Action';
  const canExecute = !!config.commandId && !!config.nodeId && !!onExecuteCommand && !isEditing;

  async function handleClick() {
    if (!canExecute) return;
    setExecuting(true);
    try {
      await onExecuteCommand!(
        config.commandId!,
        { nodeId: config.nodeId! },
        {},
      );
    } finally {
      setExecuting(false);
    }
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-2">
      <button
        type="button"
        disabled={!canExecute || executing}
        onClick={() => void handleClick()}
        className="flex items-center gap-2.5 rounded-xl border border-primary/30 bg-primary/5 px-5 py-3 text-sm font-medium shadow-sm transition-all hover:bg-primary/10 hover:shadow active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {executing ? (
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
        ) : (
          <Zap className="h-4 w-4 text-primary" />
        )}
        <span>{executing ? 'Running...' : label}</span>
      </button>
      {config.commandId && (
        <span className="text-[10px] text-muted-foreground">
          cmd: {config.commandId}
        </span>
      )}
      {!config.commandId && (
        <span className="text-[10px] text-amber-600">
          Configure a commandId in widget settings
        </span>
      )}
    </div>
  );
}
