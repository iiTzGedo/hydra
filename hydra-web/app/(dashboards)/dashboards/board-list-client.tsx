'use client';

import { QueryClient, HydrationBoundary, dehydrate } from '@tanstack/react-query';
import type { DashboardBoardSummary } from '@/types/dashboard';
import { queryKeys } from '@/lib/query-client';
import DashboardPage from '@/views/dashboard';

interface Props {
  initialBoards: DashboardBoardSummary[];
  total: number;
}

/**
 * Client wrapper that hydrates TanStack Query cache with server-fetched board data.
 * The DashboardPage component's useDashboards() hook will find the data already cached,
 * eliminating the initial client-side fetch and providing instant content on page load.
 */
export function DashboardBoardListClient({ initialBoards, total }: Props) {
  const queryClient = new QueryClient();

  if (initialBoards.length > 0) {
    const params = { limit: 50, sortBy: 'updatedAt', sortOrder: 'desc' };
    queryClient.setQueryData(
      queryKeys.dashboards.list(params),
      { items: initialBoards, total }
    );
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DashboardPage />
    </HydrationBoundary>
  );
}
