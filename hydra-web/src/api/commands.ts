import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';

export type CommandType = 'metadata' | 'service' | 'package' | 'config' | 'system' | 'custom';
export type CommandStatus =
  | 'pending'
  | 'queued'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'timeout'
  | 'cancelled';

export interface CommandTarget {
  nodeId: string;
  serviceId?: string | null;
}

export interface CreateCommandRequest {
  type: CommandType;
  target: CommandTarget;
  action: string;
  parameters?: Record<string, unknown> | null;
  timeoutSeconds?: number;
}

export interface CommandQueuedResponse {
  commandId: string;
  type: CommandType;
  target: CommandTarget;
  action: string;
  status: CommandStatus;
  queuedAt: string;
}

export interface CommandSummary {
  commandId: string;
  type: CommandType;
  target: CommandTarget;
  action: string;
  status: CommandStatus;
  createdAt: string;
}

export function useCreateCommand() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateCommandRequest) => {
      const response = await apiClient.post<ApiResponse<CommandQueuedResponse>>(
        '/commands',
        data
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.commands.list() });
    },
  });
}

export function useCommands(params?: { nodeId?: string; status?: CommandStatus; type?: CommandType }) {
  return useQuery({
    queryKey: queryKeys.commands.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<CommandSummary[]>>('/commands', {
        params,
      });
      return response.data.data;
    },
  });
}
