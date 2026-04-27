import { useState, useCallback, useMemo } from 'react';
import type {
  DashboardBoard,
  DashboardWidgetInstance,
  FreeformPosition,
  LayoutMode,
} from '@/types/dashboard';

/**
 * Maximum history depth. When exceeded, the oldest entry is dropped.
 * Consequence: undoing beyond MAX_HISTORY returns to the initial `baseBoard`
 * (the last-committed state), skipping any evicted intermediate states.
 * This is intentional — editors typically save frequently enough that the
 * edit session rarely exceeds 50 operations.
 */
const MAX_HISTORY = 50;

interface HistStack {
  history: DashboardBoard[];
  index: number;
}

export interface BoardEditorApi {
  baseBoard: DashboardBoard | null;
  draftBoard: DashboardBoard | null;
  isDirty: boolean;
  canUndo: boolean;
  canRedo: boolean;
  addWidget(widget: DashboardWidgetInstance): void;
  removeWidget(instanceId: string): void;
  duplicateWidget(instanceId: string): void;
  updateWidgetLayout(
    instanceId: string,
    placements?: DashboardWidgetInstance['placements'],
    freeformPosition?: FreeformPosition | null,
  ): void;
  updateAllWidgetLayouts(
    updates: Array<{
      instanceId: string;
      placements?: DashboardWidgetInstance['placements'];
      freeformPosition?: FreeformPosition | null;
    }>,
  ): void;
  updateWidgetConfig(instanceId: string, partialConfig: Record<string, unknown>): void;
  setLayoutMode(mode: LayoutMode): void;
  /**
   * Atomically switches the layout mode AND applies per-widget position
   * updates in a single history entry (C2 fix).
   *
   * Use this instead of calling `updateAllWidgetLayouts` + `setLayoutMode`
   * separately — two separate `mutate` calls produce two history entries,
   * making undo incoherent (mode reverts without reverting positions, and
   * vice-versa).
   */
  convertLayoutMode(
    next: LayoutMode,
    updates: Array<{
      instanceId: string;
      placements?: DashboardWidgetInstance['placements'];
      freeformPosition?: FreeformPosition | null;
    }>,
  ): void;
  undo(): void;
  redo(): void;
  discard(): void;
  commitSave(saved: DashboardBoard): void;
}

