import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Clock, GitCompare, Eye, ChevronRight } from 'lucide-react';
import { useNode } from '@/api/nodes';
import { useNodeProfiles } from '@/api/profiles';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function NodeProfilesPage() {
  const { nodeId } = useParams<{ nodeId: string }>();
  const { data: node, isLoading: nodeLoading } = useNode(nodeId!);
  const { data: profiles, isLoading: profilesLoading } = useNodeProfiles(nodeId!);
  const [selectedProfiles, setSelectedProfiles] = useState<string[]>([]);

  const isLoading = nodeLoading || profilesLoading;

  const toggleProfileSelection = (profileId: string) => {
    setSelectedProfiles((prev) => {
      if (prev.includes(profileId)) {
        return prev.filter((id) => id !== profileId);
      }
      if (prev.length >= 2) {
        return [prev[1], profileId];
      }
      return [...prev, profileId];
    });
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted mb-6" />
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      </div>
    );
  }

  if (!node) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.NODES}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Nodes
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <Clock className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Node not found</h3>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Link
        to={ROUTES.NODES + '/' + nodeId}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to {node.id}
      </Link>

      <PageHeader
        title="Profile History"
        description={`Version history for ${node.id}`}
        actions={
          selectedProfiles.length === 2 && (
            <Link
              to={`${ROUTES.NODES}/${nodeId}/profiles/compare?a=${selectedProfiles[0]}&b=${selectedProfiles[1]}`}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors'
              )}
            >
              <GitCompare className="h-4 w-4" />
              Compare Selected
            </Link>
          )
        }
      />

      {selectedProfiles.length > 0 && selectedProfiles.length < 2 && (
        <div className="mb-4 rounded-lg bg-muted p-3 text-sm">
          Select one more profile to compare
        </div>
      )}

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-4"
      >
        {!profiles?.items?.length ? (
          <div className="rounded-xl border bg-card p-8 text-center">
            <Clock className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No profiles yet</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Profiles will appear here once the agent reports them
            </p>
          </div>
        ) : (
          <div className="relative">
            <div className="absolute left-[23px] top-0 bottom-0 w-0.5 bg-border" />

            {profiles.items.map((profile, index) => {
              const profileKey = profile.profileId;
              return (
              <motion.div
                key={profileKey}
                variants={staggerItemVariants}
                className="relative pl-12 pb-6 last:pb-0"
              >
                <div
                  className={cn(
                    'absolute left-4 top-2 h-4 w-4 rounded-full border-2 bg-background',
                    index === 0 ? 'border-primary' : 'border-muted-foreground'
                  )}
                />

                <div
                  className={cn(
                    'rounded-xl border bg-card p-4 shadow-sm transition-all',
                    selectedProfiles.includes(profileKey)
                      ? 'ring-2 ring-primary'
                      : 'hover:border-primary/50'
                  )}
                >
                  <div className="flex items-start gap-4">
                    <button
                      onClick={() => toggleProfileSelection(profileKey)}
                      aria-label={`Select profile ${profile.version}`}
                      aria-pressed={selectedProfiles.includes(profileKey)}
                      className={cn(
                        'mt-1 h-5 w-5 rounded border-2 flex items-center justify-center transition-colors',
                        selectedProfiles.includes(profileKey)
                          ? 'bg-primary border-primary'
                          : 'border-muted-foreground hover:border-primary'
                      )}
                    >
                      {selectedProfiles.includes(profileKey) && (
                        <svg
                          className="h-3 w-3 text-white"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={3}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      )}
                    </button>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="font-mono font-medium">{profile.version}</span>
                        {index === 0 && (
                          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                            Latest
                          </span>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                        <span>{formatDate(new Date(profile.submittedAt))}</span>
                        <span>•</span>
                        <span>{formatRelativeTime(new Date(profile.submittedAt))}</span>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="rounded-full bg-muted px-2 py-0.5 text-xs capitalize">
                          {profile.collectionLevel || 'neutral'}
                        </span>
                      </div>
                    </div>

                    <Link
                      to={`${ROUTES.NODES}/${nodeId}/profile/${profileKey}`}
                      className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                    >
                      <Eye className="h-4 w-4" />
                      View
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  </div>
                </div>
              </motion.div>
              );
            })}
          </div>
        )}
      </motion.div>
    </div>
  );
}
