import { useState, useEffect } from 'react';
import { AlertTriangle, ShieldAlert, Info } from 'lucide-react';
import type { DangerLevel } from '@/api/commands';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

interface ControlConfirmationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dangerLevel: DangerLevel;
  resourceName: string;
  actionLabel: string;
  confirmationMessage?: string | null;
  onConfirm: () => void;
  isPending?: boolean;
}

const DANGER_CONFIG: Record<
  DangerLevel,
  {
    icon: typeof AlertTriangle | typeof ShieldAlert | typeof Info;
    iconColor: string;
    borderColor: string;
    bgColor: string;
    confirmText?: string;
    requiresResourceName?: boolean;
  }
> = {
  safe: {
    icon: Info,
    iconColor: 'text-muted-foreground',
    borderColor: 'border-border',
    bgColor: 'bg-muted/30',
  },
  low: {
    icon: Info,
    iconColor: 'text-info',
    borderColor: 'border-info/30',
    bgColor: 'bg-info/5',
  },
  medium: {
    icon: AlertTriangle,
    iconColor: 'text-warning',
    borderColor: 'border-warning/30',
    bgColor: 'bg-warning/5',
  },
  high: {
    icon: AlertTriangle,
    iconColor: 'text-warning',
    borderColor: 'border-warning/30',
    bgColor: 'bg-warning/5',
    confirmText: 'CONFIRM',
  },
  critical: {
    icon: ShieldAlert,
    iconColor: 'text-destructive',
    borderColor: 'border-destructive/30',
    bgColor: 'bg-destructive/5',
    requiresResourceName: true,
  },
};

export function ControlConfirmationDialog({
  open,
  onOpenChange,
  dangerLevel,
  resourceName,
  actionLabel,
  confirmationMessage,
  onConfirm,
  isPending = false,
}: ControlConfirmationDialogProps) {
  const [inputValue, setInputValue] = useState('');
  const config = DANGER_CONFIG[dangerLevel];
  const Icon = config.icon;

  useEffect(() => {
    if (open) {
      setInputValue('');
    }
  }, [open]);

  const requiresInput = dangerLevel === 'high' || dangerLevel === 'critical';
  const isCritical = dangerLevel === 'critical';

  const isConfirmEnabled = (() => {
    if (isPending) return false;
    if (dangerLevel === 'high') {
      return inputValue.trim().toUpperCase() === 'CONFIRM';
    }
    if (dangerLevel === 'critical') {
      return inputValue.trim() === resourceName;
    }
    return true;
  })();

  const handleConfirm = () => {
    if (isConfirmEnabled) {
      onConfirm();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className={cn(isCritical && 'text-destructive')}>
            {actionLabel}
          </DialogTitle>
          <DialogDescription>
            {isCritical
              ? 'This is a critical action that cannot be undone.'
              : 'Please confirm you want to proceed with this action.'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div
            className={cn(
              'flex items-start gap-3 rounded-md border p-3',
              config.borderColor,
              config.bgColor
            )}
          >
            <Icon className={cn('h-5 w-5 mt-0.5 shrink-0', config.iconColor)} />
            <div className="space-y-1 text-sm">
              <p className="font-medium">
                {actionLabel} on <span className="font-mono">{resourceName}</span>
              </p>
              {confirmationMessage && (
                <p className="text-muted-foreground">{confirmationMessage}</p>
              )}
            </div>
          </div>

          {requiresInput && (
            <div className="space-y-2">
              <Label htmlFor="confirmation-input">
                {isCritical ? (
                  <>
                    Type <span className="font-mono font-bold">{resourceName}</span> to
                    confirm
                  </>
                ) : (
                  <>
                    Type <span className="font-mono font-bold">CONFIRM</span> to proceed
                  </>
                )}
              </Label>
              <Input
                id="confirmation-input"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={isCritical ? resourceName : 'CONFIRM'}
                autoComplete="off"
                autoFocus
                className={cn(
                  isCritical &&
                    'border-destructive/50 focus-visible:ring-destructive/30'
                )}
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant={isCritical ? 'destructive' : 'default'}
            onClick={handleConfirm}
            disabled={!isConfirmEnabled}
          >
            {isPending ? 'Confirming...' : 'Confirm'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
