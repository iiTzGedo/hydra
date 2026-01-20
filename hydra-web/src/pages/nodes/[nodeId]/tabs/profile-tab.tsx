import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Cpu,
  HardDrive,
  Wifi,
  Package,
  FileText,
  History,
  GitCompare,
  Eye,
  X,
  Plus,
  Minus,
  ArrowRight,
  CalendarClock,
  Layers,
} from 'lucide-react';
import { useLatestProfile, useNodeProfiles, useProfile, useProfileDiff } from '@/api/profiles';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime, formatBytes } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/common/empty-state';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { Profile, ProfileSummary, ProfileDiff } from '@/types/profile';

interface ProfileTabProps {
  nodeId: string;
}

// Helper to get sections that have data
function getSectionsWithData(profile: Profile): string[] {
  const sections: string[] = [];
  if (profile.hardware) sections.push('hardware');
  if (profile.network) sections.push('network');
  if (profile.storage) sections.push('storage');
  if (profile.software) sections.push('software');
  if (profile.serviceIds && profile.serviceIds.length > 0) sections.push('services');
  if (profile.users) sections.push('users');
  if (profile.configs) sections.push('configs');
  return sections;
}

export function ProfileTab({ nodeId }: ProfileTabProps) {
  const [selectedProfiles, setSelectedProfiles] = useState<string[]>([]);

  const { data: latestProfile, isLoading: latestLoading } = useLatestProfile(nodeId);
  const { data: profilesData, isLoading: historyLoading } = useNodeProfiles(nodeId, { limit: 50 });

  const profileItems = profilesData?.items ?? [];

  const firstSelectedId = selectedProfiles[0];
  const secondSelectedId = selectedProfiles[1];

  const { data: firstProfile } = useProfile(firstSelectedId || '');
  const { data: secondProfile } = useProfile(secondSelectedId || '');

  const isDiffMode = selectedProfiles.length === 2;

  // Get versions from profile summaries for diff comparison
  const firstVersion = useMemo(() => {
    const profile = profileItems.find(p => p.profileId === firstSelectedId);
    return profile?.version;
  }, [profileItems, firstSelectedId]);

  const secondVersion = useMemo(() => {
    const profile = profileItems.find(p => p.profileId === secondSelectedId);
    return profile?.version;
  }, [profileItems, secondSelectedId]);

  // Use versions for diff API (API compares by version, not profile ID)
  const { data: diffData, isLoading: diffLoading } = useProfileDiff(
    nodeId,
    isDiffMode ? firstVersion : undefined,
    isDiffMode ? secondVersion : undefined
  );

  const displayProfile = useMemo(() => {
    if (selectedProfiles.length === 0) return latestProfile;
    if (selectedProfiles.length === 1) return firstProfile;
    return null;
  }, [selectedProfiles, latestProfile, firstProfile]);

  const selectionSummary = useMemo(() => {
    const summaryMap = new Map(profileItems.map((profile) => [profile.profileId, profile]));
    return selectedProfiles
      .map((id) => summaryMap.get(id))
      .filter(Boolean) as ProfileSummary[];
  }, [profileItems, selectedProfiles]);

  const isLoading = latestLoading || historyLoading;

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

  const clearSelection = () => {
    setSelectedProfiles([]);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-64" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  if (!profileItems.length) {
    return (
      <EmptyState
        icon={FileText}
        title="No profiles available"
        description="This node hasn't submitted any profiles yet"
      />
    );
  }

  return (
    <div className="space-y-6">
      {selectedProfiles.length > 0 && (
        <SelectionBanner
          selectedProfiles={selectionSummary}
          isDiffMode={isDiffMode}
          onClear={clearSelection}
        />
      )}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                {isDiffMode ? (
                  <>
                    <GitCompare className="h-5 w-5" />
                    Profile Comparison
                  </>
                ) : (
                  <>
                    <FileText className="h-5 w-5" />
                    {selectedProfiles.length === 0 ? 'Latest Profile' : 'Selected Profile'}
                  </>
                )}
              </CardTitle>
              <CardDescription>
                {isDiffMode
                  ? `${firstProfile?.version || '...'} → ${secondProfile?.version || '...'}`
                  : displayProfile
                  ? `Version ${displayProfile.version}`
                  : 'Loading...'}
              </CardDescription>
            </div>
            {displayProfile && !isDiffMode && (
              <Link
                to={`${ROUTES.NODES}/${nodeId}/profile/${displayProfile.profileId}`}
                className="text-sm text-primary hover:underline"
              >
                View full details
              </Link>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isDiffMode ? (
            <ProfileDiffView
              diff={diffData}
              leftProfile={firstProfile}
              rightProfile={secondProfile}
              isLoading={diffLoading}
            />
          ) : displayProfile ? (
            <ProfileSummaryView profile={displayProfile} />
          ) : (
            <div className="text-center text-muted-foreground py-8">
              Select a profile from the history below
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Profile History
              </CardTitle>
              <CardDescription>
                {profilesData?.total ?? profileItems.length} profile
                {(profilesData?.total ?? profileItems.length) !== 1 ? 's' : ''} captured
              </CardDescription>
            </div>
            <Link
              to={`${ROUTES.NODES}/${nodeId}/profiles`}
              className="text-sm text-primary hover:underline"
            >
              View all
            </Link>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <ScrollArea className="h-[320px] pr-4">
            <div className="space-y-2">
              {profileItems.map((profile, index) => (
                <ProfileHistoryItem
                  key={profile.profileId}
                  profile={profile}
                  isLatest={index === 0}
                  isSelected={selectedProfiles.includes(profile.profileId)}
                  selectionIndex={selectedProfiles.indexOf(profile.profileId)}
                  onSelect={() => toggleProfileSelection(profile.profileId)}
                />
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

function SelectionBanner({
  selectedProfiles,
  isDiffMode,
  onClear,
}: {
  selectedProfiles: ProfileSummary[];
  isDiffMode: boolean;
  onClear: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {isDiffMode ? (
          <GitCompare className="h-4 w-4" />
        ) : (
          <Eye className="h-4 w-4" />
        )}
        <span>
          {isDiffMode
            ? 'Comparing two profiles'
            : 'Viewing selected profile. Select another to compare.'}
        </span>
        <div className="flex flex-wrap gap-2">
          {selectedProfiles.map((profile) => (
            <Badge key={profile.profileId} variant="secondary" className="font-mono">
              {profile.version}
            </Badge>
          ))}
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={onClear}>
        <X className="h-4 w-4 mr-1" />
        Clear selection
      </Button>
    </div>
  );
}

function ProfileSummaryView({ profile }: { profile: Profile }) {
  const sectionsWithData = getSectionsWithData(profile);

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <ProfileSectionCard
          icon={<CalendarClock className="h-4 w-4" />}
          title="Captured"
          items={[formatDate(new Date(profile.submittedAt)), profile.collectionLevel || 'neutral']}
        />
        <ProfileSectionCard
          icon={<Layers className="h-4 w-4" />}
          title="Sections"
          items={[
            `${sectionsWithData.length} sections`,
            sectionsWithData.slice(0, 3).join(', ') || 'None',
          ]}
        />
        <ProfileSectionCard
          icon={<Cpu className="h-4 w-4" />}
          title="Hardware"
          items={[
            profile.hardware?.cpu?.model,
            profile.hardware?.memory?.totalBytes
              ? `${formatBytes(profile.hardware.memory.totalBytes)} RAM`
              : undefined,
          ].filter(Boolean) as string[]}
        />
        <ProfileSectionCard
          icon={<HardDrive className="h-4 w-4" />}
          title="Storage"
          items={[
            `${profile.storage?.blockDevices?.length || 0} block devices`,
            `${profile.storage?.filesystems?.length || 0} filesystems`,
          ]}
        />
        <ProfileSectionCard
          icon={<Wifi className="h-4 w-4" />}
          title="Network"
          items={[
            `${profile.network?.interfaces?.length || 0} interfaces`,
            profile.network?.hostname,
          ].filter(Boolean) as string[]}
        />
        <ProfileSectionCard
          icon={<Package className="h-4 w-4" />}
          title="Software"
          items={[
            profile.software?.os?.name,
            profile.software?.os?.version,
          ].filter(Boolean) as string[]}
        />
      </div>

      {sectionsWithData.length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2 text-muted-foreground">Included Sections</h4>
          <div className="flex flex-wrap gap-2">
            {sectionsWithData.map((section) => (
              <Badge key={section} variant="secondary" className="capitalize">
                {section}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileSectionCard({
  icon,
  title,
  items,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
}) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="font-medium text-sm">{title}</span>
      </div>
      <div className="space-y-1">
        {items.length > 0 ? (
          items.map((item, i) => (
            <div key={i} className="text-xs text-muted-foreground truncate">
              {item}
            </div>
          ))
        ) : (
          <div className="text-xs text-muted-foreground">No data</div>
        )}
      </div>
    </div>
  );
}

function ProfileDiffView({
  diff,
  leftProfile,
  rightProfile,
  isLoading,
}: {
  diff?: ProfileDiff;
  leftProfile?: Profile;
  rightProfile?: Profile;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  if (!diff) {
    return (
      <div className="text-center text-muted-foreground py-8">
        Unable to load diff comparison
      </div>
    );
  }

  const changedSections = diff.changedSections ?? [];

  if (changedSections.length === 0) {
    return (
      <div className="text-center py-8">
        <GitCompare className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
        <h3 className="font-medium">No differences found</h3>
        <p className="text-sm text-muted-foreground mt-1">
          These two profiles are identical
        </p>
      </div>
    );
  }

  const changeSummary = diff.changeSummary as Record<string, { added?: number; removed?: number; changed?: number }> | undefined;

  const totalChanges = changedSections.reduce((sum, section) => {
    const summary = changeSummary?.[section];
    return sum + (summary?.added ?? 0) + (summary?.removed ?? 0) + (summary?.changed ?? 0);
  }, 0);

  return (
    <div className="space-y-5">
      <div className="grid gap-4 lg:grid-cols-2">
        <DiffProfileCard label="From" profile={leftProfile} fallbackVersion={diff.fromVersion} />
        <DiffProfileCard label="To" profile={rightProfile} fallbackVersion={diff.toVersion} />
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Badge variant="secondary" className="text-base">
          {diff.diffPercentage?.toFixed(1) ?? 0}% difference
        </Badge>
        <span className="text-muted-foreground">
          {changedSections.length} section{changedSections.length !== 1 ? 's' : ''} changed
        </span>
      </div>

      <div className="space-y-3">
        {changedSections.map((section) => {
          const summary = changeSummary?.[section];
          return (
            <div key={section} className="rounded-lg border overflow-hidden">
              <div className="bg-muted/50 px-4 py-3 flex items-center justify-between">
                <h4 className="font-medium capitalize">{section}</h4>
                <div className="flex items-center gap-2 text-sm">
                  {summary?.added ? (
                    <span className="flex items-center gap-1 text-green-600">
                      <Plus className="h-3.5 w-3.5" />
                      {summary.added} added
                    </span>
                  ) : null}
                  {summary?.removed ? (
                    <span className="flex items-center gap-1 text-red-600">
                      <Minus className="h-3.5 w-3.5" />
                      {summary.removed} removed
                    </span>
                  ) : null}
                  {summary?.changed ? (
                    <span className="flex items-center gap-1 text-yellow-600">
                      <ArrowRight className="h-3.5 w-3.5" />
                      {summary.changed} modified
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {totalChanges > 0 && (
        <p className="text-sm text-muted-foreground">
          Total: {totalChanges} change{totalChanges !== 1 ? 's' : ''} across all sections
        </p>
      )}
    </div>
  );
}

function DiffProfileCard({
  label,
  profile,
  fallbackVersion,
}: {
  label: string;
  profile?: Profile;
  fallbackVersion: string;
}) {
  return (
    <div className="rounded-lg border bg-muted/30 p-4">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="font-mono">
          {profile?.version || fallbackVersion}
        </Badge>
        {profile?.collectionLevel && (
          <Badge variant="outline" className="capitalize">
            {profile.collectionLevel}
          </Badge>
        )}
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        {profile?.submittedAt
          ? formatRelativeTime(new Date(profile.submittedAt))
          : 'Timestamp unavailable'}
      </div>
    </div>
  );
}

function ProfileHistoryItem({
  profile,
  isLatest,
  isSelected,
  selectionIndex,
  onSelect,
}: {
  profile: ProfileSummary;
  isLatest: boolean;
  isSelected: boolean;
  selectionIndex: number;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full text-left rounded-lg border p-3 transition-all',
        isSelected
          ? 'ring-2 ring-primary bg-primary/5 border-primary'
          : 'hover:bg-muted/50 hover:border-muted-foreground/30'
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              'h-6 w-6 rounded-full border-2 flex items-center justify-center text-xs font-medium',
              isSelected
                ? 'bg-primary border-primary text-primary-foreground'
                : 'border-muted-foreground/30'
            )}
          >
            {isSelected ? selectionIndex + 1 : ''}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-medium">{profile.version}</span>
              {isLatest && (
                <Badge variant="success" className="text-xs">
                  Latest
                </Badge>
              )}
            </div>
            <div className="text-xs text-muted-foreground">
              {formatRelativeTime(new Date(profile.submittedAt))}
            </div>
          </div>
        </div>
        <div className="text-xs text-muted-foreground">
          {profile.collectionLevel || 'neutral'}
        </div>
      </div>
    </button>
  );
}
