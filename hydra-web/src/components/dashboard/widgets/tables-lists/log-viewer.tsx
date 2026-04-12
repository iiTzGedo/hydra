/**
 * LogViewerWidget
 *
 * Scrollable monospace log viewer with color-coded severity levels.
 * Renders log lines in a pre-formatted container with max height
 * and overflow scrolling for large log outputs.
 */

import { Terminal } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface LogLine {
  level: string;
  message: string;
  timestamp?: string;
}

interface LogViewerData {
  lines: LogLine[];
}

const LEVEL_CLASSES: Record<string, string> = {
  error: 'text-red-500',
  err: 'text-red-500',
  fatal: 'text-red-500',
  warn: 'text-yellow-500',
  warning: 'text-yellow-500',
  info: 'text-foreground',
  debug: 'text-muted-foreground',
  trace: 'text-muted-foreground/60',
};

function getLevelClass(level: string): string {
  return LEVEL_CLASSES[level.toLowerCase()] ?? 'text-foreground';
}

function getLevelBadgeClass(level: string): string {
  switch (level.toLowerCase()) {
    case 'error':
    case 'err':
    case 'fatal':
      return 'text-red-500 bg-red-500/10';
    case 'warn':
    case 'warning':
      return 'text-yellow-500 bg-yellow-500/10';
    case 'debug':
    case 'trace':
      return 'text-muted-foreground bg-muted';
    default:
      return 'text-blue-500 bg-blue-500/10';
  }
}

export function LogViewerWidget({
  data,
  config: _config,
  isLoading,
  error,
}: WidgetComponentProps<LogViewerData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data === null || data === undefined) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Terminal className="h-5 w-5" />
        <div className="text-sm">No log data</div>
      </div>
    );
  }

  if (!data.lines || data.lines.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Terminal className="h-5 w-5" />
        <div className="text-sm">No log entries</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-md border border-border/60 bg-slate-950/80 dark:bg-slate-950/60">
      {/* Header bar */}
      <div className="flex items-center gap-2 border-b border-border/40 bg-muted/10 px-3 py-1.5">
        <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">
          {data.lines.length} line{data.lines.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Log content */}
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        <pre className="font-mono text-xs leading-5">
          {data.lines.map((line, idx) => (
            <div key={idx} className="flex gap-2 hover:bg-white/5 px-1 rounded">
              {/* Line number */}
              <span className="flex-shrink-0 w-8 text-right text-muted-foreground/40 select-none tabular-nums">
                {idx + 1}
              </span>

              {/* Timestamp */}
              {line.timestamp && (
                <span className="flex-shrink-0 text-muted-foreground/60 tabular-nums">
                  {line.timestamp}
                </span>
              )}

              {/* Level badge */}
              <span
                className={`flex-shrink-0 inline-block w-12 text-center rounded px-1 text-[10px] font-semibold uppercase ${getLevelBadgeClass(line.level)}`}
              >
                {line.level}
              </span>

              {/* Message */}
              <span className={`min-w-0 break-all ${getLevelClass(line.level)}`}>
                {line.message}
              </span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
