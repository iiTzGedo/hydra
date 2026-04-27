/**
 * Tests for EditModeToolbar component.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EditModeToolbar } from '@/components/dashboard/edit-mode-toolbar';
import type { BoardEditorApi } from '@/hooks/use-board-editor';
import type { DashboardBoard } from '@/types/dashboard';

function makeDraftBoard(overrides?: Partial<DashboardBoard>): DashboardBoard {
  return {
    boardId: 'board-1',
    name: 'Test',
    description: null,
    icon: null,
    ownerId: 'user-1',
    ownerType: 'user',
    boardType: 'user',
    visibility: { scope: 'private', sharedWith: { roles: [], users: [] } },
    widgetCount: 0,
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
        breakpoints: {},
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
    widgets: [],
    ...overrides,
  };
}

function makeEditor(overrides?: Partial<BoardEditorApi>): BoardEditorApi {
  return {
    baseBoard: makeDraftBoard(),
    draftBoard: makeDraftBoard(),
    isDirty: false,
    canUndo: false,
    canRedo: false,
    addWidget: vi.fn(),
    removeWidget: vi.fn(),
    duplicateWidget: vi.fn(),
    updateWidgetLayout: vi.fn(),
    updateAllWidgetLayouts: vi.fn(),
    updateWidgetConfig: vi.fn(),
    setLayoutMode: vi.fn(),
    convertLayoutMode: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    discard: vi.fn(),
    commitSave: vi.fn(),
    ...overrides,
  };
}

describe('EditModeToolbar', () => {
  it('renders undo, redo, discard, and save buttons', () => {
    const editor = makeEditor();
    const onSave = vi.fn();
    render(<EditModeToolbar editor={editor} onSave={onSave} isSaving={false} />);

    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /redo/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /discard/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
  });

  it('undo button calls editor.undo', async () => {
    const user = userEvent.setup();
    const editor = makeEditor({ canUndo: true });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);

    await user.click(screen.getByRole('button', { name: /undo/i }));
    expect(editor.undo).toHaveBeenCalledOnce();
  });

  it('redo button calls editor.redo', async () => {
    const user = userEvent.setup();
    const editor = makeEditor({ canRedo: true });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);

    await user.click(screen.getByRole('button', { name: /redo/i }));
    expect(editor.redo).toHaveBeenCalledOnce();
  });

  it('discard button calls editor.discard', async () => {
    const user = userEvent.setup();
    const editor = makeEditor({ isDirty: true });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);

    await user.click(screen.getByRole('button', { name: /discard/i }));
    expect(editor.discard).toHaveBeenCalledOnce();
  });

  it('save button calls onSave', async () => {
    const user = userEvent.setup();
    const editor = makeEditor({ isDirty: true });
    const onSave = vi.fn();
    render(<EditModeToolbar editor={editor} onSave={onSave} isSaving={false} />);

    await user.click(screen.getByRole('button', { name: /save/i }));
    expect(onSave).toHaveBeenCalledOnce();
  });

  it('undo and redo are disabled when canUndo/canRedo are false', () => {
    const editor = makeEditor({ canUndo: false, canRedo: false });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);

    expect(screen.getByRole('button', { name: /undo/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /redo/i })).toBeDisabled();
  });

  it('discard and save are disabled when not dirty', () => {
    const editor = makeEditor({ isDirty: false });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);

    expect(screen.getByRole('button', { name: /discard/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();
  });

  it('all interactive buttons are disabled when isSaving', () => {
    const editor = makeEditor({ isDirty: true, canUndo: true, canRedo: true });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={true} />);

    expect(screen.getByRole('button', { name: /undo/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /redo/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /discard/i })).toBeDisabled();
    // Save button disabled when isSaving (shows "Saving…")
    expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled();
    expect(screen.getByText(/saving/i)).toBeInTheDocument();
  });

  it('shows "Unsaved changes" label when isDirty', () => {
    const editor = makeEditor({ isDirty: true });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);
    expect(screen.getByRole('status')).toHaveTextContent('Unsaved changes');
  });

  it('hides "Unsaved changes" label when not dirty', () => {
    const editor = makeEditor({ isDirty: false });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);
    // The aria-live region is always mounted (so announcements work), but its
    // text content is empty when there are no unsaved changes.
    const statusEl = screen.getByRole('status');
    expect(statusEl).toBeInTheDocument();
    expect(statusEl).toHaveTextContent('');
  });

  it('renders layout mode toggle buttons', () => {
    const editor = makeEditor();
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);

    expect(screen.getByRole('button', { name: /layout mode: grid/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /layout mode: columns/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /layout mode: freeform/i })).toBeInTheDocument();
  });

  it('clicking a layout mode calls editor.setLayoutMode', async () => {
    const user = userEvent.setup();
    const editor = makeEditor();
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);

    await user.click(screen.getByRole('button', { name: /layout mode: columns/i }));
    expect(editor.setLayoutMode).toHaveBeenCalledWith('columns');
  });

  it('active layout mode button has aria-pressed=true', () => {
    const editor = makeEditor({
      draftBoard: makeDraftBoard({ layoutMode: 'freeform' }),
    });
    render(<EditModeToolbar editor={editor} onSave={vi.fn()} isSaving={false} />);

    const freeformBtn = screen.getByRole('button', { name: /layout mode: freeform/i });
    expect(freeformBtn).toHaveAttribute('aria-pressed', 'true');

    const gridBtn = screen.getByRole('button', { name: /layout mode: grid/i });
    expect(gridBtn).toHaveAttribute('aria-pressed', 'false');
  });
});
