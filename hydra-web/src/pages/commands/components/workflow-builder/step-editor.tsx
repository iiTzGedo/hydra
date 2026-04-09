import { useCallback, useEffect, useState } from 'react';
import { HelpCircle, Trash2 } from 'lucide-react';
import type { CommandDefinitionSummary } from '@/api/commands';
import type { StepFailurePolicy, WorkflowStepConfig } from '@/types/workflows';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// ── Props ──────────────────────────────────────────────────────────────

interface StepEditorProps {
  step: WorkflowStepConfig;
  stepIndex: number;
  allStepIds: string[];
  catalogMap: Map<string, CommandDefinitionSummary>;
  onUpdate: (stepId: string, updates: Partial<WorkflowStepConfig>) => void;
  onDelete: (stepId: string) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────

function FieldHint({ text }: { text: string }) {
  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
        </TooltipTrigger>
        <TooltipContent side="left" className="max-w-[220px]">
          <p className="text-xs">{text}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ── Component ──────────────────────────────────────────────────────────

export function StepEditor({
  step,
  stepIndex,
  allStepIds,
  catalogMap,
  onUpdate,
  onDelete,
}: StepEditorProps) {
  const [parametersJson, setParametersJson] = useState('');
  const [compensationJson, setCompensationJson] = useState('');
  const [paramError, setParamError] = useState<string | null>(null);
  const [compError, setCompError] = useState<string | null>(null);

  // Sync JSON text fields from step data when step selection changes
  useEffect(() => {
    setParametersJson(
      step.parameters ? JSON.stringify(step.parameters, null, 2) : ''
    );
    setCompensationJson(
      step.compensation ? JSON.stringify(step.compensation, null, 2) : ''
    );
    setParamError(null);
    setCompError(null);
  }, [step.stepId]); // eslint-disable-line react-hooks/exhaustive-deps

  const definition = catalogMap.get(step.registryId);
  const otherStepIds = allStepIds.filter((id) => id !== step.stepId);

  // ── Event handlers ───────────────────────────────────────────────────

  const handleRegistryIdChange = useCallback(
    (value: string) => {
      onUpdate(step.stepId, { registryId: value });
    },
    [step.stepId, onUpdate]
  );

  const handleNodeIdChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onUpdate(step.stepId, {
        target: { ...step.target, nodeId: e.target.value },
      });
    },
    [step.stepId, step.target, onUpdate]
  );

