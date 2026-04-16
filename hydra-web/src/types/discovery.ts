import type { ListParams } from './api';

export type DiscoveryScanStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type DiscoveryDeviceStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'registered'
  | 'installing'
  | 'installed'
  | 'dismissed';

export type DiscoveryScanMethod = 'arp' | 'tcp_port' | 'mdns' | 'ssdp' | 'snmp';
export type DiscoveryPortTier = 'tier1' | 'tier2';
export type DiscoveryClass = 'compute' | 'networking' | 'iot' | 'unknown';
export type ScanTrigger = 'api' | 'web' | 'mcp';
export type HostnameSource = 'dns-reverse' | 'mdns' | 'netbios' | 'snmp' | 'http-title' | 'ssh-banner';
export type ProfilingStrategy = 'agent' | 'snmp' | 'integration' | 'homeassistant' | 'manual' | 'none';

// ── Port & Protocol Detail Types ──────────────────────────────────

export interface PortInference {
  os?: string | null;
  arch?: string | null;
  application?: string | null;
  version?: string | null;
}

export interface DetailedPort {
  port: number;
  protocol: string;
  state: string;
  service?: string | null;
  banner?: string | null;
  inference?: PortInference | null;
}

export interface MdnsDetail {
  services: string[];
  hostname?: string | null;
  txtRecords: Record<string, string>;
}

export interface SsdpDetail {
  server?: string | null;
  location?: string | null;
  usn?: string | null;
  deviceType?: string | null;
}

export interface SnmpDetail {
  sysDescr?: string | null;
  sysName?: string | null;
  sysObjectID?: string | null;
}

export interface LldpDetail {
  chassisId?: string | null;
  portId?: string | null;
  systemName?: string | null;
  systemDescription?: string | null;
}

export interface ProtocolDetails {
  mdns?: MdnsDetail | null;
  ssdp?: SsdpDetail | null;
  snmp?: SnmpDetail | null;
  lldp?: LldpDetail | null;
}

export interface HttpResponseDetail {
  port: number;
  statusCode?: number | null;
  server?: string | null;
  title?: string | null;
  redirectTo?: string | null;
  identifiedAs?: string | null;
}

// ── Identity Types ────────────────────────────────────────────────

export interface ObservedIp {
  address: string;
  seenAt: string;
  seenInScan?: string | null;
}

export interface DiscoveryScanTarget {
  networkId?: string | null;
  subnet?: string | null;
  delegateToNodeId?: string | null;
}

export interface DiscoveryScanOptions {
  methods: DiscoveryScanMethod[];
  portTier: DiscoveryPortTier;
  timeoutSeconds: number;
  includeIoTProtocols: boolean;
}

export interface DiscoveryScanSummaryResult {
  hostsScanned: number;
  hostsAlive: number;
  newDiscoveries: number;
  returningDevices: number;
  departedSinceLast: number;
  alreadyRegistered: number;
  errors: string[];
}

export interface DiscoveryDeviceIdentity {
  primaryMac?: string | null;
  observedMacs: string[];
  macVendor?: string | null;
  macResolved: boolean;
  currentIp: string;
  observedIps: ObservedIp[];
  hostname?: string | null;
  hostnameSources: HostnameSource[];
}

export interface DiscoveryProbeInfo {
  scannedBy: string;
  method: DiscoveryScanMethod;
  scannedAt: string;
  sourceSubnet?: string | null;
  delegatedByScanId?: string | null;
  scanMethods?: DiscoveryScanMethod[];
}

export interface DiscoveryRawEvidence {
  vendor?: string | null;
  macOui?: string | null;
  dnsNames?: string[];
  banners?: Record<string, string>;
  protocolDetails?: Record<string, unknown>;
  signals?: string[];
}

export interface DiscoveryFingerprint {
  openPorts: DetailedPort[];
  portNumbers: number[];
  serviceHints: string[];
  protocols?: ProtocolDetails | null;
  httpResponses: HttpResponseDetail[];
  osHint?: string | null;
  vendor?: string | null;
  macOui?: string | null;
  deviceFamily?: string | null;
}

export interface DiscoveryClassification {
  suggestedClass: DiscoveryClass;
  suggestedType?: string | null;
  suggestedKind?: string | null;
  suggestedNodeId?: string | null;
  suggestedDisplayName?: string | null;
  confidence: number;
  signals: string[];
  explanation?: string | null;
  eligibleForRegistration: boolean;
}

export interface DiscoveryEligibility {
  registerable: boolean;
  agentCompatible: boolean;
  agentPlatform?: string | null;
  profilingStrategy?: ProfilingStrategy | null;
  remoteInstallable: boolean;
  remoteInstallMethod?: string | null;
  remoteInstallBlockers: string[];
  blockers: string[];
  notes: string[];
}

export interface DiscoveryDelegationInfo {
  delegatedTo?: string | null;
  commandId?: string | null;
  executionMethod?: string | null;
  commandStatus?: string | null;
  notes: string[];
}

export interface ScanExecution {
  scannedBy?: string | null;
  scannedFrom?: string | null;
  method?: string | null;
  delegatedTo?: string | null;
}

export interface DiscoveryScanProgress {
  phase: string;
  hostsTotal: number;
  hostsScanned: number;
  hostsAlive: number;
  percentComplete: number;
}

