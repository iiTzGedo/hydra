import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button, ButtonProps } from './button';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    variant?: ButtonProps['variant'];
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
  iconClassName?: string;
}

/**
 * EmptyState - A consistent empty state component for when there's no data to display
 * 
 * @example
 * // Basic usage
 * <EmptyState 
 *   icon={Server}
 *   title="No nodes found"
 *   description="Get started by adding your first infrastructure node"
 * />
 * 
 * @example
 * // With actions
 * <EmptyState 
 *   icon={Server}
 *   title="No nodes registered"
 *   description="Install the Hydra agent on your infrastructure to get started"
 *   action={{ label: "Add Node", onClick: () => setShowModal(true) }}
 *   secondaryAction={{ label: "View Documentation", onClick: () => openDocs() }}
 * />
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  secondaryAction,
  className,
  iconClassName,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-12 px-4 text-center animate-in fade-in',
        className
      )}
    >
      {Icon && (
        <div
          className={cn(
            'flex items-center justify-center w-16 h-16 rounded-2xl bg-muted mb-4',
            iconClassName
          )}
        >
          <Icon className="h-8 w-8 text-muted-foreground/60" />
        </div>
      )}
      
      <h3 className="text-lg font-semibold text-foreground mb-1">{title}</h3>
      
      {description && (
        <p className="text-sm text-muted-foreground max-w-xs mb-6">{description}</p>
      )}
      
      {(action || secondaryAction) && (
        <div className="flex items-center gap-3">
          {action && (
            <Button onClick={action.onClick} variant={action.variant || 'default'}>
              {action.label}
            </Button>
          )}
          {secondaryAction && (
            <Button onClick={secondaryAction.onClick} variant="ghost">
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * EmptyStateCompact - A compact inline empty state for use within lists or cards
 */
interface EmptyStateCompactProps {
  icon?: LucideIcon;
  message: string;
  className?: string;
}

export function EmptyStateCompact({
  icon: Icon,
  message,
  className,
}: EmptyStateCompactProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground',
        className
      )}
    >
      {Icon && <Icon className="h-4 w-4" />}
      <span>{message}</span>
    </div>
  );
}
