import { ListParams } from './api';

export type CollectionLevel = 'shallow' | 'neutral' | 'deep';

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
  usedBytes?: number;
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

export interface ConfigFile {
  path: string;
  hash: string;
  sizeBytes?: number;
  modifiedAt?: string;
}

export interface ConfigsProfile {
  files?: ConfigFile[];
}

export interface ProfileSummary {
  profileId: string;
  nodeId: string;
  version: string;
  collectedAt: string;
  submittedAt: string;
  collectionLevel: CollectionLevel;
  serviceCount?: number;
}

export interface Profile extends ProfileSummary {
  agentVersion: string;
  serviceIds?: string[];
  hardware?: HardwareProfile;
  network?: NetworkProfile;
  storage?: StorageProfile;
  software?: SoftwareProfile;
  users?: UsersProfile;
  configs?: ConfigsProfile;
  metadata?: Record<string, unknown>;
}

export interface ProfileListParams extends ListParams {}

export interface ProfileDiff {
  fromVersion: string;
  toVersion: string;
  fromProfileId: string;
  toProfileId: string;
  changedSections: string[];
  changeSummary: Record<string, unknown>;
  diffPercentage: number;
}
