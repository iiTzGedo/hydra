import { useCallback, useMemo, useState } from 'react';
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  GripVertical,
  Layers,
  Link2,
  Plus,
  Save,
  Server,
  Terminal,
} from 'lucide-react';
import {
  useCommandCatalog,
  type CommandDefinitionSummary,
} from '@/api/commands';
import type {
  CreateWorkflowRequest,
  WorkflowResponse,
  WorkflowStepConfig,
} from '@/types/workflows';
import { generateId } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import { StepEditor } from './step-editor';
import { StepPalette } from './step-palette';

// ── Props ──────────────────────────────────────────────────────────────

interface WorkflowBuilderProps {
  onSave: (workflow: CreateWorkflowRequest) => void;
  onCancel: () => void;
  initialWorkflow?: WorkflowResponse;
}

// ── Component ──────────────────────────────────────────────────────────

export function WorkflowBuilder({
  onSave,
  onCancel,
  initialWorkflow,
}: WorkflowBuilderProps) {
  const [workflowName, setWorkflowName] = useState(
    initialWorkflow?.name ?? ''
  );
  const [workflowDescription, setWorkflowDescription] = useState(
    initialWorkflow?.description ?? ''
  );
  const [steps, setSteps] = useState<WorkflowStepConfig[]>(
    initialWorkflow?.steps ?? []
  );
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  const { data: catalog } = useCommandCatalog();

  // Build a map from registryId -> definition for lookups
  const catalogMap = useMemo(() => {
    const map = new Map<string, CommandDefinitionSummary>();
    if (catalog) {
      for (const def of catalog) {
        map.set(def.registryId, def);
      }
    }
    return map;
  }, [catalog]);

  const selectedStep = useMemo(
    () => steps.find((s) => s.stepId === selectedStepId) ?? null,
    [steps, selectedStepId]
  );

  const selectedStepIndex = useMemo(
    () => (selectedStepId ? steps.findIndex((s) => s.stepId === selectedStepId) : -1),
    [steps, selectedStepId]
  );

  const allStepIds = useMemo(() => steps.map((s) => s.stepId), [steps]);

  // ── Step operations ──────────────────────────────────────────────────

  const handleAddCommand = useCallback(
    (definition: CommandDefinitionSummary) => {
      const stepId = `step_${generateId()}`;
      const newStep: WorkflowStepConfig = {
        stepId,
        registryId: definition.registryId,
        target: { nodeId: '' },
        onFailure: 'abort',
      };
      setSteps((prev) => [...prev, newStep]);
      setSelectedStepId(stepId);
    },
    []
  );

  const handleUpdateStep = useCallback(
    (stepId: string, updates: Partial<WorkflowStepConfig>) => {
      setSteps((prev) =>
        prev.map((s) => (s.stepId === stepId ? { ...s, ...updates } : s))
      );
    },
    []
  );

  const handleDeleteStep = useCallback(
    (stepId: string) => {
      setSteps((prev) => {
        // Remove the step
        const updated = prev.filter((s) => s.stepId !== stepId);
        // Also remove from dependsOn in other steps
        return updated.map((s) => ({
          ...s,
          dependsOn: s.dependsOn?.filter((id) => id !== stepId),
        }));
      });
      if (selectedStepId === stepId) {
        setSelectedStepId(null);
      }
    },
    [selectedStepId]
  );

  const handleMoveStep = useCallback(
    (stepId: string, direction: 'up' | 'down') => {
      setSteps((prev) => {
        const idx = prev.findIndex((s) => s.stepId === stepId);
        if (idx < 0) return prev;
        const targetIdx = direction === 'up' ? idx - 1 : idx + 1;
        if (targetIdx < 0 || targetIdx >= prev.length) return prev;

        const next = [...prev];
        const temp = next[idx];
        next[idx] = next[targetIdx];
        next[targetIdx] = temp;
        return next;
      });
    },
    []
  );

  // ── Save handler ─────────────────────────────────────────────────────

  const canSave =
    workflowName.trim().length > 0 &&
    steps.length > 0 &&
    steps.every((s) => s.registryId && s.target.nodeId.trim());

  const handleSave = useCallback(() => {
    if (!canSave) return;

    // Clean up step data for submission
    const cleanSteps = steps.map((s) => {
      const clean: WorkflowStepConfig = {
        stepId: s.stepId,
        registryId: s.registryId,
        target: {
          nodeId: s.target.nodeId.trim(),
          ...(s.target.serviceId ? { serviceId: s.target.serviceId } : {}),
        },
      };

      if (s.parameters && Object.keys(s.parameters).length > 0) {
        clean.parameters = s.parameters;
      }
      if (s.dependsOn && s.dependsOn.length > 0) {
        clean.dependsOn = s.dependsOn;
      }
      if (s.onFailure && s.onFailure !== 'abort') {
        clean.onFailure = s.onFailure;
      }
      if (s.onFailure === 'retry' && s.maxRetries != null) {
        clean.onFailure = 'retry';
        clean.maxRetries = s.maxRetries;
      }
      if (s.condition) {
        clean.condition = s.condition;
      }
      if (s.parallelGroup) {
        clean.parallelGroup = s.parallelGroup;
      }
      if (s.compensation && Object.keys(s.compensation).length > 0) {
        clean.compensation = s.compensation;
      }

      return clean;
    });

    const request: CreateWorkflowRequest = {
      name: workflowName.trim(),
      steps: cleanSteps,
    };

    if (workflowDescription.trim()) {
      request.description = workflowDescription.trim();
    }

    onSave(request);
  }, [canSave, steps, workflowName, workflowDescription, onSave]);

  // ── Collect parallel groups for visual highlighting ──────────────────

  const parallelGroups = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const step of steps) {
      if (step.parallelGroup) {
        const existing = groups.get(step.parallelGroup) ?? [];
        existing.push(step.stepId);
        groups.set(step.parallelGroup, existing);
      }
    }
    return groups;
  }, [steps]);

  // Colors for parallel groups
  const GROUP_COLORS = [
    'border-blue-500/40 bg-blue-500/5',
    'border-emerald-500/40 bg-emerald-500/5',
    'border-amber-500/40 bg-amber-500/5',
    'border-purple-500/40 bg-purple-500/5',
    'border-rose-500/40 bg-rose-500/5',
  ];

  const groupColorMap = useMemo(() => {
    const map = new Map<string, string>();
    let idx = 0;
    for (const groupName of parallelGroups.keys()) {
      map.set(groupName, GROUP_COLORS[idx % GROUP_COLORS.length]);
      idx++;
    }
    return map;
  }, [parallelGroups]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <div className="flex h-[calc(100vh-240px)] min-h-[500px] flex-col rounded-lg border bg-card">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            className="h-8 gap-1.5"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <Separator orientation="vertical" className="h-6" />
          <div className="space-y-0.5">
            <Input
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              placeholder="Workflow name..."
              className="h-7 w-64 border-none bg-transparent px-1 text-sm font-semibold shadow-none focus-visible:ring-1"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">
            {steps.length} step{steps.length !== 1 ? 's' : ''}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={onCancel}
            className="h-8"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!canSave}
            className="h-8 gap-1.5"
          >
            <Save className="h-3.5 w-3.5" />
            {initialWorkflow ? 'Update' : 'Save'} Workflow
          </Button>
        </div>
      </div>

      {/* Description row */}
      <div className="border-b px-4 py-2">
        <Label htmlFor="wf-description" className="sr-only">
          Description
        </Label>
        <Textarea
          id="wf-description"
          value={workflowDescription}
          onChange={(e) => setWorkflowDescription(e.target.value)}
          placeholder="Describe what this workflow does..."
          rows={1}
          className="min-h-[32px] resize-none border-none bg-transparent px-1 text-xs shadow-none focus-visible:ring-1"
        />
      </div>

      {/* Three-panel layout */}
      <div className="grid flex-1 grid-cols-[250px_1fr_320px] overflow-hidden">
        {/* Left: Step Palette */}
        <StepPalette onAddCommand={handleAddCommand} />

        {/* Center: Step List */}
        <div className="flex flex-col">
          <div className="flex items-center gap-2 border-b px-4 py-2">
            <Layers className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Workflow Steps</span>
          </div>

          {steps.length === 0 ? (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <Plus className="mx-auto h-10 w-10 text-muted-foreground/40" />
                <p className="mt-3 text-sm text-muted-foreground">
                  Add steps from the command palette on the left
                </p>
                <p className="mt-1 text-xs text-muted-foreground/60">
                  Click a command to add it as a workflow step
                </p>
              </div>
            </div>
          ) : (
            <ScrollArea className="flex-1">
              <div className="space-y-2 p-4">
                {steps.map((step, idx) => {
                  const def = catalogMap.get(step.registryId);
                  const isSelected = step.stepId === selectedStepId;
                  const groupColor = step.parallelGroup
                    ? groupColorMap.get(step.parallelGroup)
                    : undefined;
                  const hasDependencies =
                    step.dependsOn && step.dependsOn.length > 0;

                  return (
                    <div key={step.stepId}>
                      {/* Dependency arrow */}
                      {hasDependencies && (
                        <div className="flex items-center gap-2 pl-8 pb-1">
                          <Link2 className="h-3 w-3 text-muted-foreground" />
                          <span className="text-[10px] text-muted-foreground">
                            depends on:{' '}
                            {step.dependsOn!.map((depId) => (
                              <Badge
                                key={depId}
                                variant="outline"
                                className="mx-0.5 text-[10px] px-1 py-0"
                              >
                                {depId}
                              </Badge>
                            ))}
                          </span>
                        </div>
                      )}

                      <Card
                        className={`cursor-pointer transition-all ${
                          isSelected
                            ? 'ring-2 ring-primary border-primary'
                            : 'hover:border-primary/30'
                        } ${groupColor ?? ''}`}
                        onClick={() => setSelectedStepId(step.stepId)}
                      >
                        <CardContent className="flex items-center gap-3 p-3">
                          {/* Drag handle / step number */}
                          <div className="flex flex-col items-center gap-0.5">
                            <GripVertical className="h-4 w-4 text-muted-foreground/40" />
                            <span className="text-[10px] font-bold text-muted-foreground">
                              {idx + 1}
                            </span>
                          </div>

                          {/* Step info */}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <Terminal className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                              <span className="truncate text-sm font-medium">
                                {def?.displayName ?? step.registryId}
                              </span>
                            </div>
                            <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                              <Server className="h-3 w-3" />
                              <span className="truncate">
                                {step.target.nodeId || '(no target)'}
                              </span>
                              {step.target.serviceId && (
                                <>
                                  <span className="text-muted-foreground/40">
                                    /
                                  </span>
                                  <span className="truncate">
                                    {step.target.serviceId}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>

                          {/* Badges */}
                          <div className="flex shrink-0 flex-col items-end gap-1">
                            {step.parallelGroup && (
                              <Badge
                                variant="secondary"
                                className="text-[10px] px-1.5 py-0"
                              >
                                {step.parallelGroup}
                              </Badge>
                            )}
                            {step.onFailure && step.onFailure !== 'abort' && (
                              <Badge
                                variant="outline"
                                className="text-[10px] px-1.5 py-0"
                              >
                                {step.onFailure}
                              </Badge>
                            )}
                          </div>

                          {/* Move buttons */}
                          <div className="flex flex-col gap-0.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-5 w-5 p-0"
                              disabled={idx === 0}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleMoveStep(step.stepId, 'up');
                              }}
                            >
                              <ArrowUp className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-5 w-5 p-0"
                              disabled={idx === steps.length - 1}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleMoveStep(step.stepId, 'down');
                              }}
                            >
                              <ArrowDown className="h-3 w-3" />
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </div>

        {/* Right: Step Editor */}
        {selectedStep ? (
          <StepEditor
            step={selectedStep}
            stepIndex={selectedStepIndex}
            allStepIds={allStepIds}
            catalogMap={catalogMap}
            onUpdate={handleUpdateStep}
            onDelete={handleDeleteStep}
          />
        ) : (
          <div className="flex items-center justify-center border-l">
            <div className="text-center px-6">
              <Terminal className="mx-auto h-8 w-8 text-muted-foreground/30" />
              <p className="mt-2 text-xs text-muted-foreground">
                Select a step to configure it
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
