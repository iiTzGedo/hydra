/**
 * Placeholder widget for types that are registered but not yet fully
 * implemented (e.g., Wave 3+ features like command execution or MCP).
 *
 * Shows the widget type label and a "Coming soon" indicator.
 * When a required plugin is missing, shows "Requires {plugin} plugin".
 */

import { Construction } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';

interface PlaceholderConfig {
  __widgetType?: string;
  __requiredPlugin?: string;
  __blockedBy?: string;
}

export function WidgetPlaceholder({ config }: WidgetComponentProps) {
  const { __widgetType, __requiredPlugin, __blockedBy } = config as PlaceholderConfig;
  const label = __widgetType?.replace('hydra::', '').replace(/-/g, ' ') ?? 'Widget';

  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
      <Construction className="h-5 w-5" />
      <div className="text-sm font-medium capitalize">{label}</div>
      {__requiredPlugin ? (
        <div className="text-xs">Requires {__requiredPlugin} plugin</div>
      ) : __blockedBy ? (
        <div className="text-xs">{__blockedBy}</div>
      ) : (
        <div className="text-xs">Coming soon</div>
      )}
    </div>
  );
}
