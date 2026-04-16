import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Download,
  Loader2,
  Network as NetworkIcon,
  Radar,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import {
  useApproveDiscovery,
  useDiscoveryDevice,
  useDiscoveryDevices,
  useDiscoveryScan,
  useDiscoveryScans,
  useDismissDiscovery,
  useInstallations,
  useRegisterDiscovery,
  useRejectDiscovery,
  useStartDiscoveryScan,
} from '@/api/discovery';
import { InstallDialog } from './components/install-dialog';
import { InstallProgress } from './components/install-progress';
import { useNetworks } from '@/api/networks';
import { useNodes } from '@/api/nodes';
import { PermissionGate } from '@/components/auth/permission-gate';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { EntityCombobox } from '@/components/ui/entity-combobox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { getErrorMessage } from '@/lib/api-client';
import { ROUTES, STATUS_COLORS } from '@/lib/constants';
import { formatRelativeTime } from '@/lib/utils';
import type {
  DiscoveryClass,
  DiscoveryDeviceStatus,
  DiscoveryPortTier,
  DiscoveryScanMethod,
  DiscoveredDevice,
} from '@/types/discovery';

const SCAN_METHOD_OPTIONS: Array<{
  value: DiscoveryScanMethod;
  label: string;
}> = [
  { value: 'arp', label: 'ARP' },
  { value: 'tcp_port', label: 'Ports' },
  { value: 'mdns', label: 'mDNS' },
  { value: 'ssdp', label: 'SSDP' },
  { value: 'snmp', label: 'SNMP' },
];

const DEVICE_STATUS_OPTIONS: Array<{
  value: DiscoveryDeviceStatus | 'all';
  label: string;
}> = [
  { value: 'all', label: 'All devices' },
  { value: 'pending', label: 'Pending review' },
  { value: 'approved', label: 'Approved' },
  { value: 'registered', label: 'Registered' },
  { value: 'installing', label: 'Installing' },
  { value: 'installed', label: 'Installed' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'dismissed', label: 'Dismissed' },
];

