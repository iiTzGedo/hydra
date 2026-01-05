import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';

// Health check response
export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  checks: {
    database: 'ok' | 'error';
    redis: 'ok' | 'error';
    disk?: 'ok' | 'error';
    objectStorage?: 'ok' | 'error';
  };
  uptime_seconds: number;
}

// Info response
export interface InfoResponse {
  service: string;
  version: string;
  environment: string;
  stats: {
    nodes: {
      total: number;
      active: number;
      byClass: Record<string, number>;
    };
    services: {
      total: number;
      running: number;
      byRuntime: Record<string, number>;
    };
    networks: {
      total: number;
    };
    groups: {
      total: number;
    };
    users: {
      total: number;
      byRole: Record<string, number>;
    };
  };
}

// Get health status
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health.status(),
    queryFn: async () => {
      const response = await apiClient.get<HealthResponse>('/health');
      return response.data;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 10000, // Consider stale after 10 seconds
  });
}

// Get system info
export function useInfo() {
  return useQuery({
    queryKey: queryKeys.health.info(),
    queryFn: async () => {
      const response = await apiClient.get<InfoResponse>('/info');
      return response.data;
    },
    staleTime: 60000, // 1 minute
  });
}
