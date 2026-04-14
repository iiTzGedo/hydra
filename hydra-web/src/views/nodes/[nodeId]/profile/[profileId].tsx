import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Clock,
  Cpu,
  MemoryStick,
  HardDrive,
  Wifi,
  Package,
  Boxes,
  Database,
  Wrench,
  Users,
  Shield,
} from 'lucide-react';
import { useNode } from '@/api/nodes';
import { useProfile } from '@/api/profiles';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate, formatBytes } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import type { Profile } from '@/types/profile';

export default function ProfileDetailPage() {
  const { nodeId, profileId } = useParams<{ nodeId: string; profileId: string }>()!
  const { data: node, isLoading: nodeLoading } = useNode(nodeId!);
  const { data: profile, isLoading: profileLoading } = useProfile(profileId!);

  const isLoading = nodeLoading || profileLoading;

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

  if (!node || !profile) {
    return (
      <div className="p-6">
        <Link
          href={ROUTES.NODES}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Nodes
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <Clock className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Profile not found</h3>
        </div>
      </div>
    );
  }

  const hasSectionData =
    profile.hardware ||
    profile.network ||
    profile.storage ||
    profile.software ||
    (profile.serviceIds && profile.serviceIds.length > 0) ||
    profile.users;

  return (
    <div className="p-6">
      <Link
        href={`${ROUTES.NODES}/${nodeId}/profiles`}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Profile History
      </Link>

      <PageHeader
        title={`Profile ${profile.version}`}
        description={`Captured on ${formatDate(new Date(profile.submittedAt))}`}
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <ProfileMetadataSummary nodeId={nodeId!} profile={profile} />

        {!hasSectionData && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-8 text-center"
          >
            <Database className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No Section Data Available</h3>
            <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
              This profile was collected with no section data. This may indicate the agent
              collected a minimal profile or there was an issue during collection.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Badge variant="outline">Collection Level: {profile.collectionLevel || 'unknown'}</Badge>
              <Badge variant="outline">Agent: {profile.agentVersion || 'unknown'}</Badge>
            </div>
          </motion.div>
        )}

        {profile.hardware && (
          <ProfileSection title="Hardware" icon={<Cpu className="h-5 w-5" />}>
            <HardwareSectionView profile={profile} />
          </ProfileSection>
        )}

        {profile.storage && (
          <ProfileSection title="Storage" icon={<HardDrive className="h-5 w-5" />}>
            <StorageSectionView profile={profile} />
          </ProfileSection>
        )}

        {profile.network && (
          <ProfileSection title="Network" icon={<Wifi className="h-5 w-5" />}>
            <NetworkSectionView profile={profile} />
          </ProfileSection>
        )}

        {profile.software && (
          <ProfileSection title="Software" icon={<Package className="h-5 w-5" />}>
            <SoftwareSectionView profile={profile} />
          </ProfileSection>
        )}

        {profile.serviceIds && profile.serviceIds.length > 0 && (
          <ProfileSection title="Services" icon={<Boxes className="h-5 w-5" />}>
            <ServicesSectionView profile={profile} />
          </ProfileSection>
        )}

        {profile.users && (
          <ProfileSection title="Users" icon={<Users className="h-5 w-5" />}>
            <UsersSectionView profile={profile} />
          </ProfileSection>
        )}
      </motion.div>
    </div>
  );
}

