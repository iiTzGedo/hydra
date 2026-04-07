import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import type { Profile, ProfileSummary, ProfileListParams, ProfileDiff } from '@/types/profile';

export function useProfile(profileId: string) {
  return useQuery({
    queryKey: queryKeys.profiles.detail(profileId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Profile>>(`/profiles/${profileId}`);
      const profile = response.data.data;
      return { ...profile, id: profile.profileId };
    },
    enabled: !!profileId,
  });
}

export function useNodeProfiles(nodeId: string, params?: ProfileListParams) {
  return useQuery({
    queryKey: queryKeys.profiles.byNode(nodeId, params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ProfileSummary[]>>(
        `/nodes/${nodeId}/profiles`,
        {
          params: {
            limit: params?.limit,
            offset: params?.offset,
          },
        }
      );
      return {
        items: response.data.data.map(item => ({ ...item, id: item.profileId })),
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
    enabled: !!nodeId,
  });
}

export function useLatestProfile(nodeId: string) {
  return useQuery({
    queryKey: queryKeys.profiles.latest(nodeId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Profile>>(
        `/nodes/${nodeId}/profiles/latest`
      );
      const profile = response.data.data;
      return { ...profile, id: profile.profileId };
    },
    enabled: !!nodeId,
  });
}

// API accepts fromVersion/toVersion (version strings like "E0-0.0.0.1")
// If not provided, it compares the latest two profiles
export function useProfileDiff(nodeId: string, fromVersion?: string, toVersion?: string) {
  return useQuery({
    queryKey: queryKeys.profiles.diff(nodeId, fromVersion, toVersion),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ProfileDiff>>(
        `/nodes/${nodeId}/profiles/diff`,
        {
          params: {
            fromVersion,
            toVersion,
          },
        }
      );
      return response.data.data;
    },
    enabled: !!nodeId && ((!!fromVersion && !!toVersion) || (!fromVersion && !toVersion)),
  });
}
