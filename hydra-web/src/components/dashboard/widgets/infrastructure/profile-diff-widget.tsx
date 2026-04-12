/**
 * ProfileDiffWidget -- displays a simplified before/after comparison of two
 * profile versions with collapsible sections.
 *
 * Data shape:
 *   { leftVersion: string; rightVersion: string;
 *     sections: { name: string; changes: { field: string; before: string;
 *     after: string }[] }[] }
 *
 * Sections are rendered as collapsible groups with individual field-level diffs.
 */

import { useState } from 'react';
import { GitCompare, ChevronDown, ChevronRight, ArrowRight } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface ProfileDiffChange {
  field: string;
  before: string;
  after: string;
}

interface ProfileDiffSection {
  name: string;
  changes: ProfileDiffChange[];
}

interface ProfileDiffData {
  leftVersion: string;
  rightVersion: string;
  sections: ProfileDiffSection[];
}

export function ProfileDiffWidget({
  data,
  isLoading,
  error,
}: WidgetComponentProps<ProfileDiffData>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  if (data == null) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <GitCompare className="h-5 w-5" />
        <div className="text-sm">Select two profile versions to compare</div>
      </div>
    );
  }

  const totalChanges = data.sections.reduce(
    (sum, section) => sum + section.changes.length,
    0,
  );

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-1">
      {/* Header */}
      <div className="flex items-center gap-2">
        <GitCompare className="h-4 w-4 text-muted-foreground" />
        <span className="rounded bg-red-500/10 px-1.5 py-0.5 font-mono text-xs font-medium text-red-600">
          {data.leftVersion}
        </span>
        <ArrowRight className="h-3 w-3 text-muted-foreground" />
        <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 font-mono text-xs font-medium text-emerald-600">
          {data.rightVersion}
        </span>
        <span className="ml-auto text-xs text-muted-foreground">
          {totalChanges} change{totalChanges !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Sections */}
      {data.sections.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
          No differences found
        </div>
      ) : (
        <div className="space-y-1">
          {data.sections.map((section) => (
            <CollapsibleSection key={section.name} section={section} />
          ))}
        </div>
      )}
    </div>
  );
}

function CollapsibleSection({ section }: { section: ProfileDiffSection }) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="rounded-lg border border-border/60">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs font-semibold hover:bg-muted/40"
        onClick={() => setIsOpen((prev) => !prev)}
      >
        {isOpen ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        )}
        <span className="flex-1 capitalize">{section.name}</span>
        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          {section.changes.length}
        </span>
      </button>

      {isOpen && (
        <div className="border-t border-border/40">
          {section.changes.map((change) => (
            <div
              key={`${section.name}-${change.field}`}
              className="border-b border-border/20 px-2.5 py-1.5 last:border-b-0"
            >
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                {change.field}
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="overflow-hidden rounded bg-red-500/5 px-1.5 py-1">
                  <span className="break-all font-mono text-red-600">
                    {change.before || '\u2014'}
                  </span>
                </div>
                <div className="overflow-hidden rounded bg-emerald-500/5 px-1.5 py-1">
                  <span className="break-all font-mono text-emerald-600">
                    {change.after || '\u2014'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
