/**
 * Typed localStorage abstraction for the Hydra web application.
 *
 * Provides type-safe storage operations with proper error handling,
 * JSON serialization, and a centralized storage interface.
 */

import { STORAGE_KEYS } from './constants';

// Re-export for convenience
export { STORAGE_KEYS };

/**
 * Type definitions for each storage key's value.
 * Extend this interface when adding new storage keys.
 */
export interface StorageSchema {
  [STORAGE_KEYS.theme]: 'dark' | 'light' | 'system';
}

/**
 * Valid storage keys derived from the schema.
 */
export type StorageKey = keyof StorageSchema;

/**
 * Check if localStorage is available.
 * Handles cases where localStorage is disabled or not available (e.g., SSR, private browsing).
 */
function isStorageAvailable(): boolean {
  try {
    const test = '__storage_test__';
    localStorage.setItem(test, test);
    localStorage.removeItem(test);
    return true;
  } catch {
    return false;
  }
}

/**
 * Storage service providing type-safe localStorage operations.
 */
export const storage = {
  /**
   * Check if storage is available.
   */
  isAvailable: isStorageAvailable,

  /**
   * Get a value from storage.
   *
   * @param key - The storage key to retrieve.
   * @returns The stored value or null if not found.
   */
  get<K extends StorageKey>(key: K): StorageSchema[K] | null {
    if (!isStorageAvailable()) {
      console.warn('localStorage is not available');
      return null;
    }

    try {
      const value = localStorage.getItem(key);
      return value as StorageSchema[K] | null;
    } catch (error) {
      console.error(`Failed to get storage key "${key}":`, error);
      return null;
    }
  },

  /**
   * Set a value in storage.
   *
   * @param key - The storage key to set.
   * @param value - The value to store.
   * @returns True if successful, false otherwise.
   */
  set<K extends StorageKey>(key: K, value: StorageSchema[K]): boolean {
    if (!isStorageAvailable()) {
      console.warn('localStorage is not available');
      return false;
    }

    try {
      localStorage.setItem(key, value);
      return true;
    } catch (error) {
      // Handle quota exceeded errors
      if (error instanceof DOMException && error.name === 'QuotaExceededError') {
        console.error(`Storage quota exceeded when setting "${key}"`);
      } else {
        console.error(`Failed to set storage key "${key}":`, error);
      }
      return false;
    }
  },

  /**
   * Remove a value from storage.
   *
   * @param key - The storage key to remove.
   * @returns True if successful, false otherwise.
   */
  remove<K extends StorageKey>(key: K): boolean {
    if (!isStorageAvailable()) {
      console.warn('localStorage is not available');
      return false;
    }

    try {
      localStorage.removeItem(key);
      return true;
    } catch (error) {
      console.error(`Failed to remove storage key "${key}":`, error);
      return false;
    }
  },

  /**
   * Clear all Hydra-related storage keys.
   * Only removes keys defined in STORAGE_KEYS, not all localStorage.
   */
  clearAll(): void {
    Object.values(STORAGE_KEYS).forEach((key) => {
      this.remove(key as StorageKey);
    });
  },

  /**
   * Get the current theme preference.
   */
  getTheme(): StorageSchema[typeof STORAGE_KEYS.theme] | null {
    return this.get(STORAGE_KEYS.theme);
  },

  /**
   * Set the theme preference.
   *
   * @param theme - The theme to set.
   */
  setTheme(theme: StorageSchema[typeof STORAGE_KEYS.theme]): boolean {
    return this.set(STORAGE_KEYS.theme, theme);
  },
};

export default storage;
