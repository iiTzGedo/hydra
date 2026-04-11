import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type { DocResponse, DocSearchResult, DocsListParams, DocSummary, DocTreeNode } from '@/types/docs';

export function useDocs(params?: DocsListParams) {
  return useQuery({
    queryKey: queryKeys.docs.list(params),
    queryFn: async (): Promise<PaginatedResponse<DocSummary>> => {
      const response = await apiClient.get<ApiResponse<DocSummary[]>>('/docs', { params });
      const items = response.data.data;
      return {
        items,
        total: response.data.meta?.total ?? items.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
  });
}

export function useDocsTree() {
  return useQuery({
    queryKey: queryKeys.docs.tree(),
    queryFn: async (): Promise<DocTreeNode[]> => {
      const response = await apiClient.get<ApiResponse<DocTreeNode[]>>('/docs/tree');
      return response.data.data;
    },
  });
}

export function useDocsSearch(query: string) {
  return useQuery({
    queryKey: queryKeys.docs.search(query),
    queryFn: async (): Promise<DocSearchResult[]> => {
      const response = await apiClient.get<ApiResponse<DocSearchResult[]>>('/docs/search', {
        params: { q: query, limit: 20 },
      });
      return response.data.data;
    },
    enabled: query.trim().length > 0,
  });
}

export function useDoc(docId: string | null) {
  return useQuery({
    queryKey: queryKeys.docs.detail(docId ?? ''),
    queryFn: async (): Promise<DocResponse> => {
      const response = await apiClient.get<ApiResponse<DocResponse>>(`/docs/${docId}`);
      return response.data.data;
    },
    enabled: Boolean(docId),
  });
}
