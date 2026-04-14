import type { Metadata } from 'next';
import { serverFetch } from '@/lib/server-api-client';
import type { DashboardBoardSummary } from '@/types/dashboard';
import { DashboardBoardListClient } from './board-list-client';

export const metadata: Metadata = {
  title: 'Dashboards',
  description: 'View and manage your infrastructure dashboards',
};

interface DashboardListResponse {
  items: DashboardBoardSummary[];
  total: number;
}

export default async function DashboardsPage() {
  let boards: DashboardBoardSummary[] = [];
  let total = 0;

  try {
    const data = await serverFetch<DashboardListResponse>(
      '/dashboards?limit=50&sortBy=updatedAt&sortOrder=desc'
    );
    boards = data.items;
    total = data.total;
  } catch {
    // SSR fetch failed (e.g., auth expired, API unreachable).
    // Client hydration will retry via TanStack Query.
  }

  return <DashboardBoardListClient initialBoards={boards} total={total} />;
}