function ProfileMetadataSummary({ nodeId, profile }: { nodeId: string; profile: Profile }) {
  const sectionsWithData = [
    profile.hardware,
    profile.network,
    profile.storage,
    profile.software,
    profile.serviceIds && profile.serviceIds.length > 0,
    profile.users,
  ].filter(Boolean).length;

  return (
    <motion.div
      variants={staggerItemVariants}
      className="rounded-xl border bg-card p-6 shadow-sm"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="text-sm text-muted-foreground">Node</div>
          <Link href={`${ROUTES.NODES}/${nodeId}`} className="text-lg font-semibold hover:underline">
            {nodeId}
          </Link>
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{profile.collectionLevel || 'neutral'}</Badge>
            <Badge variant="outline">{sectionsWithData} sections</Badge>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <MetadataItem label="Profile ID" value={profile.profileId} mono />
          <MetadataItem label="Version" value={profile.version} mono />
          <MetadataItem label="Submitted" value={formatDate(new Date(profile.submittedAt))} />
          <MetadataItem label="Collected" value={formatDate(new Date(profile.collectedAt))} />
          <MetadataItem label="Agent Version" value={profile.agentVersion} mono />
          {profile.serviceIds && (
            <MetadataItem label="Services" value={profile.serviceIds.length.toString()} />
          )}
        </div>
      </div>
    </motion.div>
  );
}

function MetadataItem({
  label,
  value,
  mono,
}: {
  label: string;
  value?: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn('text-sm font-medium', mono && 'font-mono')}>{value || '-'}</div>
    </div>
  );
}

function ProfileSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      variants={staggerItemVariants}
      className="rounded-xl border bg-card p-6 shadow-sm"
    >
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      {children}
    </motion.div>
  );
}

