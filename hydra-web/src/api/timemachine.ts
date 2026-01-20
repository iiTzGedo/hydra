import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-client';
import type { ApiResponse } from '@/types/api';
import type { TopologyMode } from '@/types/topology';
import type {
  NodeTimeMachineResponse,
  HistoricalTopology,
  TimelineResponse,
  TimelineParams,
} from '@/types/timemachine';

export function useNodeStateAtTime(nodeId: string, timestamp: string, sections?: string[]) {
  return useQuery({
    queryKey: queryKeys.timemachine.nodeState(nodeId, timestamp),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<NodeTimeMachineResponse>>(
        `/timemachine/node/${nodeId}`,
        {
          params: { timestamp, sections },
        }
      );
      return response.data.data;
    },
    enabled: !!nodeId && !!timestamp,
  });
}

export function useTopologyAtTime(timestamp: string, mode?: TopologyMode) {
  return useQuery({
    queryKey: queryKeys.timemachine.topology(timestamp, mode),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<HistoricalTopology>>(
        '/timemachine/topology',
        {
          params: { timestamp, mode },
        }
      );
      return response.data.data;
    },
    enabled: !!timestamp,
  });
}

export function useTimeline(params?: TimelineParams) {
  return useQuery({
    queryKey: queryKeys.timemachine.timeline(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<TimelineResponse>>(
        '/timemachine/timeline',
        {
          params: {
            since: params?.since,
            until: params?.until,
            nodeId: params?.nodeId,
            eventTypes: params?.eventTypes,
            limit: params?.limit,
            offset: params?.offset,
          },
        }
      );
      return response.data.data;
    },
  });
}

export { useTopologyAtTime as useTopologyStateAt };
