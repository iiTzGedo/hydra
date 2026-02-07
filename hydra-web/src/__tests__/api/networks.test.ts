import { describe, it, expect } from 'vitest';
import { waitFor } from '@testing-library/react';
import { useNetworks, useNetwork } from '@/api/networks';
import { renderWithQuery } from '../msw/test-utils';

describe('Networks API Hooks', () => {
  describe('useNetworks', () => {
    it('should fetch paginated list of networks with id alias', async () => {
      const { result } = renderWithQuery(() => useNetworks());

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.items).toHaveLength(2);
      expect(result.current.data?.total).toBe(2);
      expect(result.current.data?.limit).toBe(20);
      expect(result.current.data?.offset).toBe(0);

      // Verify id alias is added from networkId
      const firstNetwork = result.current.data?.items[0];
      expect(firstNetwork?.id).toBe('net-lan-192-168-0');
      expect(firstNetwork?.networkId).toBe('net-lan-192-168-0');
    });

    it('should accept pagination parameters', async () => {
      const { result } = renderWithQuery(() =>
        useNetworks({ limit: 1, offset: 0 })
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.items).toHaveLength(1);
      expect(result.current.data?.limit).toBe(1);
    });
  });

  describe('useNetwork', () => {
    it('should fetch single network detail with id alias', async () => {
      const { result } = renderWithQuery(() => useNetwork('net-lan-192-168-0'));

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.networkId).toBe('net-lan-192-168-0');
      expect(result.current.data?.id).toBe('net-lan-192-168-0');
      expect(result.current.data?.name).toBe('LAN Network');
      expect(result.current.data?.cidr).toBe('192.168.1.0/24');
      expect(result.current.data?.type).toBe('lan');
    });

    it('should be disabled when networkId is empty', async () => {
      const { result } = renderWithQuery(() => useNetwork(''));

      expect(result.current.isFetching).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
    });

    it('should handle 404 for non-existent network', async () => {
      const { result } = renderWithQuery(() => useNetwork('net-non-existent'));

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });
});
