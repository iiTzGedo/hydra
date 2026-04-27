/**
 * useEmbeddedPanel — fetches the entity-panel board for the given entity type
 * and resolves all {{entity.id}} / {{entity.type}} template variables in the
 * returned board so that widgets can use real endpoint paths.
 */

import { useMemo } from 'react';
import { useEntityPanel } from '@/api/dashboards';
import { resolveEntityVarsDeep } from '@/lib/entity-template';
import type { EntityPanelType, DashboardBoard } from '@/types/dashboard';

export interface EmbeddedPanelResult {
  /** The board with all entity template variables resolved. Null while loading or on error. */
  data: (DashboardBoard & { id: string }) | null;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

export function useEmbeddedPanel(entityType: EntityPanelType, entityId: string): EmbeddedPanelResult {
  const query = useEntityPanel(entityType);

  const resolvedBoard = useMemo((): (DashboardBoard & { id: string }) | null => {
    if (!query.data) return null;
    return resolveEntityVarsDeep(query.data, entityType, entityId);
  }, [query.data, entityType, entityId]);

  return {
    data: resolvedBoard,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error as Error | null,
  };
}
