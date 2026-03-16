import { describe, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  useArchiveUser,
  useElevateRole,
  useGrantTemporaryRole,
  useRevokeTemporaryRole,
  useUsers,
} from '@/api/users';
import { createTestQueryClient, renderWithQuery } from '../msw/test-utils';

describe('Users API Hooks', () => {
  it('maps users into paginated items with lastLoginAt aliases', async () => {
    const { result } = renderWithQuery(() =>
      useUsers({ search: 'search', limit: 10, offset: 0 })
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].username).toBe('search_match');
    expect(result.current.data?.items[0].lastLoginAt).toBe('2026-03-09T07:30:00Z');
  });

  it('invalidates the users list after archive, elevate, grant, and revoke mutations', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const archive = renderWithQuery(() => useArchiveUser(), { queryClient }).result;
    archive.current.mutate('user-003');
    await waitFor(() => expect(archive.current.isSuccess).toBe(true));

    const elevate = renderWithQuery(() => useElevateRole(), { queryClient }).result;
    elevate.current.mutate({ userId: 'user-004', data: { newRole: 'operator' } });
    await waitFor(() => expect(elevate.current.isSuccess).toBe(true));

    const grant = renderWithQuery(() => useGrantTemporaryRole(), { queryClient }).result;
    grant.current.mutate({
      userId: 'user-005',
      data: { role: 'viewer', durationHours: 12 },
    });
    await waitFor(() => expect(grant.current.isSuccess).toBe(true));

    const revoke = renderWithQuery(() => useRevokeTemporaryRole(), { queryClient }).result;
    revoke.current.mutate({ userId: 'user-005', role: 'viewer' });
    await waitFor(() => expect(revoke.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['users', 'list'] });
  });
});
