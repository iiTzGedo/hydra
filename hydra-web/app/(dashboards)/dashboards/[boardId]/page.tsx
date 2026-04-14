import type { Metadata } from 'next';
import { serverFetch } from '@/lib/server-api-client';
import type { DashboardBoard } from '@/types/dashboard';
import { BoardDetailClient } from './board-detail-client';

interface PageProps {
  params: Promise<{ boardId: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { boardId } = await params;

  try {
    const board = await serverFetch<DashboardBoard>(`/dashboards/${boardId}`);
    return {
      title: board.name,
      description: board.description || `Dashboard board: ${board.name}`,
    };
  } catch {
    return {
      title: 'Dashboard',
    };
  }
}

export default async function BoardDetailPage({ params }: PageProps) {
  const { boardId } = await params;
  let board: DashboardBoard | null = null;

  try {
    board = await serverFetch<DashboardBoard>(`/dashboards/${boardId}`);
  } catch {
    // Client will retry via TanStack Query
  }

  return <BoardDetailClient boardId={boardId} initialBoard={board} />;
}
