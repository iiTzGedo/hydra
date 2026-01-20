import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  checks: {
    database: 'ok' | 'error';
    redis: 'ok' | 'error';
    storage?: 'ok' | 'error' | 'not_configured';
  };
  uptimeSeconds: number;
}

export interface InfoResponse {
  name: string;
  version: string;
  apiVersion: string;
  stats: Record<string, unknown>;
  features: Record<string, boolean>;
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health.status(),
    queryFn: async () => {
      const response = await apiClient.get<HealthResponse>('/health');
      return response.data;
    },
    refetchInterval: 30000,
    staleTime: 10000,
  });
}

export function useInfo() {
  return useQuery({
    queryKey: queryKeys.health.info(),
    queryFn: async () => {
      const response = await apiClient.get<InfoResponse>('/info');
      return response.data;
    },
    staleTime: 60000,
  });
}
