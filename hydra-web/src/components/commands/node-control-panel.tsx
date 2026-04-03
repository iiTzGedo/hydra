import { useState, useCallback } from 'react';
import { RotateCcw, Power, Download, Edit } from 'lucide-react';
import { toast } from 'sonner';
import {
  useCreateCommand,
  useConfirmCommand,
  useCommandCatalog,
} from '@/api/commands';
import type {
  CommandQueuedResponse,
  CommandDefinitionSummary,
  DangerLevel,
} from '@/api/commands';
import { getErrorMessage } from '@/lib/api-client';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PermissionGate } from '@/components/auth/permission-gate';
import { ControlConfirmationDialog } from '@/components/commands/control-confirmation-dialog';

interface NodeControlPanelProps {
  nodeId: string;
  nodeName: string;
}

interface PendingConfirmation {
  commandId: string;
  registryId: string;
  actionLabel: string;
  dangerLevel: DangerLevel;
  confirmationMessage?: string | null;
}

const HOSTNAME_PATTERN =
  /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

function validateHostname(hostname: string): string | null {
  if (!hostname) {
    return 'Hostname is required.';
  }
  if (hostname.length > 253) {
    return 'Hostname must be 253 characters or fewer.';
  }
  if (!HOSTNAME_PATTERN.test(hostname)) {
    return 'Enter a valid hostname.';
  }
  return null;
}

const NODE_ACTIONS = [
  {
    registryId: 'reg::node::reboot',
    label: 'Reboot',
    icon: RotateCcw,
    permission: 'nodes:control:reboot',
    variant: 'outline' as const,
  },
  {
    registryId: 'reg::node::shutdown',
    label: 'Shutdown',
    icon: Power,
    permission: 'nodes:control:shutdown',
    variant: 'destructive' as const,
  },
  {
    registryId: 'reg::node::update-system',
    label: 'System Update',
    icon: Download,
    permission: 'nodes:control:update-system',
    variant: 'outline' as const,
  },
  {
    registryId: 'reg::node::set-hostname',
    label: 'Set Hostname',
    icon: Edit,
    permission: 'nodes:control:set-hostname',
    variant: 'outline' as const,
  },
];

export function NodeControlPanel({ nodeId, nodeName }: NodeControlPanelProps) {
  const createCommand = useCreateCommand();
  const confirmCommand = useConfirmCommand();
  const { data: catalog } = useCommandCatalog({ category: 'node' });

  const [pendingConfirmation, setPendingConfirmation] =
    useState<PendingConfirmation | null>(null);
  const [executingAction, setExecutingAction] = useState<string | null>(null);
  const [hostnameDialogOpen, setHostnameDialogOpen] = useState(false);
  const [hostname, setHostname] = useState('');
  const [hostnameError, setHostnameError] = useState<string | null>(null);

  const getCatalogEntry = useCallback(
    (registryId: string): CommandDefinitionSummary | undefined => {
      return catalog?.find((def) => def.registryId === registryId);
    },
    [catalog]
  );

  const submitAction = useCallback(
    async (
      registryId: string,
      label: string,
      parameters?: Record<string, unknown>
    ) => {
      setExecutingAction(registryId);
      try {
        const result: CommandQueuedResponse = await createCommand.mutateAsync({
          registryId,
          target: { nodeId },
          parameters,
        });

        if (result.requiresConfirmation) {
          const catalogEntry = getCatalogEntry(registryId);
          setPendingConfirmation({
            commandId: result.commandId,
            registryId,
            actionLabel: label,
            dangerLevel:
              result.dangerLevel ?? catalogEntry?.dangerLevel ?? 'medium',
            confirmationMessage:
              result.confirmationMessage ?? catalogEntry?.description,
          });
        } else {
          toast.success(`${label} command queued`, {
            description: `Command ${result.commandId} is ${result.status}`,
          });
        }
        return true;
      } catch (err: unknown) {
        toast.error(getErrorMessage(err, `Failed to execute ${label}`));
        return false;
      } finally {
        setExecutingAction(null);
      }
    },
    [nodeId, createCommand, getCatalogEntry]
  );

  const handleAction = useCallback(
    async (registryId: string, label: string) => {
      if (registryId === 'reg::node::set-hostname') {
        setHostname('');
        setHostnameError(null);
        setHostnameDialogOpen(true);
        return;
      }

      await submitAction(registryId, label);
    },
    [submitAction]
  );

  const handleHostnameSubmit = useCallback(async () => {
    const trimmedHostname = hostname.trim();
    const error = validateHostname(trimmedHostname);
    if (error) {
      setHostnameError(error);
      return;
    }

    setHostnameError(null);
    const wasSubmitted = await submitAction('reg::node::set-hostname', 'Set Hostname', {
      hostname: trimmedHostname,
    });
    if (wasSubmitted) {
      setHostnameDialogOpen(false);
      setHostname('');
    }
  }, [hostname, submitAction]);

  const handleConfirm = useCallback(async () => {
    if (!pendingConfirmation) return;
    try {
      const result = await confirmCommand.mutateAsync(
        pendingConfirmation.commandId
      );
      toast.success(`${pendingConfirmation.actionLabel} confirmed`, {
        description: `Command ${result.commandId} is ${result.status}`,
      });
      setPendingConfirmation(null);
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(
          err,
          `Failed to confirm ${pendingConfirmation.actionLabel}`
        )
      );
    }
  }, [pendingConfirmation, confirmCommand]);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Node Controls</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {NODE_ACTIONS.map((action) => (
              <PermissionGate
                key={action.registryId}
                permissions={[action.permission]}
              >
                <Button
                  variant={action.variant}
                  size="sm"
                  onClick={() => handleAction(action.registryId, action.label)}
                  disabled={executingAction === action.registryId}
                >
                  <action.icon className="mr-1.5 h-4 w-4" />
                  {executingAction === action.registryId
                    ? 'Sending...'
                    : action.label}
                </Button>
              </PermissionGate>
            ))}
          </div>
        </CardContent>
      </Card>

      {pendingConfirmation && (
        <ControlConfirmationDialog
          open={!!pendingConfirmation}
          onOpenChange={(open) => {
            if (!open) setPendingConfirmation(null);
          }}
          dangerLevel={pendingConfirmation.dangerLevel}
          resourceName={nodeName}
          actionLabel={pendingConfirmation.actionLabel}
          confirmationMessage={pendingConfirmation.confirmationMessage}
          onConfirm={handleConfirm}
          isPending={confirmCommand.isPending}
        />
      )}

      <Dialog
        open={hostnameDialogOpen}
        onOpenChange={(open) => {
          setHostnameDialogOpen(open);
          if (!open) {
            setHostname('');
            setHostnameError(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Set Hostname</DialogTitle>
            <DialogDescription>
              Enter the new hostname for {nodeName}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="node-hostname">Hostname</Label>
            <Input
              id="node-hostname"
              value={hostname}
              onChange={(event) => {
                setHostname(event.target.value);
                setHostnameError(null);
              }}
              placeholder="e.g. proxmox-01"
              autoFocus
            />
            {hostnameError && (
              <p className="text-xs text-destructive">{hostnameError}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setHostnameDialogOpen(false)}
              disabled={executingAction === 'reg::node::set-hostname'}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                void handleHostnameSubmit();
              }}
              disabled={executingAction === 'reg::node::set-hostname'}
            >
              {executingAction === 'reg::node::set-hostname'
                ? 'Sending...'
                : 'Send Command'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
