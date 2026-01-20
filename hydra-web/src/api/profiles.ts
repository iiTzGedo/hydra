import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import type { Profile, ProfileSummary, ProfileListParams, ProfileDiff } from '@/types/profile';

// Get single profile
export function useProfile(profileId: string) {
  return useQuery({
    queryKey: queryKeys.profiles.detail(profileId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Profile>>(`/profiles/${profileId}`);
      return response.data.data;
    },
    enabled: !!profileId,
  });
}

// Get profiles for a node
export function useNodeProfiles(nodeId: string, params?: ProfileListParams) {
  return useQuery({
    queryKey: queryKeys.profiles.byNode(nodeId, params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ProfileSummary[]>>(
        `/nodes/${nodeId}/profiles`,
        {
          params: {
            since: params?.since,
            until: params?.until,
            limit: params?.limit,
            offset: params?.offset,
            sortBy: params?.sortBy,
            sortOrder: params?.sortOrder,
          },
        }
      );
      // Transform to expected paginated format
      return {
        items: response.data.data,
        total: response.data.meta?.total ?? response.data.data.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
    enabled: !!nodeId,
  });
}

// Get latest profile for a node
export function useLatestProfile(nodeId: string) {
  return useQuery({
    queryKey: queryKeys.profiles.latest(nodeId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Profile>>(
        `/nodes/${nodeId}/profiles/latest`
      );
      return response.data.data;
    },
    enabled: !!nodeId,
  });
}

// Diff profiles
// Note: API accepts fromVersion/toVersion (version strings like "E0-0.0.0.1")
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
    // Enable if we have nodeId AND either both versions or neither (for auto-compare latest two)
    enabled: !!nodeId && ((!!fromVersion && !!toVersion) || (!fromVersion && !toVersion)),
  });
}
