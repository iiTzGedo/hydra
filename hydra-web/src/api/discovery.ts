import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  ApproveDiscoveryRequest,
  DiscoveredDevice,
  DiscoveryApprovalResponse,
  DiscoveryDeviceListParams,
  DiscoveryScan,
  DiscoveryScanListParams,
  DiscoveryScanSummary,
  DismissDiscoveryRequest,
  RejectDiscoveryRequest,
  StartDiscoveryScanRequest,
} from '@/types/discovery';

export function useDiscoveryScans(params?: DiscoveryScanListParams) {
  return useQuery({
    queryKey: queryKeys.discovery.scans(params),
    queryFn: async (): Promise<PaginatedResponse<DiscoveryScanSummary>> => {
      const response = await apiClient.get<ApiResponse<DiscoveryScanSummary[]>>(
        '/discovery/scans',
        {
          params: {
            status: params?.status,
            limit: params?.limit,
            offset: params?.offset,
            sortBy: params?.sortBy,
            sortOrder: params?.sortOrder,
          },
        }
      );
      const items = response.data.data;
      return {
        items,
        total: response.data.meta?.total ?? items.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
    refetchInterval: (query) => {
      const scans = query.state.data?.items ?? [];
      if (scans.some((scan) => scan.status === 'pending' || scan.status === 'running')) {
        return 3000;
      }
      return false;
    },
  });
}

export function useDiscoveryScan(scanId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.discovery.scan(scanId ?? ''),
    queryFn: async (): Promise<DiscoveryScan> => {
      const response = await apiClient.get<ApiResponse<DiscoveryScan>>(
        `/discovery/scans/${scanId}`
      );
      return response.data.data;
    },
    enabled: Boolean(scanId),
    refetchInterval: (query) => {
      const scan = query.state.data;
      if (scan && (scan.status === 'pending' || scan.status === 'running')) {
        return 3000;
      }
      return false;
    },
  });
}

export function useStartDiscoveryScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: StartDiscoveryScanRequest): Promise<DiscoveryScan> => {
      const response = await apiClient.post<ApiResponse<DiscoveryScan>>(
        '/discovery/scans',
        request
      );
      return response.data.data;
    },
    onSuccess: (scan) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.discovery.scans() });
      queryClient.setQueryData(queryKeys.discovery.scan(scan.scanId), scan);
    },
  });
}

export function useDiscoveryDevices(params?: DiscoveryDeviceListParams) {
  return useQuery({
    queryKey: queryKeys.discovery.devices(params),
    queryFn: async (): Promise<PaginatedResponse<DiscoveredDevice>> => {
      const response = await apiClient.get<ApiResponse<DiscoveredDevice[]>>(
        '/discovery/devices',
        {
          params: {
            status: params?.status,
            networkId: params?.networkId,
            search: params?.search,
            limit: params?.limit,
            offset: params?.offset,
            sortBy: params?.sortBy,
            sortOrder: params?.sortOrder,
          },
        }
      );
      const items = response.data.data;
      return {
        items,
        total: response.data.meta?.total ?? items.length,
        limit: response.data.meta?.limit ?? params?.limit ?? 50,
        offset: response.data.meta?.offset ?? params?.offset ?? 0,
      };
    },
  });
}

export function useDiscoveryDevice(discoveryId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.discovery.device(discoveryId ?? ''),
    queryFn: async (): Promise<DiscoveredDevice> => {
      const response = await apiClient.get<ApiResponse<DiscoveredDevice>>(
        `/discovery/devices/${discoveryId}`
      );
      return response.data.data;
    },
    enabled: Boolean(discoveryId),
  });
}

function invalidateDiscovery(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: queryKeys.discovery.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.nodes.list() });
}

export function useApproveDiscovery(discoveryId: string | null | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      request: ApproveDiscoveryRequest
    ): Promise<DiscoveryApprovalResponse> => {
      const response = await apiClient.post<ApiResponse<DiscoveryApprovalResponse>>(
        `/discovery/devices/${discoveryId}/approve`,
        request
      );
      return response.data.data;
    },
    onSuccess: () => {
      invalidateDiscovery(queryClient);
    },
  });
}

export function useRejectDiscovery(discoveryId: string | null | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      request: RejectDiscoveryRequest
    ): Promise<DiscoveryApprovalResponse> => {
      const response = await apiClient.post<ApiResponse<DiscoveryApprovalResponse>>(
        `/discovery/devices/${discoveryId}/reject`,
        request
      );
      return response.data.data;
    },
    onSuccess: () => {
      invalidateDiscovery(queryClient);
    },
  });
}

export function useDismissDiscovery(discoveryId: string | null | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: DismissDiscoveryRequest): Promise<DiscoveredDevice> => {
      const response = await apiClient.post<ApiResponse<DiscoveredDevice>>(
        `/discovery/devices/${discoveryId}/dismiss`,
        request
      );
      return response.data.data;
    },
    onSuccess: () => {
      invalidateDiscovery(queryClient);
    },
  });
}
