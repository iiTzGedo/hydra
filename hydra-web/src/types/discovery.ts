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

export interface DiscoveryScanTarget {
  networkId?: string | null;
  subnet?: string | null;
  ips?: string[] | null;
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
  errors: string[];
}

export interface DiscoveryDeviceIdentity {
  primaryMac?: string | null;
  currentIp: string;
  hostname?: string | null;
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
  openPorts: number[];
  serviceHints: string[];
  protocols: string[];
  osHint?: string | null;
  vendor?: string | null;
  macOui?: string | null;
  deviceFamily?: string | null;
}

export interface DiscoveryClassification {
  suggestedClass: DiscoveryClass;
  suggestedType?: string | null;
  confidence: number;
  signals: string[];
  explanation?: string | null;
  eligibleForRegistration: boolean;
}

export interface DiscoveryDelegationInfo {
  delegatedTo?: string | null;
  commandId?: string | null;
  executionMethod?: string | null;
  commandStatus?: string | null;
  notes: string[];
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
  dismissedAt?: string | null;
  dismissedBy?: string | null;
  dismissReason?: string | null;
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
  nodeClass?: string | null;
  tags?: string[];
}

export interface RejectDiscoveryRequest {
  reason?: string | null;
}

export interface DismissDiscoveryRequest {
  reason?: string | null;
}

export interface DiscoveryScanListParams extends Omit<ListParams, 'search'> {
  status?: DiscoveryScanStatus;
}

export interface DiscoveryDeviceListParams extends ListParams {
  status?: DiscoveryDeviceStatus;
  networkId?: string;
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
