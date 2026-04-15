import { useState, useMemo } from 'react';
import { Check, ChevronsUpDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';
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

export interface EnumOption {
  value: string;
  label: string;
}

interface EnumMultiSelectProps {
  /** Currently selected values */
  values: string[];
  /** Callback when selection changes */
  onValuesChange: (values: string[]) => void;
  /** Static options to display */
  options: EnumOption[];
  /** When true, allows typing a value not in the options list */
  allowFreeText?: boolean;
  /** Placeholder text when nothing is selected */
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function EnumMultiSelect({
  values,
  onValuesChange,
  options,
  allowFreeText = false,
  placeholder = 'Select...',
  disabled = false,
  className,
}: EnumMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const optionMap = useMemo(
    () => new Map(options.map((opt) => [opt.value, opt.label])),
    [options],
  );

  const handleToggle = (val: string) => {
    if (values.includes(val)) {
      onValuesChange(values.filter((v) => v !== val));
    } else {
      onValuesChange([...values, val]);
    }
  };

  const handleRemove = (val: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onValuesChange(values.filter((v) => v !== val));
  };

  const filteredOptions = useMemo(() => {
    if (!search.trim()) return options;
    const q = search.toLowerCase();
    return options.filter(
      (opt) =>
        opt.value.toLowerCase().includes(q) ||
        opt.label.toLowerCase().includes(q),
    );
  }, [options, search]);

  // For free-text mode: show a "Add [query]" item when search doesn't match
  const showFreeTextOption = useMemo(() => {
    if (!allowFreeText || !search.trim()) return false;
    const lower = search.trim().toLowerCase();
    return (
      !options.some((opt) => opt.value.toLowerCase() === lower) &&
      !values.includes(search.trim())
    );
  }, [allowFreeText, search, options, values]);

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
              {values.slice(0, 4).map((val) => (
                <Badge
                  key={val}
                  variant="secondary"
                  className="text-xs px-1.5 py-0 h-5 gap-1"
                >
                  <span className="truncate">
                    {optionMap.get(val) ?? val}
                  </span>
                  <X
                    className="h-3 w-3 shrink-0 opacity-50 hover:opacity-100 cursor-pointer"
                    onClick={(e) => handleRemove(val, e)}
                  />
                </Badge>
              ))}
              {values.length > 4 && (
                <Badge variant="outline" className="text-xs px-1.5 py-0 h-5">
                  +{values.length - 4} more
                </Badge>
              )}
            </div>
            <ChevronsUpDown className="ml-2 h-3.5 w-3.5 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder="Search..."
              value={search}
              onValueChange={setSearch}
            />
            <CommandList>
              <CommandEmpty>
                {allowFreeText ? 'Type to add a custom value' : 'No results found'}
              </CommandEmpty>
              <CommandGroup>
                {showFreeTextOption && (
                  <CommandItem
                    value={`__freetext__${search.trim()}`}
                    onSelect={() => {
                      handleToggle(search.trim());
                      setSearch('');
                    }}
                  >
                    <span className="text-muted-foreground mr-1">Add</span>
                    <span className="font-medium">{search.trim()}</span>
                  </CommandItem>
                )}
                {filteredOptions.map((opt) => {
                  const isSelected = values.includes(opt.value);
                  return (
                    <CommandItem
                      key={opt.value}
                      value={opt.value}
                      onSelect={() => handleToggle(opt.value)}
                    >
                      <div
                        className={cn(
                          'mr-2 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border',
                          isSelected
                            ? 'bg-primary border-primary text-primary-foreground'
                            : 'border-input',
                        )}
                      >
                        {isSelected && <Check className="h-3 w-3" />}
                      </div>
                      <span>{opt.label}</span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
