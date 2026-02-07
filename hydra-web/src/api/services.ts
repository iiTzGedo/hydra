import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import {
  createListHook,
  createDetailHook,
  createUpdateMutation,
  createDeleteMutation,
} from '@/api/create-entity-hooks';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  Service,
  ServiceSummary,
  ServiceListParams,
  UpdateServiceRequest,
} from '@/types/service';

type ServiceSummaryWithId = ServiceSummary & { id: string };

export const useServices = createListHook<ServiceSummary, ServiceListParams>({
  endpoint: '/services',
  idField: 'serviceId',
  queryKey: queryKeys.services.list,
});

export const useService = createDetailHook<Service>({
  endpoint: '/services',
  idField: 'serviceId',
  queryKey: queryKeys.services.detail,
});

export function useNodeServices(
  nodeId: string,
  params?: { runtime?: string; status?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: queryKeys.services.byNode(nodeId, params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ServiceSummary[]>>(
        `/nodes/${nodeId}/services`,
        { params }
      );
      const items: ServiceSummaryWithId[] = response.data.data.map((service) => ({
        ...service,
        id: service.serviceId,
      }));
      return {
        items,
        total: response.data.meta?.total ?? items.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      } satisfies PaginatedResponse<ServiceSummaryWithId>;
    },
    enabled: !!nodeId,
  });
}

export const useUpdateService = createUpdateMutation<UpdateServiceRequest, Service>({
  endpoint: '/services',
  method: 'patch',
  listQueryKey: queryKeys.services.list,
  detailQueryKey: queryKeys.services.detail,
});

export const useArchiveService = createDeleteMutation({
  endpoint: '/services',
  listQueryKey: queryKeys.services.list,
});
