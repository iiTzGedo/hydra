import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import type { ApiResponse } from '@/types/api';
import type {
  CreateWorkflowRequest,
  ExecuteWorkflowRequest,
  WorkflowExecutionResponse,
  WorkflowExecutionSummary,
  WorkflowListParams,
  WorkflowResponse,
  WorkflowSummary,
} from '@/types/workflows';

// ── Query Keys ─────────────────────────────────────────────────────────

export const workflowKeys = {
  all: ['workflows'] as const,
  lists: () => [...workflowKeys.all, 'list'] as const,
  list: (params?: WorkflowListParams) => [...workflowKeys.lists(), params] as const,
  details: () => [...workflowKeys.all, 'detail'] as const,
  detail: (chainId: string) => [...workflowKeys.details(), chainId] as const,
  executions: (chainId?: string) => [...workflowKeys.all, 'executions', chainId] as const,
  execution: (executionId: string) => [...workflowKeys.all, 'execution', executionId] as const,
};

// ── Queries ────────────────────────────────────────────────────────────

export function useWorkflows(params?: WorkflowListParams) {
  return useQuery({
    queryKey: workflowKeys.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<WorkflowSummary[]>>('/workflows', {
        params: {
          limit: params?.limit,
          offset: params?.offset,
        },
      });
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
  });
}

export function useWorkflow(chainId: string | null | undefined) {
  return useQuery({
    queryKey: workflowKeys.detail(chainId ?? ''),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<WorkflowResponse>>(
        `/workflows/${chainId}`
      );
      return response.data.data;
    },
    enabled: Boolean(chainId),
  });
}

export function useWorkflowExecutions(chainId?: string, params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: workflowKeys.executions(chainId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<WorkflowExecutionSummary[]>>(
        `/workflows/${chainId}/executions`,
        {
          params: {
            limit: params?.limit,
            offset: params?.offset,
          },
        }
      );
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
    enabled: Boolean(chainId),
  });
}

export function useWorkflowExecution(executionId: string | null | undefined) {
  return useQuery({
    queryKey: workflowKeys.execution(executionId ?? ''),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<WorkflowExecutionResponse>>(
        `/workflows/executions/${executionId}`
      );
      return response.data.data;
    },
    enabled: Boolean(executionId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'running' || data.status === 'pending')) {
        return 3000;
      }
      return false;
    },
  });
}

// ── Mutations ──────────────────────────────────────────────────────────

export function useCreateWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateWorkflowRequest) => {
      const response = await apiClient.post<ApiResponse<WorkflowResponse>>(
        '/workflows',
        data
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.all });
    },
  });
}

export function useExecuteWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      chainId,
      request,
    }: {
      chainId: string;
      request?: ExecuteWorkflowRequest;
    }) => {
      const response = await apiClient.post<ApiResponse<WorkflowExecutionResponse>>(
        `/workflows/${chainId}/execute`,
        request ?? {}
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.all });
    },
  });
}

export function useCancelWorkflowExecution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (executionId: string) => {
      const response = await apiClient.post<ApiResponse<WorkflowExecutionResponse>>(
        `/workflows/executions/${executionId}/cancel`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.all });
    },
  });
}

export function useUpdateWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      chainId,
      data,
    }: {
      chainId: string;
      data: Partial<CreateWorkflowRequest>;
    }) => {
      const response = await apiClient.patch<ApiResponse<WorkflowResponse>>(
        `/workflows/${chainId}`,
        data
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.all });
    },
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (chainId: string) => {
      const response = await apiClient.delete<ApiResponse<WorkflowResponse>>(
        `/workflows/${chainId}`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.all });
    },
  });
}