const NODE_CLASS_OPTIONS: Array<{
  value: DiscoveryClass | 'auto';
  label: string;
}> = [
  { value: 'auto', label: 'Use suggested class' },
  { value: 'compute', label: 'Compute' },
  { value: 'networking', label: 'Networking' },
  { value: 'iot', label: 'IoT' },
  { value: 'unknown', label: 'Unknown' },
];

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] ?? STATUS_COLORS.unknown;

  return (
    <Badge variant="outline" className={`${colors.bg} ${colors.text} border-transparent`}>
      <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${colors.dot}`} />
      {status}
    </Badge>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-5">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold">{value}</p>
        </div>
        <div className={`rounded-full p-3 ${tone}`}>
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyDetail({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <Card>
      <CardContent className="flex min-h-[320px] flex-col items-center justify-center gap-3 p-8 text-center">
        <Search className="h-10 w-10 text-muted-foreground" />
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function deviceLabel(device: DiscoveredDevice) {
  return device.identity.hostname || device.identity.currentIp;
}

function fingerprintSummary(device: DiscoveredDevice) {
  const vendor = device.rawEvidence?.vendor || device.fingerprint?.vendor;
  const family = device.fingerprint?.deviceFamily;
  return [vendor, family].filter(Boolean).join(' • ') || 'Evidence pending review';
}

export default function DiscoveryPage() {
  useDocumentTitle('Discovery Explorer');
  const [scanDialogOpen, setScanDialogOpen] = useState(false);
  const [selectedScanId, setSelectedScanId] = useState<string | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [deviceStatus, setDeviceStatus] = useState<DiscoveryDeviceStatus | 'all'>('pending');
  const [deviceSearch, setDeviceSearch] = useState('');
  const [deviceClassFilter, setDeviceClassFilter] = useState<DiscoveryClass | 'all'>('all');
  const [scanMode, setScanMode] = useState<'api-direct' | 'agent-delegated'>('api-direct');
  const [scanForm, setScanForm] = useState({
    subnet: '',
    networkId: '',
    delegateToNodeId: '',
    portTier: 'tier1' as DiscoveryPortTier,
    timeoutSeconds: '60',
    includeIoTProtocols: false,
    methods: {
      arp: true,
      tcp_port: true,
      mdns: true,
      ssdp: true,
      snmp: true,
    } as Record<DiscoveryScanMethod, boolean>,
  });
  const [installDialogOpen, setInstallDialogOpen] = useState(false);
  const [installDeviceId, setInstallDeviceId] = useState<string | null>(null);
  const [activeInstallationId, setActiveInstallationId] = useState<string | null>(null);
  const [reviewForm, setReviewForm] = useState({
    nodeId: '',
    nodeClass: '',
    tags: '',
      rejectReason: '',
      dismissReason: '',
  });

  const { data: scannersData } = useNodes({
    limit: 100,
    status: 'active',
    agentTier: 'max',
  });
  const scanners = useMemo(() => scannersData?.items ?? [], [scannersData?.items]);

  // Fetch networks for CIDR suggestions in scan dialog
  const { data: networksData } = useNetworks({ limit: 200 });
  const networkCidrOptions = useMemo(
    () =>
      (networksData?.items ?? [])
        .filter((n) => n.cidr)
        .map((n) => ({
          id: n.cidr!,
          label: `${n.name} (${n.cidr})`,
          sublabel: n.type,
          icon: NetworkIcon,
          iconColorClass: 'text-network' as const,
        })),
    [networksData],
  );

  const {
    data: scansResponse,
    isLoading: scansLoading,
  } = useDiscoveryScans({
    limit: 12,
    sortBy: 'createdAt',
    sortOrder: 'desc',
  });
  const scans = useMemo(() => scansResponse?.items ?? [], [scansResponse?.items]);

  const {
    data: devicesResponse,
    isLoading: devicesLoading,
  } = useDiscoveryDevices({
    limit: 25,
    status: deviceStatus === 'all' ? undefined : deviceStatus,
    deviceClass: deviceClassFilter === 'all' ? undefined : deviceClassFilter,
    search: deviceSearch || undefined,
    sortBy: 'lastSeen',
    sortOrder: 'desc',
  });
  const devices = useMemo(() => devicesResponse?.items ?? [], [devicesResponse?.items]);

  useEffect(() => {
    if (!scans.length) {
      setSelectedScanId(null);
      return;
    }
    if (!selectedScanId || !scans.some((scan) => scan.scanId === selectedScanId)) {
      setSelectedScanId(scans[0].scanId);
    }
  }, [scans, selectedScanId]);

  useEffect(() => {
    if (!devices.length) {
      setSelectedDeviceId(null);
      return;
    }
    if (!selectedDeviceId || !devices.some((device) => device.discoveryId === selectedDeviceId)) {
      setSelectedDeviceId(devices[0].discoveryId);
    }
  }, [devices, selectedDeviceId]);

  const { data: installationsResponse } = useInstallations({
    limit: 5,
    sortBy: 'createdAt',
    sortOrder: 'desc',
  });
  const recentInstallations = useMemo(
    () => installationsResponse?.items ?? [],
    [installationsResponse?.items]
  );

  const installDevice = useMemo(
    () => devices.find((d) => d.discoveryId === installDeviceId) ?? null,
    [devices, installDeviceId]
  );

  const { data: selectedScan } = useDiscoveryScan(selectedScanId);
  const { data: selectedDevice } = useDiscoveryDevice(selectedDeviceId);

  useEffect(() => {
    if (!selectedDevice) {
      return;
    }
    setReviewForm({
        nodeId: selectedDevice.identity.hostname || '',
        nodeClass: 'auto',
        tags: '',
        rejectReason: selectedDevice.rejectReason || '',
        dismissReason: selectedDevice.dismissReason || '',
    });
  }, [selectedDevice]);

  const startScan = useStartDiscoveryScan();
  const approveDiscovery = useApproveDiscovery(selectedDeviceId);
  const registerDiscovery = useRegisterDiscovery(selectedDeviceId);
  const rejectDiscovery = useRejectDiscovery(selectedDeviceId);
  const dismissDiscovery = useDismissDiscovery(selectedDeviceId);

  const stats = useMemo(() => {
    const pendingScans = scans.filter((scan) => scan.status === 'pending' || scan.status === 'running').length;
    const pendingDevices = devices.filter((device) => device.status === 'pending').length;
    const registrable = devices.filter((device) => device.classification?.eligibleForRegistration).length;
    return {
      pendingScans,
      pendingDevices,
      registrable,
      scanners: scanners.length,
    };
  }, [devices, scans, scanners.length]);

  const handleMethodToggle = (method: DiscoveryScanMethod, checked: boolean) => {
    setScanForm((current) => ({
      ...current,
      methods: {
        ...current.methods,
        [method]: checked,
      },
    }));
  };

  const handleStartScan = async () => {
    const methods = SCAN_METHOD_OPTIONS
      .filter((option) => scanForm.methods[option.value])
      .map((option) => option.value);

    if (!scanForm.subnet.trim()) {
      toast.error('A subnet or CIDR range is required.');
      return;
    }
    if (scanMode === 'agent-delegated' && !scanForm.delegateToNodeId) {
      toast.error('Select a max-tier scanner node to run the delegated scan.');
      return;
    }
    if (!methods.length) {
      toast.error('Select at least one scan method.');
      return;
    }

    const isApiDirect = scanMode === 'api-direct';
    const delegateNodeId = isApiDirect ? null : scanForm.delegateToNodeId;

    try {
      const scan = await startScan.mutateAsync({
        targets: [
          {
            subnet: scanForm.subnet.trim(),
            networkId: scanForm.networkId || undefined,
            delegateToNodeId: delegateNodeId,
          },
        ],
        delegateToNodeId: delegateNodeId,
        options: {
          methods,
          portTier: scanForm.portTier,
          timeoutSeconds: Number(scanForm.timeoutSeconds || 60),
          includeIoTProtocols: scanForm.includeIoTProtocols,
        },
      });
      toast.success(
        isApiDirect
          ? 'API-direct scan started. Results will appear as hosts are probed.'
          : 'Delegated scan queued for agent execution.'
      );
      setSelectedScanId(scan.scanId);
      setScanDialogOpen(false);
      setScanForm({
        subnet: '',
        networkId: '',
        delegateToNodeId: '',
        portTier: 'tier1',
        timeoutSeconds: '60',
        includeIoTProtocols: false,
        methods: {
          arp: true,
          tcp_port: true,
          mdns: true,
          ssdp: true,
          snmp: true,
        },
      });
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to start discovery scan.'));
    }
  };

  const handleApprove = async (autoRegister: boolean) => {
    if (!selectedDevice) {
      return;
    }
    try {
      const result = await approveDiscovery.mutateAsync({
        autoRegister,
        nodeId: reviewForm.nodeId.trim() || undefined,
        nodeClass: reviewForm.nodeClass === 'auto' ? undefined : reviewForm.nodeClass,
        tags: reviewForm.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      });
      toast.success(
        autoRegister
          ? `Registered ${deviceLabel(selectedDevice)} as ${result.matchedNodeId}.`
          : `Approved ${deviceLabel(selectedDevice)} for later registration.`
      );
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to approve discovery.'));
    }
  };

  const handleRegister = async () => {
    if (!selectedDevice) {
      return;
    }
    try {
      const result = await registerDiscovery.mutateAsync({
        nodeId: reviewForm.nodeId.trim() || undefined,
        class: reviewForm.nodeClass === 'auto' ? undefined : reviewForm.nodeClass,
        tags: reviewForm.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
        overrideClassification: reviewForm.nodeClass !== 'auto',
      });
      toast.success(`Registered ${deviceLabel(selectedDevice)} as ${result.nodeId}.`);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to register discovery.'));
    }
  };

  const handleReject = async () => {
    if (!selectedDevice) {
      return;
    }
    try {
      await rejectDiscovery.mutateAsync({
        reason: reviewForm.rejectReason.trim() || undefined,
      });
      toast.success(`Rejected ${deviceLabel(selectedDevice)}.`);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to reject discovery.'));
    }
  };

  const handleDismiss = async () => {
    if (!selectedDevice) {
      return;
    }
    try {
      await dismissDiscovery.mutateAsync({
        reason: reviewForm.dismissReason.trim() || undefined,
      });
      toast.success(`Dismissed ${deviceLabel(selectedDevice)}.`);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to dismiss discovery.'));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title="Discovery"
        subtitle="Scan subnets directly from the API or delegate to agents, review raw evidence, and promote new devices into managed nodes."
        showBackButton={false}
        actions={
          <PermissionGate permissions={['discovery:scan']}>
            <Button onClick={() => setScanDialogOpen(true)}>
              <Radar className="mr-2 h-4 w-4" />
              Start Scan
            </Button>
          </PermissionGate>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Radar} label="Queued or Running" value={stats.pendingScans} tone="bg-info/10 text-info" />
        <MetricCard icon={AlertTriangle} label="Pending Review" value={stats.pendingDevices} tone="bg-warning/10 text-warning" />
        <MetricCard icon={ShieldCheck} label="Registrable" value={stats.registrable} tone="bg-success/10 text-success" />
        <MetricCard icon={Server} label="Max-Tier Scanners" value={stats.scanners} tone="bg-primary/10 text-primary" />
      </div>

      <Tabs defaultValue="scans" className="space-y-4">
        <TabsList>
          <TabsTrigger value="scans">Scans</TabsTrigger>
          <TabsTrigger value="devices">Discoveries</TabsTrigger>
        </TabsList>

        <TabsContent value="scans" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
            <Card>
              <CardHeader>
                <CardTitle>Recent Scans</CardTitle>
                <CardDescription>API-direct and delegated scans update here as results arrive.</CardDescription>
              </CardHeader>
              <CardContent>
                {scansLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3].map((row) => (
                      <Skeleton key={row} className="h-14 w-full" />
                    ))}
                  </div>
                ) : !scans.length ? (
                  <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                    No discovery scans yet. Start an API-direct scan or delegate to an agent to begin discovering devices.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Target</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Progress</TableHead>
                        <TableHead>Results</TableHead>
                        <TableHead>Started</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {scans.map((scan) => (
                        <TableRow
                          key={scan.scanId}
                          className="cursor-pointer"
                          data-state={scan.scanId === selectedScanId ? 'selected' : undefined}
                          onClick={() => setSelectedScanId(scan.scanId)}
                        >
                          <TableCell>
                            <div className="space-y-1">
                              <div className="font-medium">
                                {scan.scanId}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {selectedScan?.scanId === scan.scanId && selectedScan.targets[0]?.subnet
                                  ? selectedScan.targets[0]?.subnet
                                  : `${scan.targetCount} target${scan.targetCount === 1 ? '' : 's'}`}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={scan.status} />
                          </TableCell>
                          <TableCell className="min-w-[160px]">
                            <div className="space-y-1">
                              <Progress value={scan.progress.percentComplete} />
                              <div className="text-xs text-muted-foreground">
                                {Math.round(scan.progress.percentComplete)}% • {scan.progress.hostsScanned}/{scan.progress.hostsTotal} hosts
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>{scan.resultCount}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {scan.startedAt ? formatRelativeTime(scan.startedAt) : 'Queued'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            {!selectedScanId ? (
              <EmptyDetail
                title="No Scan Selected"
                description="Pick a scan from the list to inspect progress, delegation details, and normalized results."
              />
            ) : !selectedScan ? (
              <Card>
                <CardContent className="flex min-h-[320px] items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Scan Detail</CardTitle>
                  <CardDescription>{selectedScan.targets[0]?.subnet || 'Delegated discovery target'}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <StatusBadge status={selectedScan.status} />
                      <span className="text-sm text-muted-foreground">
                        {Math.round(selectedScan.progress.percentComplete)}% complete
                      </span>
                    </div>
                    <Progress value={selectedScan.progress.percentComplete} />
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Execution</p>
                      {selectedScan.execution?.method === 'api-direct' ? (
                        <>
                          <p className="mt-1 font-medium">API Direct</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            TCP connect probing from the API server
                          </p>
                        </>
                      ) : (
                        <>
                          <p className="mt-1 font-medium">{selectedScan.delegation?.delegatedTo || 'Not assigned'}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {selectedScan.delegation?.commandStatus || selectedScan.progress.phase}
                          </p>
                        </>
                      )}
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Methods</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {selectedScan.options.methods.map((method) => (
                          <Badge key={method} variant="outline">
                            {method}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Hosts</p>
                      <div className="mt-2 grid gap-2 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Scanned</span>
                          <span className="font-medium">{selectedScan.progress.hostsScanned}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Alive</span>
                          <span className="font-medium">{selectedScan.progress.hostsAlive}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Results</span>
                          <span className="font-medium">{selectedScan.resultCount}</span>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Scan Options</p>
                      <div className="mt-2 grid gap-2 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Port tier</span>
                          <span className="font-medium">{selectedScan.options.portTier}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Timeout</span>
                          <span className="font-medium">{selectedScan.options.timeoutSeconds}s</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">IoT protocols</span>
                          <span className="font-medium">
                            {selectedScan.options.includeIoTProtocols ? 'Enabled' : 'Disabled'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {selectedScan.summary && (
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Summary</p>
                      <div className="mt-2 grid gap-2 sm:grid-cols-2 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">New discoveries</span>
                          <span className="font-medium">{selectedScan.summary.newDiscoveries}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Returning devices</span>
                          <span className="font-medium">{selectedScan.summary.returningDevices}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {selectedScan.error && (
                    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
                      <p className="text-sm font-medium text-destructive">{selectedScan.error.code}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{selectedScan.error.message}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        <TabsContent value="devices" className="space-y-4">
          <Card>
            <CardContent className="grid gap-4 p-5 md:grid-cols-[0.85fr_0.7fr_0.7fr_0.75fr]">
              <div className="space-y-2">
                <Label htmlFor="device-search">Search</Label>
                <Input
                  id="device-search"
                  placeholder="Hostname, IP, or MAC"
                  value={deviceSearch}
                  onChange={(event) => setDeviceSearch(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <Select value={deviceStatus} onValueChange={(value) => setDeviceStatus(value as DiscoveryDeviceStatus | 'all')}>
                  <SelectTrigger aria-label="Discovery device status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DEVICE_STATUS_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Class</Label>
                <Select value={deviceClassFilter} onValueChange={(value) => setDeviceClassFilter(value as DiscoveryClass | 'all')}>
                  <SelectTrigger aria-label="Discovery device class">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All classes</SelectItem>
                    <SelectItem value="compute">Compute</SelectItem>
                    <SelectItem value="networking">Networking</SelectItem>
                    <SelectItem value="iot">IoT</SelectItem>
                    <SelectItem value="unknown">Unknown</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end">
                <div className="rounded-lg border bg-muted/30 px-4 py-3 text-sm">
                  Evidence-rich discoveries can be approved directly into nodes from the detail panel.
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
            <Card>
              <CardHeader>
                <CardTitle>Discoveries</CardTitle>
                <CardDescription>Raw evidence, explainable classification, and promotion status for each device.</CardDescription>
              </CardHeader>
              <CardContent>
                {devicesLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3, 4].map((row) => (
                      <Skeleton key={row} className="h-16 w-full" />
                    ))}
                  </div>
                ) : !devices.length ? (
                  <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                    No discoveries match the current filters.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Device</TableHead>
                        <TableHead>Suggested Class</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Evidence</TableHead>
                        <TableHead>Last Seen</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {devices.map((device) => (
                        <TableRow
                          key={device.discoveryId}
                          className="cursor-pointer"
                          data-state={device.discoveryId === selectedDeviceId ? 'selected' : undefined}
                          onClick={() => setSelectedDeviceId(device.discoveryId)}
                        >
                          <TableCell>
                            <div className="space-y-1">
                              <div className="font-medium">{deviceLabel(device)}</div>
                              <div className="text-xs text-muted-foreground">
                                {device.identity.currentIp}
                                {device.identity.macVendor ? ` • ${device.identity.macVendor}` : device.rawEvidence?.macOui ? ` • ${device.rawEvidence.macOui}` : ''}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            {device.classification ? (
                              <div className="space-y-1">
                                <Badge variant="outline">{device.classification.suggestedClass}</Badge>
                                <div className="text-xs text-muted-foreground">
                                  {Math.round(device.classification.confidence * 100)}% confidence
                                </div>
                              </div>
                            ) : (
                              <span className="text-sm text-muted-foreground">Pending</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={device.status} />
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {fingerprintSummary(device)}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {formatRelativeTime(device.lastSeen)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            {!selectedDeviceId ? (
              <EmptyDetail
                title="No Discovery Selected"
                description="Choose a discovered device to inspect fingerprint evidence and approve or reject it."
              />
            ) : !selectedDevice ? (
              <Card>
                <CardContent className="flex min-h-[420px] items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>{deviceLabel(selectedDevice)}</CardTitle>
                  <CardDescription>
                    {selectedDevice.identity.currentIp}
                    {selectedDevice.networkId ? ` • ${selectedDevice.networkId}` : ''}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="flex items-center justify-between">
                    <StatusBadge status={selectedDevice.status} />
                    <span className="text-sm text-muted-foreground">
                      Seen {selectedDevice.seenCount} time{selectedDevice.seenCount === 1 ? '' : 's'}
                    </span>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Classification</p>
                      {selectedDevice.classification ? (
                        <div className="mt-2 space-y-2">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">{selectedDevice.classification.suggestedClass}</Badge>
                            {selectedDevice.classification.suggestedType && (
                              <Badge variant="secondary">{selectedDevice.classification.suggestedType}</Badge>
                            )}
                            {selectedDevice.classification.suggestedKind && (
                              <Badge variant="secondary">{selectedDevice.classification.suggestedKind}</Badge>
                            )}
                            <span className="text-xs text-muted-foreground">
                              {Math.round(selectedDevice.classification.confidence * 100)}%
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {selectedDevice.classification.explanation || 'Explainable evidence will appear here once enrichment completes.'}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {selectedDevice.classification.signals.map((signal) => (
                              <Badge key={signal} variant="outline">
                                {signal}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <p className="mt-2 text-sm text-muted-foreground">Fingerprinting still in progress.</p>
                      )}
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Probe</p>
                      <div className="mt-2 grid gap-2 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Scanner</span>
                          <span className="font-medium">{selectedDevice.probe.scannedBy}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Method</span>
                          <span className="font-medium">{selectedDevice.probe.method}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Scanned</span>
                          <span className="font-medium">{formatRelativeTime(selectedDevice.probe.scannedAt)}</span>
                        </div>
                        {selectedDevice.probe.delegatedByScanId && (
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Scan</span>
                            <span className="font-medium">{selectedDevice.probe.delegatedByScanId}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Evidence</p>
                    <div className="mt-2 grid gap-3 text-sm">
                      <div>
                        <span className="text-muted-foreground">Vendor</span>
                        <p className="font-medium">{selectedDevice.rawEvidence?.vendor || selectedDevice.fingerprint?.vendor || 'Unknown vendor'}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Open ports</span>
                        <div className="mt-1 flex flex-wrap gap-2">
                          {(selectedDevice.openPorts.length ? selectedDevice.openPorts : [0]).map((port) => (
                            <Badge key={port} variant="outline">
                              {port === 0 ? 'No open ports' : port}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Protocols</span>
                        <div className="mt-1 flex flex-wrap gap-2">
                          {(selectedDevice.protocols.length ? selectedDevice.protocols : ['No protocols']).map((protocol) => (
                            <Badge key={protocol} variant="outline">
                              {protocol}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      {selectedDevice.rawEvidence?.dnsNames?.length ? (
                        <div>
                          <span className="text-muted-foreground">DNS names</span>
                          <div className="mt-1 flex flex-wrap gap-2">
                            {selectedDevice.rawEvidence.dnsNames.map((dnsName) => (
                              <Badge key={dnsName} variant="secondary">
                                {dnsName}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {selectedDevice.rawEvidence?.banners && Object.keys(selectedDevice.rawEvidence.banners).length ? (
                        <div>
                          <span className="text-muted-foreground">Banners</span>
                          <div className="mt-2 space-y-2">
                            {Object.entries(selectedDevice.rawEvidence.banners).map(([port, banner]) => (
                              <div key={port} className="rounded-md bg-muted/40 px-3 py-2 text-xs">
                                <span className="font-medium">{port}:</span> {banner}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>

                  {selectedDevice.eligibility && (
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Eligibility</p>
                      <div className="mt-2 grid gap-2 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Registerable</span>
                          <Badge variant={selectedDevice.eligibility.registerable ? 'default' : 'secondary'}>
                            {selectedDevice.eligibility.registerable ? 'Yes' : 'No'}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Agent compatible</span>
                          <Badge variant={selectedDevice.eligibility.agentCompatible ? 'default' : 'secondary'}>
                            {selectedDevice.eligibility.agentCompatible ? 'Yes' : 'No'}
                          </Badge>
                        </div>
                        {selectedDevice.eligibility.agentPlatform && (
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Platform</span>
                            <span className="font-medium">{selectedDevice.eligibility.agentPlatform}</span>
                          </div>
                        )}
                        {selectedDevice.eligibility.profilingStrategy && (
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Profiling strategy</span>
                            <Badge variant="outline">{selectedDevice.eligibility.profilingStrategy}</Badge>
                          </div>
                        )}
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Remote installable</span>
                          <Badge variant={selectedDevice.eligibility.remoteInstallable ? 'default' : 'secondary'}>
                            {selectedDevice.eligibility.remoteInstallable ? `Yes (${selectedDevice.eligibility.remoteInstallMethod})` : 'No'}
                          </Badge>
                        </div>
                        {selectedDevice.eligibility.blockers.length > 0 && (
                          <div>
                            <span className="text-muted-foreground">Blockers</span>
                            <div className="mt-1 space-y-1">
                              {selectedDevice.eligibility.blockers.map((blocker) => (
                                <p key={blocker} className="text-xs text-destructive">{blocker}</p>
                              ))}
                            </div>
                          </div>
                        )}
                        {selectedDevice.eligibility.notes.length > 0 && (
                          <div>
                            <span className="text-muted-foreground">Notes</span>
                            <div className="mt-1 space-y-1">
                              {selectedDevice.eligibility.notes.map((note) => (
                                <p key={note} className="text-xs text-muted-foreground">{note}</p>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <PermissionGate permissions={['discovery:scan']}>
                    <div className="rounded-lg border p-4">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-primary" />
                        <h3 className="font-medium">Review and Promote</h3>
                      </div>
                      <div className="mt-4 grid gap-4">
                        <div className="grid gap-4 sm:grid-cols-2">
                          <div className="space-y-2">
                            <Label>Node ID Override</Label>
                            <EntityCombobox
                              entityType="node"
                              value={reviewForm.nodeId}
                              onValueChange={(val) =>
                                setReviewForm((current) => ({ ...current, nodeId: val }))
                              }
                              allowFreeText
                              clearable
                              placeholder="Enter new or check existing IDs..."
                              triggerAriaLabel="Node ID override"
                              searchAriaLabel="Search node IDs"
                            />
                          </div>
                          <div className="space-y-2">
                            <div className="text-sm font-medium">Node Class</div>
                            <Select
                              value={reviewForm.nodeClass || 'auto'}
                              onValueChange={(value) =>
                                setReviewForm((current) => ({ ...current, nodeClass: value }))
                              }
                            >
                              <SelectTrigger aria-label="Node class">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {NODE_CLASS_OPTIONS.map((option) => (
                                  <SelectItem key={option.label} value={option.value}>
                                    {option.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="tags">Tags</Label>
                          <Input
                            id="tags"
                            value={reviewForm.tags}
                            onChange={(event) =>
                              setReviewForm((current) => ({ ...current, tags: event.target.value }))
                            }
                            placeholder="edge, lab, iot"
                          />
                        </div>

                        <div className="grid gap-4 sm:grid-cols-2">
                          <div className="space-y-2">
                            <Label htmlFor="reject-reason">Reject Reason</Label>
                            <Textarea
                              id="reject-reason"
                              rows={3}
                              value={reviewForm.rejectReason}
                              onChange={(event) =>
                                setReviewForm((current) => ({ ...current, rejectReason: event.target.value }))
                              }
                              placeholder="Why this should not become a managed node"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="dismiss-reason">Dismiss Reason</Label>
                            <Textarea
                              id="dismiss-reason"
                              rows={3}
                              value={reviewForm.dismissReason}
                              onChange={(event) =>
                                setReviewForm((current) => ({ ...current, dismissReason: event.target.value }))
                              }
                              placeholder="Why this should leave the review queue"
                            />
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <PermissionGate permissions={['nodes:create']}>
                            <Button
                              onClick={handleRegister}
                              disabled={
                                !['pending', 'approved'].includes(selectedDevice.status) ||
                                registerDiscovery.isPending
                              }
                            >
                              {registerDiscovery.isPending ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              ) : (
                                <CheckCircle2 className="mr-2 h-4 w-4" />
                              )}
                              Register Node
                            </Button>
                          </PermissionGate>
                          <Button
                            variant="outline"
                            onClick={() => handleApprove(false)}
                            disabled={selectedDevice.status !== 'pending' || approveDiscovery.isPending}
                          >
                            Approve Only
                          </Button>
                          <Button
                            variant="outline"
                            onClick={handleReject}
                            disabled={selectedDevice.status !== 'pending' || rejectDiscovery.isPending}
                          >
                            Reject
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={handleDismiss}
                            disabled={
                              (selectedDevice.status !== 'pending' &&
                                selectedDevice.status !== 'approved') ||
                              dismissDiscovery.isPending
                            }
                          >
                            Dismiss
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => {
                              setInstallDeviceId(selectedDevice.discoveryId);
                              setInstallDialogOpen(true);
                            }}
                            disabled={selectedDevice.status !== 'approved'}
                          >
                            <Download className="mr-2 h-4 w-4" />
                            Install Agent
                          </Button>
                        </div>
                      </div>
                    </div>
                  </PermissionGate>

                  {selectedDevice.matchedNodeId ? (
                    <div className="rounded-lg border border-success/40 bg-success/5 p-3 text-sm">
                      Linked node:
                      {' '}
                      <Link className="font-medium underline" href={ROUTES.NODE_DETAIL.replace(':nodeId', selectedDevice.matchedNodeId)}>
                        {selectedDevice.matchedNodeId}
                      </Link>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Recent Installations */}
      {(recentInstallations.length > 0 || activeInstallationId) && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Installations</CardTitle>
            <CardDescription>
              Track remote agent installations deployed via SSH.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {activeInstallationId && (
              <InstallProgress installationId={activeInstallationId} />
            )}
            {recentInstallations.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Target</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Phase</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentInstallations.map((inst) => (
                    <TableRow
                      key={inst.installationId}
                      className="cursor-pointer"
                      data-state={inst.installationId === activeInstallationId ? 'selected' : undefined}
                      onClick={() => setActiveInstallationId(inst.installationId)}
                    >
                      <TableCell>
                        <div className="font-medium">
                          {inst.targetHostname || inst.targetIp}
                        </div>
                        <div className="text-xs text-muted-foreground">{inst.installationId}</div>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={inst.status} />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {inst.phase}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatRelativeTime(inst.createdAt)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      <InstallDialog
        open={installDialogOpen}
        onOpenChange={setInstallDialogOpen}
        device={installDevice}
        onSuccess={(id) => setActiveInstallationId(id)}
      />

      <Dialog open={scanDialogOpen} onOpenChange={setScanDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Start Discovery Scan</DialogTitle>
            <DialogDescription>
              Scan subnets using the API server directly (TCP connect probing) or delegate to a max-tier agent for richer evidence collection.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <div className="text-sm font-medium">Scan Mode</div>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setScanMode('api-direct')}
                  aria-pressed={scanMode === 'api-direct'}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    scanMode === 'api-direct'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'hover:bg-muted/50'
                  }`}
                >
                  <p className="font-medium text-sm">API Direct</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Scan from the API server using TCP connect probes. No agent required.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => setScanMode('agent-delegated')}
                  aria-pressed={scanMode === 'agent-delegated'}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    scanMode === 'agent-delegated'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'hover:bg-muted/50'
                  }`}
                >
                  <p className="font-medium text-sm">Agent Delegated</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Delegate to a max-tier agent for ARP, banner grabbing, and protocol discovery.
                  </p>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="scan-target-subnet">Target Subnet</Label>
              <EntityCombobox
                triggerId="scan-target-subnet"
                value={scanForm.subnet}
                onValueChange={(val) => {
                  // When selecting a network CIDR, also store the network ID
                  const matchedNetwork = (networksData?.items ?? []).find(
                    (n) => n.cidr === val
                  );
                  setScanForm((current) => ({
                    ...current,
                    subnet: val,
                    networkId: matchedNetwork?.networkId ?? '',
                  }));
                }}
                items={networkCidrOptions}
                allowFreeText
                placeholder="Select network or enter CIDR (e.g. 192.168.1.0/24)..."
                triggerAriaLabel="Target subnet"
                searchAriaLabel="Search network subnets"
              />
            </div>

            {scanMode === 'agent-delegated' && (
              <div className="space-y-2">
                <div className="text-sm font-medium">Delegated Scanner</div>
                <Select
                  value={scanForm.delegateToNodeId || undefined}
                  onValueChange={(value) =>
                    setScanForm((current) => ({ ...current, delegateToNodeId: value }))
                  }
                >
                  <SelectTrigger aria-label="Delegated scanner">
                    <SelectValue placeholder="Select a max-tier node" />
                  </SelectTrigger>
                  <SelectContent>
                    {scanners.map((scanner) => (
                      <SelectItem key={scanner.nodeId} value={scanner.nodeId}>
                        {scanner.displayName} ({scanner.nodeId})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {!scanners.length ? (
                  <p className="text-sm text-warning">No active max-tier scanners are available. Switch to API Direct mode or register an agent first.</p>
                ) : null}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <div className="text-sm font-medium">Port Tier</div>
                <Select
                  value={scanForm.portTier}
                  onValueChange={(value) =>
                    setScanForm((current) => ({ ...current, portTier: value as DiscoveryPortTier }))
                  }
                >
                  <SelectTrigger aria-label="Port tier">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="tier1">Tier 1</SelectItem>
                    <SelectItem value="tier2">Tier 2</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="timeout-seconds">Timeout Seconds</Label>
                <Input
                  id="timeout-seconds"
                  type="number"
                  min={1}
                  max={600}
                  value={scanForm.timeoutSeconds}
                  onChange={(event) =>
                    setScanForm((current) => ({ ...current, timeoutSeconds: event.target.value }))
                  }
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {SCAN_METHOD_OPTIONS.map((option) => (
                <div key={option.value} className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <p className="font-medium">{option.label}</p>
                    <p className="text-xs text-muted-foreground">Collect {option.label.toLowerCase()} evidence during this run.</p>
                  </div>
                  <Switch
                    checked={scanForm.methods[option.value]}
                    onCheckedChange={(checked) => handleMethodToggle(option.value, checked)}
                    aria-label={`${option.label} scan method`}
                  />
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="font-medium">Include IoT protocols</p>
                <p className="text-xs text-muted-foreground">Keep MQTT and embedded signals in the delegated scan payload.</p>
              </div>
              <Switch
                checked={scanForm.includeIoTProtocols}
                onCheckedChange={(checked) =>
                  setScanForm((current) => ({ ...current, includeIoTProtocols: checked }))
                }
                aria-label="Include IoT protocols"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setScanDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleStartScan}
              disabled={
                startScan.isPending ||
                (scanMode === 'agent-delegated' && !scanners.length)
              }
            >
              {startScan.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Radar className="mr-2 h-4 w-4" />}
              {scanMode === 'api-direct' ? 'Start Scan' : 'Queue Scan'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
