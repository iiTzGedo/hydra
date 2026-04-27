import { Redo2, Save, Undo2, X } from 'lucide-react';
import type { BoardEditorApi } from '@/hooks/use-board-editor';
import type { LayoutMode } from '@/types/dashboard';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface EditModeToolbarProps {
  editor: BoardEditorApi;
  onSave: () => void;
  isSaving: boolean;
  /** Override for layout mode changes — allows the page to run conversion logic. */
  onLayoutModeChange?: (mode: LayoutMode) => void;
}

export function EditModeToolbar({ editor, onSave, isSaving, onLayoutModeChange }: EditModeToolbarProps) {
  const mode = editor.draftBoard?.layoutMode ?? 'grid';
  const handleModeChange = onLayoutModeChange ?? editor.setLayoutMode;

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b bg-background">
      <Button
        size="sm"
        variant="ghost"
        disabled={!editor.canUndo || isSaving}
        onClick={editor.undo}
        aria-label="Undo"
      >
        <Undo2 className="w-4 h-4" />
      </Button>
      <Button
        size="sm"
        variant="ghost"
        disabled={!editor.canRedo || isSaving}
        onClick={editor.redo}
        aria-label="Redo"
      >
        <Redo2 className="w-4 h-4" />
      </Button>

      <div className="w-px h-6 bg-border mx-1" />

      <ModeToggle mode={mode} onChange={handleModeChange} disabled={isSaving} />

      <div className="flex-1" />

      <span
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="text-sm text-muted-foreground min-w-[110px] text-right"
      >
        {editor.isDirty ? 'Unsaved changes' : ''}
      </span>

      <Button
        size="sm"
        variant="outline"
        onClick={editor.discard}
        disabled={!editor.isDirty || isSaving}
      >
        <X className="w-4 h-4 mr-1" />
        Discard
      </Button>

      <Button
        size="sm"
        onClick={onSave}
        disabled={!editor.isDirty || isSaving}
      >
        <Save className="w-4 h-4 mr-1" />
        {isSaving ? 'Saving…' : 'Save'}
      </Button>
    </div>
  );
}

interface ModeToggleProps {
  mode: LayoutMode;
  onChange: (m: LayoutMode) => void;
  disabled?: boolean;
}

const MODE_LABELS: Record<LayoutMode, string> = {
  grid: 'Grid',
  columns: 'Columns',
  freeform: 'Freeform',
};

const ALL_MODES: LayoutMode[] = ['grid', 'columns', 'freeform'];

function ModeToggle({ mode, onChange, disabled }: ModeToggleProps) {
  return (
    <div className="inline-flex border rounded-md p-0.5">
      {ALL_MODES.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          disabled={disabled}
          className={cn(
            'px-2 py-1 text-xs rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
            mode === m
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-accent',
          )}
          aria-label={`Layout mode: ${m}`}
          aria-pressed={mode === m}
        >
          {MODE_LABELS[m]}
        </button>
      ))}
    </div>
  );
}
