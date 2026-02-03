import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle, XCircle, AlertCircle, HelpCircle } from 'lucide-react';
import { useServices } from '@/api/services';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface StatusItemProps {
  label: string;
  count: number;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
}

function StatusItem({ label, count, icon, color, bgColor }: StatusItemProps) {
  return (
    <div className="flex items-center justify-between rounded-lg px-2.5 py-1.5 hover:bg-muted/60 transition-colors">
      <div className="flex items-center gap-2">
        <div className={cn('rounded-md p-1.5', bgColor)}>
          {icon}
        </div>
        <span className="text-sm font-medium text-foreground">{label}</span>
      </div>
      <span className={cn('text-lg font-bold', color)}>{count}</span>
    </div>
  );
}

export function ServiceSummary() {
  const { data: servicesData, isLoading } = useServices({ limit: 100 });

  const statusCounts = servicesData?.items?.reduce(
    (acc, service) => {
      const status = (service.status || 'unknown') as string;
      if (status === 'running') {
        acc.running++;
      } else if (status === 'stopped') {
        acc.stopped++;
      } else if (status === 'failed') {
        acc.error++;
      } else {
        acc.unknown++;
      }
      return acc;
    },
    { running: 0, stopped: 0, error: 0, unknown: 0 }
  ) ?? { running: 0, stopped: 0, error: 0, unknown: 0 };

  const statuses = [
    {
      label: 'Running',
      count: statusCounts.running,
      icon: <CheckCircle className="h-4 w-4 text-success" />,
      color: 'text-success',
      bgColor: 'bg-success/10',
    },
    {
      label: 'Stopped',
      count: statusCounts.stopped,
      icon: <XCircle className="h-4 w-4 text-muted-foreground" />,
      color: 'text-muted-foreground',
      bgColor: 'bg-muted',
    },
    {
      label: 'Error',
      count: statusCounts.error,
      icon: <AlertCircle className="h-4 w-4 text-destructive" />,
      color: 'text-destructive',
      bgColor: 'bg-destructive/10',
    },
    {
      label: 'Unknown',
      count: statusCounts.unknown,
      icon: <HelpCircle className="h-4 w-4 text-warning" />,
      color: 'text-warning',
      bgColor: 'bg-warning/10',
    },
  ];

  return (
    <Card className="bg-card border-border">
      <CardHeader className="flex flex-row items-center justify-between pb-1 pt-4 px-4">
        <CardTitle className="text-base text-foreground">Service Status</CardTitle>
        <Link to={ROUTES.SERVICES}>
          <Button variant="ghost" size="sm" className="text-muted-foreground h-7 px-2 text-xs">
            View all
            <ArrowRight className="ml-1 h-3 w-3" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-1">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : (
          <div className="space-y-1">
            {statuses.map((status) => (
              <StatusItem key={status.label} {...status} />
            ))}
          </div>
        )}

        <div className="mt-3 border-t border-border pt-3">
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">By Runtime</h4>
          <div className="flex flex-wrap gap-1.5">
            {['docker', 'systemd', 'kubernetes', 'podman'].map((runtime) => {
              const count = servicesData?.items?.filter((s) => s.runtime === runtime).length ?? 0;
              if (count === 0) return null;
              return (
                <motion.div
                  key={runtime}
                  whileHover={{ scale: 1.05 }}
                  className="rounded-full bg-muted px-2.5 py-0.5 text-xs"
                >
                  <span className="font-medium text-foreground">{runtime}</span>
                  <span className="ml-1 text-muted-foreground">({count})</span>
                </motion.div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
