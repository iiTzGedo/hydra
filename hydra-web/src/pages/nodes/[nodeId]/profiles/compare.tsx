import { useParams, useSearchParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  GitCompare,
  RefreshCw,
  Cpu,
  MemoryStick,
  HardDrive,
  Wifi,
  Package,
  Boxes,
  Users,
  Database,
  Shield,
  Plus,
  Minus,
  Edit3,
  Equal,
} from 'lucide-react';
import { useNode } from '@/api/nodes';
import { useProfile, useProfileDiff } from '@/api/profiles';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime, formatBytes } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import type { ProfileDiffChangeSummary } from '@/types/profile';
import type {
  HardwareProfile,
  NetworkProfile,
  StorageProfile,
  SoftwareProfile,
  UsersProfile,
} from '@/types/profile';

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
    profileA?.version,
    profileB?.version
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

  const changeSummary = diff?.changeSummary ?? {};
  const totalAdded = Object.values(changeSummary).reduce(
    (acc, summary) => acc + (summary.added ?? 0),
    0,
  );
  const totalRemoved = Object.values(changeSummary).reduce(
    (acc, summary) => acc + (summary.removed ?? 0),
    0,
  );

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
        description={`Comparing ${profileA.version} → ${profileB.version}`}
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <ProfileCard
              label="From (Older)"
              version={profileA.version}
              submittedAt={profileA.submittedAt}
              nodeId={nodeId!}
              profileId={profileAId!}
              side="left"
            />
            <ProfileCard
              label="To (Newer)"
              version={profileB.version}
              submittedAt={profileB.submittedAt}
              nodeId={nodeId!}
              profileId={profileBId!}
              side="right"
            />
          </div>
        </motion.div>

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
              <StatCard
                value={`${diff.diffPercentage?.toFixed(1) || 0}%`}
                label="Total Difference"
                variant={diff.diffPercentage > 25 ? 'warning' : 'default'}
              />
              <StatCard
                value={diff.changedSections?.length || 0}
                label="Sections Changed"
                variant={diff.changedSections?.length > 0 ? 'info' : 'default'}
              />
              <StatCard
                value={totalAdded}
                label="Items Added"
                variant="success"
              />
              <StatCard
                value={totalRemoved}
                label="Items Removed"
                variant="error"
              />
            </div>

            {diff.changedSections && diff.changedSections.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {diff.changedSections.map((section) => {
                  const summary: ProfileDiffChangeSummary | undefined = changeSummary[section];
                  return (
                    <Badge key={section} variant="secondary" className="gap-2 py-1.5">
                      <span className="capitalize font-medium">{section}</span>
                      <span className="flex items-center gap-1 text-xs">
                        {summary?.added ? <span className="text-success">+{summary.added}</span> : null}
                        {summary?.removed ? <span className="text-destructive">-{summary.removed}</span> : null}
                        {summary?.changed ? <span className="text-warning">~{summary.changed}</span> : null}
                      </span>
                    </Badge>
                  );
                })}
              </div>
            )}

            {(!diff.changedSections || diff.changedSections.length === 0) && (
              <div className="text-center py-4 text-muted-foreground">
                <Equal className="mx-auto h-8 w-8 mb-2 opacity-50" />
                <p>No significant differences found between these profiles</p>
              </div>
            )}
          </motion.div>
        )}

        <HardwareComparison
          hardwareA={profileA.hardware}
          hardwareB={profileB.hardware}
          changed={diff?.changedSections?.includes('hardware')}
        />

        <NetworkComparison
          networkA={profileA.network}
          networkB={profileB.network}
          changed={diff?.changedSections?.includes('network')}
        />

        <StorageComparison
          storageA={profileA.storage}
          storageB={profileB.storage}
          changed={diff?.changedSections?.includes('storage')}
        />

        <SoftwareComparison
          softwareA={profileA.software}
          softwareB={profileB.software}
          changed={diff?.changedSections?.includes('software')}
        />

        <ServicesComparison
          serviceIdsA={profileA.serviceIds}
          serviceIdsB={profileB.serviceIds}
          changed={diff?.changedSections?.includes('services')}
        />

        <UsersComparison
          usersA={profileA.users}
          usersB={profileB.users}
          changed={diff?.changedSections?.includes('users')}
        />
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
  side,
}: {
  label: string;
  version: string;
  submittedAt: string;
  nodeId: string;
  profileId: string;
  side: 'left' | 'right';
}) {
  return (
    <div className={cn(
      'rounded-lg border p-4',
      side === 'left' ? 'border-muted-foreground/30' : 'border-primary/30 bg-primary/5'
    )}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-muted-foreground flex items-center gap-2">
          {side === 'left' ? <ArrowRight className="h-3 w-3" /> : null}
          {label}
          {side === 'right' ? <ArrowLeft className="h-3 w-3" /> : null}
        </span>
        <Link
          to={`${ROUTES.NODES}/${nodeId}/profile/${profileId}`}
          className="text-xs text-primary hover:underline"
        >
          View full profile
        </Link>
      </div>
      <div className={cn(
        'font-mono font-medium text-lg',
        side === 'right' && 'text-primary'
      )}>{version}</div>
      <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
        <Clock className="h-3.5 w-3.5" />
        <span>{formatDate(new Date(submittedAt))}</span>
        <span>•</span>
        <span>{formatRelativeTime(new Date(submittedAt))}</span>
      </div>
    </div>
  );
}