export interface DiscoveryScanError {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface DiscoveryScanSummary {
  scanId: string;
  status: DiscoveryScanStatus;
  targetCount: number;
  resultCount: number;
  progress: DiscoveryScanProgress;
  startedAt?: string | null;
  createdAt: string;
}

export interface DiscoveryScan extends DiscoveryScanSummary {
  targets: DiscoveryScanTarget[];
  options: DiscoveryScanOptions;
  triggeredVia?: ScanTrigger | null;
  execution?: ScanExecution | null;
  delegateToNodeId?: string | null;
  summary?: DiscoveryScanSummaryResult | null;
  delegation?: DiscoveryDelegationInfo | null;
  error?: DiscoveryScanError | null;
  completedAt?: string | null;
  updatedAt: string;
}

export interface DiscoveredDevice {
  discoveryId: string;
  identity: DiscoveryDeviceIdentity;
  networkId?: string | null;
  probe: DiscoveryProbeInfo;
  status: DiscoveryDeviceStatus;
  firstSeen: string;
  lastSeen: string;
  seenCount: number;
  openPorts: number[];
  protocols: string[];
  rawEvidence?: DiscoveryRawEvidence | null;
  fingerprint?: DiscoveryFingerprint | null;
  classification?: DiscoveryClassification | null;
  eligibility?: DiscoveryEligibility | null;
  dismissedAt?: string | null;
  dismissedBy?: string | null;
  dismissReason?: string | null;
  dismissPermanent?: boolean;
  approvedAt?: string | null;
  approvedBy?: string | null;
  rejectedAt?: string | null;
  rejectedBy?: string | null;
  rejectReason?: string | null;
  matchedNodeId?: string | null;
}

export interface DiscoveryApprovalResponse {
  discoveryId: string;
  status: DiscoveryDeviceStatus;
  matchedNodeId?: string | null;
}

export interface StartDiscoveryScanRequest {
  targets: DiscoveryScanTarget[];
  options?: Partial<DiscoveryScanOptions>;
  delegateToNodeId?: string | null;
}

export interface ApproveDiscoveryRequest {
  autoRegister: boolean;
  nodeId?: string | null;
  displayName?: string | null;
  description?: string | null;
  nodeClass?: string | null;
  nodeType?: string | null;
  kind?: string | null;
  tags?: string[];
}

export interface RejectDiscoveryRequest {
  reason?: string | null;
}

export interface DismissDiscoveryRequest {
  reason?: string | null;
  permanent?: boolean;
}

export interface RegisterDiscoveryRequest {
  nodeId?: string | null;
  displayName?: string | null;
  description?: string | null;
  class?: string | null;
  type?: string | null;
  kind?: string | null;
  tags?: string[];
  overrideClassification?: boolean;
}

export interface RegisterDiscoveryResponse {
  nodeId: string;
  registeredBy: string;
  registeredAt: string;
  status: string;
  fromDiscovery: string;
}

export interface DriftChange {
  field: string;
  previous: unknown;
  current: unknown;
}

export interface DriftReport {
  driftId: string;
  discoveryId: string;
  nodeId?: string | null;
  severity: 'info' | 'warning';
  changes: DriftChange[];
  previousClassification?: string | null;
  currentClassification?: string | null;
  detectedAt: string;
}

export interface DiscoveryScanListParams extends Omit<ListParams, 'search'> {
  status?: DiscoveryScanStatus;
}

export interface DiscoveryDeviceListParams extends ListParams {
  status?: DiscoveryDeviceStatus;
  networkId?: string;
  deviceClass?: DiscoveryClass;
  agentCompatible?: boolean;
  remoteInstallable?: boolean;
  minConfidence?: number;
  since?: string;
}

// ── Exclusion Types ───────────────────────────────────────────────

export type ExclusionType = 'mac' | 'ip' | 'ip-range';

export interface DiscoveryExclusion {
  exclusionId: string;
  type: ExclusionType;
  value: string;
  label: string;
  reason?: string | null;
  createdBy: string;
  createdAt: string;
}

export interface CreateExclusionRequest {
  type: ExclusionType;
  value: string;
  label: string;
  reason?: string | null;
}

export interface ExclusionListParams {
  limit?: number;
  offset?: number;
}

// ── Scan Diff Types ───────────────────────────────────────────────

export interface DiffDeviceSummary {
  discoveryId: string;
  ip?: string | null;
  mac?: string | null;
  hostname?: string | null;
  classification?: DiscoveryClassification | null;
}

export interface DiffChange {
  field: string;
  from: unknown;
  to: unknown;
}

export interface DiffChangedDevice {
  discoveryId: string;
  ip?: string | null;
  hostname?: string | null;
  changes: DiffChange[];
}

export interface ScanDiffResult {
  networkId: string;
  fromScan: { scanId: string; completedAt?: string } | null;
  toScan: { scanId: string; completedAt?: string } | null;
  arrived: DiffDeviceSummary[];
  departed: DiffDeviceSummary[];
  changed: DiffChangedDevice[];
  unchanged: number;
  error?: string | null;
}

// ── Installation Types ─────────────────────────────────────────────

export type InstallationStatus =
  | 'pending'
  | 'connecting'
  | 'transferring'
  | 'configuring'
  | 'registering'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface InstallationProgress {
  phase: InstallationStatus;
  percentComplete: number;
  message: string;
  startedAt?: string;
  updatedAt: string;
}

export interface Installation {
  installationId: string;
  discoveryId?: string;
  targetIp: string;
  targetHostname?: string;
  status: InstallationStatus;
  progress: InstallationProgress;
  nodeId?: string;
  error?: string;
  agentTier: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

export interface InstallationSummary {
  installationId: string;
  targetIp: string;
  targetHostname?: string;
  status: InstallationStatus;
  phase: InstallationStatus;
  nodeId?: string;
  createdAt: string;
}

export interface StartInstallationRequest {
  discoveryId?: string;
  targetIp?: string;
  credentials: {
    host: string;
    port?: number;
    username: string;
    password?: string;
    privateKey?: string;
    passphrase?: string;
  };
  agentTier?: string;
  tags?: string[];
}

export interface InstallationListParams extends Omit<ListParams, 'search'> {
  status?: InstallationStatus;
}
