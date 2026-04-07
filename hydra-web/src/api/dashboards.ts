import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  CreateDashboardRequest,
  DashboardBoard,
  DashboardBoardSummary,
  DashboardCreateWidgetRequest,
  DashboardListParams,
  DashboardWidgetInstance,
  UpdateDashboardRequest,
  WidgetRegistryResponse,
} from '@/types/dashboard';

type DashboardBoardSummaryWithId = DashboardBoardSummary & { id: string };
type DashboardBoardWithId = DashboardBoard & { id: string };

function withBoardId<T extends { boardId: string }>(board: T): T & { id: string } {
  return {
    ...board,
    id: board.boardId,
  };
}

export function useDashboards(params?: DashboardListParams) {
  return useQuery({
    queryKey: queryKeys.dashboards.list(params),
    queryFn: async (): Promise<PaginatedResponse<DashboardBoardSummaryWithId>> => {
      const response = await apiClient.get<ApiResponse<DashboardBoardSummary[]>>(
        '/dashboards',
        {
          params: {
            boardType: params?.boardType,
            visibility: params?.visibility,
            tags: params?.tags,
            search: params?.search,
            limit: params?.limit,
            offset: params?.offset,
            sortBy: params?.sortBy,
            sortOrder: params?.sortOrder,
          },
        }
      );
      const items = response.data.data.map(withBoardId);
      return {
        items,
        total: response.data.meta?.total ?? items.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
  });
}

export function useDashboard(boardId: string) {
  return useQuery({
    queryKey: queryKeys.dashboards.detail(boardId),
    queryFn: async (): Promise<DashboardBoardWithId> => {
      const response = await apiClient.get<ApiResponse<DashboardBoard>>(
        `/dashboards/${boardId}`
      );
      return withBoardId(response.data.data);
    },
    enabled: !!boardId,
  });
}

export function useCreateDashboard() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CreateDashboardRequest): Promise<DashboardBoardWithId> => {
      const response = await apiClient.post<ApiResponse<DashboardBoard>>(
        '/dashboards',
        request
      );
      return withBoardId(response.data.data);
    },
    onSuccess: (board) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboards.all });
      queryClient.setQueryData(queryKeys.dashboards.detail(board.boardId), board);
    },
  });
}

export function useUpdateDashboard(boardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: UpdateDashboardRequest): Promise<DashboardBoardWithId> => {
      const response = await apiClient.put<ApiResponse<DashboardBoard>>(
        `/dashboards/${boardId}`,
        request
      );
      return withBoardId(response.data.data);
    },
    onSuccess: (board) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboards.list() });
      queryClient.setQueryData(queryKeys.dashboards.detail(board.boardId), board);
    },
  });
}

export function useDeleteDashboard() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (boardId: string): Promise<void> => {
      await apiClient.delete(`/dashboards/${boardId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboards.all });
    },
  });
}

export function useCloneDashboard(boardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (): Promise<DashboardBoardWithId> => {
      const response = await apiClient.post<ApiResponse<DashboardBoard>>(
        `/dashboards/${boardId}/clone`
      );
      return withBoardId(response.data.data);
    },
    onSuccess: (board) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboards.list() });
      queryClient.setQueryData(queryKeys.dashboards.detail(board.boardId), board);
    },
  });
}

export function useAddWidget(boardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: DashboardCreateWidgetRequest): Promise<DashboardBoardWithId> => {
      const response = await apiClient.post<ApiResponse<DashboardBoard>>(
        `/dashboards/${boardId}/widgets`,
        request
      );
      return withBoardId(response.data.data);
    },
    onSuccess: (board) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboards.list() });
      queryClient.setQueryData(queryKeys.dashboards.detail(board.boardId), board);
    },
  });
}

export function useUpdateWidget(boardId: string, widgetId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: Partial<DashboardWidgetInstance>): Promise<DashboardBoardWithId> => {
      const response = await apiClient.put<ApiResponse<DashboardBoard>>(
        `/dashboards/${boardId}/widgets/${widgetId}`,
        request
      );
      return withBoardId(response.data.data);
    },
    onSuccess: (board) => {
      queryClient.setQueryData(queryKeys.dashboards.detail(board.boardId), board);
    },
  });
}

export function useWidgetRegistry(category?: string) {
  return useQuery({
    queryKey: queryKeys.dashboards.widgetRegistry(category),
    queryFn: async (): Promise<WidgetRegistryResponse> => {
      const params = category ? `?category=${category}` : '';
      const response = await apiClient.get<ApiResponse<WidgetRegistryResponse>>(
        `/dashboards/widgets/registry${params}`
      );
      return response.data.data;
    },
  });
}

export function useDeleteWidget(boardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (widgetId: string): Promise<void> => {
      await apiClient.delete(`/dashboards/${boardId}/widgets/${widgetId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboards.list() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboards.detail(boardId) });
    },
  });
}
