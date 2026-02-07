import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';

// Helper to safely extract a string field from an entity
function getIdValue(item: object, field: string): string {
  return String((item as Record<string, unknown>)[field]);
}

/**
 * Factory for creating a paginated list hook with `id` alias.
 */
export function createListHook<TSummary, TParams extends object = object>(config: {
  endpoint: string;
  idField: string;
  queryKey: (params?: TParams) => readonly unknown[];
  defaultLimit?: number;
}) {
  const defaultLimit = config.defaultLimit ?? 20;

  return function useEntityList(params?: TParams) {
    return useQuery({
      queryKey: config.queryKey(params),
      queryFn: async () => {
        const response = await apiClient.get<ApiResponse<TSummary[]>>(config.endpoint, {
          params: {
            ...params,
            limit: (params as Record<string, unknown> | undefined)?.limit ?? defaultLimit,
            offset: (params as Record<string, unknown> | undefined)?.offset ?? 0,
          },
        });
        type WithId = TSummary & { id: string };
        const items: WithId[] = response.data.data.map(item => ({
          ...(item as object),
          id: getIdValue(item as object, config.idField),
        })) as WithId[];
        const paramsObj = params as Record<string, unknown> | undefined;
        const result: PaginatedResponse<WithId> = {
          items,
          total: response.data.meta?.total ?? items.length,
          limit: response.data.meta?.limit ?? Number(paramsObj?.limit ?? defaultLimit),
          offset: response.data.meta?.offset ?? Number(paramsObj?.offset ?? 0),
        };
        return result;
      },
    });
  };
}

/**
 * Factory for creating a detail hook with `id` alias.
 */
export function createDetailHook<TDetail>(config: {
  endpoint: string;
  idField: string;
  queryKey: (id: string) => readonly unknown[];
}) {
  return function useEntityDetail(id: string) {
    return useQuery({
      queryKey: config.queryKey(id),
      queryFn: async () => {
        const response = await apiClient.get<ApiResponse<TDetail>>(`${config.endpoint}/${id}`);
        const entity = response.data.data;
        return { ...(entity as object), id: getIdValue(entity as object, config.idField) } as TDetail & { id: string };
      },
      enabled: !!id,
    });
  };
}

/**
 * Factory for creating a create mutation that invalidates the list.
 */
export function createCreateMutation<TCreate, TDetail>(config: {
  endpoint: string;
  listQueryKey: () => readonly unknown[];
}) {
  return function useEntityCreate() {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: async (data: TCreate) => {
        const response = await apiClient.post<ApiResponse<TDetail>>(config.endpoint, data);
        return response.data.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: config.listQueryKey() });
      },
    });
  };
}

/**
 * Factory for creating an update mutation that invalidates detail + list.
 */
export function createUpdateMutation<TUpdate, TDetail>(config: {
  endpoint: string;
  method?: 'patch' | 'put';
  listQueryKey: () => readonly unknown[];
  detailQueryKey: (id: string) => readonly unknown[];
}) {
  const method = config.method ?? 'patch';

  return function useEntityUpdate() {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: async ({ id, data }: { id: string; data: TUpdate }) => {
        const response = await apiClient[method]<ApiResponse<TDetail>>(
          `${config.endpoint}/${id}`,
          data,
        );
        return response.data.data;
      },
      onSuccess: (_data, { id }) => {
        queryClient.invalidateQueries({ queryKey: config.detailQueryKey(id) });
        queryClient.invalidateQueries({ queryKey: config.listQueryKey() });
      },
    });
  };
}

/**
 * Factory for creating a delete mutation that invalidates the list.
 */
export function createDeleteMutation<TDetail = unknown>(config: {
  endpoint: string;
  listQueryKey: () => readonly unknown[];
}) {
  return function useEntityDelete() {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: async (id: string) => {
        const response = await apiClient.delete<ApiResponse<TDetail>>(`${config.endpoint}/${id}`);
        return response.data.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: config.listQueryKey() });
      },
    });
  };
}
