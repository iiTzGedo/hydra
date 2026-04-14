'use client';

import { QueryClient, HydrationBoundary, dehydrate } from '@tanstack/react-query';
import type { DashboardBoard } from '@/types/dashboard';
import { queryKeys } from '@/lib/query-client';
import KioskPage from '@/views/kiosk';

interface Props {
  boardId: string;
  initialBoard: DashboardBoard | null;
}

export function KioskClient({ boardId, initialBoard }: Props) {
  const queryClient = new QueryClient();

  if (initialBoard) {
    queryClient.setQueryData(
      queryKeys.dashboards.detail(boardId),
      initialBoard,
    );
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <KioskPage />
    </HydrationBoundary>
  );
}
