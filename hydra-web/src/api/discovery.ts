import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse, PaginatedResponse } from '@/types/api';
import type {
  ApproveDiscoveryRequest,
  CreateExclusionRequest,
  DiscoveredDevice,
  DiscoveryApprovalResponse,
  DiscoveryDeviceListParams,
  DiscoveryExclusion,
  DiscoveryScan,
  DiscoveryScanListParams,
  DiscoveryScanSummary,
  DismissDiscoveryRequest,
  ExclusionListParams,
  Installation,
  InstallationListParams,
  InstallationSummary,
  RegisterDiscoveryRequest,
  RegisterDiscoveryResponse,
  RejectDiscoveryRequest,
  ScanDiffResult,
  StartDiscoveryScanRequest,
  StartInstallationRequest,
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
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: queryKeys.discovery.devices(params),
    queryFn: async (): Promise<PaginatedResponse<DiscoveredDevice>> => {
      const response = await apiClient.get<ApiResponse<DiscoveredDevice[]>>(
        '/discovery/devices',
        {
          params: {
            status: params?.status,
            networkId: params?.networkId,
            deviceClass: params?.deviceClass,
            agentCompatible: params?.agentCompatible,
            remoteInstallable: params?.remoteInstallable,
            minConfidence: params?.minConfidence,
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
    refetchInterval: () => {
      const scanQueries = queryClient.getQueriesData<PaginatedResponse<DiscoveryScanSummary>>({
        queryKey: queryKeys.discovery.scans(),
      });
      const hasActiveScans = scanQueries.some(([, data]) =>
        (data?.items ?? []).some((scan) => scan.status === 'pending' || scan.status === 'running')
      );
      return hasActiveScans ? 3000 : false;
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

export function useRegisterDiscovery(discoveryId: string | null | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      request: RegisterDiscoveryRequest
    ): Promise<RegisterDiscoveryResponse> => {
      const response = await apiClient.post<ApiResponse<RegisterDiscoveryResponse>>(
        `/discovery/devices/${discoveryId}/register`,
        request
      );
      return response.data.data;
    },
    onSuccess: () => {
      invalidateDiscovery(queryClient);
    },
  });
}

export function useDeleteDiscovery() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (discoveryId: string): Promise<{ deleted: boolean; discoveryId: string }> => {
      const response = await apiClient.delete<
        ApiResponse<{ deleted: boolean; discoveryId: string }>
      >(`/discovery/devices/${discoveryId}`);
      return response.data.data;
    },
    onSuccess: () => {
      invalidateDiscovery(queryClient);
    },
  });
}

export function useDeleteDiscoveryScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      scanId: string;
      cascade?: boolean;
    }): Promise<{ deleted: boolean; scanId: string; cascadeDeleted: number }> => {
      const response = await apiClient.delete<
        ApiResponse<{ deleted: boolean; scanId: string; cascadeDeleted: number }>
      >(`/discovery/scans/${params.scanId}`, {
        params: { cascade: params.cascade ?? false },
      });
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.discovery.all });
    },
  });
}

// ── Exclusion Hooks ────────────────────────────────────────────────

const exclusionKeys = {
  all: ['discovery', 'exclusions'] as const,
  list: (params?: ExclusionListParams) => {
    if (params) return [...exclusionKeys.all, 'list', params] as const;
    return [...exclusionKeys.all, 'list'] as const;
  },
};

export function useDiscoveryExclusions(params?: ExclusionListParams) {
  return useQuery({
    queryKey: exclusionKeys.list(params),
    queryFn: async (): Promise<PaginatedResponse<DiscoveryExclusion>> => {
      const response = await apiClient.get<ApiResponse<DiscoveryExclusion[]>>(
        '/discovery/exclusions',
        {
          params: {
            limit: params?.limit,
            offset: params?.offset,
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

export function useCreateExclusion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CreateExclusionRequest): Promise<DiscoveryExclusion> => {
      const response = await apiClient.post<ApiResponse<DiscoveryExclusion>>(
        '/discovery/exclusions',
        request
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: exclusionKeys.all });
    },
  });
}

export function useDeleteExclusion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (exclusionId: string): Promise<void> => {
      await apiClient.delete(`/discovery/exclusions/${exclusionId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: exclusionKeys.all });
    },
  });
}

// ── Scan Diff Hook ─────────────────────────────────────────────────

export function useScanDiff(
  networkId: string | null | undefined,
  fromScan?: string | null,
  toScan?: string | null,
) {
  return useQuery({
    queryKey: [...queryKeys.discovery.all, 'diff', networkId ?? '', fromScan ?? '', toScan ?? ''] as const,
    queryFn: async (): Promise<ScanDiffResult> => {
      const response = await apiClient.get<ApiResponse<ScanDiffResult>>(
        '/discovery/diff',
        {
          params: {
            networkId,
            fromScan: fromScan || undefined,
            toScan: toScan || undefined,
          },
        }
      );
      return response.data.data;
    },
    enabled: Boolean(networkId),
  });
}

// ── Installation Hooks ──────────────────────────────────────────────

const installationKeys = {
  all: ['installations'] as const,
  list: <T extends object = Record<string, unknown>>(params?: T) => {
    if (params) {
      return [...installationKeys.all, 'list', params] as const;
    }
    return [...installationKeys.all, 'list'] as const;
  },
  detail: (installationId: string) =>
    [...installationKeys.all, 'detail', installationId] as const,
};

const ACTIVE_INSTALLATION_STATUSES = new Set([
  'pending',
  'connecting',
  'transferring',
  'configuring',
  'registering',
  'running',
]);

export function useInstallations(params?: InstallationListParams) {
  return useQuery({
    queryKey: installationKeys.list(params),
    queryFn: async (): Promise<PaginatedResponse<InstallationSummary>> => {
      const response = await apiClient.get<ApiResponse<InstallationSummary[]>>(
        '/installations',
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
      const installs = query.state.data?.items ?? [];
      if (installs.some((inst) => ACTIVE_INSTALLATION_STATUSES.has(inst.status))) {
        return 3000;
      }
      return false;
    },
  });
}

export function useInstallation(installationId: string | null | undefined) {
  return useQuery({
    queryKey: installationKeys.detail(installationId ?? ''),
    queryFn: async (): Promise<Installation> => {
      const response = await apiClient.get<ApiResponse<Installation>>(
        `/installations/${installationId}`
      );
      return response.data.data;
    },
    enabled: Boolean(installationId),
    refetchInterval: (query) => {
      const inst = query.state.data;
      if (inst && ACTIVE_INSTALLATION_STATUSES.has(inst.status)) {
        return 3000;
      }
      return false;
    },
  });
}

export function useStartInstallation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: StartInstallationRequest): Promise<Installation> => {
      const response = await apiClient.post<ApiResponse<Installation>>(
        '/installations',
        request
      );
      return response.data.data;
    },
    onSuccess: (installation) => {
      queryClient.invalidateQueries({ queryKey: installationKeys.all });
      queryClient.setQueryData(
        installationKeys.detail(installation.installationId),
        installation
      );
      invalidateDiscovery(queryClient);
    },
  });
}

export function useCancelInstallation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (installationId: string): Promise<Installation> => {
      const response = await apiClient.post<ApiResponse<Installation>>(
        `/installations/${installationId}/cancel`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: installationKeys.all });
    },
  });
}

export function useRetryInstallation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (installationId: string): Promise<Installation> => {
      const response = await apiClient.post<ApiResponse<Installation>>(
        `/installations/${installationId}/retry`
      );
      return response.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: installationKeys.all });
    },
  });
}
