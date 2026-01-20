import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export type StatusType =
  | 'active'
  | 'inactive'
  | 'pending'
  | 'running'
  | 'stopped'
  | 'failed'
  | 'online'
  | 'offline'
  | 'unknown'
  | string;

export interface StatusBadgeProps {
  status: StatusType;
  showDot?: boolean;
  size?: 'sm' | 'default';
  className?: string;
}

const statusConfig: Record<
  string,
  { variant: 'success' | 'destructive' | 'warning' | 'secondary' | 'outline'; label: string; dotColor: string }
> = {
  active: { variant: 'success', label: 'Active', dotColor: 'bg-success' },
  online: { variant: 'success', label: 'Online', dotColor: 'bg-success' },
  running: { variant: 'success', label: 'Running', dotColor: 'bg-success' },
  inactive: { variant: 'destructive', label: 'Inactive', dotColor: 'bg-destructive' },
  offline: { variant: 'destructive', label: 'Offline', dotColor: 'bg-destructive' },
  stopped: { variant: 'secondary', label: 'Stopped', dotColor: 'bg-muted-foreground' },
  failed: { variant: 'destructive', label: 'Failed', dotColor: 'bg-destructive' },
  pending: { variant: 'warning', label: 'Pending', dotColor: 'bg-warning' },
  archived: { variant: 'secondary', label: 'Archived', dotColor: 'bg-muted-foreground' },
  unknown: { variant: 'outline', label: 'Unknown', dotColor: 'bg-muted-foreground' },
};

export function StatusBadge({
  status,
  showDot = false,
  size = 'default',
  className,
}: StatusBadgeProps) {
  const config = statusConfig[status.toLowerCase()] || {
    variant: 'outline' as const,
    label: status.charAt(0).toUpperCase() + status.slice(1),
    dotColor: 'bg-muted-foreground',
  };

  return (
    <Badge
      variant={config.variant}
      className={cn(
        'gap-1.5',
        size === 'sm' && 'px-1.5 py-0.5 text-[10px]',
        className
      )}
    >
      {showDot && (
        <span
          className={cn('h-1.5 w-1.5 rounded-full', config.dotColor)}
          aria-hidden="true"
        />
      )}
      {config.label}
    </Badge>
  );
}
