import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  HelpCircle,
  Boxes,
  Play,
  Square,
  AlertTriangle
} from 'lucide-react';
import { useServices } from '@/api/services';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';

interface StatusItemProps {
  label: string;
  count: number;
  total: number;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  progressColor: string;
  index: number;
}

function StatusItem({ label, count, total, icon, color, bgColor, progressColor, index }: StatusItemProps) {
  const percentage = total > 0 ? Math.round((count / total) * 100) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      className="group space-y-2"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={cn('rounded-lg p-1.5', bgColor)}>
            {icon}
          </div>
          <span className="text-sm font-medium text-foreground">{label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn('text-lg font-bold', color)}>{count}</span>
          <span className="text-xs text-muted-foreground">({percentage}%)</span>
        </div>
      </div>
      <div className="relative h-2 rounded-full bg-muted overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
          className={cn('absolute inset-y-0 left-0 rounded-full', progressColor)}
        />
      </div>
    </motion.div>
  );
}

const runtimeColors: Record<string, { color: string; bg: string }> = {
  docker: { color: 'text-blue-500', bg: 'bg-blue-500/10' },
  systemd: { color: 'text-amber-500', bg: 'bg-amber-500/10' },
  kubernetes: { color: 'text-purple-500', bg: 'bg-purple-500/10' },
  podman: { color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
};

export function ServiceSummary() {
  const { data: servicesData, isLoading } = useServices({ limit: 100 });
  const services = servicesData?.items ?? [];
  const totalServices = services.length;

  const statusCounts = services.reduce(
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
  );

  const statuses = [
    {
      label: 'Running',
      count: statusCounts.running,
      icon: <Play className="h-4 w-4 text-success" />,
      color: 'text-success',
      bgColor: 'bg-success/10',
      progressColor: 'bg-success',
    },
    {
      label: 'Stopped',
      count: statusCounts.stopped,
      icon: <Square className="h-4 w-4 text-muted-foreground" />,
      color: 'text-muted-foreground',
      bgColor: 'bg-muted',
      progressColor: 'bg-muted-foreground',
    },
    {
      label: 'Failed',
      count: statusCounts.error,
      icon: <AlertTriangle className="h-4 w-4 text-destructive" />,
      color: 'text-destructive',
      bgColor: 'bg-destructive/10',
      progressColor: 'bg-destructive',
    },
    {
      label: 'Unknown',
      count: statusCounts.unknown,
      icon: <HelpCircle className="h-4 w-4 text-warning" />,
      color: 'text-warning',
      bgColor: 'bg-warning/10',
      progressColor: 'bg-warning',
    },
  ];

  // Calculate runtime distribution
  const runtimeCounts = ['docker', 'systemd', 'kubernetes', 'podman'].map((runtime) => ({
    runtime,
    count: services.filter((s) => s.runtime === runtime).length,
  })).filter(r => r.count > 0);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="space-y-2">
            <div className="flex justify-between">
              <div className="h-4 w-20 bg-muted animate-pulse rounded" />
              <div className="h-4 w-12 bg-muted animate-pulse rounded" />
            </div>
            <div className="h-2 bg-muted animate-pulse rounded-full" />
          </div>
        ))}
      </div>
    );
  }

  if (totalServices === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
        <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-muted mb-3">
          <Boxes className="h-7 w-7 text-muted-foreground/50" />
        </div>
        <h4 className="text-base font-medium text-foreground mb-1">No services found</h4>
        <p className="text-sm text-muted-foreground/70 max-w-[200px]">
          Services will appear here once discovered
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Status breakdown */}
      <div className="space-y-4">
        {statuses.map((status, index) => (
          <StatusItem
            key={status.label}
            {...status}
            total={totalServices}
            index={index}
          />
        ))}
      </div>

      {/* Runtime distribution */}
      {runtimeCounts.length > 0 && (
        <div className="pt-4 border-t border-border">
          <h4 className="text-xs font-medium text-muted-foreground mb-3">By Runtime</h4>
          <div className="flex flex-wrap gap-2">
            {runtimeCounts.map(({ runtime, count }) => {
              const colors = runtimeColors[runtime] || { color: 'text-muted-foreground', bg: 'bg-muted' };
              return (
                <motion.div
                  key={runtime}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.2 }}
                  whileHover={{ scale: 1.05 }}
                >
                  <Link to={`${ROUTES.SERVICES}?runtime=${runtime}`}>
                    <Badge
                      variant="secondary"
                      className={cn(
                        'cursor-pointer transition-colors',
                        colors.bg,
                        colors.color,
                        'border-0 hover:opacity-80'
                      )}
                    >
                      <span className="capitalize">{runtime}</span>
                      <span className="ml-1 opacity-60">({count})</span>
                    </Badge>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