  const handleServiceIdChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onUpdate(step.stepId, {
        target: {
          ...step.target,
          serviceId: e.target.value || null,
        },
      });
    },
    [step.stepId, step.target, onUpdate]
  );

  const handleFailurePolicyChange = useCallback(
    (value: string) => {
      const policy = value as StepFailurePolicy;
      const updates: Partial<WorkflowStepConfig> = { onFailure: policy };
      if (policy !== 'retry') {
        updates.maxRetries = undefined;
      }
      onUpdate(step.stepId, updates);
    },
    [step.stepId, onUpdate]
  );

  const handleMaxRetriesChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseInt(e.target.value, 10);
      onUpdate(step.stepId, { maxRetries: isNaN(val) ? undefined : val });
    },
    [step.stepId, onUpdate]
  );

  const handleConditionChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onUpdate(step.stepId, {
        condition: e.target.value || null,
      });
    },
    [step.stepId, onUpdate]
  );

  const handleParallelGroupChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onUpdate(step.stepId, {
        parallelGroup: e.target.value || null,
      });
    },
    [step.stepId, onUpdate]
  );

  const handleParametersBlur = useCallback(() => {
    const trimmed = parametersJson.trim();
    if (!trimmed) {
      onUpdate(step.stepId, { parameters: null });
      setParamError(null);
      return;
    }
    try {
      const parsed = JSON.parse(trimmed) as Record<string, unknown>;
      onUpdate(step.stepId, { parameters: parsed });
      setParamError(null);
    } catch {
      setParamError('Invalid JSON');
    }
  }, [step.stepId, parametersJson, onUpdate]);

  const handleCompensationBlur = useCallback(() => {
    const trimmed = compensationJson.trim();
    if (!trimmed) {
      onUpdate(step.stepId, { compensation: null });
      setCompError(null);
      return;
    }
    try {
      const parsed = JSON.parse(trimmed) as Record<string, unknown>;
      onUpdate(step.stepId, { compensation: parsed });
      setCompError(null);
    } catch {
      setCompError('Invalid JSON');
    }
  }, [step.stepId, compensationJson, onUpdate]);

  const handleDependsOnChange = useCallback(
    (depStepId: string, checked: boolean) => {
      const current = step.dependsOn ?? [];
      const updated = checked
        ? [...current, depStepId]
        : current.filter((id) => id !== depStepId);
      onUpdate(step.stepId, { dependsOn: updated.length > 0 ? updated : undefined });
    },
    [step.stepId, step.dependsOn, onUpdate]
  );

  // ── Catalog entries for the command select ───────────────────────────

  const catalogEntries = Array.from(catalogMap.values()).filter(
    (d) => !d.deprecated
  );

  return (
    <div className="flex h-full flex-col border-l">
      <div className="flex items-center justify-between p-3 pb-2">
        <h3 className="text-sm font-semibold text-muted-foreground">
          Step {stepIndex + 1} Config
        </h3>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 text-destructive hover:text-destructive"
          onClick={() => onDelete(step.stepId)}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      <Separator />

      <ScrollArea className="flex-1">
        <div className="space-y-4 p-3">
          {/* Registry ID */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="step-registry" className="text-xs">
                Command
              </Label>
              <FieldHint text="The registered command to execute in this step." />
            </div>
            <Select value={step.registryId} onValueChange={handleRegistryIdChange}>
              <SelectTrigger id="step-registry" className="h-8 text-xs">
                <SelectValue placeholder="Select command..." />
              </SelectTrigger>
              <SelectContent>
                {catalogEntries.map((def) => (
                  <SelectItem key={def.registryId} value={def.registryId}>
                    {def.displayName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {definition && (
              <p className="text-[10px] text-muted-foreground">
                {definition.description}
              </p>
            )}
          </div>

          {/* Target Node ID */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="step-node" className="text-xs">
                Target Node ID
              </Label>
              <FieldHint text="The node where this command will execute." />
            </div>
            <Input
              id="step-node"
              value={step.target.nodeId}
              onChange={handleNodeIdChange}
              placeholder="e.g. proxmox-01"
              className="h-8 text-xs"
            />
          </div>

          {/* Target Service ID */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="step-service" className="text-xs">
                Target Service ID
              </Label>
              <FieldHint text="Optional. Required for service-scoped commands." />
            </div>
            <Input
              id="step-service"
              value={step.target.serviceId ?? ''}
              onChange={handleServiceIdChange}
              placeholder="e.g. svc-nginx-a1b2"
              className="h-8 text-xs"
            />
          </div>

          <Separator />

          {/* Parameters */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="step-params" className="text-xs">
                Parameters (JSON)
              </Label>
              <FieldHint text="Key-value parameters passed to the command. Must be valid JSON." />
            </div>
            <Textarea
              id="step-params"
              value={parametersJson}
              onChange={(e) => {
                setParametersJson(e.target.value);
                setParamError(null);
              }}
              onBlur={handleParametersBlur}
              placeholder='{"key": "value"}'
              rows={3}
              className="font-mono text-xs resize-none"
            />
            {paramError && (
              <p className="text-[10px] text-destructive">{paramError}</p>
            )}
          </div>

          <Separator />

          {/* On Failure Policy */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="step-failure" className="text-xs">
                On Failure
              </Label>
              <FieldHint text="What to do if this step fails: abort the workflow, continue to next step, or retry." />
            </div>
            <Select
              value={step.onFailure ?? 'abort'}
              onValueChange={handleFailurePolicyChange}
            >
              <SelectTrigger id="step-failure" className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="abort">Abort workflow</SelectItem>
                <SelectItem value="continue">Continue</SelectItem>
                <SelectItem value="retry">Retry</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Max Retries */}
          {(step.onFailure === 'retry') && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5">
                <Label htmlFor="step-retries" className="text-xs">
                  Max Retries
                </Label>
                <FieldHint text="Maximum number of retry attempts before giving up." />
              </div>
              <Input
                id="step-retries"
                type="number"
                min={1}
                max={10}
                value={step.maxRetries ?? 3}
                onChange={handleMaxRetriesChange}
                className="h-8 text-xs"
              />
            </div>
          )}

          <Separator />

          {/* Condition */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="step-condition" className="text-xs">
                Condition
              </Label>
              <FieldHint text="Optional expression evaluated at runtime. Step runs only when condition is truthy." />
            </div>
            <Input
              id="step-condition"
              value={step.condition ?? ''}
              onChange={handleConditionChange}
              placeholder="e.g. steps.check_status.result.success == true"
              className="h-8 text-xs"
            />
          </div>

          {/* Parallel Group */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="step-parallel" className="text-xs">
                Parallel Group
              </Label>
              <FieldHint text="Steps with the same parallel group execute concurrently." />
            </div>
            <Input
              id="step-parallel"
              value={step.parallelGroup ?? ''}
              onChange={handleParallelGroupChange}
              placeholder="e.g. deploy-group-1"
              className="h-8 text-xs"
            />
          </div>

          <Separator />

          {/* Depends On */}
          {otherStepIds.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5">
                <Label className="text-xs">Depends On</Label>
                <FieldHint text="This step will wait until all selected dependencies have completed." />
              </div>
              <div className="space-y-1">
                {otherStepIds.map((depId) => {
                  const isChecked = step.dependsOn?.includes(depId) ?? false;
                  return (
                    <label
                      key={depId}
                      className="flex items-center gap-2 rounded-md px-2 py-1 text-xs cursor-pointer hover:bg-muted/50"
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) =>
                          handleDependsOnChange(depId, e.target.checked)
                        }
                        className="h-3.5 w-3.5 rounded border-input"
                      />
                      <span className="truncate font-mono">{depId}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Compensation */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="step-compensation" className="text-xs">
                Compensation (JSON)
              </Label>
              <FieldHint text="Optional rollback command configuration executed if the workflow fails after this step succeeds." />
            </div>
            <Textarea
              id="step-compensation"
              value={compensationJson}
              onChange={(e) => {
                setCompensationJson(e.target.value);
                setCompError(null);
              }}
              onBlur={handleCompensationBlur}
              placeholder='{"registryId": "...", "target": {...}}'
              rows={3}
              className="font-mono text-xs resize-none"
            />
            {compError && (
              <p className="text-[10px] text-destructive">{compError}</p>
            )}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
