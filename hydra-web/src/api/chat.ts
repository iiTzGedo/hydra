/**
 * Chat API hooks
 * Manages chat projects, sessions, and message persistence
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import type { ApiResponse } from '@/types/api';

// Types based on backend models
export interface ChatProject {
  projectId: string;
  name: string;
  description?: string;
  sessionCount: number;
  createdAt: string;
  updatedAt?: string;
}

export interface ChatSession {
  sessionId: string;
  projectId?: string;
  name: string;
  messageCount: number;
  createdAt: string;
  updatedAt?: string;
}

export interface ChatMessage {
  messageId: string;
  sessionId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: ChatToolCall[];
  error?: boolean;
  createdAt: string;
}

export interface ChatToolCall {
  id: string;
  name: string;
  serverName: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
  error?: string;
  status: 'pending' | 'success' | 'error';
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
  name: string;
}

export interface ChatSessionUpdate {
  name?: string;
  projectId?: string;
}

export interface ChatMessageCreate {
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: ChatToolCall[];
  error?: boolean;
}

// Query keys
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

// ==================== Projects ====================

export function useChatProjects(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: chatKeys.projects(),
    queryFn: async () => {
      const response = await apiClient.get<
        ApiResponse<{ projects: ChatProject[]; total: number }>
      >('/chat/projects', { params });
      return response.data.data;
    },
  });
}

export function useChatProject(projectId: string) {
  return useQuery({
    queryKey: chatKeys.projectDetail(projectId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ChatProject>>(
        `/chat/projects/${projectId}`
      );
      return response.data.data;
    },
    enabled: !!projectId,
  });
}

export function useCreateChatProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ChatProjectCreate) => {
      const response = await apiClient.post<ApiResponse<ChatProject>>('/chat/projects', data);
      return response.data.data;
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
      const response = await apiClient.put<ApiResponse<ChatProject>>(
        `/chat/projects/${projectId}`,
        data
      );
      return response.data.data;
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
    },
  });
}

// ==================== Sessions ====================

export function useChatSessions(params?: { projectId?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: chatKeys.sessions(params?.projectId),
    queryFn: async () => {
      const response = await apiClient.get<
        ApiResponse<{ sessions: ChatSession[]; total: number }>
      >('/chat/sessions', { params });
      return response.data.data;
    },
  });
}

export function useChatSession(sessionId: string) {
  return useQuery({
    queryKey: chatKeys.sessionDetail(sessionId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ChatSession>>(
        `/chat/sessions/${sessionId}`
      );
      return response.data.data;
    },
    enabled: !!sessionId,
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ChatSessionCreate) => {
      const response = await apiClient.post<ApiResponse<ChatSession>>('/chat/sessions', data);
      return response.data.data;
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
      const response = await apiClient.put<ApiResponse<ChatSession>>(
        `/chat/sessions/${sessionId}`,
        data
      );
      return response.data.data;
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

// ==================== Messages ====================

export function useChatMessages(
  sessionId: string,
  params?: { limit?: number; offset?: number; order?: 'asc' | 'desc' }
) {
  return useQuery({
    queryKey: chatKeys.messages(sessionId),
    queryFn: async () => {
      const response = await apiClient.get<
        ApiResponse<{ messages: ChatMessage[]; total: number; has_more: boolean }>
      >(`/chat/sessions/${sessionId}/messages`, { params });
      return response.data.data;
    },
    enabled: !!sessionId,
  });
}

export function useCreateChatMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ sessionId, data }: { sessionId: string; data: ChatMessageCreate }) => {
      const response = await apiClient.post<ApiResponse<ChatMessage>>(
        `/chat/sessions/${sessionId}/messages`,
        data
      );
      return response.data.data;
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
      messages: Array<ChatMessageCreate & { messageId?: string }>;
    }) => {
      const response = await apiClient.post<ApiResponse<{ created: number; updated: number }>>(
        `/chat/sessions/${sessionId}/messages/bulk`,
        { messages }
      );
      return response.data.data;
    },
    onSuccess: (_data, { sessionId }) => {
      queryClient.invalidateQueries({ queryKey: chatKeys.messages(sessionId) });
    },
  });
}
