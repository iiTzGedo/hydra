/**
 * Tests for useBoardEditor hook — undo/redo history stack,
 * mutation helpers, save/discard semantics.
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useBoardEditor } from '@/hooks/use-board-editor';
import type { DashboardBoard, DashboardWidgetInstance } from '@/types/dashboard';

// ── Fixtures ───────────────────────────────────────────────────────

function makeWidget(id: string): DashboardWidgetInstance {
  return {
    instanceId: id,
    widgetType: 'hydra::test-widget',
    position: { x: 0, y: 0, w: 4, h: 2 },
    placements: { lg: { x: 0, y: 0, w: 4, h: 2 } },
    config: { title: `Widget ${id}` },
    dataBinding: null,
  };
}

function makeBoard(overrides?: Partial<DashboardBoard>): DashboardBoard {
  return {
    boardId: 'board-test',
    name: 'Test Board',
    description: 'A board for testing',
    icon: null,
    ownerId: 'user-1',
    ownerType: 'user',
    boardType: 'user',
    visibility: { scope: 'private', sharedWith: { roles: [], users: [] } },
    widgetCount: 1,
    tags: [],
    isHome: false,
    version: 1,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    layoutMode: 'grid',
    scope: 'standalone',
    entityTypeFilter: null,
    isSystemDefault: false,
    layout: {
      mode: 'grid',
      grid: {
        columns: 12,
        rowHeight: 80,
        breakpoints: {
          xl: { columns: 12, width: 1536 },
          lg: { columns: 12, width: 1200 },
        },
        compaction: 'vertical',
        margin: [16, 16],
        padding: [0, 0],
      },
    },
    settings: {
      theme: 'inherit',
      autoRefresh: true,
      refreshInterval: 30,
      showHeader: true,
      kioskMode: false,
      kioskAutoScroll: false,
      kioskScrollSpeed: 30,
      backgroundImage: null,
      customCss: null,
    },
    widgets: [makeWidget('w1')],
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────────

describe('useBoardEditor', () => {
  it('initializes with baseBoard; no dirty; empty history', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    expect(result.current.baseBoard?.boardId).toBe('board-test');
    expect(result.current.draftBoard?.boardId).toBe('board-test');
    expect(result.current.isDirty).toBe(false);
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });

  it('initializes with null board when null passed', () => {
    const { result } = renderHook(() => useBoardEditor(null));

    expect(result.current.baseBoard).toBeNull();
    expect(result.current.draftBoard).toBeNull();
    expect(result.current.isDirty).toBe(false);
  });

  it('addWidget pushes history and marks dirty', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => {
      result.current.addWidget(makeWidget('w2'));
    });

    expect(result.current.draftBoard?.widgets).toHaveLength(2);
    expect(result.current.isDirty).toBe(true);
    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);
  });

  it('undo restores previous state', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => {
      result.current.addWidget(makeWidget('w2'));
    });

    expect(result.current.draftBoard?.widgets).toHaveLength(2);

    act(() => {
      result.current.undo();
    });

    // After undo of the only op, should revert to base (1 widget)
    expect(result.current.draftBoard?.widgets).toHaveLength(1);
    expect(result.current.isDirty).toBe(false);
    expect(result.current.canUndo).toBe(false);
  });

  it('undo with multiple ops walks back step by step', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => { result.current.addWidget(makeWidget('w2')); });
    act(() => { result.current.addWidget(makeWidget('w3')); });

    expect(result.current.draftBoard?.widgets).toHaveLength(3);

    act(() => { result.current.undo(); });
    expect(result.current.draftBoard?.widgets).toHaveLength(2);
    expect(result.current.canRedo).toBe(true);

    act(() => { result.current.undo(); });
    expect(result.current.draftBoard?.widgets).toHaveLength(1);
    expect(result.current.isDirty).toBe(false);
  });

  it('redo reapplies operation', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => { result.current.addWidget(makeWidget('w2')); });
    act(() => { result.current.undo(); });

    expect(result.current.canRedo).toBe(true);

    act(() => { result.current.redo(); });

    expect(result.current.draftBoard?.widgets).toHaveLength(2);
    expect(result.current.isDirty).toBe(true);
    expect(result.current.canRedo).toBe(false);
  });

  it('save clears history; dirty false; canUndo false', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => { result.current.addWidget(makeWidget('w2')); });
    expect(result.current.isDirty).toBe(true);

    const savedBoard = { ...board, widgets: [...board.widgets, makeWidget('w2')] };
    act(() => { result.current.commitSave(savedBoard); });

    expect(result.current.isDirty).toBe(false);
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
    // baseBoard should now reflect the saved state
    expect(result.current.baseBoard?.widgets).toHaveLength(2);
  });

  it('discard reverts to baseBoard; dirty false', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => { result.current.addWidget(makeWidget('w2')); });
    act(() => { result.current.addWidget(makeWidget('w3')); });
    expect(result.current.draftBoard?.widgets).toHaveLength(3);

    act(() => { result.current.discard(); });

    expect(result.current.draftBoard?.widgets).toHaveLength(1);
    expect(result.current.isDirty).toBe(false);
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });

  it('caps history at 50 entries — after 60 adds, canUndo true with max 50 steps', () => {
    const board = makeBoard({ widgets: [] });
    const { result } = renderHook(() => useBoardEditor(board));

    for (let i = 0; i < 60; i++) {
      act(() => {
        result.current.addWidget(makeWidget(`w${i}`));
      });
    }

    expect(result.current.draftBoard?.widgets).toHaveLength(60);

    // We can undo up to 50 times (history capped at 50)
    let undoCount = 0;
    while (result.current.canUndo) {
      act(() => { result.current.undo(); });
      undoCount++;
      if (undoCount > 60) break; // safety guard
    }

    // Should have undone exactly 50 times (not 60)
    expect(undoCount).toBe(50);
    // After 50 undos the draft has 10 widgets remaining (60 - 50)
    expect(result.current.draftBoard?.widgets.length).toBeLessThanOrEqual(11);
  });

  it('new operation after undo drops redo chain', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => { result.current.addWidget(makeWidget('w2')); });
    act(() => { result.current.addWidget(makeWidget('w3')); });

    // Undo one step — redo chain exists
    act(() => { result.current.undo(); });
    expect(result.current.canRedo).toBe(true);

    // New mutation clears redo chain
    act(() => { result.current.addWidget(makeWidget('w4')); });
    expect(result.current.canRedo).toBe(false);
    expect(result.current.draftBoard?.widgets).toHaveLength(3);
  });

  it('updateWidgetConfig merges partial config — existing keys preserved', () => {
    const widget = makeWidget('w1');
    widget.config = { title: 'Original', subtitle: 'Keep me', count: 5 };
    const board = makeBoard({ widgets: [widget] });
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => {
      result.current.updateWidgetConfig('w1', { title: 'Updated' });
    });

    const updatedWidget = result.current.draftBoard?.widgets.find(
      (w) => w.instanceId === 'w1',
    );
    expect(updatedWidget?.config.title).toBe('Updated');
    expect(updatedWidget?.config.subtitle).toBe('Keep me');
    expect(updatedWidget?.config.count).toBe(5);
    expect(result.current.canUndo).toBe(true);
  });

  it('updateWidgetLayout preserves placements when freeformPosition set', () => {
    const widget = makeWidget('w1');
    widget.placements = { lg: { x: 0, y: 0, w: 4, h: 2 } };
    widget.freeformPosition = null;
    const board = makeBoard({ widgets: [widget] });
    const { result } = renderHook(() => useBoardEditor(board));

    const newFreeform = { x: 100, y: 200, w: 300, h: 150 };
    act(() => {
      result.current.updateWidgetLayout('w1', undefined, newFreeform);
    });

    const updatedWidget = result.current.draftBoard?.widgets.find(
      (w) => w.instanceId === 'w1',
    );
    // placements preserved when not passed
    expect(updatedWidget?.placements).toEqual({ lg: { x: 0, y: 0, w: 4, h: 2 } });
    // freeformPosition updated
    expect(updatedWidget?.freeformPosition).toEqual(newFreeform);
  });

  it('updateWidgetLayout preserves freeformPosition when placements updated', () => {
    const widget = makeWidget('w1');
    widget.placements = { lg: { x: 0, y: 0, w: 4, h: 2 } };
    widget.freeformPosition = { x: 10, y: 20, w: 100, h: 80 };
    const board = makeBoard({ widgets: [widget] });
    const { result } = renderHook(() => useBoardEditor(board));

    const newPlacements = { lg: { x: 2, y: 4, w: 6, h: 3 } };
    act(() => {
      result.current.updateWidgetLayout('w1', newPlacements, undefined);
    });

    const updatedWidget = result.current.draftBoard?.widgets.find(
      (w) => w.instanceId === 'w1',
    );
    expect(updatedWidget?.placements).toEqual(newPlacements);
    // freeformPosition untouched when freeformPosition param is undefined
    expect(updatedWidget?.freeformPosition).toEqual({ x: 10, y: 20, w: 100, h: 80 });
  });

  it('setLayoutMode updates layoutMode and is tracked in history', () => {
    const board = makeBoard({ layoutMode: 'grid' });
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => {
      result.current.setLayoutMode('freeform');
    });

    expect(result.current.draftBoard?.layoutMode).toBe('freeform');
    expect(result.current.isDirty).toBe(true);
    expect(result.current.canUndo).toBe(true);

    act(() => { result.current.undo(); });
    expect(result.current.draftBoard?.layoutMode).toBe('grid');
  });

  it('removeWidget removes widget and tracks history', () => {
    const board = makeBoard({ widgets: [makeWidget('w1'), makeWidget('w2')] });
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => { result.current.removeWidget('w1'); });

    expect(result.current.draftBoard?.widgets).toHaveLength(1);
    expect(result.current.draftBoard?.widgets[0].instanceId).toBe('w2');
    expect(result.current.canUndo).toBe(true);

    act(() => { result.current.undo(); });
    expect(result.current.draftBoard?.widgets).toHaveLength(2);
  });

  it('duplicateWidget creates a copy with a new instanceId', () => {
    const board = makeBoard({ widgets: [makeWidget('w1')] });
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => { result.current.duplicateWidget('w1'); });

    expect(result.current.draftBoard?.widgets).toHaveLength(2);
    const [original, copy] = result.current.draftBoard!.widgets;
    expect(original.instanceId).toBe('w1');
    expect(copy.instanceId).toMatch(/^w1-copy-\d+$/);
    expect(copy.widgetType).toBe(original.widgetType);
  });

  it('isDirty is false after commitSave with same content', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    // Commit the same board — no changes
    act(() => { result.current.commitSave(board); });
    expect(result.current.isDirty).toBe(false);
  });

  it('undo does nothing when history is empty', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    // No ops — undo should be a no-op
    act(() => { result.current.undo(); });

    expect(result.current.draftBoard?.boardId).toBe('board-test');
    expect(result.current.isDirty).toBe(false);
  });

  it('redo does nothing when at latest history position', () => {
    const board = makeBoard();
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => { result.current.addWidget(makeWidget('w2')); });
    expect(result.current.canRedo).toBe(false);

    // Redo should be a no-op
    act(() => { result.current.redo(); });
    expect(result.current.draftBoard?.widgets).toHaveLength(2);
  });

  // ── Regression: stale closure bug ─────────────────────────────────

  it('handles rapid synchronous mutations without history corruption', () => {
    const board = makeBoard({ widgets: [] });
    const { result } = renderHook(() => useBoardEditor(board));

    // Simulate multiple widget updates in one call frame (as if a loop
    // called updateWidgetLayout N times before React commits any state)
    act(() => {
      result.current.addWidget(makeWidget('wA'));
      result.current.addWidget(makeWidget('wB'));
      result.current.addWidget(makeWidget('wC'));
    });

    expect(result.current.draftBoard?.widgets).toHaveLength(3);

    // Should be able to undo exactly 3 times, one step per mutation
    act(() => { result.current.undo(); });
    expect(result.current.draftBoard?.widgets).toHaveLength(2);

    act(() => { result.current.undo(); });
    expect(result.current.draftBoard?.widgets).toHaveLength(1);

    act(() => { result.current.undo(); });
    expect(result.current.draftBoard?.widgets).toHaveLength(0);

    expect(result.current.canUndo).toBe(false);
  });

  // ── updateAllWidgetLayouts batch method ───────────────────────────

  it('updateAllWidgetLayouts produces single history entry for N widget changes', () => {
    const board = makeBoard({
      widgets: [makeWidget('w1'), makeWidget('w2'), makeWidget('w3')],
    });
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => {
      result.current.updateAllWidgetLayouts([
        { instanceId: 'w1', placements: { lg: { x: 0, y: 0, w: 2, h: 2 } } },
        { instanceId: 'w2', placements: { lg: { x: 2, y: 0, w: 2, h: 2 } } },
        { instanceId: 'w3', placements: { lg: { x: 4, y: 0, w: 2, h: 2 } } },
      ]);
    });

    // Verify placements were applied
    const w1 = result.current.draftBoard?.widgets.find((w) => w.instanceId === 'w1');
    const w2 = result.current.draftBoard?.widgets.find((w) => w.instanceId === 'w2');
    const w3 = result.current.draftBoard?.widgets.find((w) => w.instanceId === 'w3');
    expect(w1?.placements?.lg).toMatchObject({ x: 0, y: 0, w: 2, h: 2 });
    expect(w2?.placements?.lg).toMatchObject({ x: 2, y: 0, w: 2, h: 2 });
    expect(w3?.placements?.lg).toMatchObject({ x: 4, y: 0, w: 2, h: 2 });

    // ONE undo should revert ALL 3 widget placement changes at once
    act(() => { result.current.undo(); });

    const orig1 = result.current.draftBoard?.widgets.find((w) => w.instanceId === 'w1');
    const orig2 = result.current.draftBoard?.widgets.find((w) => w.instanceId === 'w2');
    const orig3 = result.current.draftBoard?.widgets.find((w) => w.instanceId === 'w3');
    // All reverted to original placements from makeWidget
    expect(orig1?.placements).toEqual({ lg: { x: 0, y: 0, w: 4, h: 2 } });
    expect(orig2?.placements).toEqual({ lg: { x: 0, y: 0, w: 4, h: 2 } });
    expect(orig3?.placements).toEqual({ lg: { x: 0, y: 0, w: 4, h: 2 } });

    // After reverting the batch, there should be nothing left to undo
    expect(result.current.canUndo).toBe(false);
  });

  // ── convertLayoutMode (C2) ────────────────────────────────────────

  it('convertLayoutMode applies mode change + widget updates in single history entry', () => {
    const board = makeBoard({
      layoutMode: 'grid',
      widgets: [
        { ...makeWidget('w1'), freeformPosition: null },
        { ...makeWidget('w2'), freeformPosition: null },
      ],
    });
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => {
      result.current.convertLayoutMode('freeform', [
        { instanceId: 'w1', freeformPosition: { x: 0, y: 0, w: 200, h: 150 } },
        { instanceId: 'w2', freeformPosition: { x: 220, y: 0, w: 200, h: 150 } },
      ]);
    });

    // Mode and positions should both be applied
    expect(result.current.draftBoard!.layoutMode).toBe('freeform');
    const w1 = result.current.draftBoard!.widgets.find((w) => w.instanceId === 'w1');
    const w2 = result.current.draftBoard!.widgets.find((w) => w.instanceId === 'w2');
    expect(w1!.freeformPosition).toEqual({ x: 0, y: 0, w: 200, h: 150 });
    expect(w2!.freeformPosition).toEqual({ x: 220, y: 0, w: 200, h: 150 });

    // Single undo reverts BOTH the layoutMode AND the positions in one step
    act(() => result.current.undo());

    expect(result.current.draftBoard!.layoutMode).toBe('grid');
    const orig1 = result.current.draftBoard!.widgets.find((w) => w.instanceId === 'w1');
    const orig2 = result.current.draftBoard!.widgets.find((w) => w.instanceId === 'w2');
    expect(orig1!.freeformPosition).toBeNull();
    expect(orig2!.freeformPosition).toBeNull();
    // After a single undo there should be nothing left to undo
    expect(result.current.canUndo).toBe(false);
  });

  it('convertLayoutMode with empty updates only changes the mode', () => {
    const board = makeBoard({ layoutMode: 'grid' });
    const { result } = renderHook(() => useBoardEditor(board));

    act(() => {
      result.current.convertLayoutMode('columns', []);
    });

    expect(result.current.draftBoard!.layoutMode).toBe('columns');
    // Widgets untouched
    expect(result.current.draftBoard!.widgets).toHaveLength(1);
    expect(result.current.canUndo).toBe(true);
  });

  it('updateAllWidgetLayouts preserves unrelated widget placements', () => {
    const board = makeBoard({
      widgets: [makeWidget('w1'), makeWidget('w2'), makeWidget('w3')],
    });
    const { result } = renderHook(() => useBoardEditor(board));

    // Only update w1 and w3; w2 should be untouched
    act(() => {
      result.current.updateAllWidgetLayouts([
        { instanceId: 'w1', placements: { lg: { x: 0, y: 10, w: 3, h: 3 } } },
        { instanceId: 'w3', placements: { lg: { x: 6, y: 10, w: 3, h: 3 } } },
      ]);
    });

    const w2 = result.current.draftBoard?.widgets.find((w) => w.instanceId === 'w2');
    // w2's placements should be original from makeWidget
    expect(w2?.placements).toEqual({ lg: { x: 0, y: 0, w: 4, h: 2 } });
  });
});
