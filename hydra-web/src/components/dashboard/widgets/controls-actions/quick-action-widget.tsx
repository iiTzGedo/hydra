/**
 * QuickActionWidget -- displays a styled action button with icon and label.
 * Placeholder for Wave 3 command execution integration.
 *
 * Config: { label: string; icon?: string; commandId: string }
 *
 * Currently shows a toast notification indicating command execution is
 * not yet available. The onExecuteCommand callback will be wired in Wave 3.
 */

import { Zap } from 'lucide-react';
import { toast } from 'sonner';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface QuickActionConfig extends Record<string, unknown> {
  label?: string;
  icon?: string;
  commandId?: string;
}

export function QuickActionWidget({
  config,
  isLoading,
  error,
}: WidgetComponentProps<unknown, QuickActionConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const label = config.label ?? 'Quick Action';

  function handleClick() {
    toast.info('Command execution coming in Wave 3', {
      description: config.commandId
        ? `Command: ${config.commandId}`
        : 'Configure a command ID in widget settings.',
    });
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-2">
      <button
        type="button"
        onClick={handleClick}
        className="flex items-center gap-2.5 rounded-xl border border-border/60 bg-primary/5 px-5 py-3 text-sm font-medium shadow-sm transition-all hover:bg-primary/10 hover:shadow active:scale-[0.98]"
      >
        <Zap className="h-4 w-4 text-primary" />
        <span>{label}</span>
      </button>
      {config.commandId && (
        <span className="text-[10px] text-muted-foreground">
          cmd: {config.commandId}
        </span>
      )}
    </div>
  );
}
