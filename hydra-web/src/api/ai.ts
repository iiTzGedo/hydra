import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';

export type LLMProviderType = 'anthropic' | 'openai' | 'ollama' | 'openrouter';

export interface LLMProviderResponse {
  configId: string;
  name: string;
  type: LLMProviderType;
  apiKeyLast4?: string | null;
  apiKeySet: boolean;
  baseUrl?: string | null;
  model: string;
  isDefault: boolean;
  isValid?: boolean | null;
  lastValidatedAt?: string | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface LLMProviderListResponse {
  configs: LLMProviderResponse[];
  total: number;
}

export interface LLMProviderCreate {
  name: string;
  type: LLMProviderType;
  model: string;
  apiKey?: string;
  baseUrl?: string;
  isDefault?: boolean;
}

export interface LLMProviderUpdate {
  name?: string;
  model?: string;
  apiKey?: string;
  baseUrl?: string;
  isDefault?: boolean;
}

export interface LLMProviderValidateResponse {
  configId: string;
  isValid: boolean;
  message: string;
  validatedAt: string;
  models?: string[] | null;
}

export function useLLMProviders() {
  return useQuery({
    queryKey: queryKeys.ai.models(),
    queryFn: async () => {
      const response = await apiClient.get<LLMProviderListResponse>('/ai/configs');
      return response.data;
    },
  });
}

export function useLLMProvider(providerId: string) {
  return useQuery({
    queryKey: queryKeys.ai.model(providerId),
    queryFn: async () => {
      const response = await apiClient.get<LLMProviderResponse>(`/ai/configs/${providerId}`);
      return response.data;
    },
    enabled: !!providerId,
  });
}

export function useCreateLLMProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: LLMProviderCreate) => {
      const response = await apiClient.post<LLMProviderResponse>('/ai/configs', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.models() });
    },
  });
}

export function useUpdateLLMProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      providerId,
      data,
    }: {
      providerId: string;
      data: LLMProviderUpdate;
    }) => {
      const response = await apiClient.put<LLMProviderResponse>(
        `/ai/configs/${providerId}`,
        data
      );
      return response.data;
    },
    onSuccess: (_data, { providerId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.model(providerId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.models() });
    },
  });
}

export function useDeleteLLMProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (providerId: string) => {
      const response = await apiClient.delete(`/ai/configs/${providerId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.models() });
    },
  });
}

export function useValidateLLMProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (providerId: string) => {
      const response = await apiClient.post<LLMProviderValidateResponse>(
        `/ai/configs/${providerId}/validate`
      );
      return response.data;
    },
    onSuccess: (_data, providerId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.model(providerId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.models() });
    },
  });
}

// =============================================================================
// Provider Models (Dynamic model fetching from provider APIs)
// =============================================================================

export interface LLMModel {
  id: string;
  name: string;
  contextWindow: number;
  supportsTools: boolean;
  supportsVision: boolean;
  supportsReasoning: boolean;
  costPer1kInput?: number | null;
  costPer1kOutput?: number | null;
}

export interface LLMModelsResponse {
  models: LLMModel[];
  provider: LLMProviderType;
  fetchedAt: string;
  cached: boolean;
}

export function useProviderModels(
  providerType: LLMProviderType,
  options?: { configId?: string; enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.ai.providerModels(providerType),
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (options?.configId) {
        params.configId = options.configId;
      }
      const response = await apiClient.get<LLMModelsResponse>(
        `/ai/providers/${providerType}/models`,
        { params }
      );
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: options?.enabled !== false,
  });
}

// =============================================================================
// Global API Keys (User's global API keys per provider with scopes)
// =============================================================================

export type GlobalKeyScope = 'chat' | 'meta' | 'title_gen';

export interface GlobalAPIKey {
  providerType: LLMProviderType;
  apiKeyLast4: string;
  apiKeySet: boolean;
  scopes: GlobalKeyScope[];
  isValid?: boolean | null;
  lastValidatedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GlobalAPIKeysResponse {
  keys: GlobalAPIKey[];
}

export interface GlobalAPIKeyCreate {
  apiKey: string;
  scopes?: GlobalKeyScope[];
}

export interface GlobalKeyValidateResponse {
  providerType: LLMProviderType;
  isValid: boolean;
  message: string;
  validatedAt: string;
}

export function useGlobalKeys() {
  return useQuery({
    queryKey: queryKeys.ai.globalKeys(),
    queryFn: async () => {
      const response = await apiClient.get<GlobalAPIKeysResponse>('/ai/global-keys');
      return response.data;
    },
  });
}

export function useGlobalKey(providerType: LLMProviderType) {
  return useQuery({
    queryKey: queryKeys.ai.globalKey(providerType),
    queryFn: async () => {
      const response = await apiClient.get<GlobalAPIKey>(`/ai/global-keys/${providerType}`);
      return response.data;
    },
    enabled: !!providerType,
  });
}

export function useSetGlobalKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      providerType,
      data,
    }: {
      providerType: LLMProviderType;
      data: GlobalAPIKeyCreate;
    }) => {
      const response = await apiClient.put<GlobalAPIKey>(
        `/ai/global-keys/${providerType}`,
        data
      );
      return response.data;
    },
    onSuccess: (_data, { providerType }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.globalKey(providerType) });
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.globalKeys() });
    },
  });
}

export function useDeleteGlobalKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (providerType: LLMProviderType) => {
      const response = await apiClient.delete(`/ai/global-keys/${providerType}`);
      return response.data;
    },
    onSuccess: (_data, providerType) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.globalKey(providerType) });
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.globalKeys() });
    },
  });
}

export function useValidateGlobalKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (providerType: LLMProviderType) => {
      const response = await apiClient.post<GlobalKeyValidateResponse>(
        `/ai/global-keys/${providerType}/validate`
      );
      return response.data;
    },
    onSuccess: (_data, providerType) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.globalKey(providerType) });
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.globalKeys() });
    },
  });
}
