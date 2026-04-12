/**
 * ProfileTimelineWidget -- vertical timeline of profile versions for a node,
 * displayed as dots on a vertical line with version labels and timestamps.
 *
 * Data shape:
 *   { versions: { version: string; submittedAt: string;
 *     changesSummary?: string }[] }
 *
 * Config: { nodeId: string }
 */

import { GitCommitVertical } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ProfileVersion {
  version: string;
  submittedAt: string;
  changesSummary?: string;
}

interface ProfileTimelineData {
  versions: ProfileVersion[];
}

interface ProfileTimelineConfig extends Record<string, unknown> {
  nodeId?: string;
}

function formatTimestamp(isoString: string): string {
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return isoString;
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function ProfileTimelineWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<ProfileTimelineData, ProfileTimelineConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null || data.versions.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <GitCommitVertical className="h-5 w-5" />
        <div className="text-sm">No profile versions</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-auto p-1">
      <div className="relative pl-5">
        {/* Vertical line */}
        <div className="absolute bottom-0 left-[7px] top-0 w-px bg-border" />

        {data.versions.map((entry, index) => (
          <div key={`${entry.version}-${index}`} className="relative pb-4 last:pb-0">
            {/* Dot */}
            <div className="absolute left-[-13px] top-1 h-3 w-3 rounded-full border-2 border-primary bg-background" />

            {/* Content */}
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-xs font-semibold text-primary">
                  {entry.version}
                </span>
                <span className="text-[10px] text-muted-foreground tabular-nums">
                  {formatTimestamp(entry.submittedAt)}
                </span>
              </div>
              {entry.changesSummary && (
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {entry.changesSummary}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
