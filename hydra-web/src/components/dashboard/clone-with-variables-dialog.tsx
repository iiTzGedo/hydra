/**
 * CloneWithVariablesDialog — prompts for a name and optional variable values
 * when cloning a dashboard board.
 *
 * If the source board declares `variables` (an array of FieldSchema entries),
 * the dialog renders one FieldSchemaRenderer per variable so the user can
 * supply values for the new copy. When there are no variables only the name
 * field is shown, keeping the UX lean.
 */

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { FieldSchemaRenderer } from './field-schema-renderer';
import type { DashboardBoard, FieldSchema } from '@/types/dashboard';

// ── Props ──────────────────────────────────────────────────────────

export interface CloneWithVariablesDialogProps {
  /** The board being cloned. May optionally declare `variables`. */
  sourceBoard: DashboardBoard & { variables?: FieldSchema[] };
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called when the user confirms the clone. */
  onSubmit: (payload: { name: string; variables: Record<string, unknown> }) => void;
  /** True while the clone mutation is in flight — disables the submit button. */
  isSubmitting: boolean;
}

// ── Component ──────────────────────────────────────────────────────

export function CloneWithVariablesDialog({
  sourceBoard,
  open,
  onOpenChange,
  onSubmit,
  isSubmitting,
}: CloneWithVariablesDialogProps) {
  const variables = sourceBoard.variables;
  const hasVariables = Array.isArray(variables) && variables.length > 0;

  const [name, setName] = useState(`${sourceBoard.name} (clone)`);
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    if (!hasVariables) return {};
    return Object.fromEntries(variables!.map((v) => [v.key, v.default]));
  });

  // The dialog might re-open for a different board — reset state when it opens.
  // We use a key on the dialog content in the parent to force remount, but
  // also defend here by deriving the default name from the current sourceBoard.
  const defaultName = `${sourceBoard.name} (clone)`;

  const allRequiredFilled = !hasVariables || variables!.every((v) => {
    if (!v.required) return true;
    const val = values[v.key];
    return val !== undefined && val !== '' && val !== null;
  });

  const canSubmit = !isSubmitting && name.trim().length > 0 && allRequiredFilled;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit({ name: name.trim(), variables: values });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-foreground">
            Clone &ldquo;{sourceBoard.name}&rdquo;
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          {/* Name field — always visible */}
          <div className="space-y-1">
            <Label htmlFor="clone-name" className="text-xs">
              Name
            </Label>
            <Input
              id="clone-name"
              value={name}
              placeholder={defaultName}
              onChange={(e) => setName(e.target.value)}
              className="bg-muted/50 border-border"
              autoFocus
            />
          </div>

          {/* Variable fields — only when the source board declares variables */}
          {hasVariables && (
            <div className="space-y-3 pt-2 border-t border-border/60">
              <p className="text-xs text-muted-foreground">
                This board uses variables. Fill them in for the new copy.
              </p>
              {variables!.map((v) => (
                <FieldSchemaRenderer
                  key={v.key}
                  schema={v}
                  value={values[v.key]}
                  onChange={(val) =>
                    setValues((prev) => ({ ...prev, [v.key]: val }))
                  }
                />
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {isSubmitting ? 'Cloning\u2026' : 'Clone'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
