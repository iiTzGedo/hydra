import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useQueries } from '@tanstack/react-query';
import {
  Server,
  Network,
  Cpu,
  Tag,
  Info,
  HardDrive,
  Wifi,
  Boxes,
  Activity,
  TrendingUp,
  MemoryStick,
  History,
  GitCompare,
  FileText,
  AlertCircle,
  ExternalLink,
  Globe,
  Monitor,
  Users,
  Layers,
  Shield,
  Clock,
  XCircle,
  PlayCircle,
  PauseCircle,
} from 'lucide-react';
import { ROUTES, SERVICE_RUNTIME_COLORS } from '@/lib/constants';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { Node } from '@/types/node';
import { useNodeProfiles, useLatestProfile } from '@/api/profiles';
import { useNodeServices } from '@/api/services';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import { NODE_CLASS_COLORS, NODE_KIND_LABELS, STATUS_COLORS } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime, formatBytes } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import type { Profile } from '@/types/profile';
import type { ServiceSummary } from '@/types/service';

const classIcons = {
  compute: Server,
  networking: Network,
  iot: Cpu,
};

interface OverviewTabProps {
  node: Node;
}

const SNAPSHOT_LIMIT = 12;

export function OverviewTab({ node }: OverviewTabProps) {
  const [showAllFilesystems, setShowAllFilesystems] = useState(false);
  const [showAllInterfaces, setShowAllInterfaces] = useState(false);
  const [showAllUsers, setShowAllUsers] = useState(false);
  const [showAllNetworks, setShowAllNetworks] = useState(false);

  const Icon = classIcons[node.class] || Server;
  const colors = NODE_CLASS_COLORS[node.class];
  const statusColors = STATUS_COLORS[node.status] || STATUS_COLORS.inactive;
  const kindLabel = NODE_KIND_LABELS[node.kind as keyof typeof NODE_KIND_LABELS] || node.kind;

  const nodeIdStr = node.id || node.nodeId;
  const { data: latestProfile, isLoading: latestLoading } = useLatestProfile(nodeIdStr);
  const { data: profileHistory, isLoading: historyLoading } = useNodeProfiles(nodeIdStr, { limit: 30 });
  const { data: servicesData, isLoading: servicesLoading } = useNodeServices(nodeIdStr);

  const snapshotProfiles = profileHistory?.items?.slice(0, SNAPSHOT_LIMIT) ?? [];

  const profileSnapshotsQueries = useQueries({
    queries: snapshotProfiles.map((profile) => ({
      queryKey: queryKeys.profiles.detail(profile.profileId),
      queryFn: async () => {
        const response = await apiClient.get<ApiResponse<Profile>>(`/profiles/${profile.profileId}`);
        return response.data.data;
      },
      enabled: !!profile.profileId,
      staleTime: 60 * 1000,
    })),
  });

  const profileSnapshots = useMemo(() => {
    return profileSnapshotsQueries
      .map((query) => query.data)
      .filter(Boolean) as Profile[];
  }, [profileSnapshotsQueries]);

  const snapshotsLoading = profileSnapshotsQueries.some((query) => query.isLoading);

  const hasProfileData =
    latestProfile?.hardware ||
    latestProfile?.network ||
    latestProfile?.storage ||
    latestProfile?.software ||
    latestProfile?.users;

  const services = servicesData?.items || [];
  const runningServices = services.filter((s) => s.status === 'running');
  const latestProfileVersion = latestProfile?.version;
  const serverConfig = node.agent?.serverConfig;
  const controlServerUrl =
    node.agent?.tier === 'max' && serverConfig?.advertiseAddress && serverConfig?.port
      ? `${serverConfig.tlsEnabled === false ? 'http' : 'https'}://${serverConfig.advertiseAddress}:${serverConfig.port}`
      : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <Link href={`${ROUTES.NODES}/${node.id}/profiles`}>
          <Button variant="outline" size="sm">
            <History className="mr-2 h-4 w-4" />
            Profile History
          </Button>
        </Link>
        {profileHistory?.items && profileHistory.items.length >= 2 && (
          <Link href={`${ROUTES.NODES}/${node.id}/profiles/compare`}>
            <Button variant="outline" size="sm">
              <GitCompare className="mr-2 h-4 w-4" />
              Compare Profiles
            </Button>
          </Link>
        )}
        {latestProfile && (
          <Link href={`${ROUTES.NODES}/${node.id}/profile/${latestProfile.profileId}`}>
            <Button variant="outline" size="sm">
              <FileText className="mr-2 h-4 w-4" />
              View Latest Profile
            </Button>
          </Link>
        )}
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-start gap-6">
            <div className={cn('rounded-xl p-4', colors?.bg || 'bg-muted')}>
              <Icon className="h-8 w-8 text-white" />
            </div>

            <div className="flex-1 grid gap-6 md:grid-cols-3">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Classification</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Class</span>
                    <span className="font-medium capitalize">{node.class}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Type</span>
                    <span className="font-medium capitalize">{node.type}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Kind</span>
                    <span className="font-medium">{kindLabel}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Agent Tier</span>
                    <span className="font-medium capitalize">{node.agent?.tier || 'normal'}</span>
                  </div>
                  {controlServerUrl && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Control Server</span>
                      <span className="font-medium font-mono text-xs">{controlServerUrl}</span>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Status</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Status</span>
                    <Badge
                      variant={node.status === 'active' ? 'success' : 'secondary'}
                      className="gap-1.5"
                    >
                      <span className={cn('h-1.5 w-1.5 rounded-full', statusColors.dot)} />
                      {node.status}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Profile Version</span>
                    <span className="font-mono text-sm">{latestProfileVersion || '-'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Last Profiled</span>
                    <span className="text-sm">
                      {node.lastProfileAt
                        ? formatRelativeTime(new Date(node.lastProfileAt))
                        : 'Never'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Last Seen</span>
                    <span className="text-sm">
                      {node.lastSeenAt
                        ? formatRelativeTime(new Date(node.lastSeenAt))
                        : 'Never'}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Timestamps</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Registered</span>
                    <span className="text-sm">{formatDate(new Date(node.registeredAt))}</span>
                  </div>
                  {node.lastUpdated && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Updated</span>
                      <span className="text-sm">{formatDate(new Date(node.lastUpdated))}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          icon={<Activity className="h-4 w-4" />}
          title="Profiles Captured"
          value={profileHistory?.total ?? 0}
          description={
            profileHistory?.items?.[0]
              ? `Latest: ${formatRelativeTime(new Date(profileHistory.items[0].submittedAt))}`
              : 'No profiles yet'
          }
          isLoading={historyLoading}
        />
        <StatsCard
          icon={<Boxes className="h-4 w-4" />}
          title="Services"
          value={servicesData?.total ?? 0}
          description={
            servicesData?.items
              ? `${runningServices.length} running`
              : 'Loading...'
          }
          isLoading={servicesLoading}
        />
        <StatsCard
          icon={<HardDrive className="h-4 w-4" />}
          title="Block Devices"
          value={latestProfile?.storage?.blockDevices?.length ?? 0}
          description={
            latestProfile?.storage?.filesystems
              ? `${latestProfile.storage.filesystems.length} filesystems`
              : 'No storage data'
          }
          isLoading={latestLoading}
        />
        <StatsCard
          icon={<Wifi className="h-4 w-4" />}
          title="Network Interfaces"
          value={latestProfile?.network?.interfaces?.length ?? 0}
          description={latestProfile?.network?.hostname || 'No hostname'}
          isLoading={latestLoading}
        />
      </div>

      {!latestLoading && latestProfile && !hasProfileData && (
        <Card className="border-dashed">
          <CardContent className="py-8">
            <div className="flex flex-col items-center justify-center text-center">
              <AlertCircle className="h-10 w-10 text-muted-foreground mb-3" />
              <h3 className="text-lg font-semibold mb-1">Limited Profile Data</h3>
              <p className="text-sm text-muted-foreground max-w-md mb-4">
                The latest profile for this node has no detailed section data (hardware, storage, network, etc.).
                This may be due to a minimal collection level or agent configuration.
              </p>
              <div className="flex flex-wrap justify-center gap-2 mb-4">
                <Badge variant="outline">Collection Level: {latestProfile.collectionLevel || 'unknown'}</Badge>
                <Badge variant="outline">Agent: {latestProfile.agentVersion || 'unknown'}</Badge>
                <Badge variant="outline">Version: {latestProfile.version}</Badge>
              </div>
              <Link href={`${ROUTES.NODES}/${node.id}/profile/${latestProfile.profileId}`}>
                <Button variant="outline" size="sm">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  View Profile Details
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {!latestLoading && !latestProfile && (
        <Card className="border-dashed">
          <CardContent className="py-8">
            <div className="flex flex-col items-center justify-center text-center">
              <FileText className="h-10 w-10 text-muted-foreground mb-3" />
              <h3 className="text-lg font-semibold mb-1">No Profiles Yet</h3>
              <p className="text-sm text-muted-foreground max-w-md">
                This node has not submitted any profiles yet. Once the agent starts collecting data,
                you'll see hardware, storage, network, and software information here.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {hasProfileData && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-6">
            {latestProfile?.software?.os && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Monitor className="h-4 w-4" />
                    System Overview
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-3">
                      <div>
                        <div className="text-xs text-muted-foreground uppercase tracking-wide">Operating System</div>
                        <div className="text-lg font-semibold">{latestProfile.software.os.name}</div>
                        {latestProfile.software.os.version && (
                          <div className="text-sm text-muted-foreground">{latestProfile.software.os.version}</div>
                        )}
                      </div>
                      {latestProfile.software.os.kernelVersion && (
                        <div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wide">Kernel</div>
                          <div className="font-mono text-sm">{latestProfile.software.os.kernelVersion}</div>
                        </div>
                      )}
                    </div>
                    <div className="space-y-3">
                      {latestProfile.software.os.architecture && (
                        <div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wide">Architecture</div>
                          <div className="font-medium">{latestProfile.software.os.architecture}</div>
                        </div>
                      )}
                      {latestProfile.software.os.family && (
                        <div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wide">Family</div>
                          <div className="font-medium capitalize">{latestProfile.software.os.family}</div>
                        </div>
                      )}
                      {latestProfile.software.packageCount !== undefined && (
                        <div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wide">Packages</div>
                          <div className="font-medium">{latestProfile.software.packageCount.toLocaleString()}</div>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {latestProfile?.hardware && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Cpu className="h-4 w-4" />
                    Hardware
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {latestProfile.hardware.cpu && (
                      <div className="rounded-lg border p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <Cpu className="h-6 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium">CPU</span>
                        </div>
                        <div className="text-sm truncate mb-1" title={latestProfile.hardware.cpu.model}>
                          {latestProfile.hardware.cpu.model || 'Unknown CPU'}
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                          {latestProfile.hardware.cpu.coresPhysical && (
                            <span>{latestProfile.hardware.cpu.coresPhysical} cores</span>
                          )}
                          {latestProfile.hardware.cpu.coresLogical && (
                            <span>• {latestProfile.hardware.cpu.coresLogical} threads</span>
                          )}
                          {latestProfile.hardware.cpu.frequencyMhz && (
                            <span>• {(latestProfile.hardware.cpu.frequencyMhz / 1000).toFixed(1)} GHz</span>
                          )}
                        </div>
                      </div>
                    )}
                    {latestProfile.hardware.memory && (
                      <div className="rounded-lg border p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <MemoryStick className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium">Memory</span>
                        </div>
                        <div className="text-sm mb-1">
                          {latestProfile.hardware.memory.totalBytes
                            ? formatBytes(latestProfile.hardware.memory.totalBytes)
                            : 'Unknown'}
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                          {latestProfile.hardware.memory.type && (
                            <span>{latestProfile.hardware.memory.type}</span>
                          )}
                          {latestProfile.hardware.memory.speedMhz && (
                            <span>• {latestProfile.hardware.memory.speedMhz} MHz</span>
                          )}
                          {latestProfile.hardware.memory.slotsUsed !== undefined &&
                            latestProfile.hardware.memory.slotsTotal !== undefined && (
                              <span>• {latestProfile.hardware.memory.slotsUsed}/{latestProfile.hardware.memory.slotsTotal} slots</span>
                            )}
                        </div>
                      </div>
                    )}
                  </div>
                  {(latestProfile.hardware.systemManufacturer || latestProfile.hardware.systemModel) && (
                    <div className="mt-4 pt-4 border-t">
                      <div className="flex items-center gap-2 mb-2">
                        <Shield className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">System</span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                        {latestProfile.hardware.systemManufacturer && (
                          <span>{latestProfile.hardware.systemManufacturer}</span>
                        )}
                        {latestProfile.hardware.systemModel && (
                          <span className="text-muted-foreground">{latestProfile.hardware.systemModel}</span>
                        )}
                      </div>
                    </div>
                  )}
                  {latestProfile.hardware.gpus && latestProfile.hardware.gpus.length > 0 && (
                    <div className="mt-4 pt-4 border-t">
                      <div className="flex items-center gap-2 mb-2">
                        <Layers className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">GPU ({latestProfile.hardware.gpus.length})</span>
                      </div>
                      <div className="space-y-2">
                        {latestProfile.hardware.gpus.slice(0, 2).map((gpu, idx) => (
                          <div key={idx} className="text-sm">
                            <span>{gpu.model || 'Unknown GPU'}</span>
                            {gpu.memoryBytes && (
                              <span className="text-muted-foreground ml-2">
                                ({formatBytes(gpu.memoryBytes)})
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}


          </div>

          <div className="space-y-6">
            {latestProfile?.storage?.filesystems && latestProfile.storage.filesystems.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <HardDrive className="h-4 w-4" />
                    Storage Usage
                  </CardTitle>
                  {latestProfile.storage.totalCapacityBytes && (
                    <CardDescription>
                      Total capacity: {formatBytes(latestProfile.storage.totalCapacityBytes)}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {(showAllFilesystems ? latestProfile.storage.filesystems : latestProfile.storage.filesystems.slice(0, 6)).map((fs, idx) => {
                      const usedPercent =
                        fs.sizeBytes && fs.usedBytes
                          ? Math.round((fs.usedBytes / fs.sizeBytes) * 100)
                          : 0;
                      return (
                        <div key={`${fs.mountPoint}-${idx}`} className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-mono text-muted-foreground truncate max-w-[150px]" title={fs.mountPoint}>
                              {fs.mountPoint}
                            </span>
                            <span className="text-xs">
                              {fs.usedBytes ? formatBytes(fs.usedBytes) : '?'} / {fs.sizeBytes ? formatBytes(fs.sizeBytes) : '?'}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Progress
                              value={usedPercent}
                              className="h-2 flex-1"
                              indicatorClassName={cn(
                                usedPercent > 90
                                  ? 'bg-destructive'
                                  : usedPercent > 75
                                    ? 'bg-warning'
                                    : 'bg-chart-1'
                              )}
                            />
                            <span className={cn(
                              'text-xs font-medium w-10 text-right',
                              usedPercent > 90 && 'text-destructive',
                              usedPercent > 75 && usedPercent <= 90 && 'text-warning'
                            )}>
                              {usedPercent}%
                            </span>
                          </div>
                        </div>
                      );
                    })}
                    {latestProfile.storage.filesystems.length > 6 && (
                      <button
                        onClick={() => setShowAllFilesystems(!showAllFilesystems)}
                        className="w-full text-xs text-muted-foreground hover:text-foreground text-center pt-2 hover:bg-muted/50 rounded transition-colors py-1"
                      >
                        {showAllFilesystems ? 'Show less' : `+${latestProfile.storage.filesystems.length - 6} more filesystems`}
                      </button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {latestProfile?.network && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Globe className="h-4 w-4" />
                    Network
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="grid gap-3 sm:grid-cols-2">
                      {latestProfile.network.hostname && (
                        <div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wide">Hostname</div>
                          <div className="font-mono text-sm">{latestProfile.network.hostname}</div>
                        </div>
                      )}
                      {latestProfile.network.fqdn && (
                        <div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wide">FQDN</div>
                          <div className="font-mono text-sm truncate" title={latestProfile.network.fqdn}>
                            {latestProfile.network.fqdn}
                          </div>
                        </div>
                      )}
                      {latestProfile.network.defaultGateway && (
                        <div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wide">Default Gateway</div>
                          <div className="font-mono text-sm">{latestProfile.network.defaultGateway}</div>
                        </div>
                      )}
                      {latestProfile.network.dnsServers && latestProfile.network.dnsServers.length > 0 && (
                        <div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wide">DNS Servers</div>
                          <div className="font-mono text-sm">{latestProfile.network.dnsServers.slice(0, 2).join(', ')}</div>
                        </div>
                      )}
                    </div>

                    {latestProfile.network.interfaces && latestProfile.network.interfaces.length > 0 && (
                      <div className="pt-4 border-t">
                        <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                          Interfaces ({latestProfile.network.interfaces.length})
                        </div>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {(showAllInterfaces ? latestProfile.network.interfaces : latestProfile.network.interfaces.slice(0, 4)).map((iface) => (
                            <div key={iface.name} className="rounded-lg border p-2 text-sm">
                              <div className="flex items-center justify-between">
                                <span className="font-mono">{iface.name}</span>
                                <Badge
                                  variant={iface.state === 'up' ? 'success' : 'secondary'}
                                  className="text-[10px] px-1.5 py-0"
                                >
                                  {iface.state}
                                </Badge>
                              </div>
                              {iface.ipv4Addresses && iface.ipv4Addresses.length > 0 && (
                                <div className="font-mono text-xs text-muted-foreground mt-1">
                                  {iface.ipv4Addresses[0]}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                        {latestProfile.network.interfaces.length > 4 && (
                          <button
                            onClick={() => setShowAllInterfaces(!showAllInterfaces)}
                            className="text-xs text-muted-foreground hover:text-foreground mt-2 hover:bg-muted/50 rounded transition-colors px-2 py-1"
                          >
                            {showAllInterfaces ? 'Show less' : `+${latestProfile.network.interfaces.length - 4} more interfaces`}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {services.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Boxes className="h-4 w-4" />
                      Services
                    </CardTitle>
                    <Badge variant="outline" className="text-xs">
                      {runningServices.length}/{services.length} running
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {services.slice(0, 8).map((service) => (
                      <ServiceItem key={service.serviceId} service={service} nodeId={nodeIdStr} />
                    ))}
                    {services.length > 8 && (
                      <Link
                        href={`${ROUTES.SERVICES}?nodeId=${node.id}`}
                        className="block text-xs text-primary hover:underline text-center pt-2"
                      >
                        View all {services.length} services
                      </Link>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {latestProfile?.users?.users && latestProfile.users.users.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    Users ({latestProfile.users.users.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {(showAllUsers ? latestProfile.users.users : latestProfile.users.users.slice(0, 12)).map((user) => (
                      <Badge key={user.username} variant="outline" className="font-mono text-xs">
                        {user.username}
                      </Badge>
                    ))}
                    {latestProfile.users.users.length > 12 && (
                      <button
                        onClick={() => setShowAllUsers(!showAllUsers)}
                        className="px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                      >
                        {showAllUsers ? 'less' : `+${latestProfile.users.users.length - 12} more`}
                      </button>
                    )}
                  </div>
                  {latestProfile.users.sshKeys && latestProfile.users.sshKeys.length > 0 && (
                    <div className="mt-3 pt-3 border-t text-xs text-muted-foreground">
                      {latestProfile.users.sshKeys.length} SSH key{latestProfile.users.sshKeys.length !== 1 ? 's' : ''} configured
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {profileSnapshots.length > 0 && (
        <NodeDashboardCharts
          profileSnapshots={profileSnapshots}
          isLoading={snapshotsLoading}
        />
      )}

      {node.tags && node.tags.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Tag className="h-4 w-4" />
              Tags
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {node.tags.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {(node.parentNodeId || (node.networkIds && node.networkIds.length > 0)) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Info className="h-4 w-4" />
              Relationships
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {node.parentNodeId && (
                <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                  <span className="text-muted-foreground">Parent</span>
                  <Link
                    href={`${ROUTES.NODES}/${node.parentNodeId}`}
                    className="font-mono text-sm text-primary hover:underline"
                  >
                    {node.parentNodeId}
                  </Link>
                </div>
              )}
              {node.networkIds && node.networkIds.length > 0 && (
                <div className="rounded-lg bg-muted/50 px-3 py-2">
                  <span className="text-muted-foreground">Networks</span>
                  <div className="mt-2 space-y-1">
                    {(showAllNetworks ? node.networkIds : node.networkIds.slice(0, 4)).map((networkId) => (
                      <Link
                        key={networkId}
                        href={`${ROUTES.NETWORKS}/${networkId}`}
                        className="block font-mono text-sm text-primary hover:underline"
                      >
                        {networkId}
                      </Link>
                    ))}
                    {node.networkIds.length > 4 && (
                      <button
                        onClick={() => setShowAllNetworks(!showAllNetworks)}
                        className="text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded transition-colors px-1 py-0.5"
                      >
                        {showAllNetworks ? 'less' : `+${node.networkIds.length - 4} more`}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatsCard({
  icon,
  title,
  value,
  description,
  isLoading,
}: {
  icon: React.ReactNode;
  title: string;
  value: number | string;
  description: string;
  isLoading: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <div className="text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-16" />
        ) : (
          <>
            <div className="text-2xl font-bold">{value}</div>
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ServiceItem({ service }: { service: ServiceSummary; nodeId: string }) {
  const statusIcon = {
    running: <PlayCircle className="h-3.5 w-3.5 text-success" />,
    stopped: <PauseCircle className="h-3.5 w-3.5 text-muted-foreground" />,
    failed: <XCircle className="h-3.5 w-3.5 text-destructive" />,
    unknown: <AlertCircle className="h-3.5 w-3.5 text-muted-foreground" />,
  };

  const runtimeStyle = SERVICE_RUNTIME_COLORS[service.runtime];

  return (
    <Link
      href={`${ROUTES.SERVICES}/${service.id || service.serviceId}`}
      className="flex items-center justify-between rounded-lg border p-2 hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-center gap-2 min-w-0">
        {statusIcon[service.status as keyof typeof statusIcon] || statusIcon.unknown}
        <span className="text-sm font-medium truncate">{service.name}</span>
      </div>
      <Badge
        variant="outline"
        className={cn('text-[10px] px-1.5 py-0 shrink-0', runtimeStyle?.bg, runtimeStyle?.text)}
      >
        {service.runtime}
      </Badge>
    </Link>
  );
}

function NodeDashboardCharts({
  profileSnapshots,
  isLoading,
}: {
  profileSnapshots: Profile[];
  isLoading: boolean;
}) {
  const [chartMetric, setChartMetric] = useState<'memory' | 'storage' | 'cpu' | 'services' | 'interfaces'>(
    'storage'
  );

  const timelineData = useMemo(() => {
    return profileSnapshots
      .slice()
      .sort((a, b) => new Date(a.submittedAt).getTime() - new Date(b.submittedAt).getTime())
      .map((profile) => {
        const memoryTotal = profile.hardware?.memory?.totalBytes;
        const memoryGB = memoryTotal ? Math.round(memoryTotal / (1024 * 1024 * 1024)) : null;

        const filesystems = profile.storage?.filesystems || [];
        const storageTotals = filesystems.reduce(
          (acc, fs) => {
            acc.used += fs.usedBytes || 0;
            acc.total += fs.sizeBytes || 0;
            return acc;
          },
          { used: 0, total: 0 }
        );
        const storageUsedPercent =
          storageTotals.total > 0 ? Math.round((storageTotals.used / storageTotals.total) * 100) : null;

        const cpuCores = profile.hardware?.cpu?.coresLogical ?? null;
        const servicesCount = profile.serviceIds?.length ?? null;
        const interfacesCount = profile.network?.interfaces?.length ?? null;

        return {
          timestamp: new Date(profile.submittedAt),
          label: new Date(profile.submittedAt).toLocaleDateString([], {
            month: 'short',
            day: 'numeric',
          }),
          memoryGB,
          storageUsedPercent,
          cpuCores,
          servicesCount,
          interfacesCount,
        };
      });
  }, [profileSnapshots]);

  const metricConfig = {
    memory: {
      label: 'Memory (GB)',
      dataKey: 'memoryGB',
      unit: ' GB',
      color: 'hsl(var(--chart-1))',
    },
    storage: {
      label: 'Storage Used (%)',
      dataKey: 'storageUsedPercent',
      unit: '%',
      color: 'hsl(var(--chart-2))',
    },
    cpu: {
      label: 'CPU Cores',
      dataKey: 'cpuCores',
      unit: '',
      color: 'hsl(var(--chart-3))',
    },
    services: {
      label: 'Services Discovered',
      dataKey: 'servicesCount',
      unit: '',
      color: 'hsl(var(--chart-4))',
    },
    interfaces: {
      label: 'Network Interfaces',
      dataKey: 'interfacesCount',
      unit: '',
      color: 'hsl(var(--chart-5))',
    },
  } as const;

  const config = metricConfig[chartMetric];
  const latestPoint = timelineData[timelineData.length - 1];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Profile History
            </CardTitle>
            <CardDescription>
              Tracking {timelineData.length} profile snapshots
            </CardDescription>
          </div>
          <Select
            value={chartMetric}
            onValueChange={(v) => setChartMetric(v as typeof chartMetric)}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="storage">Storage Usage</SelectItem>
              <SelectItem value="memory">Memory (GB)</SelectItem>
              <SelectItem value="cpu">CPU Cores</SelectItem>
              <SelectItem value="services">Services Count</SelectItem>
              <SelectItem value="interfaces">Interfaces Count</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="text-sm text-muted-foreground">{config.label}</div>
          {latestPoint && latestPoint[config.dataKey as keyof typeof latestPoint] !== null && (
            <div className="flex items-center gap-2 text-sm">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span>Latest: </span>
              <span className="font-semibold">
                {String(latestPoint[config.dataKey as keyof typeof latestPoint])}{config.unit}
              </span>
            </div>
          )}
        </div>
        {isLoading ? (
          <Skeleton className="h-[200px]" />
        ) : (
          <div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timelineData}>
                <defs>
                  <linearGradient id="metricGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={config.color} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={config.color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="label"
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  unit={config.unit}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--popover))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                  labelFormatter={(_, payload) => {
                    if (payload && payload[0]) {
                      const data = payload[0].payload;
                      return data.timestamp.toLocaleString();
                    }
                    return '';
                  }}
                  formatter={(value: string | number | (string | number)[]) =>
                    value == null ? ['No data', 'Value'] : [`${value}${config.unit}`, config.label]
                  }
                />
                <Area
                  type="monotone"
                  dataKey={config.dataKey}
                  stroke={config.color}
                  fill="url(#metricGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
