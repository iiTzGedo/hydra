import { Badge } from '@/components/ui/badge';
import { statusToken } from '@/lib/design-tokens';
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

type KnownStatus =
  | 'active'
  | 'running'
  | 'online'
  | 'inactive'
  | 'stopped'
  | 'exited'
  | 'unknown'
  | 'pending'
  | 'paused'
  | 'restarting'
  | 'failed'
  | 'archived'
  | 'offline';

const KNOWN_STATUSES: ReadonlySet<KnownStatus> = new Set<KnownStatus>([
  'active',
  'running',
  'online',
  'inactive',
  'stopped',
  'exited',
  'unknown',
  'pending',
  'paused',
  'restarting',
  'failed',
  'archived',
  'offline',
]);

const STATUS_LABELS: Record<KnownStatus, string> = {
  active: 'Active',
  running: 'Running',
  online: 'Online',
  inactive: 'Inactive',
  stopped: 'Stopped',
  exited: 'Exited',
  unknown: 'Unknown',
  pending: 'Pending',
  paused: 'Paused',
  restarting: 'Restarting',
  failed: 'Failed',
  archived: 'Archived',
  offline: 'Offline',
};

export function StatusBadge({
  status,
  showDot = false,
  size = 'default',
  className,
}: StatusBadgeProps) {
  const lower = status.toLowerCase();
  const known = KNOWN_STATUSES.has(lower as KnownStatus)
    ? (lower as KnownStatus)
    : null;

  const label = known
    ? STATUS_LABELS[known]
    : status.charAt(0).toUpperCase() + status.slice(1);

  const surfaceClass = known
    ? statusToken({ status: known, surface: 'soft' })
    : 'bg-muted text-muted-foreground';
  const dotClass = known ? statusToken({ status: known, surface: 'dot' }) : 'bg-muted-foreground';

  return (
    <Badge
      variant="outline"
      className={cn(
        'gap-1.5 border-transparent',
        surfaceClass,
        size === 'sm' && 'px-1.5 py-0.5 text-[10px]',
        className
      )}
    >
      {showDot && (
        <span
          className={cn('h-1.5 w-1.5 rounded-full', dotClass)}
          aria-hidden="true"
        />
      )}
      {label}
    </Badge>
  );
}