export function useBoardEditor(initialBoard: DashboardBoard | null): BoardEditorApi {
  const [baseBoard, setBaseBoard] = useState<DashboardBoard | null>(
    initialBoard ? structuredClone(initialBoard) : null,
  );
  const [draftBoard, setDraftBoard] = useState<DashboardBoard | null>(
    initialBoard ? structuredClone(initialBoard) : null,
  );

  // Merged state object so both history array and index always update atomically
  // via a single functional updater — eliminates stale-closure corruption when
  // multiple mutations fire synchronously in one call frame.
  const [histStack, setHistStack] = useState<HistStack>({ history: [], index: -1 });

  const isDirty = useMemo(() => {
    if (!baseBoard || !draftBoard) return false;
    return JSON.stringify(baseBoard) !== JSON.stringify(draftBoard);
  }, [baseBoard, draftBoard]);

  /**
   * Central mutation helper — every widget operation goes through here so
   * history tracking is consistent.
   *
   * Uses a functional updater for histStack so `prev` always reflects the
   * most-recent committed state even when multiple mutations fire in the same
   * React render cycle (avoids stale-closure corruption of historyIndex).
   */
  const mutate = useCallback((fn: (board: DashboardBoard) => DashboardBoard) => {
    setDraftBoard((current) => {
      if (!current) return current;
      const next = fn(structuredClone(current));
      setHistStack(({ history, index }) => {
        // Drop the redo chain (everything after current index)
        const truncated = history.slice(0, index + 1);
        const appended = [...truncated, structuredClone(next)];
        // Cap at MAX_HISTORY — drop oldest entry if overflow
        const newHistory =
          appended.length > MAX_HISTORY
            ? appended.slice(appended.length - MAX_HISTORY)
            : appended;
        return { history: newHistory, index: Math.min(index + 1, MAX_HISTORY - 1) };
      });
      return next;
    });
  }, []); // no deps — truly stable reference

  const addWidget = useCallback(
    (widget: DashboardWidgetInstance) => {
      mutate((b) => ({ ...b, widgets: [...b.widgets, widget] }));
    },
    [mutate],
  );

  const removeWidget = useCallback(
    (instanceId: string) => {
      mutate((b) => ({
        ...b,
        widgets: b.widgets.filter((w) => w.instanceId !== instanceId),
      }));
    },
    [mutate],
  );

  const duplicateWidget = useCallback(
    (instanceId: string) => {
      mutate((b) => {
        const src = b.widgets.find((w) => w.instanceId === instanceId);
        if (!src) return b;
        const copy: DashboardWidgetInstance = {
          ...structuredClone(src),
          instanceId: `${instanceId}-copy-${Date.now()}`,
        };
        return { ...b, widgets: [...b.widgets, copy] };
      });
    },
    [mutate],
  );

  const updateWidgetLayout = useCallback(
    (
      instanceId: string,
      placements?: DashboardWidgetInstance['placements'],
      freeformPosition?: FreeformPosition | null,
    ) => {
      mutate((b) => ({
        ...b,
        widgets: b.widgets.map((w) => {
          if (w.instanceId !== instanceId) return w;
          return {
            ...w,
            placements: placements ?? w.placements,
            freeformPosition:
              freeformPosition !== undefined ? freeformPosition : w.freeformPosition,
          };
        }),
      }));
    },
    [mutate],
  );

  /**
   * Batch-update placements/freeformPosition for multiple widgets in one
   * history entry. Use this instead of looping over updateWidgetLayout to
   * avoid producing N separate undo steps for a single drag operation.
   */
  const updateAllWidgetLayouts = useCallback(
    (
      updates: Array<{
        instanceId: string;
        placements?: DashboardWidgetInstance['placements'];
        freeformPosition?: FreeformPosition | null;
      }>,
    ) => {
      mutate((b) => ({
        ...b,
        widgets: b.widgets.map((w) => {
          const update = updates.find((u) => u.instanceId === w.instanceId);
          if (!update) return w;
          return {
            ...w,
            placements: update.placements ?? w.placements,
            freeformPosition:
              update.freeformPosition !== undefined
                ? update.freeformPosition
                : w.freeformPosition,
          };
        }),
      }));
    },
    [mutate],
  );

  const updateWidgetConfig = useCallback(
    (instanceId: string, partialConfig: Record<string, unknown>) => {
      mutate((b) => ({
        ...b,
        widgets: b.widgets.map((w) =>
          w.instanceId === instanceId
            ? { ...w, config: { ...(w.config as object), ...partialConfig } }
            : w,
        ),
      }));
    },
    [mutate],
  );

  const setLayoutMode = useCallback(
    (mode: LayoutMode) => {
      mutate((b) => ({ ...b, layoutMode: mode }));
    },
    [mutate],
  );

  /**
   * Atomically switches the layout mode AND applies per-widget position
   * updates in a SINGLE history entry (C2 fix).
   *
   * Two separate `mutate` calls (updateAllWidgetLayouts + setLayoutMode)
   * would push TWO history entries, making undo incoherent: one undo would
   * revert the mode without reverting the positions.
   */
  const convertLayoutMode = useCallback(
    (
      next: LayoutMode,
      updates: Array<{
        instanceId: string;
        placements?: DashboardWidgetInstance['placements'];
        freeformPosition?: FreeformPosition | null;
      }>,
    ) => {
      mutate((b) => ({
        ...b,
        layoutMode: next,
        widgets: b.widgets.map((w) => {
          const update = updates.find((u) => u.instanceId === w.instanceId);
          if (!update) return w;
          return {
            ...w,
            placements: update.placements ?? w.placements,
            freeformPosition:
              update.freeformPosition !== undefined
                ? update.freeformPosition
                : w.freeformPosition,
          };
        }),
      }));
    },
    [mutate],
  );

  const undo = useCallback(() => {
    setHistStack((prev) => {
      if (prev.index <= 0) {
        // Nothing left in history stack — revert to saved base
        setDraftBoard(baseBoard ? structuredClone(baseBoard) : null);
        return { ...prev, index: -1 };
      }
      const prevBoard = prev.history[prev.index - 1];
      setDraftBoard(structuredClone(prevBoard));
      return { ...prev, index: prev.index - 1 };
    });
  }, [baseBoard]);

  const redo = useCallback(() => {
    setHistStack((prev) => {
      if (prev.index >= prev.history.length - 1) return prev;
      const nextBoard = prev.history[prev.index + 1];
      setDraftBoard(structuredClone(nextBoard));
      return { ...prev, index: prev.index + 1 };
    });
  }, []);

  const discard = useCallback(() => {
    setDraftBoard(baseBoard ? structuredClone(baseBoard) : null);
    setHistStack({ history: [], index: -1 });
  }, [baseBoard]);

  const commitSave = useCallback((saved: DashboardBoard) => {
    const clone = structuredClone(saved);
    setBaseBoard(clone);
    setDraftBoard(structuredClone(saved));
    setHistStack({ history: [], index: -1 });
  }, []);

  return {
    baseBoard,
    draftBoard,
    isDirty,
    canUndo: histStack.index >= 0,
    canRedo: histStack.index < histStack.history.length - 1,
    addWidget,
    removeWidget,
    duplicateWidget,
    updateWidgetLayout,
    updateAllWidgetLayouts,
    updateWidgetConfig,
    setLayoutMode,
    convertLayoutMode,
    undo,
    redo,
    discard,
    commitSave,
  };
}
