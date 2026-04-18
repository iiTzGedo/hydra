import { memo } from 'react';
import { Handle, Position, NodeProps, Node } from '@xyflow/react';
import { HydraIcon } from '@/components/icons/hydra-icon';
import { NODE_CLASS_COLORS, STATUS_COLORS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import type { IconDescriptor } from '@/types/icons';

export interface TopologyNodeData {
  label: string;
  class?: string;
  type?: string;
  kind?: string;
  status?: string;
  icon?: IconDescriptor | null;
  nodeId?: string;
  networkId?: string;
  serviceId?: string;
  [key: string]: unknown;
}

export type TopologyFlowNode = Node<TopologyNodeData, 'topology'>;

export const TopologyNodeComponent = memo(({ data, selected }: NodeProps<TopologyFlowNode>) => {
  const nodeClass = data.class as string | undefined;
  const nodeKind = data.kind as string | undefined;
  const nodeStatus = data.status as string | undefined;
  const isHighlighted = data.isHighlighted as boolean | undefined;

  const colors = NODE_CLASS_COLORS[nodeClass as keyof typeof NODE_CLASS_COLORS];
  const statusColors = STATUS_COLORS[nodeStatus as keyof typeof STATUS_COLORS] || STATUS_COLORS.inactive;

  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-muted-foreground !border-background !w-2 !h-2"
      />

      <div
        className={cn(
          'rounded-xl border-2 bg-card shadow-lg min-w-[140px] transition-all duration-200',
          selected ? 'ring-2 ring-primary border-primary scale-105' : 'border-border hover:border-primary/50',
          isHighlighted && !selected && 'ring-2 ring-warning border-warning shadow-warning/50 shadow-lg',
          'cursor-pointer'
        )}
      >
        <div className={cn('flex items-center gap-2 rounded-t-lg px-3 py-2', colors?.bg || 'bg-muted')}>
          <HydraIcon
            icon={data.icon as IconDescriptor | null | undefined}
            fallback={nodeKind || nodeClass || 'server'}
            className="text-white"
            size={16}
          />
          <span className="text-xs font-medium text-white capitalize">{nodeKind || nodeClass}</span>
        </div>

        <div className="px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-sm truncate">{data.label}</span>
            <span
              className={cn(
                'flex-shrink-0 h-2 w-2 rounded-full',
                statusColors.dot
              )}
              title={nodeStatus}
            />
          </div>

          {data.type && (
            <div className="mt-1 text-xs text-muted-foreground capitalize">
              {data.type as string}
            </div>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!bg-muted-foreground !border-background !w-2 !h-2"
      />
    </>
  );
});

TopologyNodeComponent.displayName = 'TopologyNodeComponent';
