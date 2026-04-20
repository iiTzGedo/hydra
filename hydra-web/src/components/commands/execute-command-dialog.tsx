import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { AlertTriangle, Clock, ShieldCheck } from 'lucide-react';
import type { CommandDefinitionSummary } from '@/api/commands';
import { useCreateCommand } from '@/api/commands';
import { getErrorMessage } from '@/lib/api-client';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { EntityCombobox } from '@/components/ui/entity-combobox';
import { HydraIcon } from '@/components/icons/hydra-icon';
import { categoryToCommandKind, getCommandIconDescriptor } from '@/lib/command-icons';
import { commandToken, dangerToken } from '@/lib/design-tokens';
import { cn } from '@/lib/utils';

const DANGER_LABELS: Record<string, string> = {
  safe: 'Safe',
  low: 'Low risk',
  medium: 'Medium risk',
  high: 'High risk',
  critical: 'Critical',
};

interface ExecuteCommandDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  definition?: CommandDefinitionSummary;
  nodeId?: string;
}

export function ExecuteCommandDialog({
  open,
  onOpenChange,
  definition,
  nodeId: initialNodeId,
}: ExecuteCommandDialogProps) {
  const createCommand = useCreateCommand();

  const [nodeId, setNodeId] = useState(initialNodeId ?? '');
  const [serviceId, setServiceId] = useState('');
  const [parametersJson, setParametersJson] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);

  // Reset form when dialog opens or definition changes
  useEffect(() => {
    if (open) {
      setNodeId(initialNodeId ?? '');
      setServiceId('');
      setParametersJson('');
      setConfirmed(false);
      setJsonError(null);
    }
  }, [open, initialNodeId]);

  const isServiceCategory = definition?.category === 'service';
  const requiresConfirmation = definition?.requiresConfirmation ?? false;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!definition) return;
    if (!nodeId.trim()) return;
    if (requiresConfirmation && !confirmed) return;

    let parameters: Record<string, unknown> | undefined;
    if (parametersJson.trim()) {
      try {
        parameters = JSON.parse(parametersJson.trim());
        setJsonError(null);
      } catch {
        setJsonError('Invalid JSON');
        return;
      }
    }

    try {
      const result = await createCommand.mutateAsync({
        registryId: definition.registryId,
        target: {
          nodeId: nodeId.trim(),
          serviceId: isServiceCategory && serviceId.trim() ? serviceId.trim() : undefined,
        },
        parameters: parameters ?? undefined,
        timeoutSeconds: definition.timeout,
      });

      toast.success(`Command queued: ${result.commandId}`);
      onOpenChange(false);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to execute command'));
    }
  };

  const canSubmit =
    !!definition &&
    nodeId.trim().length > 0 &&
    (!requiresConfirmation || confirmed) &&
    !createCommand.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-start gap-3">
            {definition && (
              <div
                className={cn(
                  'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border',
                  commandToken({
                    kind: categoryToCommandKind(definition.category),
                    surface: 'soft',
                  }),
                )}
              >
                <HydraIcon
                  icon={getCommandIconDescriptor({
                    registryId: definition.registryId,
                    category: definition.category,
                  })}
                  fallback="terminal"
                  size={20}
                />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <DialogTitle>
                {definition?.displayName ?? 'Execute Command'}
              </DialogTitle>
              {definition?.description && (
                <DialogDescription className="mt-1">
                  {definition.description}
                </DialogDescription>
              )}
              {definition && (
                <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">
                  {definition.registryId}
                </p>
              )}
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {definition && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium capitalize',
                  commandToken({
                    kind: categoryToCommandKind(definition.category),
                    surface: 'soft',
                  }),
                )}
              >
                {definition.category}
              </span>
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium capitalize',
                  dangerToken({
                    level: definition.dangerLevel ?? 'safe',
                    surface: 'soft',
                  }),
                )}
              >
                <span
                  className={cn(
                    'inline-block h-1.5 w-1.5 rounded-full',
                    dangerToken({
                      level: definition.dangerLevel ?? 'safe',
                      surface: 'dot',
                    }),
                  )}
                  aria-hidden="true"
                />
                {DANGER_LABELS[definition.dangerLevel ?? 'safe'] ?? definition.dangerLevel}
              </span>
              <Badge variant="outline" className="h-5 px-1.5">
                <ShieldCheck className="mr-1 h-3 w-3" />
                {definition.minimumRole}
              </Badge>
              <span className="inline-flex items-center gap-1 font-mono tabular-nums text-muted-foreground">
                <Clock className="h-3 w-3" />
                {definition.timeout}s
              </span>
            </div>
          )}

          <div className="space-y-2">
            <Label>Node *</Label>
            <EntityCombobox
              entityType="node"
              value={nodeId}
              onValueChange={setNodeId}
              placeholder="Select a node..."
            />
          </div>

          {isServiceCategory && (
            <div className="space-y-2">
              <Label>Service</Label>
              <EntityCombobox
                entityType="service"
                value={serviceId}
                onValueChange={setServiceId}
                clearable
                placeholder="Select a service..."
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="exec-parameters">Parameters (JSON, optional)</Label>
            <Textarea
              id="exec-parameters"
              value={parametersJson}
              onChange={(e) => {
                setParametersJson(e.target.value);
                setJsonError(null);
              }}
              placeholder='{"key": "value"}'
              rows={3}
              className="font-mono text-sm"
            />
            {jsonError && (
              <p className="text-xs text-destructive">{jsonError}</p>
            )}
          </div>

          {requiresConfirmation && (
            <div className="flex items-start gap-3 rounded-md border border-warning/30 bg-warning/5 p-3">
              <AlertTriangle className="h-5 w-5 text-warning mt-0.5 shrink-0" />
              <div className="space-y-2">
                <p className="text-sm font-medium text-warning">
                  This command requires confirmation
                </p>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="exec-confirm"
                    checked={confirmed}
                    onCheckedChange={(checked) => setConfirmed(checked === true)}
                  />
                  <Label htmlFor="exec-confirm" className="text-sm cursor-pointer">
                    I understand and want to proceed
                  </Label>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={createCommand.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit}>
              {createCommand.isPending ? 'Executing...' : 'Execute'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
