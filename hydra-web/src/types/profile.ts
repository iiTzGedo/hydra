import { ListParams } from './api';

// Profile collection level
export type CollectionLevel = 'minimal' | 'standard' | 'full';

// Profile metadata
export interface ProfileMetadata {
  agentVersion: string;
  collectionDuration: number;
  collectionTimestamp: string;
}

// Hardware section
export interface HardwareSection {
  system?: {
    manufacturer?: string;
    model?: string;
    serial?: string;
    uuid?: string;
    formFactor?: string;
  };
  cpu?: {
    model: string;
    vendor: string;
    cores: number;
    threads: number;
    frequency: number;
    cache?: Record<string, number>;
    architecture?: string;
    flags?: string[];
  };
  memory?: {
    total: number;
    available?: number;
    type?: string;
    speed?: number;
    slots?: number;
    modules?: Array<{
      slot: string;
      size: number;
      type?: string;
      speed?: number;
    }>;
  };
  gpu?: Array<{
    model: string;
    vendor: string;
    memory?: number;
    driver?: string;
  }>;
  bios?: {
    vendor?: string;
    version?: string;
    date?: string;
  };
}

// Network section
export interface NetworkSection {
  hostname?: string;
  domain?: string;
  interfaces?: Array<{
    name: string;
    type: string;
    mac?: string;
    state: string;
    speed?: number;
    mtu?: number;
    addresses?: Array<{
      address: string;
      prefix: number;
      family: 'ipv4' | 'ipv6';
    }>;
  }>;
  routes?: Array<{
    destination: string;
    gateway?: string;
    interface: string;
    metric?: number;
  }>;
  dns?: {
    servers: string[];
    search?: string[];
  };
  firewall?: {
    enabled: boolean;
    rules?: number;
  };
}

// Storage section
export interface StorageSection {
  disks?: Array<{
    name: string;
    model?: string;
    serial?: string;
    size: number;
    type: string;
    rotational?: boolean;
    partitions?: Array<{
      name: string;
      size: number;
      filesystem?: string;
      mountpoint?: string;
    }>;
  }>;
  filesystems?: Array<{
    device: string;
    mountpoint: string;
    type: string;
    size: number;
    used: number;
    available: number;
  }>;
  volumes?: Array<{
    name: string;
    type: string;
    size: number;
    path?: string;
  }>;
}

// Software section
export interface SoftwareSection {
  os?: {
    name: string;
    version: string;
    kernel?: string;
    architecture: string;
    distribution?: string;
  };
  packages?: {
    manager?: string;
    count?: number;
    installed?: Array<{
      name: string;
      version: string;
      source?: string;
    }>;
  };
  runtimes?: Array<{
    name: string;
    version: string;
    path?: string;
  }>;
}

// Services section (in profile)
export interface ProfileServicesSection {
  services?: Array<{
    serviceId: string;
    name: string;
    runtime: string;
    status: string;
    ports?: number[];
  }>;
}

// Users section
export interface UsersSection {
  users?: Array<{
    username: string;
    uid: number;
    gid: number;
    home?: string;
    shell?: string;
    groups?: string[];
  }>;
  groups?: Array<{
    name: string;
    gid: number;
    members?: string[];
  }>;
}

// Profile sections
export interface ProfileSections {
  hardware?: HardwareSection;
  network?: NetworkSection;
  storage?: StorageSection;
  software?: SoftwareSection;
  services?: ProfileServicesSection;
  users?: UsersSection;
}

// Profile summary (for list views)
export interface ProfileSummary {
  profileId: string;
  id?: string; // Alias for profileId for component convenience
  nodeId: string;
  version: string;
  submittedAt: string;
  collectionLevel: CollectionLevel;
  sectionsIncluded: string[];
}

// Full profile
export interface Profile extends ProfileSummary {
  sections: ProfileSections;
  metadata: ProfileMetadata;
}

// Profile list params
export interface ProfileListParams extends ListParams {
  since?: string;
  until?: string;
}

// Profile diff
export interface ProfileDiff {
  fromProfileId: string;
  toProfileId: string;
  fromVersion: string;
  toVersion: string;
  changes: {
    section: string;
    type: 'added' | 'removed' | 'modified';
    path: string;
    oldValue?: unknown;
    newValue?: unknown;
  }[];
  summary: {
    totalChanges: number;
    bySection: Record<string, number>;
  };
}
