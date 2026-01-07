import { useParams, useSearchParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Clock,
  GitCompare,
  Plus,
  Minus,
  RefreshCw,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useState } from 'react';
import { useNode } from '@/api/nodes';
import { useProfile, useProfileDiff } from '@/api/profiles';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function ProfileComparePage() {
  const { nodeId } = useParams<{ nodeId: string }>();
  const [searchParams] = useSearchParams();
  const profileAId = searchParams.get('a');
  const profileBId = searchParams.get('b');

  const { data: node, isLoading: nodeLoading } = useNode(nodeId!);
  const { data: profileA, isLoading: profileALoading } = useProfile(profileAId || '');
  const { data: profileB, isLoading: profileBLoading } = useProfile(profileBId || '');
  const { data: diff, isLoading: diffLoading } = useProfileDiff(
    nodeId!,
    profileAId || undefined,
    profileBId || undefined
  );

  const isLoading = nodeLoading || profileALoading || profileBLoading || diffLoading;

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted mb-6" />
        <div className="space-y-6">
          <div className="h-32 animate-pulse rounded-xl bg-muted" />
          <div className="h-64 animate-pulse rounded-xl bg-muted" />
        </div>
      </div>
    );
  }

  if (!node || !profileA || !profileB) {
    return (
      <div className="p-6">
        <Link
          to={`${ROUTES.NODES}/${nodeId}/profiles`}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Profiles
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <GitCompare className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Unable to compare profiles</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Please select two valid profiles to compare
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Link
        to={`${ROUTES.NODES}/${nodeId}/profiles`}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Profile History
      </Link>

      <PageHeader
        title="Profile Comparison"
        description={`Comparing ${profileA.version} to ${profileB.version}`}
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Profile headers comparison */}
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <ProfileCard
              label="From"
              version={profileA.version}
              submittedAt={profileA.submittedAt}
              nodeId={nodeId!}
              profileId={profileAId!}
            />
            <ProfileCard
              label="To"
              version={profileB.version}
              submittedAt={profileB.submittedAt}
              nodeId={nodeId!}
              profileId={profileBId!}
            />
          </div>
        </motion.div>

        {/* Diff summary */}
        {diff && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
              <RefreshCw className="h-5 w-5" />
              Changes Summary
            </h3>

            <div className="grid gap-4 md:grid-cols-4 mb-6">
              <div className="rounded-lg bg-muted/50 p-4 text-center">
                <div className="text-2xl font-bold">{diff.summary?.totalChanges || 0}</div>
                <div className="text-sm text-muted-foreground">Total Changes</div>
              </div>
              {diff.summary?.bySection && Object.entries(diff.summary.bySection).map(([section, count]) => (
                <div key={section} className="rounded-lg bg-muted/50 p-4 text-center">
                  <div className="text-2xl font-bold">{count as number}</div>
                  <div className="text-sm text-muted-foreground capitalize">{section}</div>
                </div>
              ))}
            </div>

            {/* Change list */}
            {diff.changes && diff.changes.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium text-muted-foreground">Detailed Changes</h4>
                <div className="divide-y rounded-lg border overflow-hidden">
                  {diff.changes.map((change, index) => (
                    <DiffEntry key={index} change={change} />
                  ))}
                </div>
              </div>
            )}

            {(!diff.changes || diff.changes.length === 0) && (
              <div className="text-center py-8 text-muted-foreground">
                <GitCompare className="mx-auto h-12 w-12 mb-4 opacity-50" />
                <p>No significant differences found between these profiles</p>
              </div>
            )}
          </motion.div>
        )}

        {/* Side-by-side section comparison */}
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
            <GitCompare className="h-5 w-5" />
            Side-by-Side Comparison
          </h3>

          <SectionComparison
            profileA={{ sections: profileA.sections as unknown as Record<string, unknown> }}
            profileB={{ sections: profileB.sections as unknown as Record<string, unknown> }}
          />
        </motion.div>
      </motion.div>
    </div>
  );
}

function ProfileCard({
  label,
  version,
  submittedAt,
  nodeId,
  profileId,
}: {
  label: string;
  version: string;
  submittedAt: string;
  nodeId: string;
  profileId: string;
}) {
  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Link
          to={`${ROUTES.NODES}/${nodeId}/profiles/${profileId}`}
          className="text-xs text-primary hover:underline"
        >
          View full profile
        </Link>
      </div>
      <div className="font-mono font-medium text-lg">{version}</div>
      <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
        <Clock className="h-3.5 w-3.5" />
        <span>{formatDate(new Date(submittedAt))}</span>
        <span>•</span>
        <span>{formatRelativeTime(new Date(submittedAt))}</span>
      </div>
    </div>
  );
}