function HardwareSectionView({ profile }: { profile: Profile }) {
  const hw = profile.hardware;
  if (!hw) return null;

  const cpu = hw.cpu;
  const memory = hw.memory;
  const gpus = hw.gpus || [];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h4 className="flex items-center gap-2 text-sm font-medium mb-3">
            <Cpu className="h-4 w-4" />
            CPU
          </h4>
          <div className="space-y-1 text-sm">
            <KeyValue label="Model" value={cpu?.model} />
            <KeyValue label="Vendor" value={cpu?.vendor} />
            <KeyValue label="Physical Cores" value={cpu?.coresPhysical?.toString()} />
            <KeyValue label="Logical Cores" value={cpu?.coresLogical?.toString()} />
            <KeyValue label="Frequency" value={cpu?.frequencyMhz ? `${cpu.frequencyMhz} MHz` : undefined} />
            <KeyValue label="Architecture" value={cpu?.architecture} />
          </div>
        </div>
        <div className="rounded-lg border p-4">
          <h4 className="flex items-center gap-2 text-sm font-medium mb-3">
            <MemoryStick className="h-4 w-4" />
            Memory
          </h4>
          <div className="space-y-1 text-sm">
            <KeyValue label="Total" value={memory?.totalBytes ? formatBytes(memory.totalBytes) : undefined} />
            <KeyValue label="Type" value={memory?.type} />
            <KeyValue label="Speed" value={memory?.speedMhz ? `${memory.speedMhz} MHz` : undefined} />
            <KeyValue label="Slots Used" value={memory?.slotsUsed?.toString()} />
            <KeyValue label="Slots Total" value={memory?.slotsTotal?.toString()} />
          </div>
        </div>
      </div>

      {(hw.systemManufacturer || hw.systemModel || hw.biosVendor) && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-lg border p-4">
            <h4 className="flex items-center gap-2 text-sm font-medium mb-3">
              <Database className="h-4 w-4" />
              System
            </h4>
            <div className="space-y-1 text-sm">
              <KeyValue label="Manufacturer" value={hw.systemManufacturer} />
              <KeyValue label="Model" value={hw.systemModel} />
              <KeyValue label="Serial" value={hw.systemSerial} />
            </div>
          </div>
          <div className="rounded-lg border p-4">
            <h4 className="flex items-center gap-2 text-sm font-medium mb-3">
              <Shield className="h-4 w-4" />
              BIOS
            </h4>
            <div className="space-y-1 text-sm">
              <KeyValue label="Vendor" value={hw.biosVendor} />
              <KeyValue label="Version" value={hw.biosVersion} />
            </div>
          </div>
        </div>
      )}

      {gpus.length > 0 && (
        <div className="rounded-lg border p-4">
          <h4 className="flex items-center gap-2 text-sm font-medium mb-3">
            <Wrench className="h-4 w-4" />
            GPUs ({gpus.length})
          </h4>
          <div className="space-y-3">
            {gpus.map((gpu, index) => (
              <div key={`${gpu.model}-${index}`} className="rounded-lg border bg-muted/30 p-3">
                <div className="font-medium text-sm">{gpu.model || 'Unknown GPU'}</div>
                <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                  <KeyValue label="Vendor" value={gpu.vendor} />
                  <KeyValue
                    label="Memory"
                    value={gpu.memoryBytes ? formatBytes(gpu.memoryBytes) : undefined}
                  />
                  <KeyValue label="Driver" value={gpu.driverVersion} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StorageSectionView({ profile }: { profile: Profile }) {
  const storage = profile.storage;
  if (!storage) return null;

  const blockDevices = storage.blockDevices || [];
  const filesystems = storage.filesystems || [];

  return (
    <div className="space-y-4">
      {storage.totalCapacityBytes && (
        <div className="rounded-lg border p-4">
          <h4 className="text-sm font-medium mb-2">Total Capacity</h4>
          <div className="text-2xl font-bold">{formatBytes(storage.totalCapacityBytes)}</div>
        </div>
      )}

      {blockDevices.length > 0 && (
        <div className="rounded-lg border overflow-hidden">
          <div className="bg-muted/50 px-4 py-2 border-b">
            <h4 className="text-sm font-medium">Block Devices ({blockDevices.length})</h4>
          </div>
          <div className="divide-y">
            {blockDevices.map((device) => (
              <div key={device.name} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-mono text-sm">{device.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {device.model || 'Unknown model'}
                  </div>
                </div>
                <div className="mt-2 grid gap-2 md:grid-cols-3 text-sm">
                  <KeyValue label="Size" value={device.sizeBytes ? formatBytes(device.sizeBytes) : undefined} />
                  <KeyValue label="Type" value={device.type} />
                  <KeyValue label="Transport" value={device.transport} />
                  <KeyValue label="Rotational" value={device.rotational !== undefined ? (device.rotational ? 'Yes' : 'No') : undefined} />
                  <KeyValue label="Serial" value={device.serial} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {filesystems.length > 0 && (
        <div className="rounded-lg border overflow-hidden">
          <div className="bg-muted/50 px-4 py-2 border-b">
            <h4 className="text-sm font-medium">Filesystems ({filesystems.length})</h4>
          </div>
          <div className="divide-y">
            {filesystems.map((fs) => {
              const usedPercent =
                fs.sizeBytes && fs.usedBytes
                  ? Math.round((fs.usedBytes / fs.sizeBytes) * 100)
                  : 0;
              return (
                <div key={fs.mountPoint} className="p-4 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-mono">{fs.mountPoint}</span>
                    <span className="text-muted-foreground">
                      {fs.usedBytes ? formatBytes(fs.usedBytes) : '?'} /{' '}
                      {fs.sizeBytes ? formatBytes(fs.sizeBytes) : '?'} ({usedPercent}%)
                    </span>
                  </div>
                  {fs.sizeBytes && fs.usedBytes && (
                    <Progress
                      value={usedPercent}
                      className="h-2"
                      indicatorClassName={cn(
                        usedPercent > 90
                          ? 'bg-destructive'
                          : usedPercent > 75
                          ? 'bg-warning'
                          : 'bg-chart-1'
                      )}
                    />
                  )}
                  <div className="text-xs text-muted-foreground">
                    {fs.device} - {fs.fsType}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {blockDevices.length === 0 && filesystems.length === 0 && (
        <EmptySectionNotice message="No storage details reported." />
      )}
    </div>
  );
}

function NetworkSectionView({ profile }: { profile: Profile }) {
  const network = profile.network;
  if (!network) return null;

  const interfaces = network.interfaces || [];
  const routes = network.routes || [];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h4 className="text-sm font-medium mb-3">Identity</h4>
          <div className="space-y-1 text-sm">
            <KeyValue label="Hostname" value={network.hostname} mono />
            <KeyValue label="Domain" value={network.domain} />
            <KeyValue label="FQDN" value={network.fqdn} mono />
            <KeyValue label="Default Gateway" value={network.defaultGateway} mono />
          </div>
        </div>
        <div className="rounded-lg border p-4">
          <h4 className="text-sm font-medium mb-3">DNS</h4>
          <div className="space-y-1 text-sm">
            <KeyValue
              label="Servers"
              value={network.dnsServers?.join(', ')}
              mono
            />
            <KeyValue
              label="Search Domains"
              value={network.dnsSearch?.join(', ')}
              mono
            />
          </div>
        </div>
      </div>

      {interfaces.length > 0 && (
        <div className="rounded-lg border overflow-hidden">
          <div className="bg-muted/50 px-4 py-2 border-b">
            <h4 className="text-sm font-medium">Interfaces ({interfaces.length})</h4>
          </div>
          <div className="divide-y">
            {interfaces.map((iface) => (
              <div key={iface.name} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-mono text-sm">{iface.name}</div>
                  <Badge variant={iface.state === 'up' ? 'success' : 'secondary'}>
                    {iface.state}
                  </Badge>
                </div>
                <div className="mt-2 grid gap-2 md:grid-cols-2 text-sm">
                  <KeyValue label="Type" value={iface.type} />
                  <KeyValue label="MAC" value={iface.macAddress} mono />
                  <KeyValue label="Speed" value={iface.speedMbps ? `${iface.speedMbps} Mbps` : undefined} />
                  <KeyValue label="MTU" value={iface.mtu?.toString()} />
                </div>
                {((iface.ipv4Addresses && iface.ipv4Addresses.length > 0) ||
                  (iface.ipv6Addresses && iface.ipv6Addresses.length > 0)) && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {iface.ipv4Addresses?.map((addr) => (
                      <Badge key={addr} variant="outline" className="font-mono">
                        {addr} (IPv4)
                      </Badge>
                    ))}
                    {iface.ipv6Addresses?.map((addr) => (
                      <Badge key={addr} variant="outline" className="font-mono text-xs">
                        {addr} (IPv6)
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {routes.length > 0 && (
        <div className="rounded-lg border overflow-hidden">
          <div className="bg-muted/50 px-4 py-2 border-b">
            <h4 className="text-sm font-medium">Routes ({routes.length})</h4>
          </div>
          <div className="divide-y">
            {routes.map((route, index) => (
              <div key={`${route.destination}-${index}`} className="p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono">{route.destination}</span>
                  <span className="text-muted-foreground">{route.interface}</span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {route.gateway ? `Gateway: ${route.gateway}` : 'Direct'}
                  {route.metric !== undefined ? ` - Metric: ${route.metric}` : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {interfaces.length === 0 && routes.length === 0 && (
        <EmptySectionNotice message="No network details reported." />
      )}
    </div>
  );
}

function SoftwareSectionView({ profile }: { profile: Profile }) {
  const software = profile.software;
  if (!software) return null;

  const packages = software.packages || [];

  return (
    <div className="space-y-4">
      {software.os && (
        <div className="rounded-lg border p-4">
          <h4 className="text-sm font-medium mb-3">Operating System</h4>
          <div className="space-y-1 text-sm">
            <KeyValue label="Name" value={software.os.name} />
            <KeyValue label="Version" value={software.os.version} />
            <KeyValue label="Kernel" value={software.os.kernelVersion} />
            <KeyValue label="Architecture" value={software.os.architecture} />
            <KeyValue label="Family" value={software.os.family} />
          </div>
        </div>
      )}

      {(software.packageCount !== undefined || packages.length > 0) && (
        <div className="rounded-lg border p-4">
          <h4 className="text-sm font-medium mb-3">Packages</h4>
          <div className="space-y-1 text-sm mb-3">
            <KeyValue label="Total Count" value={software.packageCount?.toString()} />
          </div>
          {packages.length > 0 && (
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {packages.slice(0, 12).map((pkg) => (
                <div key={pkg.name} className="rounded-lg border bg-muted/30 px-3 py-2">
                  <div className="text-xs text-muted-foreground">{pkg.name}</div>
                  <div className="text-sm font-mono">{pkg.version || '-'}</div>
                  {pkg.manager && (
                    <div className="text-xs text-muted-foreground">{pkg.manager}</div>
                  )}
                </div>
              ))}
              {packages.length > 12 && (
                <div className="rounded-lg border bg-muted/30 px-3 py-2 flex items-center justify-center">
                  <span className="text-sm text-muted-foreground">
                    +{packages.length - 12} more
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {!software.os && software.packageCount === undefined && packages.length === 0 && (
        <EmptySectionNotice message="No software details reported." />
      )}
    </div>
  );
}

function ServicesSectionView({ profile }: { profile: Profile }) {
  const serviceIds = profile.serviceIds || [];

  if (serviceIds.length === 0) {
    return <EmptySectionNotice message="No services discovered in this profile." />;
  }

  return (
    <div className="rounded-lg border overflow-hidden">
      <div className="bg-muted/50 px-4 py-2 border-b">
        <h4 className="text-sm font-medium">Services ({serviceIds.length})</h4>
      </div>
      <div className="p-4">
        <p className="text-sm text-muted-foreground mb-3">
          Service IDs associated with this profile. View full service details in the Services section.
        </p>
        <div className="flex flex-wrap gap-2">
          {serviceIds.map((serviceId) => (
            <Badge key={serviceId} variant="outline" className="font-mono">
              {serviceId}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}

function UsersSectionView({ profile }: { profile: Profile }) {
  const users = profile.users?.users || [];
  const sshKeys = profile.users?.sshKeys || [];

  return (
    <div className="space-y-4">
      {users.length > 0 && (
        <div className="rounded-lg border overflow-hidden">
          <div className="bg-muted/50 px-4 py-2 border-b">
            <h4 className="text-sm font-medium">Users ({users.length})</h4>
          </div>
          <div className="divide-y">
            {users.map((user) => (
              <div key={user.username} className="p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono">{user.username}</span>
                  <span className="text-muted-foreground">
                    UID {user.uid} / GID {user.gid}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {user.home ? `Home: ${user.home}` : ''}
                  {user.shell ? ` - Shell: ${user.shell}` : ''}
                </div>
                {user.groups && user.groups.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {user.groups.map((group) => (
                      <Badge key={group} variant="outline" className="font-mono">
                        {group}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {sshKeys.length > 0 && (
        <div className="rounded-lg border overflow-hidden">
          <div className="bg-muted/50 px-4 py-2 border-b">
            <h4 className="text-sm font-medium">SSH Keys ({sshKeys.length})</h4>
          </div>
          <div className="divide-y">
            {sshKeys.map((key, index) => (
              <div key={`${key.fingerprint}-${index}`} className="p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono">{key.username}</span>
                  <Badge variant="outline">{key.keyType}</Badge>
                </div>
                <div className="mt-1 font-mono text-xs text-muted-foreground truncate">
                  {key.fingerprint}
                </div>
                {key.comment && (
                  <div className="mt-1 text-xs text-muted-foreground">{key.comment}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {users.length === 0 && sshKeys.length === 0 && (
        <EmptySectionNotice message="No user data reported." />
      )}
    </div>
  );
}

function EmptySectionNotice({ message }: { message: string }) {
  return (
    <div className="rounded-lg border bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

function KeyValue({
  label,
  value,
  mono,
}: {
  label: string;
  value?: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('text-right', mono && 'font-mono')}>{value || '-'}</span>
    </div>
  );
}
