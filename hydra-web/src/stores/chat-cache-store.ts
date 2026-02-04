import { create } from 'zustand';
import type { ChatMessageResponse, SessionContext } from '@/api/chat';

/**
 * Cache TTL values in milliseconds
 */
const CACHE_TTL = {
  MESSAGES: 5 * 60 * 1000, // 5 minutes
  CONTEXT: 60 * 1000, // 1 minute
};

/**
 * Maximum messages to cache per session
 */
const MAX_CACHED_MESSAGES = 100;

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

interface ChatCacheStore {
  // Message cache: sessionId -> cached messages
  messageCache: Record<string, CacheEntry<ChatMessageResponse[]>>;

  // Context cache: sessionId -> session context
  contextCache: Record<string, CacheEntry<SessionContext>>;

  // Message cache operations
  setCachedMessages: (sessionId: string, messages: ChatMessageResponse[]) => void;
  getCachedMessages: (sessionId: string) => ChatMessageResponse[] | null;
  appendMessage: (sessionId: string, message: ChatMessageResponse) => void;
  invalidateMessages: (sessionId: string) => void;

  // Context cache operations
  setCachedContext: (sessionId: string, context: SessionContext) => void;
  getCachedContext: (sessionId: string) => SessionContext | null;
  invalidateContext: (sessionId: string) => void;

  // Utility operations
  isMessagesCacheStale: (sessionId: string) => boolean;
  isContextCacheStale: (sessionId: string) => boolean;
  clearSessionCache: (sessionId: string) => void;
  clearAllCache: () => void;

  // Cache stats for debugging
  getCacheStats: () => { messageCacheSize: number; contextCacheSize: number };
}

export const useChatCacheStore = create<ChatCacheStore>()((set, get) => ({
  messageCache: {},
  contextCache: {},

  // Message cache operations
  setCachedMessages: (sessionId, messages) => {
    const entry: CacheEntry<ChatMessageResponse[]> = {
      data: messages.slice(-MAX_CACHED_MESSAGES), // Keep only last N messages
      timestamp: Date.now(),
    };
    set((state) => ({
      messageCache: { ...state.messageCache, [sessionId]: entry },
    }));
  },

  getCachedMessages: (sessionId) => {
    const entry = get().messageCache[sessionId];
    if (!entry) return null;

    // Check if cache is stale
    if (Date.now() - entry.timestamp > CACHE_TTL.MESSAGES) {
      // Don't invalidate here, just return null - let caller decide
      return null;
    }

    return entry.data;
  },

  appendMessage: (sessionId, message) => {
    const currentEntry = get().messageCache[sessionId];
    if (!currentEntry) {
      // No cache exists, create new with single message
      get().setCachedMessages(sessionId, [message]);
      return;
    }

    const updatedMessages = [...currentEntry.data, message].slice(-MAX_CACHED_MESSAGES);
    const entry: CacheEntry<ChatMessageResponse[]> = {
      data: updatedMessages,
      timestamp: Date.now(), // Refresh timestamp on append
    };

    set((state) => ({
      messageCache: { ...state.messageCache, [sessionId]: entry },
    }));
  },

  invalidateMessages: (sessionId) => {
    set((state) => {
      const { [sessionId]: _, ...rest } = state.messageCache;
      return { messageCache: rest };
    });
  },

  // Context cache operations
  setCachedContext: (sessionId, context) => {
    const entry: CacheEntry<SessionContext> = {
      data: context,
      timestamp: Date.now(),
    };
    set((state) => ({
      contextCache: { ...state.contextCache, [sessionId]: entry },
    }));
  },

  getCachedContext: (sessionId) => {
    const entry = get().contextCache[sessionId];
    if (!entry) return null;

    // Check if cache is stale
    if (Date.now() - entry.timestamp > CACHE_TTL.CONTEXT) {
      return null;
    }

    return entry.data;
  },

  invalidateContext: (sessionId) => {
    set((state) => {
      const { [sessionId]: _, ...rest } = state.contextCache;
      return { contextCache: rest };
    });
  },

  // Utility operations
  isMessagesCacheStale: (sessionId) => {
    const entry = get().messageCache[sessionId];
    if (!entry) return true;
    return Date.now() - entry.timestamp > CACHE_TTL.MESSAGES;
  },

  isContextCacheStale: (sessionId) => {
    const entry = get().contextCache[sessionId];
    if (!entry) return true;
    return Date.now() - entry.timestamp > CACHE_TTL.CONTEXT;
  },

  clearSessionCache: (sessionId) => {
    set((state) => {
      const { [sessionId]: _msg, ...restMessages } = state.messageCache;
      const { [sessionId]: _ctx, ...restContext } = state.contextCache;
      return {
        messageCache: restMessages,
        contextCache: restContext,
      };
    });
  },

  clearAllCache: () => {
    set({
      messageCache: {},
      contextCache: {},
    });
  },

  getCacheStats: () => {
    const state = get();
    return {
      messageCacheSize: Object.keys(state.messageCache).length,
      contextCacheSize: Object.keys(state.contextCache).length,
    };
  },
}));
