import { describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  useLatestProfile,
  useNodeProfiles,
  useProfile,
  useProfileDiff,
} from '@/api/profiles';
import { renderWithQuery } from '../msw/test-utils';

describe('Profiles API Hooks', () => {
  it('fetches a profile detail', async () => {
    const { result } = renderWithQuery(() => useProfile('profile-002'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.profileId).toBe('profile-002');
    expect(result.current.data?.software?.packageCount).toBe(140);
  });

  it('disables profile detail when profileId is empty', () => {
    const { result } = renderWithQuery(() => useProfile(''));

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('shapes node profile history as a paginated response', async () => {
    const { result } = renderWithQuery(() =>
      useNodeProfiles('proxmox-01', { limit: 1, offset: 0 })
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].profileId).toBe('profile-001');
    expect(result.current.data?.total).toBe(2);
    expect(result.current.data?.limit).toBe(1);
    expect(result.current.data?.offset).toBe(0);
  });

  it('fetches the latest profile for a node', async () => {
    const { result } = renderWithQuery(() => useLatestProfile('proxmox-01'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.profileId).toBe('profile-002');
    expect(result.current.data?.version).toBe('E0-0.0.1.1');
  });

  it('fetches a profile diff when both versions are provided', async () => {
    const { result } = renderWithQuery(() =>
      useProfileDiff('proxmox-01', 'E0-0.0.1.0', 'E0-0.0.1.1')
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.changedSections).toContain('services');
    expect(result.current.data?.diffPercentage).toBe(31.5);
  });

  it('disables profile diff when only one version is provided', () => {
    const { result } = renderWithQuery(() =>
      useProfileDiff('proxmox-01', 'E0-0.0.1.0', undefined)
    );

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
  });
});
