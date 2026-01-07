import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type { AuditEntry, AuditLogParams, CapacityParams, CapacityResponse } from '@/types/query';

export function useCapacity(params?: CapacityParams) {
  return useQuery({
    queryKey: queryKeys.query.capacity(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<CapacityResponse>>('/capacity', {
        params: {
          groupBy: params?.groupBy,
          includeLogical: params?.includeLogical,
          groupId: params?.groupId,
          networkId: params?.networkId,
        },
      });
      return response.data.data;
    },
  });
}

export function useAuditLog(params?: AuditLogParams) {
  return useQuery({
    queryKey: queryKeys.query.audit(params),
    queryFn: async (): Promise<PaginatedResponse<AuditEntry>> => {
      const response = await apiClient.get<ApiResponse<AuditEntry[]>>('/audit', {
        params: {
          action: params?.action,
          resourceType: params?.resourceType,
          resourceId: params?.resourceId,
          actorId: params?.actorId,
          since: params?.since,
          until: params?.until,
          limit: params?.limit,
          offset: params?.offset,
        },
      });

      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 100,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
  });
}
