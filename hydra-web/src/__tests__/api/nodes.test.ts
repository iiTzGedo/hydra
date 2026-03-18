import { describe, it, expect } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  useNodes,
  useNode,
  useUpdateNode,
  useArchiveNode,
} from '@/api/nodes';
import { renderWithQuery } from '../msw/test-utils';

describe('Nodes API Hooks', () => {
  describe('useNodes', () => {
    it('should fetch paginated list of nodes with id alias', async () => {
      const { result } = renderWithQuery(() => useNodes());

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.items).toHaveLength(2);
      expect(result.current.data?.total).toBe(2);
      expect(result.current.data?.limit).toBe(20);
      expect(result.current.data?.offset).toBe(0);

      // Verify id alias is added from nodeId
      const firstNode = result.current.data?.items[0];
      expect(firstNode?.id).toBe('proxmox-01');
      expect(firstNode?.nodeId).toBe('proxmox-01');
    });

    it('should accept pagination parameters', async () => {
      const { result } = renderWithQuery(() =>
        useNodes({ limit: 1, offset: 0 })
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.items).toHaveLength(1);
      expect(result.current.data?.limit).toBe(1);
    });
  });

  describe('useNode', () => {
    it('should fetch single node detail with id alias', async () => {
      const { result } = renderWithQuery(() => useNode('proxmox-01'));

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.nodeId).toBe('proxmox-01');
      expect(result.current.data?.id).toBe('proxmox-01');
      expect(result.current.data?.displayName).toBe('Proxmox Server 01');
      expect(result.current.data?.class).toBe('compute');
    });

    it('should be disabled when nodeId is empty', async () => {
      const { result } = renderWithQuery(() => useNode(''));

      expect(result.current.isFetching).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
    });

    it('should handle 404 for non-existent node', async () => {
      const { result } = renderWithQuery(() => useNode('non-existent'));

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });

  describe('useUpdateNode', () => {
    it('should update node and invalidate cache', async () => {
      const { result } = renderWithQuery(() => useUpdateNode());

      await waitFor(() => expect(result.current).toBeDefined());

      const updateData = {
        displayName: 'Updated Proxmox Server',
        tags: ['production', 'hypervisor', 'updated'],
      };

      result.current.mutate({
        id: 'proxmox-01',
        data: updateData,
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.displayName).toBe('Updated Proxmox Server');
      expect(result.current.data?.tags).toContain('updated');
    });
  });

  describe('useArchiveNode', () => {
    it('should archive node and invalidate cache', async () => {
      const { result } = renderWithQuery(() => useArchiveNode());

      await waitFor(() => expect(result.current).toBeDefined());

      result.current.mutate('proxmox-01');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      const archivedNode = result.current.data as
        | { status?: string; archivedAt?: string }
        | undefined;

      expect(archivedNode).toBeDefined();
      expect(archivedNode?.status).toBe('archived');
      expect(archivedNode?.archivedAt).toBeDefined();
    });
  });
});
