import { LayoutDashboard, Pin, Save, Star } from 'lucide-react';
import { toast } from 'sonner';
import { useDashboards } from '@/api/dashboards';
import { useUpdateUserSettings, useUserSettings } from '@/api/settings';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function DashboardSettings() {
  const { data: settings } = useUserSettings();
  const { data: dashboards } = useDashboards({ limit: 50, sortBy: 'updatedAt', sortOrder: 'desc' });
  const updateUserSettings = useUpdateUserSettings();

  const pinnedBoardIds = settings?.dashboard?.pinnedBoardIds ?? [];
  const lastOpenedBoardId = settings?.dashboard?.lastOpenedBoardId ?? null;
  const boardItems = dashboards?.items ?? [];

  const handleTogglePin = async (boardId: string) => {
    const nextPins = pinnedBoardIds.includes(boardId)
      ? pinnedBoardIds.filter((id) => id !== boardId)
      : [...pinnedBoardIds, boardId].slice(0, 5);

    try {
      await updateUserSettings.mutateAsync({
        dashboard: {
          pinnedBoardIds: nextPins,
          lastOpenedBoardId,
        },
      });
      toast.success('Dashboard preferences updated');
    } catch {
      toast.error('Failed to update dashboard preferences');
    }
  };

  return (
    <Card className="border-border bg-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <LayoutDashboard className="h-4 w-4 text-primary" />
          Dashboard Preferences
        </CardTitle>
        <CardDescription>
          Manage pinned boards for the sidebar dropdown and review your last-opened board.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Last Opened
          </div>
          <div className="mt-2 text-sm font-medium text-foreground">
            {boardItems.find((board) => board.boardId === lastOpenedBoardId)?.name ?? 'No board opened yet'}
          </div>
        </div>

        <div className="space-y-3">
          {boardItems.map((board) => {
            const pinned = pinnedBoardIds.includes(board.boardId);
            return (
              <div key={board.boardId} className="flex items-center justify-between gap-4 rounded-2xl border border-border/60 p-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{board.name}</span>
                    {board.isHome ? (
                      <Badge variant="info">
                        <Star className="mr-1 h-3 w-3" />
                        Home
                      </Badge>
                    ) : null}
                    {pinned ? (
                      <Badge variant="secondary">
                        <Pin className="mr-1 h-3 w-3" />
                        Pinned
                      </Badge>
                    ) : null}
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {board.widgetCount} widgets
                  </div>
                </div>

                <Button variant="outline" size="sm" onClick={() => void handleTogglePin(board.boardId)} disabled={updateUserSettings.isPending}>
                  <Save className="mr-2 h-4 w-4" />
                  {pinned ? 'Unpin' : 'Pin'}
                </Button>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
