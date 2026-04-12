/**
 * Standard error display for widget data binding failures.
 */

import { AlertTriangle } from 'lucide-react';

interface WidgetErrorStateProps {
  error: Error | null;
  message?: string;
}

export function WidgetErrorState({ error, message }: WidgetErrorStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
      <AlertTriangle className="h-5 w-5 text-destructive/70" />
      <div className="text-sm font-medium">
        {message ?? 'Failed to load data'}
      </div>
      {error?.message ? (
        <div className="max-w-[80%] truncate text-xs text-muted-foreground/70">
          {error.message}
        </div>
      ) : null}
    </div>
  );
}