function StatCard({
  value,
  label,
  variant = 'default',
}: {
  value: string | number;
  label: string;
  variant?: 'default' | 'success' | 'error' | 'warning' | 'info';
}) {
  return (
    <div className="rounded-lg bg-muted/50 p-4 text-center">
      <div className={cn(
        'text-2xl font-bold',
        variant === 'success' && 'text-success',
        variant === 'error' && 'text-destructive',
        variant === 'warning' && 'text-warning',
        variant === 'info' && 'text-primary',
      )}>{value}</div>
      <div className="text-sm text-muted-foreground">{label}</div>
    </div>
  );
}

function HardwareComparison({
  hardwareA,
  hardwareB,
  changed,
}: {
  hardwareA?: HardwareProfile;
  hardwareB?: HardwareProfile;
  changed?: boolean;
}) {
  if (!hardwareA && !hardwareB) return null;

  return (
    <motion.div variants={staggerItemVariants}>
      <ComparisonSection
        title="Hardware"
        icon={<Cpu className="h-5 w-5" />}
        changed={changed}
        onlyInA={!hardwareB && !!hardwareA}
        onlyInB={!hardwareA && !!hardwareB}
      >
        <div className="space-y-4">
          {(hardwareA?.cpu || hardwareB?.cpu) && (
            <ComparisonCard title="CPU" icon={<Cpu className="h-4 w-4" />}>
              <ComparisonRow
                label="Model"
                valueA={hardwareA?.cpu?.model}
                valueB={hardwareB?.cpu?.model}
              />
              <ComparisonRow
                label="Vendor"
                valueA={hardwareA?.cpu?.vendor}
                valueB={hardwareB?.cpu?.vendor}
              />
              <ComparisonRow
                label="Physical Cores"
                valueA={hardwareA?.cpu?.coresPhysical?.toString()}
                valueB={hardwareB?.cpu?.coresPhysical?.toString()}
              />
              <ComparisonRow
                label="Logical Cores"
                valueA={hardwareA?.cpu?.coresLogical?.toString()}
                valueB={hardwareB?.cpu?.coresLogical?.toString()}
              />
              <ComparisonRow
                label="Frequency"
                valueA={hardwareA?.cpu?.frequencyMhz ? `${hardwareA.cpu.frequencyMhz} MHz` : undefined}
                valueB={hardwareB?.cpu?.frequencyMhz ? `${hardwareB.cpu.frequencyMhz} MHz` : undefined}
              />
              <ComparisonRow
                label="Architecture"
                valueA={hardwareA?.cpu?.architecture}
                valueB={hardwareB?.cpu?.architecture}
              />
            </ComparisonCard>
          )}

          {(hardwareA?.memory || hardwareB?.memory) && (
            <ComparisonCard title="Memory" icon={<MemoryStick className="h-4 w-4" />}>
              <ComparisonRow
                label="Total"
                valueA={hardwareA?.memory?.totalBytes ? formatBytes(hardwareA.memory.totalBytes) : undefined}
                valueB={hardwareB?.memory?.totalBytes ? formatBytes(hardwareB.memory.totalBytes) : undefined}
              />
              <ComparisonRow
                label="Type"
                valueA={hardwareA?.memory?.type}
                valueB={hardwareB?.memory?.type}
              />
              <ComparisonRow
                label="Speed"
                valueA={hardwareA?.memory?.speedMhz ? `${hardwareA.memory.speedMhz} MHz` : undefined}
                valueB={hardwareB?.memory?.speedMhz ? `${hardwareB.memory.speedMhz} MHz` : undefined}
              />
              <ComparisonRow
                label="Slots Used"
                valueA={hardwareA?.memory?.slotsUsed?.toString()}
                valueB={hardwareB?.memory?.slotsUsed?.toString()}
              />
              <ComparisonRow
                label="Total Slots"
                valueA={hardwareA?.memory?.slotsTotal?.toString()}
                valueB={hardwareB?.memory?.slotsTotal?.toString()}
              />
            </ComparisonCard>
          )}

          {(hardwareA?.systemManufacturer || hardwareA?.systemModel || hardwareB?.systemManufacturer || hardwareB?.systemModel) && (
            <ComparisonCard title="System" icon={<Database className="h-4 w-4" />}>
              <ComparisonRow
                label="Manufacturer"
                valueA={hardwareA?.systemManufacturer}
                valueB={hardwareB?.systemManufacturer}
              />
              <ComparisonRow
                label="Model"
                valueA={hardwareA?.systemModel}
                valueB={hardwareB?.systemModel}
              />
              <ComparisonRow
                label="Serial"
                valueA={hardwareA?.systemSerial}
                valueB={hardwareB?.systemSerial}
                mono
              />
            </ComparisonCard>
          )}

          {(hardwareA?.biosVendor || hardwareA?.biosVersion || hardwareB?.biosVendor || hardwareB?.biosVersion) && (
            <ComparisonCard title="BIOS" icon={<Shield className="h-4 w-4" />}>
              <ComparisonRow
                label="Vendor"
                valueA={hardwareA?.biosVendor}
                valueB={hardwareB?.biosVendor}
              />
              <ComparisonRow
                label="Version"
                valueA={hardwareA?.biosVersion}
                valueB={hardwareB?.biosVersion}
              />
            </ComparisonCard>
          )}

          {((hardwareA?.gpus && hardwareA.gpus.length > 0) || (hardwareB?.gpus && hardwareB.gpus.length > 0)) && (
            <ComparisonCard title="GPU" icon={<Database className="h-4 w-4" />}>
              <ArrayComparison
                itemsA={hardwareA?.gpus || []}
                itemsB={hardwareB?.gpus || []}
                getKey={(gpu) => gpu.model || 'unknown'}
                renderItem={(gpu) => (
                  <div>
                    <div className="font-medium">{gpu.model}</div>
                    <div className="text-xs text-muted-foreground">
                      {gpu.vendor} {gpu.memoryBytes ? `• ${formatBytes(gpu.memoryBytes)}` : ''}
                    </div>
                  </div>
                )}
              />
            </ComparisonCard>
          )}
        </div>
      </ComparisonSection>
    </motion.div>
  );
}

