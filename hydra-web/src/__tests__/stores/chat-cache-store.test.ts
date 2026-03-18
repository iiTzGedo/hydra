/**
 * Tests for chat-cache-store.ts
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useChatCacheStore } from '@/stores/chat-cache-store';
import type { ChatMessageResponse, SessionContext } from '@/api/chat';

describe('chat-cache-store', () => {
  // Mock data
  const createMockMessage = (id: string, sessionId: string): ChatMessageResponse => ({
    messageId: id,
    sessionId,
    role: 'user',
    content: `Message ${id}`,
    order: 1,
    createdAt: new Date().toISOString(),
  });

  const createMockContext = (): SessionContext => ({
    totalTokens: 1000,
    inputTokens: 600,
    outputTokens: 400,
    estimatedCost: 0.05,
    toolCallsCount: 2,
    messageCount: 10,
    modelUsed: 'claude-3-5-sonnet-20241022',
    providerType: 'anthropic',
    thread: ['msg-1', 'msg-2', 'msg-3'],
  });

  beforeEach(() => {
    // Reset store
    useChatCacheStore.setState({
      messageCache: {},
      contextCache: {},
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Initial State', () => {
    it('should have empty caches initially', () => {
      const state = useChatCacheStore.getState();
      expect(state.messageCache).toEqual({});
      expect(state.contextCache).toEqual({});
    });
  });

  describe('setCachedMessages', () => {
    it('should cache messages for a session', () => {
      const { setCachedMessages } = useChatCacheStore.getState();
      const messages = [
        createMockMessage('msg-1', 'session-1'),
        createMockMessage('msg-2', 'session-1'),
      ];

      setCachedMessages('session-1', messages);

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1']).toBeDefined();
      expect(state.messageCache['session-1'].data).toEqual(messages);
      expect(state.messageCache['session-1'].timestamp).toBeDefined();
    });

    it('should cap cached messages at MAX_CACHED_MESSAGES (100)', () => {
      const { setCachedMessages } = useChatCacheStore.getState();
      const messages: ChatMessageResponse[] = [];

      // Create 150 messages
      for (let i = 1; i <= 150; i++) {
        messages.push(createMockMessage(`msg-${i}`, 'session-1'));
      }

      setCachedMessages('session-1', messages);

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1'].data).toHaveLength(100);
      // Should keep the last 100 messages
      expect(state.messageCache['session-1'].data[0].messageId).toBe('msg-51');
      expect(state.messageCache['session-1'].data[99].messageId).toBe('msg-150');
    });

    it('should update timestamp when setting cached messages', () => {
      const { setCachedMessages } = useChatCacheStore.getState();
      const now = Date.now();
      vi.setSystemTime(now);

      const messages = [createMockMessage('msg-1', 'session-1')];
      setCachedMessages('session-1', messages);

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1'].timestamp).toBe(now);
    });
  });

  describe('getCachedMessages', () => {
    it('should return null when no cache exists for session', () => {
      const { getCachedMessages } = useChatCacheStore.getState();
      const result = getCachedMessages('non-existent-session');
      expect(result).toBeNull();
    });

    it('should return cached messages when cache is fresh', () => {
      const { setCachedMessages, getCachedMessages } = useChatCacheStore.getState();
      const messages = [createMockMessage('msg-1', 'session-1')];

      setCachedMessages('session-1', messages);
      const result = getCachedMessages('session-1');

      expect(result).toEqual(messages);
    });

    it('should return null when cache is stale (>5 minutes)', () => {
      const { setCachedMessages, getCachedMessages } = useChatCacheStore.getState();
      const messages = [createMockMessage('msg-1', 'session-1')];

      const now = Date.now();
      vi.setSystemTime(now);
      setCachedMessages('session-1', messages);

      // Advance time by 5 minutes + 1 second
      vi.setSystemTime(now + 5 * 60 * 1000 + 1000);

      const result = getCachedMessages('session-1');
      expect(result).toBeNull();
    });

    it('should return messages when cache is just under TTL', () => {
      const { setCachedMessages, getCachedMessages } = useChatCacheStore.getState();
      const messages = [createMockMessage('msg-1', 'session-1')];

      const now = Date.now();
      vi.setSystemTime(now);
      setCachedMessages('session-1', messages);

      // Advance time by 4 minutes 59 seconds
      vi.setSystemTime(now + 4 * 60 * 1000 + 59 * 1000);

      const result = getCachedMessages('session-1');
      expect(result).toEqual(messages);
    });
  });

  describe('appendMessage', () => {
    it('should create new cache with single message when no cache exists', () => {
      const { appendMessage } = useChatCacheStore.getState();
      const message = createMockMessage('msg-1', 'session-1');

      appendMessage('session-1', message);

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1'].data).toEqual([message]);
    });

    it('should append message to existing cache', () => {
      const { setCachedMessages, appendMessage } = useChatCacheStore.getState();
      const existingMessages = [createMockMessage('msg-1', 'session-1')];
      const newMessage = createMockMessage('msg-2', 'session-1');

      setCachedMessages('session-1', existingMessages);
      appendMessage('session-1', newMessage);

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1'].data).toHaveLength(2);
      expect(state.messageCache['session-1'].data[1]).toEqual(newMessage);
    });

    it('should refresh timestamp when appending message', () => {
      const { setCachedMessages, appendMessage } = useChatCacheStore.getState();
      const now = Date.now();
      vi.setSystemTime(now);

      const existingMessages = [createMockMessage('msg-1', 'session-1')];
      setCachedMessages('session-1', existingMessages);

      // Advance time
      const laterTime = now + 60 * 1000;
      vi.setSystemTime(laterTime);

      const newMessage = createMockMessage('msg-2', 'session-1');
      appendMessage('session-1', newMessage);

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1'].timestamp).toBe(laterTime);
    });

    it('should cap at MAX_CACHED_MESSAGES when appending', () => {
      const { setCachedMessages, appendMessage } = useChatCacheStore.getState();
      const messages: ChatMessageResponse[] = [];

      // Create 100 messages
      for (let i = 1; i <= 100; i++) {
        messages.push(createMockMessage(`msg-${i}`, 'session-1'));
      }
      setCachedMessages('session-1', messages);

      // Append one more
      appendMessage('session-1', createMockMessage('msg-101', 'session-1'));

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1'].data).toHaveLength(100);
      // Should keep last 100 (msg-2 to msg-101)
      expect(state.messageCache['session-1'].data[0].messageId).toBe('msg-2');
      expect(state.messageCache['session-1'].data[99].messageId).toBe('msg-101');
    });
  });

  describe('invalidateMessages', () => {
    it('should remove message cache for session', () => {
      const { setCachedMessages, invalidateMessages } = useChatCacheStore.getState();
      const messages = [createMockMessage('msg-1', 'session-1')];

      setCachedMessages('session-1', messages);
      invalidateMessages('session-1');

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1']).toBeUndefined();
    });

    it('should not affect other session caches', () => {
      const { setCachedMessages, invalidateMessages } = useChatCacheStore.getState();

      setCachedMessages('session-1', [createMockMessage('msg-1', 'session-1')]);
      setCachedMessages('session-2', [createMockMessage('msg-2', 'session-2')]);

      invalidateMessages('session-1');

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1']).toBeUndefined();
      expect(state.messageCache['session-2']).toBeDefined();
    });
  });

  describe('setCachedContext', () => {
    it('should cache context for a session', () => {
      const { setCachedContext } = useChatCacheStore.getState();
      const context = createMockContext();

      setCachedContext('session-1', context);

      const state = useChatCacheStore.getState();
      expect(state.contextCache['session-1']).toBeDefined();
      expect(state.contextCache['session-1'].data).toEqual(context);
    });

    it('should set timestamp when caching context', () => {
      const { setCachedContext } = useChatCacheStore.getState();
      const now = Date.now();
      vi.setSystemTime(now);

      const context = createMockContext();
      setCachedContext('session-1', context);

      const state = useChatCacheStore.getState();
      expect(state.contextCache['session-1'].timestamp).toBe(now);
    });
  });

  describe('getCachedContext', () => {
    it('should return null when no cache exists', () => {
      const { getCachedContext } = useChatCacheStore.getState();
      const result = getCachedContext('non-existent-session');
      expect(result).toBeNull();
    });

    it('should return cached context when fresh', () => {
      const { setCachedContext, getCachedContext } = useChatCacheStore.getState();
      const context = createMockContext();

      setCachedContext('session-1', context);
      const result = getCachedContext('session-1');

      expect(result).toEqual(context);
    });

    it('should return null when cache is stale (>1 minute)', () => {
      const { setCachedContext, getCachedContext } = useChatCacheStore.getState();
      const context = createMockContext();

      const now = Date.now();
      vi.setSystemTime(now);
      setCachedContext('session-1', context);

      // Advance time by 1 minute + 1 second
      vi.setSystemTime(now + 60 * 1000 + 1000);

      const result = getCachedContext('session-1');
      expect(result).toBeNull();
    });
  });

  describe('invalidateContext', () => {
    it('should remove context cache for session', () => {
      const { setCachedContext, invalidateContext } = useChatCacheStore.getState();
      const context = createMockContext();

      setCachedContext('session-1', context);
      invalidateContext('session-1');

      const state = useChatCacheStore.getState();
      expect(state.contextCache['session-1']).toBeUndefined();
    });
  });

  describe('isMessagesCacheStale', () => {
    it('should return true when no cache exists', () => {
      const { isMessagesCacheStale } = useChatCacheStore.getState();
      expect(isMessagesCacheStale('non-existent-session')).toBe(true);
    });

    it('should return false when cache is fresh', () => {
      const { setCachedMessages, isMessagesCacheStale } = useChatCacheStore.getState();
      const messages = [createMockMessage('msg-1', 'session-1')];

      setCachedMessages('session-1', messages);
      expect(isMessagesCacheStale('session-1')).toBe(false);
    });

    it('should return true when cache is stale', () => {
      const { setCachedMessages, isMessagesCacheStale } = useChatCacheStore.getState();
      const now = Date.now();
      vi.setSystemTime(now);

      const messages = [createMockMessage('msg-1', 'session-1')];
      setCachedMessages('session-1', messages);

      // Advance time beyond TTL
      vi.setSystemTime(now + 5 * 60 * 1000 + 1000);

      expect(isMessagesCacheStale('session-1')).toBe(true);
    });
  });

  describe('isContextCacheStale', () => {
    it('should return true when no cache exists', () => {
      const { isContextCacheStale } = useChatCacheStore.getState();
      expect(isContextCacheStale('non-existent-session')).toBe(true);
    });

    it('should return false when cache is fresh', () => {
      const { setCachedContext, isContextCacheStale } = useChatCacheStore.getState();
      const context = createMockContext();

      setCachedContext('session-1', context);
      expect(isContextCacheStale('session-1')).toBe(false);
    });

    it('should return true when cache is stale', () => {
      const { setCachedContext, isContextCacheStale } = useChatCacheStore.getState();
      const now = Date.now();
      vi.setSystemTime(now);

      const context = createMockContext();
      setCachedContext('session-1', context);

      // Advance time beyond TTL
      vi.setSystemTime(now + 60 * 1000 + 1000);

      expect(isContextCacheStale('session-1')).toBe(true);
    });
  });

  describe('clearSessionCache', () => {
    it('should clear both message and context cache for session', () => {
      const { setCachedMessages, setCachedContext, clearSessionCache } =
        useChatCacheStore.getState();

      setCachedMessages('session-1', [createMockMessage('msg-1', 'session-1')]);
      setCachedContext('session-1', createMockContext());

      clearSessionCache('session-1');

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1']).toBeUndefined();
      expect(state.contextCache['session-1']).toBeUndefined();
    });

    it('should not affect other sessions', () => {
      const { setCachedMessages, clearSessionCache } = useChatCacheStore.getState();

      setCachedMessages('session-1', [createMockMessage('msg-1', 'session-1')]);
      setCachedMessages('session-2', [createMockMessage('msg-2', 'session-2')]);

      clearSessionCache('session-1');

      const state = useChatCacheStore.getState();
      expect(state.messageCache['session-1']).toBeUndefined();
      expect(state.messageCache['session-2']).toBeDefined();
    });
  });

  describe('clearAllCache', () => {
    it('should clear all message and context caches', () => {
      const { setCachedMessages, setCachedContext, clearAllCache } = useChatCacheStore.getState();

      setCachedMessages('session-1', [createMockMessage('msg-1', 'session-1')]);
      setCachedMessages('session-2', [createMockMessage('msg-2', 'session-2')]);
      setCachedContext('session-1', createMockContext());
      setCachedContext('session-2', createMockContext());

      clearAllCache();

      const state = useChatCacheStore.getState();
      expect(state.messageCache).toEqual({});
      expect(state.contextCache).toEqual({});
    });
  });

  describe('getCacheStats', () => {
    it('should return zero counts for empty caches', () => {
      const { getCacheStats } = useChatCacheStore.getState();
      const stats = getCacheStats();

      expect(stats.messageCacheSize).toBe(0);
      expect(stats.contextCacheSize).toBe(0);
    });

    it('should return correct counts for populated caches', () => {
      const { setCachedMessages, setCachedContext, getCacheStats } = useChatCacheStore.getState();

      setCachedMessages('session-1', [createMockMessage('msg-1', 'session-1')]);
      setCachedMessages('session-2', [createMockMessage('msg-2', 'session-2')]);
      setCachedContext('session-1', createMockContext());

      const stats = getCacheStats();
      expect(stats.messageCacheSize).toBe(2);
      expect(stats.contextCacheSize).toBe(1);
    });

    it('should return updated counts after clearing cache', () => {
      const { setCachedMessages, clearSessionCache, getCacheStats } = useChatCacheStore.getState();

      setCachedMessages('session-1', [createMockMessage('msg-1', 'session-1')]);
      setCachedMessages('session-2', [createMockMessage('msg-2', 'session-2')]);

      clearSessionCache('session-1');

      const stats = getCacheStats();
      expect(stats.messageCacheSize).toBe(1);
    });
  });
});
