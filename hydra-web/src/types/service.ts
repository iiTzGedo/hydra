import { ListParams } from './api';

export type ServiceRuntime =
  | 'systemd'
  | 'docker'
  | 'podman'
  | 'kubernetes'
  | 'lxc'
  | 'supervisord'
  | 'pm2'
  | 'rc'
  | 'openrc'
  | 'winservice'
  | 'launchd'
  | 'containerd'
  | 'unknown';

export type ServiceStatus =
  | 'running'
  | 'stopped'
  | 'paused'
  | 'exited'
  | 'failed'
  | 'restarting'
  | 'unknown';

export interface ServicePort {
  port: number;
  protocol?: string;
  hostPort?: number;
}

export interface ServiceEndpoint {
  url: string;
  type: string;
  internal?: boolean;
}

export interface ServiceExposure {
  ports: ServicePort[];
  endpoints: ServiceEndpoint[];
}

export interface ServiceOrigin {
  nativeId: string;
  discoveredBy: string;
  collectedAt: string;
}

export interface ServiceHealth {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown';
  lastCheck?: string;
}

export interface ServiceSummary {
  serviceId: string;
  id?: string;
  nodeId: string;
  name: string;
  displayName: string;
  runtime: ServiceRuntime;
  status: ServiceStatus;
  version?: string;
  lastSeen: string;
}

export interface Service extends ServiceSummary {
  description?: string;
  image?: string;
  profileId: string;
  exposure?: ServiceExposure;
  resources?: Record<string, unknown> | null;
  attachments?: Record<string, unknown> | null;
  origin: ServiceOrigin;
  health?: ServiceHealth;
  tags: string[];
  firstSeen: string;
}

export interface ServiceListParams extends ListParams {
  nodeId?: string;
  runtime?: ServiceRuntime;
  status?: ServiceStatus;
  name?: string;
  tags?: string[];
  port?: number;
}

export interface UpdateServiceRequest {
  displayName?: string;
  description?: string;
  tags?: string[];
}
