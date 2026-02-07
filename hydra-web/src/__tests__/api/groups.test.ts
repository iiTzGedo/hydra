import { describe, it, expect } from 'vitest';
import { waitFor } from '@testing-library/react';
import { useGroups, useGroup } from '@/api/groups';
import { renderWithQuery } from '../msw/test-utils';

describe('Groups API Hooks', () => {
  describe('useGroups', () => {
    it('should fetch paginated list of groups with id alias', async () => {
      const { result } = renderWithQuery(() => useGroups());

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.items).toHaveLength(2);
      expect(result.current.data?.total).toBe(2);
      expect(result.current.data?.limit).toBe(20);
      expect(result.current.data?.offset).toBe(0);

      // Verify id alias is added from groupId
      const firstGroup = result.current.data?.items[0];
      expect(firstGroup?.id).toBe('grp-production');
      expect(firstGroup?.groupId).toBe('grp-production');
    });

    it('should accept pagination parameters', async () => {
      const { result } = renderWithQuery(() =>
        useGroups({ limit: 1, offset: 0 })
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.items).toHaveLength(1);
      expect(result.current.data?.limit).toBe(1);
    });
  });

  describe('useGroup', () => {
    it('should fetch single group detail with id alias', async () => {
      const { result } = renderWithQuery(() => useGroup('grp-production'));

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.groupId).toBe('grp-production');
      expect(result.current.data?.id).toBe('grp-production');
      expect(result.current.data?.name).toBe('Production Servers');
      expect(result.current.data?.types).toContain('node');
    });

    it('should be disabled when groupId is empty', async () => {
      const { result } = renderWithQuery(() => useGroup(''));

      expect(result.current.isFetching).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
    });

    it('should handle 404 for non-existent group', async () => {
      const { result } = renderWithQuery(() => useGroup('grp-non-existent'));

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });
});
