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
export function useProfileDiff(nodeId: string, fromId?: string, toId?: string) {
  return useQuery({
    queryKey: queryKeys.profiles.diff(nodeId, fromId, toId),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ProfileDiff>>(
        `/nodes/${nodeId}/profiles/diff`,
        {
          params: {
            fromId,
            toId,
          },
        }
      );
      return response.data.data;
    },
    enabled: !!nodeId && (!!fromId || !!toId),
  });
}
