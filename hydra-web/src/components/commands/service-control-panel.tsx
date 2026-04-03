import { useState, useCallback, useMemo } from 'react';
import {
  Play,
  Square,
  RefreshCw,
  RotateCcw,
  FileText,
  Search,
  Download,
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
import { Separator } from '@/components/ui/separator';
import { PermissionGate } from '@/components/auth/permission-gate';
import { ControlConfirmationDialog } from '@/components/commands/control-confirmation-dialog';

interface ServiceControlPanelProps {
  nodeId: string;
  serviceId: string;
  serviceName: string;
  runtime?: string;
}

interface PendingConfirmation {
  commandId: string;
  registryId: string;
  actionLabel: string;
  dangerLevel: DangerLevel;
  confirmationMessage?: string | null;
}

interface ServiceAction {
  registryId: string;
  label: string;
  icon: typeof Play;
  permission: string;
  variant?: 'outline' | 'destructive' | 'default';
  group: 'state' | 'read' | 'admin';
  runtimeFilter?: string[];
}

const SERVICE_ACTIONS: ServiceAction[] = [
  {
    registryId: 'reg::service::start',
    label: 'Start',
    icon: Play,
    permission: 'services:control:start',
    variant: 'outline',
    group: 'state',
  },
  {
    registryId: 'reg::service::stop',
    label: 'Stop',
    icon: Square,
    permission: 'services:control:stop',
    variant: 'outline',
    group: 'state',
  },
  {
    registryId: 'reg::service::restart',
    label: 'Restart',
    icon: RefreshCw,
    permission: 'services:control:restart',
    variant: 'outline',
    group: 'state',
  },
  {
    registryId: 'reg::service::reload',
    label: 'Reload',
    icon: RotateCcw,
    permission: 'services:control:reload',
    variant: 'outline',
    group: 'state',
    runtimeFilter: ['systemd'],
  },
  {
    registryId: 'reg::service::logs',
    label: 'Logs',
    icon: FileText,
    permission: 'services:control:logs',
    variant: 'outline',
    group: 'read',
  },
  {
    registryId: 'reg::service::inspect',
    label: 'Inspect',
    icon: Search,
    permission: 'services:control:inspect',
    variant: 'outline',
    group: 'read',
  },
  {
    registryId: 'reg::service::update',
    label: 'Update',
    icon: Download,
    permission: 'services:control:update',
    variant: 'outline',
    group: 'admin',
    runtimeFilter: ['docker', 'podman'],
  },
];

export function ServiceControlPanel({
  nodeId,
  serviceId,
  serviceName,
  runtime,
}: ServiceControlPanelProps) {
  const createCommand = useCreateCommand();
  const confirmCommand = useConfirmCommand();
  const { data: catalog } = useCommandCatalog({ category: 'service' });

  const [pendingConfirmation, setPendingConfirmation] =
    useState<PendingConfirmation | null>(null);
  const [executingAction, setExecutingAction] = useState<string | null>(null);

  const visibleActions = useMemo(() => {
    return SERVICE_ACTIONS.filter((action) => {
      if (!action.runtimeFilter) return true;
      if (!runtime) return false;
      return action.runtimeFilter.includes(runtime.toLowerCase());
    });
  }, [runtime]);

  const groupedActions = useMemo(() => {
    const state = visibleActions.filter((a) => a.group === 'state');
    const read = visibleActions.filter((a) => a.group === 'read');
    const admin = visibleActions.filter((a) => a.group === 'admin');
    return { state, read, admin };
  }, [visibleActions]);

  const getCatalogEntry = useCallback(
    (registryId: string): CommandDefinitionSummary | undefined => {
      return catalog?.find((def) => def.registryId === registryId);
    },
    [catalog]
  );

  const handleAction = useCallback(
    async (registryId: string, label: string) => {
      setExecutingAction(registryId);
      try {
        const result: CommandQueuedResponse = await createCommand.mutateAsync({
          registryId,
          target: { nodeId, serviceId },
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
      } catch (err: unknown) {
        toast.error(getErrorMessage(err, `Failed to execute ${label}`));
      } finally {
        setExecutingAction(null);
      }
    },
    [nodeId, serviceId, createCommand, getCatalogEntry]
  );

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

  const renderGroup = (actions: ServiceAction[]) =>
    actions.map((action) => (
      <PermissionGate key={action.registryId} permissions={[action.permission]}>
        <Button
          variant={action.variant ?? 'outline'}
          size="sm"
          onClick={() => handleAction(action.registryId, action.label)}
          disabled={executingAction === action.registryId}
        >
          <action.icon className="mr-1.5 h-4 w-4" />
          {executingAction === action.registryId ? 'Sending...' : action.label}
        </Button>
      </PermissionGate>
    ));

  const hasRead = groupedActions.read.length > 0;
  const hasAdmin = groupedActions.admin.length > 0;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Service Controls</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            {renderGroup(groupedActions.state)}

            {hasRead && (
              <>
                <Separator orientation="vertical" className="mx-1 h-6" />
                {renderGroup(groupedActions.read)}
              </>
            )}

            {hasAdmin && (
              <>
                <Separator orientation="vertical" className="mx-1 h-6" />
                {renderGroup(groupedActions.admin)}
              </>
            )}
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
          resourceName={serviceName}
          actionLabel={pendingConfirmation.actionLabel}
          confirmationMessage={pendingConfirmation.confirmationMessage}
          onConfirm={handleConfirm}
          isPending={confirmCommand.isPending}
        />
      )}
    </>
  );
}
