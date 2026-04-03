import type { CommandStatus } from '@/api/commands';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const COMMAND_STATUS_CONFIG: Record<
  CommandStatus,
  { variant: 'success' | 'destructive' | 'warning' | 'info' | 'secondary'; label: string }
> = {
  completed: { variant: 'success', label: 'Completed' },
  failed: { variant: 'destructive', label: 'Failed' },
  timeout: { variant: 'destructive', label: 'Timeout' },
  executing: { variant: 'warning', label: 'Executing' },
  queued: { variant: 'info', label: 'Queued' },
  pending: { variant: 'secondary', label: 'Pending' },
  pending_confirmation: { variant: 'warning', label: 'Awaiting Confirmation' },
  cancelled: { variant: 'secondary', label: 'Cancelled' },
  rejected: { variant: 'destructive', label: 'Rejected' },
};

interface CommandStatusBadgeProps {
  status: CommandStatus;
  className?: string;
}

export function CommandStatusBadge({ status, className }: CommandStatusBadgeProps) {
  const config = COMMAND_STATUS_CONFIG[status] ?? { variant: 'secondary' as const, label: status };

  return (
    <Badge variant={config.variant} className={cn(className)}>
      {config.label}
    </Badge>
  );
}
