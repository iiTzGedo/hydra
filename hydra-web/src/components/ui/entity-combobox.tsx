import { useState, useMemo } from 'react';
import { Check, ChevronsUpDown, Loader2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useEntityOptions,
  type EntityOption,
  type EntityType,
} from '@/hooks/use-entity-options';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';

interface EntityComboboxProps {
  /** Currently selected entity ID */
  value: string;
  /** Callback when selection changes */
  onValueChange: (value: string) => void;
  /** Entity type to fetch and display */
  entityType?: EntityType;
  /** Pre-built options (overrides entityType fetch when provided) */
  items?: EntityOption[];
  /** Loading state for externally-provided items */
  itemsLoading?: boolean;
  /** When true, allows typing a value not in the list */
  allowFreeText?: boolean;
  /** When true, shows a clear button for optional fields */
  clearable?: boolean;
  /** IDs to exclude from the options list */
  excludeIds?: string[];
  /** Pass-through query params for the underlying API hook */
  queryParams?: Record<string, unknown>;
  /** Placeholder text */
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  triggerClassName?: string;
}

export function EntityCombobox({
  value,
  onValueChange,
  entityType,
  items: externalItems,
  itemsLoading: externalLoading,
  allowFreeText = false,
  clearable = false,
  excludeIds,
  queryParams,
  placeholder = 'Select...',
  disabled = false,
  className,
  triggerClassName,
}: EntityComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  // Fetch options from API if no external items provided
  const fetchEnabled = !externalItems && !!entityType;
  const { options: fetchedOptions, isLoading: fetchLoading } = useEntityOptions(
    entityType ?? 'node',
    fetchEnabled ? { excludeIds, queryParams } : { excludeIds },
  );

  const options = useMemo(
    () => externalItems ?? (fetchEnabled ? fetchedOptions : []),
    [externalItems, fetchEnabled, fetchedOptions],
  );
  const isLoading = externalLoading ?? (fetchEnabled ? fetchLoading : false);

  // Find the selected option for display
  const selectedOption = useMemo(
    () => options.find((opt) => opt.id === value),
    [options, value],
  );

  // For free-text mode: show a "Use [query]" item when search doesn't match any option
  const showFreeTextOption = useMemo(() => {
    if (!allowFreeText || !search.trim()) return false;
    const lower = search.trim().toLowerCase();
    return !options.some((opt) => opt.id.toLowerCase() === lower);
  }, [allowFreeText, search, options]);

  const handleSelect = (selectedId: string) => {
    onValueChange(selectedId);
    setOpen(false);
    setSearch('');
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onValueChange('');
  };

  // Display label for trigger
  const displayLabel = selectedOption
    ? selectedOption.label
    : value && allowFreeText
      ? value
      : null;

  return (
    <div className={cn('relative', className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              'w-full justify-between font-normal',
              !displayLabel && 'text-muted-foreground',
              triggerClassName,
            )}
          >
            <span className="truncate">
              {displayLabel ?? placeholder}
            </span>
            <div className="ml-2 flex shrink-0 items-center gap-1">
              {clearable && value && (
                <X
                  className="h-3.5 w-3.5 opacity-50 hover:opacity-100"
                  onClick={handleClear}
                />
              )}
              <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
            </div>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder={`Search${entityType ? ` ${entityType}s` : ''}...`}
              value={search}
              onValueChange={setSearch}
            />
            <CommandList>
              {isLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <>
                  <CommandEmpty>
                    {allowFreeText ? 'Type to enter a custom value' : 'No results found'}
                  </CommandEmpty>
                  <CommandGroup>
                    {showFreeTextOption && (
                      <CommandItem
                        value={`__freetext__${search.trim()}`}
                        onSelect={() => handleSelect(search.trim())}
                      >
                        <span className="text-muted-foreground mr-1">Use</span>
                        <span className="font-medium">{search.trim()}</span>
                      </CommandItem>
                    )}
                    {options
                      .filter((opt) => {
                        if (!search.trim()) return true;
                        const q = search.toLowerCase();
                        return (
                          opt.id.toLowerCase().includes(q) ||
                          opt.label.toLowerCase().includes(q) ||
                          opt.sublabel?.toLowerCase().includes(q)
                        );
                      })
                      .map((opt) => (
                        <CommandItem
                          key={opt.id}
                          value={opt.id}
                          onSelect={() => handleSelect(opt.id)}
                        >
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <div
                              className={cn(
                                'flex h-6 w-6 shrink-0 items-center justify-center rounded',
                                opt.iconColorClass
                                  ? `${opt.iconColorClass} bg-current/10`
                                  : 'text-muted-foreground',
                              )}
                            >
                              <opt.icon className="h-3.5 w-3.5" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-sm">{opt.label}</div>
                              {opt.sublabel && (
                                <div className="truncate text-xs text-muted-foreground">
                                  {opt.sublabel}
                                </div>
                              )}
                            </div>
                          </div>
                          {value === opt.id && (
                            <Check className="ml-auto h-4 w-4 shrink-0" />
                          )}
                        </CommandItem>
                      ))}
                  </CommandGroup>
                </>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
