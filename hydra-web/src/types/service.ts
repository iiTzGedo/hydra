import { ListParams } from './api';

// Service runtime
export type ServiceRuntime =
  | 'systemd'
  | 'docker'
  | 'kubernetes'
  | 'podman'
  | 'launchd'
  | 'windows_service'
  | 'cron'
  | 'supervisor'
  | 'pm2'
  | 'custom';

// Service status
export type ServiceStatus = 'running' | 'stopped' | 'paused' | 'failed' | 'restarting' | 'unknown';

// Port exposure
export interface PortExposure {
  internal: number;
  external?: number;
  protocol: 'tcp' | 'udp';
  host?: string;
}

// Service endpoint
export interface ServiceEndpoint {
  name: string;
  url: string;
  protocol?: string;
  health?: 'healthy' | 'unhealthy' | 'unknown';
}

// Resource allocation
export interface ResourceAllocation {
  cpuLimit?: number;
  cpuRequest?: number;
  memoryLimit?: number;
  memoryRequest?: number;
  storageLimit?: number;
}

// Service exposure type
export type ExposureType = 'internal' | 'external' | 'both';

// Service summary (for list views)
export interface ServiceSummary {
  serviceId: string;
  id?: string; // Alias for serviceId for component convenience
  nodeId: string;
  name: string;
  runtime: ServiceRuntime;
  status: ServiceStatus;
  ports: number[];
  exposure: ExposureType;
  tags: string[];
  lastSeen: string;
}

// Full service details
export interface Service extends ServiceSummary {
  displayName?: string;
  description?: string;
  image?: string;
  version?: string;
  command?: string[];
  environment?: Record<string, string>;
  portMappings?: PortExposure[];
  endpoints?: ServiceEndpoint[];
  resources?: ResourceAllocation;
  healthCheck?: {
    type: string;
    interval?: number;
    timeout?: number;
    retries?: number;
  };
  health?: 'healthy' | 'unhealthy' | 'unknown'; // Overall health status
  labels?: Record<string, string>; // Container labels/annotations
  metadata?: Record<string, unknown>; // Additional runtime-specific metadata
  dependencies?: string[];
  createdAt: string;
  updatedAt: string;
}

// Service list params
export interface ServiceListParams extends ListParams {
  nodeId?: string;
  runtime?: ServiceRuntime;
  status?: ServiceStatus;
  name?: string;
  tags?: string[];
  port?: number;
}

// Update service request
export interface UpdateServiceRequest {
  displayName?: string;
  description?: string;
  tags?: string[];
}
