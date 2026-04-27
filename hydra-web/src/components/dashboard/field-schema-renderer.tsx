/**
 * FieldSchemaRenderer — renders a single FieldSchema entry as its
 * appropriate input control.
 *
 * Supported types:
 *  string     → <Input type="text">
 *  number     → <Input type="number"> with min/max/step
 *  boolean    → <Switch>
 *  enum       → <Select> with options
 *  color      → <Input type="color">
 *  entity-ref → <EntityCombobox> (searchable entity selector)
 */

import type { FieldSchema } from '@/types/dashboard';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EntityCombobox } from '@/components/ui/entity-combobox';

// ── Props ──────────────────────────────────────────────────────────

export interface FieldSchemaRendererProps {
  schema: FieldSchema;
  value: unknown;
  onChange: (value: unknown) => void;
}

// ── Component ──────────────────────────────────────────────────────

export function FieldSchemaRenderer({ schema, value, onChange }: FieldSchemaRendererProps) {
  return (
    <div className="space-y-1">
      <Label
        htmlFor={`field-schema-${schema.key}`}
        className="text-xs flex items-center gap-1"
      >
        {schema.label}
        {schema.required && (
          <span className="text-destructive" aria-hidden>
            *
          </span>
        )}
      </Label>
      {schema.description && (
        <p className="text-[10px] text-muted-foreground leading-snug">{schema.description}</p>
      )}
      {renderControl(schema, value, onChange)}
    </div>
  );
}

// ── Control renderer (pure function, no hooks) ─────────────────────

function renderControl(schema: FieldSchema, value: unknown, onChange: (v: unknown) => void) {
  // Use schema default when the provided value is explicitly undefined
  const current = value === undefined ? schema.default : value;
  const fieldId = `field-schema-${schema.key}`;

  switch (schema.type) {
    case 'string':
      return (
        <Input
          id={fieldId}
          value={String(current ?? '')}
          onChange={(e) => onChange(e.target.value)}
          className="h-7 text-xs"
        />
      );

    case 'number':
      return (
        <Input
          id={fieldId}
          type="number"
          min={schema.min}
          max={schema.max}
          step={schema.step ?? 1}
          value={Number(current ?? 0)}
          onChange={(e) => {
            let n = Number(e.target.value);
            if (Number.isNaN(n)) n = Number(schema.default ?? 0);
            if (schema.min !== undefined) n = Math.max(schema.min, n);
            if (schema.max !== undefined) n = Math.min(schema.max, n);
            onChange(n);
          }}
          className="h-7 text-xs"
        />
      );

    case 'boolean':
      return (
        <Switch
          id={fieldId}
          checked={Boolean(current)}
          onCheckedChange={onChange}
          aria-label={schema.label}
        />
      );

    case 'enum': {
      const enumValue = typeof current === 'string' && current.length > 0
        ? current
        : '__default__';
      return (
        <Select
          value={enumValue}
          onValueChange={(val) => onChange(val === '__default__' ? '' : val)}
        >
          <SelectTrigger id={fieldId} className="h-7 text-xs">
            <SelectValue placeholder={schema.default !== undefined ? String(schema.default) : 'Select...'} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__default__">Default</SelectItem>
            {(schema.options ?? []).map((opt) => (
              <SelectItem key={opt.value} value={opt.value} className="text-xs">
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }

    case 'color':
      return (
        <div className="flex items-center gap-2">
          <Input
            id={fieldId}
            type="color"
            value={String(current ?? '#000000')}
            onChange={(e) => onChange(e.target.value)}
            className="h-7 w-12 cursor-pointer p-0.5"
          />
          <span className="text-xs text-muted-foreground font-mono">
            {String(current ?? '#000000')}
          </span>
        </div>
      );

    case 'entity-ref': {
      const entityType = schema.entityType;
      if (!entityType) {
        // Defensive fallback — should never happen in production with a well-formed schema
        return (
          <div className="text-xs text-destructive">
            Configuration error: entity-ref field &quot;{schema.key}&quot; missing entityType
          </div>
        );
      }
      return (
        <EntityCombobox
          entityType={entityType}
          value={typeof current === 'string' ? current : ''}
          onValueChange={(val) => onChange(val)}
          clearable
          placeholder={`Select ${entityType}...`}
          triggerClassName="h-7 text-xs"
        />
      );
    }

    default:
      return null;
  }
}
