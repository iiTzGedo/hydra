import { Link } from 'react-router-dom';
import { Clock, ArrowRight } from 'lucide-react';
import { formatRelativeTime } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useAuditLog } from '@/api/query';
import type { AuditEntry } from '@/types/query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';

function toActivity(entry: AuditEntry) {
  return {
    id: entry.entryId,
    type: entry.resource.type,
    action: entry.action,
    title: `${entry.action} ${entry.resource.type}`,
    description: `${entry.resource.type}:${entry.resource.id}`,
    timestamp: entry.timestamp,
  };
}

export function RecentActivity() {
  const { data, isLoading } = useAuditLog({ limit: 8, offset: 0 });
  const activity = data?.items?.map(toActivity) ?? [];

  return (
    <Card className="bg-card border-border">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-foreground">Recent Activity</CardTitle>
          <CardDescription className="text-muted-foreground">Latest events and changes</CardDescription>
        </div>
        <Link to={`${ROUTES.SETTINGS}?bottom=audit`}>
          <Button variant="ghost" size="sm" className="text-muted-foreground">
            View all
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(4)].map((_, index) => (
              <div key={index} className="h-12 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : activity.length === 0 ? (
          <div className="flex h-32 items-center justify-center rounded-lg bg-muted/60">
            <p className="text-sm text-muted-foreground">No recent activity available</p>
          </div>
        ) : (
          <ScrollArea className="h-[300px] pr-4">
            <div className="space-y-4">
              {activity.map((item) => (
                <div key={item.id} className="flex gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 space-y-1">
                    <p className="text-sm font-medium text-foreground capitalize">{item.title}</p>
                    <p className="text-xs text-muted-foreground">{item.description}</p>
                    <p className="text-xs text-muted-foreground/70">
                      {formatRelativeTime(item.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
