import { ListParams } from './api';

// Profile collection level - matches API CollectionLevel enum
export type CollectionLevel = 'shallow' | 'neutral' | 'deep';

// ============================================
// Hardware Profile Types (matches API HardwareProfile)
// ============================================

export interface CpuInfo {
  model?: string;
  vendor?: string;
  coresPhysical?: number;
  coresLogical?: number;
  frequencyMhz?: number;
  architecture?: string;
  features?: string[];
}

export interface MemoryInfo {
  totalBytes?: number;
  type?: string;
  speedMhz?: number;
  slotsUsed?: number;
  slotsTotal?: number;
}

export interface GpuInfo {
  model?: string;
  vendor?: string;
  memoryBytes?: number;
  driverVersion?: string;
}

export interface HardwareProfile {
  systemManufacturer?: string;
  systemModel?: string;
  systemSerial?: string;
  biosVendor?: string;
  biosVersion?: string;
  cpu?: CpuInfo;
  memory?: MemoryInfo;
  gpus?: GpuInfo[];
}

// ============================================
// Network Profile Types (matches API NetworkProfile)
// ============================================

export interface NetworkInterface {
  name: string;
  macAddress?: string;
  ipv4Addresses?: string[];
  ipv6Addresses?: string[];
  netmask?: string;
  gateway?: string;
  mtu?: number;
  state: 'up' | 'down' | 'unknown';
  type?: string;
  speedMbps?: number;
}

export interface NetworkRoute {
  destination: string;
  gateway?: string;
  interface?: string;
  metric?: number;
}

export interface NetworkProfile {
  hostname?: string;
  domain?: string;
  fqdn?: string;
  interfaces?: NetworkInterface[];
  dnsServers?: string[];
  dnsSearch?: string[];
  defaultGateway?: string;
  routes?: NetworkRoute[];
}

// ============================================
// Storage Profile Types (matches API StorageProfile)
// ============================================

export interface BlockDevice {
  name: string;
  sizeBytes?: number;
  type?: string;
  model?: string;
  serial?: string;
  rotational?: boolean;
  transport?: string;
}

export interface Filesystem {
  mountPoint: string;
  device: string;
  fsType: string;
  sizeBytes?: number;
  usedBytes?: number;
  options?: string[];
}

export interface StorageProfile {
  blockDevices?: BlockDevice[];
  filesystems?: Filesystem[];
  totalCapacityBytes?: number;
}

// ============================================
// Software Profile Types (matches API SoftwareProfile)
// ============================================

export interface OsInfo {
  name: string;
  version?: string;
  kernelVersion?: string;
  architecture?: string;
  family?: string;
}

export interface Package {
  name: string;
  version?: string;
  manager?: string;
}

export interface SoftwareProfile {
  os?: OsInfo;
  packages?: Package[];
  packageCount?: number;
}

// ============================================
// Services Profile Types (matches API ServicesProfile)
// ============================================

export interface ServiceInfo {
  name: string;
  runtime: string;
  status: string;
  version?: string;
  image?: string;
  ports?: Array<Record<string, unknown>>;
  endpoints?: Array<Record<string, unknown>>;
  resources?: Record<string, unknown>;
  attachments?: Record<string, unknown>;
}

export interface ServicesProfile {
  services?: ServiceInfo[];
}

// ============================================
// Users Profile Types (matches API UsersProfile)
// ============================================

export interface UserInfo {
  username: string;
  uid?: number;
  gid?: number;
  home?: string;
  shell?: string;
  groups?: string[];
}

export interface SshKey {
  username: string;
  keyType: string;
  fingerprint: string;
  comment?: string;
}

export interface UsersProfile {
  users?: UserInfo[];
  sshKeys?: SshKey[];
}

// ============================================
// Configs Profile Types (matches API ConfigsProfile)
// ============================================

export interface ConfigFile {
  path: string;
  hash: string;
  sizeBytes?: number;
  modifiedAt?: string;
}

export interface ConfigsProfile {
  files?: ConfigFile[];
}

// ============================================
// Profile Summary (for list views)
// ============================================

export interface ProfileSummary {
  profileId: string;
  nodeId: string;
  version: string;
  collectedAt: string;
  submittedAt: string;
  collectionLevel: CollectionLevel;
  serviceCount?: number;
}

// ============================================
// Full Profile Response (matches API ProfileResponse)
// ============================================

export interface Profile extends ProfileSummary {
  agentVersion: string;
  serviceIds?: string[];
  hardware?: HardwareProfile;
  network?: NetworkProfile;
  storage?: StorageProfile;
  software?: SoftwareProfile;
  // Note: API returns serviceIds, not services section.
  // Services are stored separately and fetched via the services API.
  users?: UsersProfile;
  configs?: ConfigsProfile;
  metadata?: Record<string, unknown>;
}

// ============================================
// Profile List Params
// ============================================

export interface ProfileListParams extends ListParams {
  since?: string;
  until?: string;
}

// ============================================
// Profile Diff (matches API ProfileDiff)
// ============================================

export interface ProfileDiff {
  fromVersion: string;
  toVersion: string;
  fromProfileId: string;
  toProfileId: string;
  changedSections: string[];
  changeSummary: Record<string, unknown>;
  diffPercentage: number;
}
