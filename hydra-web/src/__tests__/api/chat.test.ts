import { beforeEach, describe, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  useBulkUpsertMessages,
  useChatMessages,
  useChatProject,
  useChatProjects,
  useChatSessions,
  useCreateChatMessage,
  useCreateChatProject,
  useDeleteChatSession,
  useSessionContext,
  useUpdateChatSession,
} from '@/api/chat';
import { useChatCacheStore } from '@/stores/chat-cache-store';
import { createTestQueryClient, renderWithQuery } from '../msw/test-utils';

describe('Chat API Hooks', () => {
  beforeEach(() => {
    useChatCacheStore.setState({
      messageCache: {},
      contextCache: {},
    });
  });

  it('fetches chat projects', async () => {
    const { result } = renderWithQuery(() => useChatProjects());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.projects).toHaveLength(2);
    expect(result.current.data?.projects[0].projectId).toBe('proj-homelab');
    expect(result.current.data?.total).toBe(2);
  });

  it('fetches project-filtered sessions', async () => {
    const { result } = renderWithQuery(() => useChatSessions({ projectId: 'proj-homelab' }));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.sessions).toHaveLength(1);
    expect(result.current.data?.sessions[0].sessionId).toBe('sess-alpha');
  });

  it('disables project detail when projectId is empty', () => {
    const { result } = renderWithQuery(() => useChatProject(''));

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('hydrates the message cache after fetching messages', async () => {
    const { result } = renderWithQuery(() => useChatMessages('sess-alpha'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.messages).toHaveLength(2);
    expect(useChatCacheStore.getState().getCachedMessages('sess-alpha')).toHaveLength(2);
  });

  it('serves default message queries from the fresh browser cache', async () => {
    useChatCacheStore.getState().setCachedMessages('sess-alpha', [
      {
        messageId: 'cached-001',
        sessionId: 'sess-alpha',
        role: 'assistant',
        content: 'Cached reply',
        order: 1,
        createdAt: '2026-03-09T12:00:00Z',
      },
    ]);

    const { result } = renderWithQuery(() => useChatMessages('sess-alpha'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.messages[0].messageId).toBe('cached-001');
    expect(result.current.data?.messages[0].content).toBe('Cached reply');
  });

  it('appends created messages to cache and invalidates the session message query', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    useChatCacheStore.getState().setCachedMessages('sess-alpha', [
      {
        messageId: 'msg-001',
        sessionId: 'sess-alpha',
        role: 'user',
        content: 'Original',
        order: 1,
        createdAt: '2026-03-09T12:00:00Z',
      },
    ]);

    const { result } = renderWithQuery(() => useCreateChatMessage(), { queryClient });

    await waitFor(() => expect(result.current).toBeDefined());

    result.current.mutate({
      sessionId: 'sess-alpha',
      data: {
        role: 'assistant',
        content: 'New response',
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      useChatCacheStore.getState().getCachedMessages('sess-alpha')?.map((message) => message.content)
    ).toContain('New response');
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['chat', 'messages', 'sess-alpha'] });
  });

  it('invalidates cached messages after bulk upsert', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    useChatCacheStore.getState().setCachedMessages('sess-alpha', [
      {
        messageId: 'msg-001',
        sessionId: 'sess-alpha',
        role: 'user',
        content: 'Existing',
        order: 1,
        createdAt: '2026-03-09T12:00:00Z',
      },
    ]);

    const { result } = renderWithQuery(() => useBulkUpsertMessages(), { queryClient });

    result.current.mutate({
      sessionId: 'sess-alpha',
      messages: [
        {
          role: 'assistant',
          content: 'Bulk response',
        },
      ],
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(useChatCacheStore.getState().getCachedMessages('sess-alpha')).toBeNull();
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['chat', 'messages', 'sess-alpha'] });
  });

  it('returns null session context queries only when a session id is provided', async () => {
    const { result } = renderWithQuery(() => useSessionContext(null));

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('serves session context from the fresh browser cache', async () => {
    useChatCacheStore.getState().setCachedContext('sess-alpha', {
      totalTokens: 321,
      inputTokens: 100,
      outputTokens: 221,
      estimatedCost: 0.01,
      toolCallsCount: 1,
      messageCount: 2,
      modelUsed: 'cached-model',
      providerType: 'anthropic',
      thread: ['cached-001', 'cached-002'],
    });

    const { result } = renderWithQuery(() => useSessionContext('sess-alpha'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.context.modelUsed).toBe('cached-model');
    expect(result.current.data?.sessionId).toBe('sess-alpha');
  });

  it('invalidates the expected keys when chat mutations complete', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const createProject = renderWithQuery(() => useCreateChatProject(), { queryClient }).result;
    createProject.current.mutate({ name: 'Test project' });
    await waitFor(() => expect(createProject.current.isSuccess).toBe(true));

    const updateSession = renderWithQuery(() => useUpdateChatSession(), { queryClient }).result;
    updateSession.current.mutate({
      sessionId: 'sess-alpha',
      data: { title: 'Renamed session' },
    });
    await waitFor(() => expect(updateSession.current.isSuccess).toBe(true));

    const deleteSession = renderWithQuery(() => useDeleteChatSession(), { queryClient }).result;
    deleteSession.current.mutate('sess-standalone');
    await waitFor(() => expect(deleteSession.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['chat', 'projects'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['chat', 'session', 'sess-alpha'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['chat', 'sessions'] });
  });
});
