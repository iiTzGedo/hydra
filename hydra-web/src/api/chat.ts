import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface ChatProjectResponse {
  projectId: string;
  name: string;
  description?: string;
  sessionCount: number;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatProjectListResponse {
  projects: ChatProjectResponse[];
  total: number;
}

export type ChatSessionStatus = 'active' | 'archived';

export interface ChatSessionResponse {
  sessionId: string;
  projectId?: string | null;
  title?: string | null;
  status: ChatSessionStatus;
  messageCount: number;
  llmProviderId?: string | null;
  mcpServerIds: string[];
  ownerId: string;
  createdAt: string;
  updatedAt: string;
  lastMessageAt?: string | null;
}

export interface ChatSessionListResponse {
  sessions: ChatSessionResponse[];
  total: number;
}

export type ChatMessageRole = 'user' | 'assistant' | 'system' | 'tool';
export type ChatToolCallStatus = 'pending' | 'running' | 'success' | 'error';

export interface ChatToolCall {
  id: string;
  serverId: string;
  serverName?: string | null;
  name: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
  error?: string | null;
  status: ChatToolCallStatus;
}

export interface ChatMessageResponse {
  messageId: string;
  sessionId: string;
  role: ChatMessageRole;
  content: string;
  toolCalls?: ChatToolCall[];
  order: number;
  createdAt: string;
}

export interface ChatMessageListResponse {
  messages: ChatMessageResponse[];
  total: number;
  hasMore: boolean;
}

export interface ChatProjectCreate {
  name: string;
  description?: string;
}

export interface ChatProjectUpdate {
  name?: string;
  description?: string;
}

export interface ChatSessionCreate {
  projectId?: string;
  title?: string;
  llmProviderId?: string;
  mcpServerIds?: string[];
}

export interface ChatSessionUpdate {
  title?: string;
  projectId?: string;
  status?: ChatSessionStatus;
  llmProviderId?: string;
  mcpServerIds?: string[];
}

export interface ChatMessageCreate {
  role: ChatMessageRole;
  content: string;
  toolCalls?: ChatToolCall[];
}

export interface ChatBulkUpsertResponse {
  upsertedCount: number;
  sessionId: string;
}

const chatKeys = {
  all: ['chat'] as const,
  projects: () => [...chatKeys.all, 'projects'] as const,
  projectDetail: (id: string) => [...chatKeys.all, 'project', id] as const,
  sessions: (projectId?: string) => {
    if (projectId) {
      return [...chatKeys.all, 'sessions', projectId] as const;
    }
    return [...chatKeys.all, 'sessions'] as const;
  },
  sessionDetail: (id: string) => [...chatKeys.all, 'session', id] as const,
  messages: (sessionId: string) => [...chatKeys.all, 'messages', sessionId] as const,
};

export function useChatProjects(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: chatKeys.projects(),
    queryFn: async () => {
      const response = await apiClient.get<ChatProjectListResponse>('/chat/projects', { params });
      return response.data;
    },
  });
}

export function useChatProject(projectId: string) {
  return useQuery({
    queryKey: chatKeys.projectDetail(projectId),
    queryFn: async () => {
      const response = await apiClient.get<ChatProjectResponse>(
        `/chat/projects/${projectId}`
      );
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function useCreateChatProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ChatProjectCreate) => {
      const response = await apiClient.post<ChatProjectResponse>('/chat/projects', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.projects() });
    },
  });
}

export function useUpdateChatProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ projectId, data }: { projectId: string; data: ChatProjectUpdate }) => {
      const response = await apiClient.put<ChatProjectResponse>(
        `/chat/projects/${projectId}`,
        data
      );
      return response.data;
    },
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: chatKeys.projectDetail(projectId) });
      queryClient.invalidateQueries({ queryKey: chatKeys.projects() });
    },
  });
}

export function useDeleteChatProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ projectId, cascade }: { projectId: string; cascade?: boolean }) => {
      const response = await apiClient.delete(`/chat/projects/${projectId}`, {
        params: { cascade },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.projects() });
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
  });
}

export function useChatSessions(params?: { projectId?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: chatKeys.sessions(params?.projectId),
    queryFn: async () => {
      const response = await apiClient.get<ChatSessionListResponse>('/chat/sessions', { params });
      return response.data;
    },
  });
}

export function useChatSession(sessionId: string) {
  return useQuery({
    queryKey: chatKeys.sessionDetail(sessionId),
    queryFn: async () => {
      const response = await apiClient.get<ChatSessionResponse>(
        `/chat/sessions/${sessionId}`
      );
      return response.data;
    },
    enabled: !!sessionId,
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ChatSessionCreate) => {
      const response = await apiClient.post<ChatSessionResponse>('/chat/sessions', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
  });
}

export function useUpdateChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ sessionId, data }: { sessionId: string; data: ChatSessionUpdate }) => {
      const response = await apiClient.put<ChatSessionResponse>(
        `/chat/sessions/${sessionId}`,
        data
      );
      return response.data;
    },
    onSuccess: (_data, { sessionId }) => {
      queryClient.invalidateQueries({ queryKey: chatKeys.sessionDetail(sessionId) });
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
  });
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (sessionId: string) => {
      const response = await apiClient.delete(`/chat/sessions/${sessionId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
  });
}

export function useChatMessages(
  sessionId: string,
  params?: { limit?: number; offset?: number; order?: 'asc' | 'desc' }
) {
  return useQuery({
    queryKey: chatKeys.messages(sessionId),
    queryFn: async () => {
      const response = await apiClient.get<ChatMessageListResponse>(
        `/chat/sessions/${sessionId}/messages`,
        { params }
      );
      return response.data;
    },
    enabled: !!sessionId,
  });
}

export function useCreateChatMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ sessionId, data }: { sessionId: string; data: ChatMessageCreate }) => {
      const response = await apiClient.post<ChatMessageResponse>(
        `/chat/sessions/${sessionId}/messages`,
        data
      );
      return response.data;
    },
    onSuccess: (_data, { sessionId }) => {
      queryClient.invalidateQueries({ queryKey: chatKeys.messages(sessionId) });
    },
  });
}

export function useBulkUpsertMessages() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      sessionId,
      messages,
    }: {
      sessionId: string;
      messages: Array<ChatMessageCreate & { messageId?: string; order?: number }>;
    }) => {
      const response = await apiClient.post<ChatBulkUpsertResponse>(
        `/chat/sessions/${sessionId}/messages/bulk`,
        { messages }
      );
      return response.data;
    },
    onSuccess: (_data, { sessionId }) => {
      queryClient.invalidateQueries({ queryKey: chatKeys.messages(sessionId) });
    },
  });
}
