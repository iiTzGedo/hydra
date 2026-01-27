/**
 * Hook to integrate IndexedDB chat storage with the MCP store
 * Provides automatic migration and sync between localStorage and IndexedDB
 */

import { useEffect, useState, useCallback } from 'react';
import { useMCPStore } from '@/stores/mcp-store';
import {
  initChatDB,
  getAllSessions,
  getAllProjects,
  saveSessions,
  saveSession,
  deleteSession as deleteSessionFromDB,
  saveProject,
  deleteProject as deleteProjectFromDB,
  migrateFromLocalStorage,
  isIndexedDBAvailable,
  getSessionCount,
} from '@/lib/chat-db';
import type { MCPChatSession, ChatProject } from '@/types/mcp';

interface UseChatDBResult {
  isReady: boolean;
  isLoading: boolean;
  error: string | null;
  sessionCount: number;
  syncToIndexedDB: () => Promise<void>;
  loadFromIndexedDB: () => Promise<void>;
}

let migrationComplete = false;

export function useChatDB(): UseChatDBResult {
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionCount, setSessionCount] = useState(0);

  const sessions = useMCPStore((state) => state.sessions);
  const projects = useMCPStore((state) => state.projects);

  // Initialize IndexedDB and migrate data on first load
  useEffect(() => {
    const initialize = async () => {
      if (!isIndexedDBAvailable()) {
        setError('IndexedDB is not available in this browser');
        setIsLoading(false);
        return;
      }

      try {
        // Initialize the database
        await initChatDB();

        // Run migration only once
        if (!migrationComplete) {
          await migrateFromLocalStorage();
          migrationComplete = true;
        }

        // Get session count
        const count = await getSessionCount();
        setSessionCount(count);

        setIsReady(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to initialize chat database');
        console.error('Chat DB initialization error:', err);
      } finally {
        setIsLoading(false);
      }
    };

    initialize();
  }, []);

  // Sync sessions to IndexedDB when they change (debounced)
  useEffect(() => {
    if (!isReady) return;

    const syncTimeout = setTimeout(async () => {
      try {
        await saveSessions(sessions);
        const count = await getSessionCount();
        setSessionCount(count);
      } catch (err) {
        console.error('Failed to sync sessions to IndexedDB:', err);
      }
    }, 1000); // Debounce by 1 second

    return () => clearTimeout(syncTimeout);
  }, [sessions, isReady]);

  // Sync projects to IndexedDB when they change
  useEffect(() => {
    if (!isReady) return;

    const syncProjects = async () => {
      try {
        for (const project of projects) {
          await saveProject(project);
        }
      } catch (err) {
        console.error('Failed to sync projects to IndexedDB:', err);
      }
    };

    syncProjects();
  }, [projects, isReady]);

  // Manual sync to IndexedDB
  const syncToIndexedDB = useCallback(async () => {
    if (!isReady) return;

    try {
      await saveSessions(sessions);
      for (const project of projects) {
        await saveProject(project);
      }
      const count = await getSessionCount();
      setSessionCount(count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync to IndexedDB');
      throw err;
    }
  }, [sessions, projects, isReady]);

  // Load from IndexedDB (useful for recovery)
  const loadFromIndexedDB = useCallback(async () => {
    if (!isReady) return;

    try {
      const [dbSessions, dbProjects] = await Promise.all([
        getAllSessions(),
        getAllProjects(),
      ]);

      // Update store with IndexedDB data
      // Note: This would require adding a setter to the store
      console.log(`Loaded ${dbSessions.length} sessions and ${dbProjects.length} projects from IndexedDB`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load from IndexedDB');
      throw err;
    }
  }, [isReady]);

  return {
    isReady,
    isLoading,
    error,
    sessionCount,
    syncToIndexedDB,
    loadFromIndexedDB,
  };
}

/**
 * Hook to persist a single session change to IndexedDB
 */
export function usePersistSession() {
  const persistSession = useCallback(async (session: MCPChatSession) => {
    try {
      await saveSession(session);
    } catch (err) {
      console.error('Failed to persist session:', err);
    }
  }, []);

  const removeSession = useCallback(async (sessionId: string) => {
    try {
      await deleteSessionFromDB(sessionId);
    } catch (err) {
      console.error('Failed to remove session:', err);
    }
  }, []);

  return { persistSession, removeSession };
}

/**
 * Hook to persist project changes to IndexedDB
 */
export function usePersistProject() {
  const persistProject = useCallback(async (project: ChatProject) => {
    try {
      await saveProject(project);
    } catch (err) {
      console.error('Failed to persist project:', err);
    }
  }, []);

  const removeProject = useCallback(async (projectId: string) => {
    try {
      await deleteProjectFromDB(projectId);
    } catch (err) {
      console.error('Failed to remove project:', err);
    }
  }, []);

  return { persistProject, removeProject };
}
