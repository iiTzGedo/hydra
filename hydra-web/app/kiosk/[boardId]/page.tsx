import type { Metadata } from 'next';
import { serverFetch } from '@/lib/server-api-client';
import type { DashboardBoard } from '@/types/dashboard';
import { KioskClient } from './kiosk-client';

interface PageProps {
  params: Promise<{ boardId: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { boardId } = await params;

  try {
    const board = await serverFetch<DashboardBoard>(`/dashboards/${boardId}`);
    return {
      title: `${board.name} — Kiosk`,
      description: board.description || `Kiosk view: ${board.name}`,
    };
  } catch {
    return {
      title: 'Kiosk',
    };
  }
}

export default async function KioskBoardPage({ params }: PageProps) {
  const { boardId } = await params;
  let board: DashboardBoard | null = null;

  try {
    board = await serverFetch<DashboardBoard>(`/dashboards/${boardId}`);
  } catch {
    // Client will retry via TanStack Query
  }

  return <KioskClient boardId={boardId} initialBoard={board} />;
}
