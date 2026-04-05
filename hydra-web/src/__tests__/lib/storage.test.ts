import { beforeEach, describe, expect, it, vi } from 'vitest';

import { storage, STORAGE_KEYS } from '@/lib/storage';

describe('storage', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('reads and writes theme values', () => {
    expect(storage.getTheme()).toBeNull();
    expect(storage.setTheme('dark')).toBe(true);
    expect(storage.getTheme()).toBe('dark');
    expect(localStorage.getItem(STORAGE_KEYS.theme)).toBe('dark');
  });

  it('removes stored values', () => {
    localStorage.setItem(STORAGE_KEYS.theme, 'light');

    expect(storage.remove(STORAGE_KEYS.theme)).toBe(true);
    expect(storage.getTheme()).toBeNull();
  });

  it('clears all managed Hydra storage keys', () => {
    localStorage.setItem(STORAGE_KEYS.theme, 'system');
    localStorage.setItem('unrelated-key', 'keep-me');

    storage.clearAll();

    expect(localStorage.getItem(STORAGE_KEYS.theme)).toBeNull();
    expect(localStorage.getItem('unrelated-key')).toBe('keep-me');
  });

  it('returns null when localStorage access fails', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('Storage error');
    });

    expect(storage.getTheme()).toBeNull();

    spy.mockRestore();
  });

  it('exposes only the tracked theme key', () => {
    expect(STORAGE_KEYS).toEqual({ theme: 'hydra-theme' });
  });
});
