import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { Alert, AlertSummary, AlertStats, AlertListParams } from '@/types/alert';
import type { PaginatedResponse } from '@/types/api';

// Query keys for alerts
export const alertQueryKeys = {
  all: ['alerts'] as const,
  list: (params?: AlertListParams) => [...alertQueryKeys.all, 'list', params] as const,
  stats: () => [...alertQueryKeys.all, 'stats'] as const,
  detail: (id: string) => [...alertQueryKeys.all, 'detail', id] as const,
};

// Mock data generator - simulates real alerts
function generateMockAlerts(params?: AlertListParams): PaginatedResponse<AlertSummary> {
  const now = new Date();
  const mockAlerts: AlertSummary[] = [
    {
      id: 'alert-1',
      severity: 'critical',
      title: 'High CPU usage on proxmox-01',
      nodeId: 'proxmox-01',
      timestamp: new Date(now.getTime() - 5 * 60000).toISOString(),
      status: 'active',
    },
    {
      id: 'alert-2',
      severity: 'warning',
      title: 'Disk space below 20% on nas-01',
      nodeId: 'nas-01',
      timestamp: new Date(now.getTime() - 15 * 60000).toISOString(),
      status: 'active',
    },
    {
      id: 'alert-3',
      severity: 'warning',
      title: 'Service nginx unhealthy on web-01',
      nodeId: 'web-01',
      timestamp: new Date(now.getTime() - 30 * 60000).toISOString(),
      status: 'acknowledged',
    },
    {
      id: 'alert-4',
      severity: 'info',
      title: 'Node opnsense-gw rebooted',
      nodeId: 'opnsense-gw',
      timestamp: new Date(now.getTime() - 60 * 60000).toISOString(),
      status: 'resolved',
    },
    {
      id: 'alert-5',
      severity: 'critical',
      title: 'Memory usage critical on docker-host',
      nodeId: 'docker-host',
      timestamp: new Date(now.getTime() - 2 * 60000).toISOString(),
      status: 'active',
    },
  ];

  // Filter by severity
  let filtered = mockAlerts;
  if (params?.severity) {
    filtered = filtered.filter(a => a.severity === params.severity);
  }
  if (params?.status) {
    filtered = filtered.filter(a => a.status === params.status);
  }
  if (params?.nodeId) {
    filtered = filtered.filter(a => a.nodeId === params.nodeId);
  }

  // Pagination
  const limit = params?.limit ?? 20;
  const offset = params?.offset ?? 0;
  const items = filtered.slice(offset, offset + limit);

  return {
    items,
    total: filtered.length,
    limit,
    offset,
  };
}

function calculateMockStats(): AlertStats {
  const alerts = generateMockAlerts().items;
  return {
    total: alerts.length,
    critical: alerts.filter(a => a.severity === 'critical' && a.status === 'active').length,
    warning: alerts.filter(a => a.severity === 'warning' && a.status === 'active').length,
    info: alerts.filter(a => a.severity === 'info' && a.status === 'active').length,
    unacknowledged: alerts.filter(a => a.status === 'active').length,
  };
}

/**
 * Hook to fetch alerts list
 * TODO: Replace mock data with real API call when backend is ready
 * Endpoint: GET /api/v1/alerts
 */
export function useAlerts(params?: AlertListParams) {
  return useQuery({
    queryKey: alertQueryKeys.list(params),
    queryFn: async () => {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 300));
      return generateMockAlerts(params);
    },
    // Refresh every 30 seconds for real-time updates
    refetchInterval: 30000,
  });
}

/**
 * Hook to fetch alert statistics for dashboard
 * TODO: Replace mock data with real API call when backend is ready
 * Endpoint: GET /api/v1/alerts/stats
 */
export function useAlertStats() {
  return useQuery({
    queryKey: alertQueryKeys.stats(),
    queryFn: async () => {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 200));
      return calculateMockStats();
    },
    // Refresh every 30 seconds
    refetchInterval: 30000,
  });
}

/**
 * Hook to fetch single alert details
 * TODO: Replace mock data with real API call when backend is ready
 * Endpoint: GET /api/v1/alerts/:id
 */
export function useAlert(alertId: string) {
  return useQuery({
    queryKey: alertQueryKeys.detail(alertId),
    queryFn: async (): Promise<Alert> => {
      await new Promise(resolve => setTimeout(resolve, 200));
      const alerts = generateMockAlerts().items;
      const summary = alerts.find(a => a.id === alertId);
      if (!summary) throw new Error('Alert not found');
      return {
        ...summary,
        message: `Detailed message for ${summary.title}. This would contain more context about the alert condition.`,
      };
    },
    enabled: !!alertId,
  });
}

/**
 * Hook to acknowledge an alert
 * TODO: Replace with real API call when backend is ready
 * Endpoint: POST /api/v1/alerts/:id/acknowledge
 */
export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (alertId: string) => {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 300));
      return { alertId, acknowledged: true };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertQueryKeys.all });
    },
  });
}

/**
 * Hook to acknowledge all active alerts
 * TODO: Replace with real API call when backend is ready
 * Endpoint: POST /api/v1/alerts/acknowledge-all
 */
export function useAcknowledgeAllAlerts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await new Promise(resolve => setTimeout(resolve, 500));
      return { acknowledged: true };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertQueryKeys.all });
    },
  });
}
