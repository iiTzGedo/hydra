/**
 * WidgetConfiguratorPopover — in-place widget configuration popover
 * shown when a widget is clicked in edit mode.
 *
 * Contains:
 *  - Title input (widget display title)
 *  - Size presets (S / M / L / XL)
 *  - Refresh interval dropdown
 *  - Dynamic configSchema fields via FieldSchemaRenderer
 *  - Actions: Duplicate, Remove
 *  - Footer: "Edit data binding…" button
 */

import { useId, useRef } from 'react';
import { Copy, Database, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DashboardWidgetInstance, WidgetTypeDefinition } from '@/types/dashboard';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { FieldSchemaRenderer } from '@/components/dashboard/field-schema-renderer';

// ── Constants ──────────────────────────────────────────────────────

export const SIZE_PRESETS = {
  S: { w: 2, h: 2 },
  M: { w: 4, h: 3 },
  L: { w: 6, h: 4 },
  XL: { w: 12, h: 6 },
} as const;

export type SizePresetKey = keyof typeof SIZE_PRESETS;

const REFRESH_INTERVALS = [
  { value: '0', label: 'Off' },
  { value: '10', label: '10s' },
  { value: '30', label: '30s' },
  { value: '60', label: '1m' },
  { value: '300', label: '5m' },
  { value: '900', label: '15m' },
  { value: '3600', label: '1h' },
] as const;

// ── Props ──────────────────────────────────────────────────────────

export interface WidgetConfiguratorPopoverProps {
  /** The widget type definition (provides displayName + configSchema) */
  typeDef: WidgetTypeDefinition;
  /** The current widget instance (provides config values) */
  instance: DashboardWidgetInstance;
  /** Whether the popover is open */
  open?: boolean;
  /** Trigger element — if omitted, the popover is rendered with no trigger */
  trigger?: React.ReactNode;
  /** Called when a config key changes */
  onConfigChange: (key: string, value: unknown) => void;
  /** Called when a size preset is selected */
  onSizeChange: (size: { w: number; h: number }) => void;
  /** Called when the refresh interval changes (0 = off) */
  onRefreshChange?: (seconds: number) => void;
  /** Called to remove this widget */
  onDelete: () => void;
  /** Called to duplicate this widget */
  onDuplicate: () => void;
  /** Called to open the data binding editor */
  onOpenDataBinding: () => void;
  /** Controlled open state handler */
  onOpenChange?: (open: boolean) => void;
}

// ── Component ──────────────────────────────────────────────────────

export function WidgetConfiguratorPopover({
  typeDef,
  instance,
  open,
  trigger,
  onConfigChange,
  onSizeChange,
  onRefreshChange,
  onDelete,
  onDuplicate,
  onOpenDataBinding,
  onOpenChange,
}: WidgetConfiguratorPopoverProps) {
  const titleId = useId();
  const refreshId = useId();
  const titleInputRef = useRef<HTMLInputElement>(null);

  const config = (instance.config ?? {}) as Record<string, unknown>;
  const currentTitle = typeof config.title === 'string' ? config.title : '';
  const currentRefresh =
    typeof config.refreshInterval === 'number' ? String(config.refreshInterval) : '0';

  // Determine which size preset is active (match w and h against lg placement)
  const lgPlacement = instance.placements?.lg ?? instance.position;
  const activeSizeKey = lgPlacement
    ? (Object.entries(SIZE_PRESETS).find(
        ([, dims]) => dims.w === lgPlacement.w && dims.h === lgPlacement.h,
      )?.[0] as SizePresetKey | undefined)
    : undefined;

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      {trigger ? <PopoverTrigger asChild>{trigger}</PopoverTrigger> : null}
      <PopoverContent
        className="w-[260px] p-0 overflow-hidden"
        side="right"
        align="start"
        sideOffset={8}
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          titleInputRef.current?.focus();
        }}
      >
        {/* Header */}
        <div className="px-3 py-2 border-b border-border/60 bg-muted/30">
          <p className="text-xs font-semibold truncate">{typeDef.displayName}</p>
          <p className="text-[10px] text-muted-foreground">{instance.instanceId}</p>
        </div>

        <div className="px-3 py-2 space-y-3 max-h-[70vh] overflow-y-auto">
          {/* Title field */}
          <div className="space-y-1">
            <Label htmlFor={titleId} className="text-xs">
              Title
            </Label>
            <Input
              id={titleId}
              ref={titleInputRef}
              value={currentTitle}
              placeholder={typeDef.displayName}
              onChange={(e) => onConfigChange('title', e.target.value)}
              className="h-7 text-xs"
            />
          </div>

          {/* Size presets */}
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Size</p>
            <div className="grid grid-cols-4 gap-1">
              {(Object.entries(SIZE_PRESETS) as Array<[SizePresetKey, { w: number; h: number }]>).map(
                ([key, dims]) => (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={activeSizeKey === key}
                    onClick={() => onSizeChange(dims)}
                    className={cn(
                      'rounded border px-1.5 py-1 text-[10px] font-medium transition-colors',
                      activeSizeKey === key
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border hover:bg-muted text-muted-foreground hover:text-foreground',
                    )}
                    title={`${dims.w} × ${dims.h}`}
                  >
                    {key}
                  </button>
                ),
              )}
            </div>
          </div>

          {/* Refresh interval */}
          {onRefreshChange ? (
            <div className="space-y-1">
              <Label htmlFor={refreshId} className="text-xs">
                Refresh
              </Label>
              <Select
                value={currentRefresh}
                onValueChange={(val) => onRefreshChange(Number(val))}
              >
                <SelectTrigger id={refreshId} className="h-7 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REFRESH_INTERVALS.map((interval) => (
                    <SelectItem
                      key={interval.value}
                      value={interval.value}
                      className="text-xs"
                    >
                      {interval.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          {/* Dynamic configSchema fields */}
          {typeDef.configSchema.length > 0 ? (
            <>
              <Separator />
              <div className="space-y-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Widget Settings
                </p>
                {typeDef.configSchema.map((field) => (
                  <FieldSchemaRenderer
                    key={field.key}
                    schema={field}
                    value={config[field.key]}
                    onChange={(val) => onConfigChange(field.key, val)}
                  />
                ))}
              </div>
            </>
          ) : null}

          {/* Actions */}
          <Separator />
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="flex-1 h-7 text-xs gap-1.5"
              onClick={onDuplicate}
            >
              <Copy className="h-3 w-3" />
              Duplicate
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="flex-1 h-7 text-xs gap-1.5 border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={onDelete}
            >
              <Trash2 className="h-3 w-3" />
              Remove
            </Button>
          </div>
        </div>

        {/* Footer — data binding */}
        <div className="border-t border-border/60 px-3 py-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="w-full h-7 text-xs gap-1.5 justify-start text-muted-foreground hover:text-foreground"
            onClick={onOpenDataBinding}
          >
            <Database className="h-3 w-3 shrink-0" />
            Edit data binding…
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
