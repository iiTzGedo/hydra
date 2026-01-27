import { useCallback, useState } from 'react';
import { Eye, Edit, Archive, Trash2, Play, Square, RotateCcw } from 'lucide-react';
import type { ActionMenuItemOrDivider } from '@/components/ui/action-menu';
import { ROUTES } from '@/lib/constants';

interface UseEntityActionsOptions<T> {
  entity: T;
  entityType: 'node' | 'service' | 'network' | 'group';
  getDetailPath: (entity: T) => string;
  onEdit?: (entity: T) => void;
  onArchive?: (entity: T) => Promise<void>;
  onDelete?: (entity: T) => Promise<void>;
  onStart?: (entity: T) => Promise<void>;
  onStop?: (entity: T) => Promise<void>;
  onRestart?: (entity: T) => Promise<void>;
}

interface UseEntityActionsResult {
  actions: ActionMenuItemOrDivider[];
  isProcessing: boolean;
  processingAction: string | null;
}

export function useEntityActions<T extends { id: string }>({
  entity,
  entityType,
  getDetailPath,
  onEdit,
  onArchive,
  onDelete,
  onStart,
  onStop,
  onRestart,
}: UseEntityActionsOptions<T>): UseEntityActionsResult {
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingAction, setProcessingAction] = useState<string | null>(null);

  const handleAction = useCallback(
    async (action: string, handler?: (entity: T) => Promise<void>) => {
      if (!handler) return;
      setIsProcessing(true);
      setProcessingAction(action);
      try {
        await handler(entity);
      } finally {
        setIsProcessing(false);
        setProcessingAction(null);
      }
    },
    [entity]
  );

  const actions: ActionMenuItemOrDivider[] = [
    {
      label: 'View',
      icon: Eye,
      href: getDetailPath(entity),
    },
  ];

  if (onEdit) {
    actions.push({
      label: 'Edit',
      icon: Edit,
      onClick: () => onEdit(entity),
      disabled: isProcessing,
    });
  }

  if (entityType === 'service') {
    if (onStart || onStop || onRestart) {
      actions.push({ type: 'divider' });
    }

    if (onStart) {
      actions.push({
        label: processingAction === 'start' ? 'Starting...' : 'Start',
        icon: Play,
        onClick: () => handleAction('start', onStart),
        disabled: isProcessing,
      });
    }

    if (onStop) {
      actions.push({
        label: processingAction === 'stop' ? 'Stopping...' : 'Stop',
        icon: Square,
        onClick: () => handleAction('stop', onStop),
        disabled: isProcessing,
      });
    }

    if (onRestart) {
      actions.push({
        label: processingAction === 'restart' ? 'Restarting...' : 'Restart',
        icon: RotateCcw,
        onClick: () => handleAction('restart', onRestart),
        disabled: isProcessing,
      });
    }
  }

  if (onArchive || onDelete) {
    actions.push({ type: 'divider' });

    if (onArchive) {
      actions.push({
        label: processingAction === 'archive' ? 'Archiving...' : 'Archive',
        icon: Archive,
        onClick: () => handleAction('archive', onArchive),
        variant: 'destructive',
        disabled: isProcessing,
      });
    }

    if (onDelete) {
      actions.push({
        label: processingAction === 'delete' ? 'Deleting...' : 'Delete',
        icon: Trash2,
        onClick: () => handleAction('delete', onDelete),
        variant: 'destructive',
        disabled: isProcessing,
      });
    }
  }

  return {
    actions,
    isProcessing,
    processingAction,
  };
}

export function getNodeDetailPath(nodeId: string): string {
  return `${ROUTES.NODES}/${encodeURIComponent(nodeId)}`;
}

export function getServiceDetailPath(serviceId: string): string {
  return `${ROUTES.SERVICES}/${encodeURIComponent(serviceId)}`;
}

export function getNetworkDetailPath(networkId: string): string {
  return `${ROUTES.NETWORKS}/${encodeURIComponent(networkId)}`;
}

export function getGroupDetailPath(groupId: string): string {
  return `${ROUTES.GROUPS}/${encodeURIComponent(groupId)}`;
}
