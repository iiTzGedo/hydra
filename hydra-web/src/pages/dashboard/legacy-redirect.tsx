import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDashboards } from '@/api/dashboards';
import { useUserSettings } from '@/api/settings';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ROUTES } from '@/lib/constants';

export default function LegacyDashboardRedirectPage() {
  const navigate = useNavigate();
  const dashboards = useDashboards({ limit: 50, sortBy: 'updatedAt', sortOrder: 'desc' });
  const settings = useUserSettings();

  useEffect(() => {
    if (dashboards.isLoading || settings.isLoading) {
      return;
    }

    const items = dashboards.data?.items ?? [];
    const pinned = settings.data?.dashboard?.pinnedBoardIds ?? [];
    const homeBoard = items.find((board) => board.isHome)
      ?? items.find((board) => pinned.includes(board.boardId))
      ?? items[0];

    if (homeBoard) {
      navigate(ROUTES.DASHBOARD_BOARD.replace(':boardId', homeBoard.boardId), { replace: true });
      return;
    }

    navigate(ROUTES.DASHBOARDS, { replace: true });
  }, [dashboards.data, dashboards.isLoading, navigate, settings.data, settings.isLoading]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <LoadingSpinner />
        Resolving your dashboard...
      </div>
    </div>
  );
}
