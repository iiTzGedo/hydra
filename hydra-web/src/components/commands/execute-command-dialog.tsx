import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { AlertTriangle } from 'lucide-react';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';

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
          <DialogTitle>Execute Command</DialogTitle>
          {definition && (
            <DialogDescription>
              {definition.displayName}
              {definition.description ? ` - ${definition.description}` : ''}
            </DialogDescription>
          )}
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {definition && (
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="outline">{definition.category}</Badge>
              <span>Timeout: {definition.timeout}s</span>
              <span>Min Role: {definition.minimumRole}</span>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="exec-node-id">Node ID *</Label>
            <Input
              id="exec-node-id"
              value={nodeId}
              onChange={(e) => setNodeId(e.target.value)}
              placeholder="e.g. proxmox-01"
              required
            />
          </div>

          {isServiceCategory && (
            <div className="space-y-2">
              <Label htmlFor="exec-service-id">Service ID</Label>
              <Input
                id="exec-service-id"
                value={serviceId}
                onChange={(e) => setServiceId(e.target.value)}
                placeholder="e.g. svc-nginx-a1b2"
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
