import { useCallback, useMemo } from 'react';
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Server, Terminal } from 'lucide-react';

import type { CommandDefinitionSummary } from '@/api/commands';
import type { WorkflowStepConfig } from '@/types/workflows';
import { cn } from '@/lib/utils';

// ── Cycle detection ────────────────────────────────────────────────────

/**
 * Returns true if `fromId` already depends (transitively, via dependsOn) on
 * `targetId`. Used to reject dependency edges that would create a cycle.
 */
export function dependsOnTransitively(
  steps: WorkflowStepConfig[],
  fromId: string,
  targetId: string
): boolean {
  const byId = new Map(steps.map((s) => [s.stepId, s]));
  const seen = new Set<string>();
  const stack = [...(byId.get(fromId)?.dependsOn ?? [])];
  while (stack.length) {
    const current = stack.pop()!;
    if (current === targetId) return true;
    if (seen.has(current)) continue;
    seen.add(current);
    stack.push(...(byId.get(current)?.dependsOn ?? []));
  }
  return false;
}

// ── Custom node ────────────────────────────────────────────────────────

type StepNodeData = {
  label: string;
  target: string;
  selected: boolean;
  groupColor?: string;
  failurePolicy?: string;
};

function StepNode({ data }: NodeProps<Node<StepNodeData>>) {
  return (
    <div
      className={cn(
        'min-w-[180px] rounded-md border bg-card px-3 py-2 shadow-sm transition-all',
        data.selected ? 'border-primary ring-2 ring-primary' : 'border-border',
        data.groupColor
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <div className="flex items-center gap-2">
        <Terminal className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate text-sm font-medium">{data.label}</span>
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <Server className="h-3 w-3" />
        <span className="truncate">{data.target || '(no target)'}</span>
        {data.failurePolicy && data.failurePolicy !== 'abort' && (
          <span className="ml-auto rounded bg-muted px-1 py-0.5">{data.failurePolicy}</span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground" />
    </div>
  );
}

const nodeTypes = { step: StepNode };

// ── Canvas ─────────────────────────────────────────────────────────────

interface WorkflowCanvasProps {
  steps: WorkflowStepConfig[];
  selectedStepId: string | null;
  catalogMap: Map<string, CommandDefinitionSummary>;
  groupColorMap: Map<string, string>;
  onSelectStep: (stepId: string) => void;
  /** Add `dependsOnId` to `stepId`'s dependencies. Returns false if rejected (cycle). */
  onAddDependency: (stepId: string, dependsOnId: string) => boolean;
  onRemoveDependency: (stepId: string, dependsOnId: string) => void;
}

export function WorkflowCanvas({
  steps,
  selectedStepId,
  catalogMap,
  groupColorMap,
  onSelectStep,
  onAddDependency,
  onRemoveDependency,
}: WorkflowCanvasProps) {
  const nodes = useMemo<Node<StepNodeData>[]>(() => {
    // Lay steps out in a vertical flow; users can drag to rearrange.
    return steps.map((step, idx) => ({
      id: step.stepId,
      type: 'step',
      position: { x: (idx % 2) * 260, y: idx * 130 },
      data: {
        label: catalogMap.get(step.registryId)?.displayName ?? step.registryId,
        target: step.target.nodeId,
        selected: step.stepId === selectedStepId,
        groupColor: step.parallelGroup
          ? groupColorMap.get(step.parallelGroup)
          : undefined,
        failurePolicy: step.onFailure,
      },
    }));
  }, [steps, catalogMap, selectedStepId, groupColorMap]);

  const edges = useMemo<Edge[]>(() => {
    const result: Edge[] = [];
    for (const step of steps) {
      for (const dep of step.dependsOn ?? []) {
        // Edge from the dependency (source) to the dependent step (target).
        result.push({
          id: `${dep}->${step.stepId}`,
          source: dep,
          target: step.stepId,
          animated: true,
        });
      }
    }
    return result;
  }, [steps]);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      if (connection.source === connection.target) return;
      // target depends on source (source runs first).
      onAddDependency(connection.target, connection.source);
    },
    [onAddDependency]
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      for (const change of changes) {
        if (change.type === 'remove') {
          const [source, target] = change.id.split('->');
          if (source && target) {
            onRemoveDependency(target, source);
          }
        }
      }
    },
    [onRemoveDependency]
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      onSelectStep(node.id);
    },
    [onSelectStep]
  );

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onConnect={onConnect}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
        deleteKeyCode={['Backspace', 'Delete']}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
