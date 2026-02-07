import { describe, it, expect } from 'vitest';
import { waitFor } from '@testing-library/react';
import { useServices, useService } from '@/api/services';
import { renderWithQuery } from '../msw/test-utils';

describe('Services API Hooks', () => {
  describe('useServices', () => {
    it('should fetch paginated list of services with id alias', async () => {
      const { result } = renderWithQuery(() => useServices());

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.items).toHaveLength(2);
      expect(result.current.data?.total).toBe(2);
      expect(result.current.data?.limit).toBe(20);
      expect(result.current.data?.offset).toBe(0);

      // Verify id alias is added from serviceId
      const firstService = result.current.data?.items[0];
      expect(firstService?.id).toBe('svc-nginx-a1b2');
      expect(firstService?.serviceId).toBe('svc-nginx-a1b2');
    });

    it('should accept pagination parameters', async () => {
      const { result } = renderWithQuery(() =>
        useServices({ limit: 1, offset: 0 })
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.items).toHaveLength(1);
      expect(result.current.data?.limit).toBe(1);
    });
  });

  describe('useService', () => {
    it('should fetch single service detail with id alias', async () => {
      const { result } = renderWithQuery(() => useService('svc-nginx-a1b2'));

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.serviceId).toBe('svc-nginx-a1b2');
      expect(result.current.data?.id).toBe('svc-nginx-a1b2');
      expect(result.current.data?.name).toBe('nginx');
      expect(result.current.data?.displayName).toBe('NGINX Web Server');
      expect(result.current.data?.runtime).toBe('systemd');
    });

    it('should be disabled when serviceId is empty', async () => {
      const { result } = renderWithQuery(() => useService(''));

      expect(result.current.isFetching).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
    });

    it('should handle 404 for non-existent service', async () => {
      const { result } = renderWithQuery(() => useService('svc-non-existent'));

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });
});