function NetworkComparison({
  networkA,
  networkB,
  changed,
}: {
  networkA?: NetworkProfile;
  networkB?: NetworkProfile;
  changed?: boolean;
}) {
  if (!networkA && !networkB) return null;

  return (
    <motion.div variants={staggerItemVariants}>
      <ComparisonSection
        title="Network"
        icon={<Wifi className="h-5 w-5" />}
        changed={changed}
        onlyInA={!networkB && !!networkA}
        onlyInB={!networkA && !!networkB}
      >
        <div className="space-y-4">
          <ComparisonCard title="Identity">
            <ComparisonRow label="Hostname" valueA={networkA?.hostname} valueB={networkB?.hostname} mono />
            <ComparisonRow label="Domain" valueA={networkA?.domain} valueB={networkB?.domain} mono />
            <ComparisonRow label="FQDN" valueA={networkA?.fqdn} valueB={networkB?.fqdn} mono />
            <ComparisonRow
              label="DNS Servers"
              valueA={networkA?.dnsServers?.join(', ')}
              valueB={networkB?.dnsServers?.join(', ')}
              mono
            />
            <ComparisonRow
              label="Default Gateway"
              valueA={networkA?.defaultGateway}
              valueB={networkB?.defaultGateway}
              mono
            />
          </ComparisonCard>

          {((networkA?.interfaces && networkA.interfaces.length > 0) || (networkB?.interfaces && networkB.interfaces.length > 0)) && (
            <ComparisonCard title="Network Interfaces">
              <ArrayComparison
                itemsA={networkA?.interfaces || []}
                itemsB={networkB?.interfaces || []}
                getKey={(iface) => iface.name}
                renderItem={(iface) => (
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-medium">{iface.name}</span>
                      <Badge variant={iface.state === 'up' ? 'success' : 'secondary'} className="text-[10px] px-1 py-0">
                        {iface.state}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {iface.macAddress} • {iface.type}
                      {(iface.ipv4Addresses && iface.ipv4Addresses.length > 0) && (
                        <span className="block mt-0.5">
                          IPv4: {iface.ipv4Addresses.join(', ')}
                        </span>
                      )}
                      {(iface.ipv6Addresses && iface.ipv6Addresses.length > 0) && (
                        <span className="block mt-0.5">
                          IPv6: {iface.ipv6Addresses.join(', ')}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              />
            </ComparisonCard>
          )}
        </div>
      </ComparisonSection>
    </motion.div>
  );
}

function StorageComparison({
  storageA,
  storageB,
  changed,
}: {
  storageA?: StorageProfile;
  storageB?: StorageProfile;
  changed?: boolean;
}) {
  if (!storageA && !storageB) return null;

  return (
    <motion.div variants={staggerItemVariants}>
      <ComparisonSection
        title="Storage"
        icon={<HardDrive className="h-5 w-5" />}
        changed={changed}
        onlyInA={!storageB && !!storageA}
        onlyInB={!storageA && !!storageB}
      >
        <div className="space-y-4">
          {((storageA?.blockDevices && storageA.blockDevices.length > 0) || (storageB?.blockDevices && storageB.blockDevices.length > 0)) && (
            <ComparisonCard title="Block Devices">
              <ArrayComparison
                itemsA={storageA?.blockDevices || []}
                itemsB={storageB?.blockDevices || []}
                getKey={(device) => device.name}
                renderItem={(device) => (
                  <div>
                    <div className="font-mono font-medium">{device.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {device.model || 'Unknown'} • {device.sizeBytes ? formatBytes(device.sizeBytes) : 'Unknown size'} • {device.type}
                    </div>
                  </div>
                )}
              />
            </ComparisonCard>
          )}

          {((storageA?.filesystems && storageA.filesystems.length > 0) || (storageB?.filesystems && storageB.filesystems.length > 0)) && (
            <ComparisonCard title="Filesystems">
              <FilesystemComparison
                filesystemsA={storageA?.filesystems || []}
                filesystemsB={storageB?.filesystems || []}
              />
            </ComparisonCard>
          )}
        </div>
      </ComparisonSection>
    </motion.div>
  );
}

function FilesystemComparison({
  filesystemsA,
  filesystemsB,
}: {
  filesystemsA: NonNullable<StorageProfile['filesystems']>;
  filesystemsB: NonNullable<StorageProfile['filesystems']>;
}) {
  const allMountpoints = new Set([
    ...filesystemsA.map(f => f.mountPoint),
    ...filesystemsB.map(f => f.mountPoint),
  ]);

  return (
    <div className="space-y-3">
      {Array.from(allMountpoints).map((mountpoint) => {
        const fsA = filesystemsA.find(f => f.mountPoint === mountpoint);
        const fsB = filesystemsB.find(f => f.mountPoint === mountpoint);
        const usedPercentA = fsA && fsA.sizeBytes && fsA.sizeBytes > 0 ? Math.round(((fsA.usedBytes || 0) / fsA.sizeBytes) * 100) : 0;
        const usedPercentB = fsB && fsB.sizeBytes && fsB.sizeBytes > 0 ? Math.round(((fsB.usedBytes || 0) / fsB.sizeBytes) * 100) : 0;

        return (
          <div key={mountpoint} className="rounded-lg border p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-sm font-medium">{mountpoint}</span>
              <DiffIndicator
                onlyInA={!fsB && !!fsA}
                onlyInB={!fsA && !!fsB}
                changed={!!fsA && !!fsB && ((fsA.usedBytes || 0) !== (fsB.usedBytes || 0) || (fsA.sizeBytes || 0) !== (fsB.sizeBytes || 0))}
              />
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <div className="text-sm">
                <div className="text-xs text-muted-foreground mb-1">Profile A</div>
                {fsA ? (
                  <>
                    <Progress
                      value={usedPercentA}
                      className="h-2 mb-1"
                      indicatorClassName={usedPercentA > 90 ? 'bg-destructive' : usedPercentA > 75 ? 'bg-warning' : 'bg-chart-1'}
                    />
                    <span className="text-xs text-muted-foreground">
                      {formatBytes(fsA.usedBytes || 0)} / {formatBytes(fsA.sizeBytes || 0)} ({usedPercentA}%)
                    </span>
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground italic">Not present</span>
                )}
              </div>
              <div className="text-sm">
                <div className="text-xs text-muted-foreground mb-1">Profile B</div>
                {fsB ? (
                  <>
                    <Progress
                      value={usedPercentB}
                      className="h-2 mb-1"
                      indicatorClassName={usedPercentB > 90 ? 'bg-destructive' : usedPercentB > 75 ? 'bg-warning' : 'bg-chart-1'}
                    />
                    <span className="text-xs text-muted-foreground">
                      {formatBytes(fsB.usedBytes || 0)} / {formatBytes(fsB.sizeBytes || 0)} ({usedPercentB}%)
                    </span>
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground italic">Not present</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SoftwareComparison({
  softwareA,
  softwareB,
  changed,
}: {
  softwareA?: SoftwareProfile;
  softwareB?: SoftwareProfile;
  changed?: boolean;
}) {
  if (!softwareA && !softwareB) return null;

  return (
    <motion.div variants={staggerItemVariants}>
      <ComparisonSection
        title="Software"
        icon={<Package className="h-5 w-5" />}
        changed={changed}
        onlyInA={!softwareB && !!softwareA}
        onlyInB={!softwareA && !!softwareB}
      >
        <div className="space-y-4">
          {(softwareA?.os || softwareB?.os) && (
            <ComparisonCard title="Operating System">
              <ComparisonRow label="Name" valueA={softwareA?.os?.name} valueB={softwareB?.os?.name} />
              <ComparisonRow label="Version" valueA={softwareA?.os?.version} valueB={softwareB?.os?.version} />
              <ComparisonRow label="Kernel" valueA={softwareA?.os?.kernelVersion} valueB={softwareB?.os?.kernelVersion} mono />
              <ComparisonRow label="Architecture" valueA={softwareA?.os?.architecture} valueB={softwareB?.os?.architecture} />
              <ComparisonRow label="Family" valueA={softwareA?.os?.family} valueB={softwareB?.os?.family} />
            </ComparisonCard>
          )}

          {(softwareA?.packageCount !== undefined || softwareB?.packageCount !== undefined) && (
            <ComparisonCard title="Packages">
              <ComparisonRow
                label="Count"
                valueA={softwareA?.packageCount?.toString()}
                valueB={softwareB?.packageCount?.toString()}
              />
            </ComparisonCard>
          )}
        </div>
      </ComparisonSection>
    </motion.div>
  );
}

function ServicesComparison({
  serviceIdsA,
  serviceIdsB,
  changed,
}: {
  serviceIdsA?: string[];
  serviceIdsB?: string[];
  changed?: boolean;
}) {
  const idsA = serviceIdsA || [];
  const idsB = serviceIdsB || [];

  if (idsA.length === 0 && idsB.length === 0) return null;

  return (
    <motion.div variants={staggerItemVariants}>
      <ComparisonSection
        title="Services"
        icon={<Boxes className="h-5 w-5" />}
        changed={changed}
        onlyInA={idsB.length === 0 && idsA.length > 0}
        onlyInB={idsA.length === 0 && idsB.length > 0}
      >
        <ArrayComparison
          itemsA={idsA}
          itemsB={idsB}
          getKey={(serviceId) => serviceId}
          renderItem={(serviceId) => (
            <div>
              <span className="font-mono text-sm">{serviceId}</span>
            </div>
          )}
        />
      </ComparisonSection>
    </motion.div>
  );
}

function UsersComparison({
  usersA,
  usersB,
  changed,
}: {
  usersA?: UsersProfile;
  usersB?: UsersProfile;
  changed?: boolean;
}) {
  const userListA = usersA?.users || [];
  const userListB = usersB?.users || [];
  const sshKeysA = usersA?.sshKeys || [];
  const sshKeysB = usersB?.sshKeys || [];

  if (userListA.length === 0 && userListB.length === 0 && sshKeysA.length === 0 && sshKeysB.length === 0) {
    return null;
  }

  return (
    <motion.div variants={staggerItemVariants}>
      <ComparisonSection
        title="Users & SSH Keys"
        icon={<Users className="h-5 w-5" />}
        changed={changed}
        onlyInA={!usersB && !!usersA}
        onlyInB={!usersA && !!usersB}
      >
        <div className="space-y-4">
          {(userListA.length > 0 || userListB.length > 0) && (
            <ComparisonCard title="Users">
              <ArrayComparison
                itemsA={userListA}
                itemsB={userListB}
                getKey={(user) => user.username}
                renderItem={(user) => (
                  <div>
                    <div className="font-mono font-medium">{user.username}</div>
                    <div className="text-xs text-muted-foreground">
                      UID {user.uid} • {user.shell || 'no shell'}
                    </div>
                  </div>
                )}
              />
            </ComparisonCard>
          )}

          {(sshKeysA.length > 0 || sshKeysB.length > 0) && (
            <ComparisonCard title="SSH Keys">
              <ArrayComparison
                itemsA={sshKeysA}
                itemsB={sshKeysB}
                getKey={(key) => `${key.username}-${key.fingerprint}`}
                renderItem={(key) => (
                  <div>
                    <div className="font-mono font-medium text-xs">{key.fingerprint}</div>
                    <div className="text-xs text-muted-foreground">
                      {key.username} • {key.keyType}
                      {key.comment && <span> • {key.comment}</span>}
                    </div>
                  </div>
                )}
              />
            </ComparisonCard>
          )}
        </div>
      </ComparisonSection>
    </motion.div>
  );
}

function ComparisonSection({
  title,
  icon,
  children,
  changed,
  onlyInA,
  onlyInB,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  changed?: boolean;
  onlyInA?: boolean;
  onlyInB?: boolean;
}) {
  return (
    <div className={cn(
      'rounded-xl border bg-card p-6 shadow-sm',
      changed && 'border-warning/50',
      onlyInA && 'border-destructive/50',
      onlyInB && 'border-success/50',
    )}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="flex items-center gap-2 text-lg font-semibold">
          {icon}
          {title}
        </h3>
        <DiffIndicator onlyInA={onlyInA} onlyInB={onlyInB} changed={changed} />
      </div>
      {children}
    </div>
  );
}

function ComparisonCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border overflow-hidden">
      <div className="bg-muted/50 px-4 py-2 border-b flex items-center gap-2">
        {icon}
        <h4 className="text-sm font-medium">{title}</h4>
      </div>
      <div className="p-4 space-y-2">
        {children}
      </div>
    </div>
  );
}

function ComparisonRow({
  label,
  valueA,
  valueB,
  mono,
}: {
  label: string;
  valueA?: string;
  valueB?: string;
  mono?: boolean;
}) {
  const isDifferent = valueA !== valueB;
  const isAdded = !valueA && valueB;
  const isRemoved = valueA && !valueB;

  return (
    <div className={cn(
      'grid grid-cols-[1fr_1fr_1fr] gap-4 py-1.5 px-2 rounded',
      isDifferent && 'bg-warning/5',
      isAdded && 'bg-success/5',
      isRemoved && 'bg-destructive/5',
    )}>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className={cn(
        'text-sm',
        mono && 'font-mono',
        isRemoved && 'text-destructive line-through',
      )}>
        {valueA || <span className="text-muted-foreground/50 italic">-</span>}
      </div>
      <div className={cn(
        'text-sm',
        mono && 'font-mono',
        isAdded && 'text-success font-medium',
        isDifferent && !isAdded && !isRemoved && 'text-warning font-medium',
      )}>
        {valueB || <span className="text-muted-foreground/50 italic">-</span>}
      </div>
    </div>
  );
}

function ArrayComparison<T>({
  itemsA,
  itemsB,
  getKey,
  renderItem,
}: {
  itemsA: T[];
  itemsB: T[];
  getKey: (item: T) => string;
  renderItem: (item: T) => React.ReactNode;
}) {
  const keysA = new Set(itemsA.map(getKey));
  const keysB = new Set(itemsB.map(getKey));
  const allKeys = new Set([...keysA, ...keysB]);

  const itemMapA = new Map(itemsA.map(item => [getKey(item), item]));
  const itemMapB = new Map(itemsB.map(item => [getKey(item), item]));

  return (
    <div className="space-y-2">
      {Array.from(allKeys).map((key) => {
        const itemA = itemMapA.get(key);
        const itemB = itemMapB.get(key);
        const onlyInA = !keysB.has(key);
        const onlyInB = !keysA.has(key);
        const changed = itemA && itemB && JSON.stringify(itemA) !== JSON.stringify(itemB);

        return (
          <div
            key={key}
            className={cn(
              'grid grid-cols-[1fr_auto_1fr] gap-4 p-3 rounded-lg border',
              onlyInA && 'bg-destructive/5 border-destructive/20',
              onlyInB && 'bg-success/5 border-success/20',
              changed && 'bg-warning/5 border-warning/20',
            )}
          >
            <div className={cn(onlyInA && 'text-destructive')}>
              {itemA ? renderItem(itemA) : <span className="text-muted-foreground/50 italic text-sm">Not present</span>}
            </div>
            <div className="flex items-center">
              <DiffIndicator onlyInA={onlyInA} onlyInB={onlyInB} changed={changed} compact />
            </div>
            <div className={cn(onlyInB && 'text-success')}>
              {itemB ? renderItem(itemB) : <span className="text-muted-foreground/50 italic text-sm">Not present</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DiffIndicator({
  onlyInA,
  onlyInB,
  changed,
  compact,
}: {
  onlyInA?: boolean;
  onlyInB?: boolean;
  changed?: boolean;
  compact?: boolean;
}) {
  if (onlyInA) {
    return (
      <Badge variant="destructive" className={cn('gap-1', compact && 'px-1.5 py-0')}>
        <Minus className="h-3 w-3" />
        {!compact && 'Removed'}
      </Badge>
    );
  }
  if (onlyInB) {
    return (
      <Badge variant="success" className={cn('gap-1', compact && 'px-1.5 py-0')}>
        <Plus className="h-3 w-3" />
        {!compact && 'Added'}
      </Badge>
    );
  }
  if (changed) {
    return (
      <Badge variant="warning" className={cn('gap-1', compact && 'px-1.5 py-0')}>
        <Edit3 className="h-3 w-3" />
        {!compact && 'Modified'}
      </Badge>
    );
  }
  return null;
}
