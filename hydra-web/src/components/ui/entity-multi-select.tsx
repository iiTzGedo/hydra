import { useState, useMemo } from 'react';
import { Check, ChevronsUpDown, Loader2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useEntityOptions,
  type EntityOption,
  type EntityType,
} from '@/hooks/use-entity-options';
import { Badge } from '@/components/ui/badge';
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

interface EntityMultiSelectProps {
  /** Currently selected entity IDs */
  values: string[];
  /** Callback when selection changes */
  onValuesChange: (values: string[]) => void;
  /** Entity type to fetch and display */
  entityType: EntityType;
  /** Pre-built options (overrides entityType fetch when provided) */
  items?: EntityOption[];
  /** Loading state for externally-provided items */
  itemsLoading?: boolean;
  /** IDs to exclude from the options list */
  excludeIds?: string[];
  /** Pass-through query params for the underlying API hook */
  queryParams?: Record<string, unknown>;
  /** Placeholder text when nothing is selected */
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function EntityMultiSelect({
  values,
  onValuesChange,
  entityType,
  items: externalItems,
  itemsLoading: externalLoading,
  excludeIds,
  queryParams,
  placeholder = 'Select...',
  disabled = false,
  className,
}: EntityMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const fetchEnabled = !externalItems;
  const { options: fetchedOptions, isLoading: fetchLoading } = useEntityOptions(
    entityType,
    fetchEnabled ? { excludeIds, queryParams } : { excludeIds },
  );

  const options = externalItems ?? fetchedOptions;
  const isLoading = externalLoading ?? (fetchEnabled ? fetchLoading : false);

  // Map of id → option for quick lookup
  const optionMap = useMemo(
    () => new Map(options.map((opt) => [opt.id, opt])),
    [options],
  );

  const handleToggle = (id: string) => {
    if (values.includes(id)) {
      onValuesChange(values.filter((v) => v !== id));
    } else {
      onValuesChange([...values, id]);
    }
  };

  const handleRemove = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onValuesChange(values.filter((v) => v !== id));
  };

  const filteredOptions = useMemo(() => {
    if (!search.trim()) return options;
    const q = search.toLowerCase();
    return options.filter(
      (opt) =>
        opt.id.toLowerCase().includes(q) ||
        opt.label.toLowerCase().includes(q) ||
        opt.sublabel?.toLowerCase().includes(q),
    );
  }, [options, search]);

  return (
    <div className={className}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              'w-full justify-between font-normal h-auto min-h-9',
              !values.length && 'text-muted-foreground',
            )}
          >
            <div className="flex flex-wrap gap-1 flex-1 min-w-0">
              {values.length === 0 && (
                <span className="py-0.5">{placeholder}</span>
              )}
              {values.slice(0, 3).map((id) => {
                const opt = optionMap.get(id);
                return (
                  <Badge
                    key={id}
                    variant="secondary"
                    className="text-xs px-1.5 py-0 h-5 gap-1 max-w-[140px]"
                  >
                    <span className="truncate">{opt?.label ?? id}</span>
                    <X
                      className="h-3 w-3 shrink-0 opacity-50 hover:opacity-100 cursor-pointer"
                      onClick={(e) => handleRemove(id, e)}
                    />
                  </Badge>
                );
              })}
              {values.length > 3 && (
                <Badge variant="outline" className="text-xs px-1.5 py-0 h-5">
                  +{values.length - 3} more
                </Badge>
              )}
            </div>
            <ChevronsUpDown className="ml-2 h-3.5 w-3.5 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder={`Search ${entityType}s...`}
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
                  <CommandEmpty>No results found</CommandEmpty>
                  <CommandGroup>
                    {filteredOptions.map((opt) => {
                      const isSelected = values.includes(opt.id);
                      return (
                        <CommandItem
                          key={opt.id}
                          value={opt.id}
                          onSelect={() => handleToggle(opt.id)}
                        >
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <div
                              className={cn(
                                'flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border',
                                isSelected
                                  ? 'bg-primary border-primary text-primary-foreground'
                                  : 'border-input',
                              )}
                            >
                              {isSelected && <Check className="h-3 w-3" />}
                            </div>
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
                        </CommandItem>
                      );
                    })}
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
