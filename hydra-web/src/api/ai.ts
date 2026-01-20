import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';

export type LLMProviderType = 'anthropic' | 'openai' | 'ollama';

export interface LLMProviderResponse {
  providerId: string;
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
  providers: LLMProviderResponse[];
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
  providerId: string;
  isValid: boolean;
  message: string;
  validatedAt: string;
  models?: string[] | null;
}

export function useLLMProviders() {
  return useQuery({
    queryKey: queryKeys.ai.models(),
    queryFn: async () => {
      const response = await apiClient.get<LLMProviderListResponse>('/ai/models');
      return response.data;
    },
  });
}

export function useLLMProvider(providerId: string) {
  return useQuery({
    queryKey: queryKeys.ai.model(providerId),
    queryFn: async () => {
      const response = await apiClient.get<LLMProviderResponse>(`/ai/models/${providerId}`);
      return response.data;
    },
    enabled: !!providerId,
  });
}

export function useCreateLLMProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: LLMProviderCreate) => {
      const response = await apiClient.post<LLMProviderResponse>('/ai/models', data);
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
        `/ai/models/${providerId}`,
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
      const response = await apiClient.delete(`/ai/models/${providerId}`);
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
        `/ai/models/${providerId}/validate`
      );
      return response.data;
    },
    onSuccess: (_data, providerId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.model(providerId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.ai.models() });
    },
  });
}
