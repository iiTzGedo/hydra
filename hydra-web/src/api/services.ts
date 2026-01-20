import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  Service,
  ServiceSummary,
  ServiceListParams,
  UpdateServiceRequest,
} from '@/types/service';

type ServiceSummaryWithId = ServiceSummary & { id: string };

export function useServices(params?: ServiceListParams) {
  return useQuery({
    queryKey: queryKeys.services.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ServiceSummary[]>>('/services', {
        params: {
          nodeId: params?.nodeId,
          runtime: params?.runtime,
          status: params?.status,
          name: params?.name,
          tags: params?.tags,
          port: params?.port,
          search: params?.search,
          limit: params?.limit ?? 20,
          offset: params?.offset ?? 0,
          sortBy: params?.sortBy,
          sortOrder: params?.sortOrder,
        },
      });
      const items: ServiceSummaryWithId[] = response.data.data.map(service => ({
        ...service,
        id: service.serviceId,
      }));
      const result: PaginatedResponse<ServiceSummaryWithId> = {
        items,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 20,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
      return result;
    },
  });
}

export function useService(serviceId: string) {
  return useQuery({
    queryKey: queryKeys.services.detail(serviceId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Service>>(`/services/${serviceId}`);
      const service = response.data.data;
      return { ...service, id: service.serviceId };
    },
    enabled: !!serviceId,
  });
}

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
      };
    },
    enabled: !!nodeId,
  });
}

export function useUpdateService() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      serviceId,
      data,
    }: {
      serviceId: string;
      data: UpdateServiceRequest;
    }) => {
      const response = await apiClient.patch<ApiResponse<Service>>(
        `/services/${serviceId}`,
        data
      );
      return response.data.data;
    },
    onSuccess: (_data, { serviceId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.services.detail(serviceId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.services.list() });
    },
  });
}

export function useArchiveService() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (serviceId: string) => {
      const response = await apiClient.delete<ApiResponse<Service>>(
        `/services/${serviceId}`
      );
      return response.data.data;
    },
    onSuccess: (_data, serviceId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.services.detail(serviceId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.services.list() });
    },
  });
}
