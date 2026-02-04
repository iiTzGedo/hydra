import { ListParams } from './api';

export type AuditAction = 'create' | 'update' | 'delete' | 'login' | 'logout' | 'register' | 'execute' | 'acknowledge' | 'resolve' | 'archive' | 'submit' | 'revoke';

export interface AuditResource {
  type: string;
  id: string;
}

export interface AuditActor {
  type: 'user' | 'agent' | 'system';
  id: string;
  ip?: string;
}

export interface AuditResult {
  success: boolean;
  error?: string;
}

export interface AuditEntry {
  entryId: string;
  timestamp: string;
  action: AuditAction;
  resource: AuditResource;
  actor: AuditActor;
  details?: Record<string, unknown>;
  result: AuditResult;
}

export interface AuditLogParams extends ListParams {
  action?: AuditAction;
  resourceType?: string;
  resourceId?: string;
  actorId?: string;
  since?: string;
  until?: string;
}

export type CapacityGroupBy = 'node' | 'class' | 'location' | 'network' | 'group';

export interface CapacitySummary {
  totalNodes: number;
  physicalNodes: number;
  logicalNodes: number;
  totalCores: number;
  totalMemoryGB: number;
  totalStorageTB: number;
}

export interface ClassCapacity {
  nodes: number;
  cores?: number;
  memoryGB?: number;
  storageTB?: number;
}

export interface LocationCapacity {
  nodes: number;
  cores?: number;
  memoryGB?: number;
}

export interface CapacityResponse {
  summary: CapacitySummary;
  byClass?: Record<string, ClassCapacity>;
  byLocation?: Record<string, LocationCapacity>;
}

export interface CapacityParams {
  groupBy?: CapacityGroupBy;
  includeLogical?: boolean;
  groupId?: string;
  networkId?: string;
}
