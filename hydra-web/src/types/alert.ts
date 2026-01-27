export type AlertSeverity = 'critical' | 'warning' | 'info';
export type AlertStatus = 'active' | 'acknowledged' | 'resolved';

export interface Alert {
  id: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  nodeId?: string;
  nodeName?: string;
  serviceId?: string;
  serviceName?: string;
  timestamp: string;
  status: AlertStatus;
  acknowledgedAt?: string;
  acknowledgedBy?: string;
  resolvedAt?: string;
}

export interface AlertSummary {
  id: string;
  severity: AlertSeverity;
  title: string;
  nodeId?: string;
  timestamp: string;
  status: AlertStatus;
}

export interface AlertStats {
  total: number;
  critical: number;
  warning: number;
  info: number;
  unacknowledged: number;
}

export interface AlertListParams {
  severity?: AlertSeverity;
  status?: AlertStatus;
  nodeId?: string;
  serviceId?: string;
  limit?: number;
  offset?: number;
}
