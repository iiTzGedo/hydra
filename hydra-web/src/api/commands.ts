import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';

export type CommandType =
  | 'metadata'
  | 'service'
  | 'package'
  | 'config'
  | 'system'
  | 'custom'
  | 'node'
  | 'agent';
export type CommandCategory = 'service' | 'node' | 'agent';
export type CommandStatus =
  | 'pending'
  | 'rejected'
  | 'queued'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'timeout'
  | 'cancelled';
export type CommandExecutionMethod = 'agent-direct' | 'agent-poll' | 'integration';
export type CommandDeliveryMode = 'direct_or_poll' | 'poll_only';

export interface CommandTarget {
  nodeId: string;
  serviceId?: string | null;
}

export interface CreateCommandRequest {
  registryId: string;
  target: CommandTarget;
  parameters?: Record<string, unknown> | null;
  timeoutSeconds?: number;
}

export interface CommandResult {
  success: boolean;
  output?: string | null;
  exitCode?: number | null;
  error?: string | null;
  data?: Record<string, unknown> | null;
}

export interface CommandError {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface RequestedBy {
  userId?: string | null;
  source: string;
  clientId?: string | null;
}

export interface CommandQueuedResponse {
  commandId: string;
  registryId?: string;
  type: CommandType;
  target: CommandTarget;
  action: string;
  status: CommandStatus;
  executionMethod: CommandExecutionMethod;
  result?: CommandResult | null;
  queuePosition?: number | null;
  queuedAt?: string | null;
  completedAt?: string | null;
}

export interface CommandSummary {
  commandId: string;
  registryId?: string | null;
  type: CommandType;
  target: CommandTarget;
  action: string;
  status: CommandStatus;
  createdAt: string;
}

export interface CommandResponse {
  commandId: string;
  registryId?: string | null;
  type: CommandType;
  target: CommandTarget;
  action: string;
  parameters?: Record<string, unknown> | null;
  status: CommandStatus;
  executionMethod?: CommandExecutionMethod | null;
  result?: CommandResult | null;
  error?: CommandError | null;
  requestedBy?: RequestedBy | null;
  timeoutSeconds: number;
  retryCount: number;
  queuePosition?: number | null;
  chain?: Record<string, unknown> | null;
  createdAt: string;
  queuedAt?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  cancelledAt?: string | null;
  cancelledBy?: string | null;
}

export interface CommandDefinitionSummary {
  registryId: string;
  category: CommandCategory;
  action: string;
  displayName: string;
  description?: string | null;
  minimumRole: string;
  requiresConfirmation: boolean;
  timeout: number;
  deliveryMode: CommandDeliveryMode;
  builtIn: boolean;
  deprecated: boolean;
}

export interface QueueStats {
  totalQueued: number;
  totalExecuting: number;
  oldestQueuedAt?: string | null;
}

export interface QueueViewResponse {
  queue: CommandSummary[];
  stats: QueueStats;
}

export interface CommandCancelledResponse {
  commandId: string;
  status: CommandStatus;
  cancelledAt: string;
  cancelledBy?: string | null;
}

// ── Mutations ────────────────────────────────────────────────────────────

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
      queryClient.invalidateQueries({ queryKey: queryKeys.commands.queue() });
    },
  });
}

export function useCancelCommand() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (commandId: string) => {
      const response = await apiClient.post<ApiResponse<CommandCancelledResponse>>(
        `/commands/${commandId}/cancel`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.commands.all });
    },
  });
}

export function useFlushQueue() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (scope: string = 'all') => {
      const response = await apiClient.post<ApiResponse<{ flushedCount: number }>>(
        '/commands/queue/flush',
        { scope, confirm: true }
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.commands.all });
    },
  });
}

// ── Queries ──────────────────────────────────────────────────────────────

export function useCommands(params?: { nodeId?: string; status?: CommandStatus; type?: CommandType; registryId?: string }) {
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

export function useCommand(commandId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.commands.detail(commandId ?? ''),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<CommandResponse>>(
        `/commands/${commandId}`
      );
      return response.data.data;
    },
    enabled: !!commandId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'queued' || data.status === 'executing')) {
        return 2000; // Poll every 2s while active
      }
      return false;
    },
  });
}

export function useCommandQueue(params?: { nodeId?: string }) {
  return useQuery({
    queryKey: queryKeys.commands.queue(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<QueueViewResponse>>('/commands/queue', {
        params,
      });
      return response.data.data;
    },
    refetchInterval: 5000, // Auto-refresh every 5s
  });
}

export function useCommandCatalog(params?: { category?: CommandCategory; includeDeprecated?: boolean }) {
  return useQuery({
    queryKey: queryKeys.commandCatalog.list(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<CommandDefinitionSummary[]>>('/command-catalog', {
        params,
      });
      return response.data.data;
    },
  });
}
