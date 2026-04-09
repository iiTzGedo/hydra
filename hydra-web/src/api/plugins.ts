import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import type {
  PluginResponse,
  PluginSummary,
  PluginHealthStatus,
  UpdatePluginConfigRequest,
  BindNodeRequest,
} from '@/types/plugins';

// ── Query Keys ────────────────────────────────────────────────────

const pluginKeys = {
  all: ['plugins'] as const,
  list: (params?: Record<string, string>) => [...pluginKeys.all, 'list', params] as const,
  detail: (pluginId: string) => [...pluginKeys.all, 'detail', pluginId] as const,
  health: (pluginId: string) => [...pluginKeys.all, 'health', pluginId] as const,
};

// ── List ──────────────────────────────────────────────────────────

export function usePlugins(params?: Record<string, string>) {
  return useQuery({
    queryKey: pluginKeys.list(params),
    queryFn: async () => {
      const response = await apiClient.get<{
        data: PluginSummary[];
        meta: { total: number; limit: number; offset: number };
      }>('/plugins', { params });
      return response.data;
    },
    retry: false,
  });
}

// ── Detail ────────────────────────────────────────────────────────

export function usePlugin(pluginId: string) {
  return useQuery({
    queryKey: pluginKeys.detail(pluginId),
    queryFn: async () => {
      const response = await apiClient.get<{ data: PluginResponse }>(`/plugins/${encodeURIComponent(pluginId)}`);
      return response.data.data;
    },
    enabled: Boolean(pluginId),
  });
}

// ── Health ────────────────────────────────────────────────────────

export function usePluginHealth(pluginId: string) {
  return useQuery({
    queryKey: pluginKeys.health(pluginId),
    queryFn: async () => {
      const response = await apiClient.get<{ data: PluginHealthStatus }>(`/plugins/${encodeURIComponent(pluginId)}/health`);
      return response.data.data;
    },
    enabled: Boolean(pluginId),
  });
}

// ── Enable / Disable ──────────────────────────────────────────────

export function useEnablePlugin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (pluginId: string) => {
      const response = await apiClient.post<{ data: PluginResponse }>(`/plugins/${encodeURIComponent(pluginId)}/enable`);
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pluginKeys.all });
    },
  });
}

export function useDisablePlugin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (pluginId: string) => {
      const response = await apiClient.post<{ data: PluginResponse }>(`/plugins/${encodeURIComponent(pluginId)}/disable`);
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pluginKeys.all });
    },
  });
}

// ── Configure ─────────────────────────────────────────────────────

export function useUpdatePluginConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ pluginId, request }: { pluginId: string; request: UpdatePluginConfigRequest }) => {
      const response = await apiClient.patch<{ data: PluginResponse }>(`/plugins/${encodeURIComponent(pluginId)}/config`, request);
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pluginKeys.all });
    },
  });
}

// ── Node Bindings ─────────────────────────────────────────────────

export function useBindNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ pluginId, nodeId, request }: { pluginId: string; nodeId: string; request?: BindNodeRequest }) => {
      const response = await apiClient.post<{ data: PluginResponse }>(
        `/plugins/${encodeURIComponent(pluginId)}/nodes/${encodeURIComponent(nodeId)}`,
        request ?? {}
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pluginKeys.all });
    },
  });
}

export function useUnbindNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ pluginId, nodeId }: { pluginId: string; nodeId: string }) => {
      const response = await apiClient.delete<{ data: PluginResponse }>(
        `/plugins/${encodeURIComponent(pluginId)}/nodes/${encodeURIComponent(nodeId)}`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pluginKeys.all });
    },
  });
}

// ── Uninstall ─────────────────────────────────────────────────────

export function useUninstallPlugin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (pluginId: string) => {
      const response = await apiClient.delete<{ data: PluginResponse }>(`/plugins/${encodeURIComponent(pluginId)}`);
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pluginKeys.all });
    },
  });
}
