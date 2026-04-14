'use client';

import { QueryClient, HydrationBoundary, dehydrate } from '@tanstack/react-query';
import type { DashboardBoard } from '@/types/dashboard';
import { queryKeys } from '@/lib/query-client';
import DashboardPage from '@/views/dashboard';

interface Props {
  boardId: string;
  initialBoard: DashboardBoard | null;
}

/**
 * Client wrapper that hydrates TanStack Query cache with server-fetched board data.
 * The DashboardPage component's useDashboard(boardId) hook will find the data already
 * cached, providing instant board rendering with widget grid on first paint.
 */
export function BoardDetailClient({ boardId, initialBoard }: Props) {
  const queryClient = new QueryClient();

  if (initialBoard) {
    queryClient.setQueryData(
      queryKeys.dashboards.detail(boardId),
      initialBoard
    );
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DashboardPage />
    </HydrationBoundary>
  );
}