function DiffEntry({
  change,
}: {
  change: {
    section: string;
    type: 'added' | 'removed' | 'modified';
    path: string;
    oldValue?: unknown;
    newValue?: unknown;
  };
}) {
  const [expanded, setExpanded] = useState(false);

  const typeColors = {
    added: { bg: 'bg-success/10', text: 'text-success', icon: Plus },
    removed: { bg: 'bg-error/10', text: 'text-error', icon: Minus },
    modified: { bg: 'bg-warning/10', text: 'text-warning', icon: RefreshCw },
  };

  const colors = typeColors[change.type];
  const Icon = colors.icon;

  return (
    <div className="bg-background">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-muted/50 transition-colors text-left"
      >
        <div className={cn('rounded p-1', colors.bg)}>
          <Icon className={cn('h-3.5 w-3.5', colors.text)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium capitalize">{change.section}</span>
            <span className="text-muted-foreground">•</span>
            <span className="text-sm text-muted-foreground font-mono truncate">
              {change.path}
            </span>
          </div>
        </div>
        <span className={cn('text-xs font-medium px-2 py-0.5 rounded', colors.bg, colors.text)}>
          {change.type}
        </span>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-3">
          <div className="grid gap-2 md:grid-cols-2">
            {(change.type === 'removed' || change.type === 'modified') && (
              <div className="rounded-lg bg-error/5 border border-error/20 p-3">
                <div className="text-xs text-error mb-1 font-medium">Old Value</div>
                <pre className="text-xs font-mono overflow-auto max-h-32">
                  {typeof change.oldValue === 'object'
                    ? JSON.stringify(change.oldValue, null, 2)
                    : String(change.oldValue)}
                </pre>
              </div>
            )}
            {(change.type === 'added' || change.type === 'modified') && (
              <div className="rounded-lg bg-success/5 border border-success/20 p-3">
                <div className="text-xs text-success mb-1 font-medium">New Value</div>
                <pre className="text-xs font-mono overflow-auto max-h-32">
                  {typeof change.newValue === 'object'
                    ? JSON.stringify(change.newValue, null, 2)
                    : String(change.newValue)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SectionComparison({
  profileA,
  profileB,
}: {
  profileA: { sections?: Record<string, unknown> | null };
  profileB: { sections?: Record<string, unknown> | null };
}) {
  const allSections = new Set([
    ...Object.keys(profileA.sections || {}),
    ...Object.keys(profileB.sections || {}),
  ]);

  if (allSections.size === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No sections available for comparison
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {Array.from(allSections).map((section) => (
        <SectionComparisonRow
          key={section}
          section={section}
          dataA={profileA.sections?.[section]}
          dataB={profileB.sections?.[section]}
        />
      ))}
    </div>
  );
}

function SectionComparisonRow({
  section,
  dataA,
  dataB,
}: {
  section: string;
  dataA: unknown;
  dataB: unknown;
}) {
  const [expanded, setExpanded] = useState(false);

  const hasA = dataA !== undefined;
  const hasB = dataB !== undefined;
  const isDifferent = JSON.stringify(dataA) !== JSON.stringify(dataB);

  return (
    <div className="rounded-lg border overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-muted/50 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <span className="font-medium capitalize">{section}</span>
        <div className="flex-1" />
        {!hasA && hasB && (
          <span className="text-xs font-medium px-2 py-0.5 rounded bg-success/10 text-success">
            Added
          </span>
        )}
        {hasA && !hasB && (
          <span className="text-xs font-medium px-2 py-0.5 rounded bg-error/10 text-error">
            Removed
          </span>
        )}
        {hasA && hasB && isDifferent && (
          <span className="text-xs font-medium px-2 py-0.5 rounded bg-warning/10 text-warning">
            Modified
          </span>
        )}
        {hasA && hasB && !isDifferent && (
          <span className="text-xs font-medium px-2 py-0.5 rounded bg-muted text-muted-foreground">
            Unchanged
          </span>
        )}
      </button>

      {expanded && (
        <div className="border-t grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x">
          <div className="p-3">
            <div className="text-xs text-muted-foreground mb-2 font-medium">Profile A</div>
            <pre className="text-xs font-mono overflow-auto max-h-64 bg-muted/30 rounded p-2">
              {hasA ? JSON.stringify(dataA, null, 2) : '(not present)'}
            </pre>
          </div>
          <div className="p-3">
            <div className="text-xs text-muted-foreground mb-2 font-medium">Profile B</div>
            <pre className="text-xs font-mono overflow-auto max-h-64 bg-muted/30 rounded p-2">
              {hasB ? JSON.stringify(dataB, null, 2) : '(not present)'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
