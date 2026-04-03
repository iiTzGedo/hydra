import { useState, useCallback } from 'react';
import {
  Activity,
  RotateCcw,
  Download,
  Settings,
  RefreshCw,
  Wifi,
} from 'lucide-react';
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

interface AgentControlPanelProps {
  nodeId: string;
}

interface PendingConfirmation {
  commandId: string;
  registryId: string;
  actionLabel: string;
  dangerLevel: DangerLevel;
  confirmationMessage?: string | null;
}

function validateIpv4Cidr(subnet: string): string | null {
  if (!subnet) {
    return 'Subnet is required.';
  }

  const [address, prefix] = subnet.split('/');
  if (!address || prefix === undefined) {
    return 'Enter a subnet in CIDR notation, for example 192.168.1.0/24.';
  }

  const octets = address.split('.');
  if (octets.length !== 4) {
    return 'Enter a valid IPv4 subnet.';
  }

  for (const octet of octets) {
    if (!/^\d+$/.test(octet)) {
      return 'Enter a valid IPv4 subnet.';
    }
    const value = Number(octet);
    if (value < 0 || value > 255) {
      return 'IPv4 octets must be between 0 and 255.';
    }
  }

  if (!/^\d+$/.test(prefix)) {
    return 'CIDR prefix must be numeric.';
  }

  const prefixValue = Number(prefix);
  if (prefixValue < 0 || prefixValue > 32) {
    return 'CIDR prefix must be between 0 and 32.';
  }

  return null;
}

const AGENT_ACTIONS = [
  {
    registryId: 'reg::agent::status',
    label: 'Status',
    icon: Activity,
    permission: 'agent:control:status',
    variant: 'outline' as const,
  },
  {
    registryId: 'reg::agent::restart',
    label: 'Restart',
    icon: RotateCcw,
    permission: 'agent:control:restart',
    variant: 'outline' as const,
  },
  {
    registryId: 'reg::agent::update',
    label: 'Update',
    icon: Download,
    permission: 'agent:control:update',
    variant: 'outline' as const,
  },
  {
    registryId: 'reg::agent::config-reload',
    label: 'Config Reload',
    icon: Settings,
    permission: 'agent:control:config-reload',
    variant: 'outline' as const,
  },
  {
    registryId: 'reg::agent::collect-now',
    label: 'Collect Now',
    icon: RefreshCw,
    permission: 'agent:control:collect-now',
    variant: 'outline' as const,
  },
  {
    registryId: 'reg::agent::probe-network',
    label: 'Probe Network',
    icon: Wifi,
    permission: 'agent:control:probe-network',
    variant: 'outline' as const,
  },
];

export function AgentControlPanel({ nodeId }: AgentControlPanelProps) {
  const createCommand = useCreateCommand();
  const confirmCommand = useConfirmCommand();
  const { data: catalog } = useCommandCatalog({ category: 'agent' });

  const [pendingConfirmation, setPendingConfirmation] =
    useState<PendingConfirmation | null>(null);
  const [executingAction, setExecutingAction] = useState<string | null>(null);
  const [probeDialogOpen, setProbeDialogOpen] = useState(false);
  const [subnet, setSubnet] = useState('');
  const [subnetError, setSubnetError] = useState<string | null>(null);

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
      if (registryId === 'reg::agent::probe-network') {
        setSubnet('');
        setSubnetError(null);
        setProbeDialogOpen(true);
        return;
      }

      await submitAction(registryId, label);
    },
    [submitAction]
  );

  const handleProbeSubmit = useCallback(async () => {
    const trimmedSubnet = subnet.trim();
    const error = validateIpv4Cidr(trimmedSubnet);
    if (error) {
      setSubnetError(error);
      return;
    }

    setSubnetError(null);
    const wasSubmitted = await submitAction(
      'reg::agent::probe-network',
      'Probe Network',
      {
        subnet: trimmedSubnet,
      }
    );
    if (wasSubmitted) {
      setProbeDialogOpen(false);
      setSubnet('');
    }
  }, [subnet, submitAction]);

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
          <CardTitle className="text-base">Agent Controls</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {AGENT_ACTIONS.map((action) => (
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
          resourceName={nodeId}
          actionLabel={pendingConfirmation.actionLabel}
          confirmationMessage={pendingConfirmation.confirmationMessage}
          onConfirm={handleConfirm}
          isPending={confirmCommand.isPending}
        />
      )}

      <Dialog
        open={probeDialogOpen}
        onOpenChange={(open) => {
          setProbeDialogOpen(open);
          if (!open) {
            setSubnet('');
            setSubnetError(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Probe Network</DialogTitle>
            <DialogDescription>
              Enter a single IPv4 subnet in CIDR notation for {nodeId}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="agent-subnet">Subnet</Label>
            <Input
              id="agent-subnet"
              value={subnet}
              onChange={(event) => {
                setSubnet(event.target.value);
                setSubnetError(null);
              }}
              placeholder="e.g. 192.168.1.0/24"
              autoFocus
            />
            {subnetError && (
              <p className="text-xs text-destructive">{subnetError}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setProbeDialogOpen(false)}
              disabled={executingAction === 'reg::agent::probe-network'}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                void handleProbeSubmit();
              }}
              disabled={executingAction === 'reg::agent::probe-network'}
            >
              {executingAction === 'reg::agent::probe-network'
                ? 'Sending...'
                : 'Send Command'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
