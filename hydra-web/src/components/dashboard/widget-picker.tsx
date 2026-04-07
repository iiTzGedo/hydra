/**
 * Widget Picker dialog for adding widgets to a dashboard board.
 *
 * Fetches the widget registry from the API and presents a categorised,
 * searchable grid of available widget types. When the user selects a
 * widget the parent receives the widget type and its default size so it
 * can create the widget instance via the board API.
 */

import { useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  Bell,
  Clock,
  FileText,
  GitCommit,
  Globe,
  HardDrive,
  LayoutGrid,
  Network,
  Plus,
  Search,
  Server,
  Square,
  Terminal,
  type LucideIcon,
} from 'lucide-react';
import { useWidgetRegistry } from '@/api/dashboards';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { WidgetSize, WidgetTypeDefinition } from '@/types/dashboard';

/** Map lucide icon name strings from the API to actual icon components. */
const ICON_MAP: Record<string, LucideIcon> = {
  'bar-chart-3': BarChart3,
  'hard-drive': HardDrive,
  activity: Activity,
  clock: Clock,
  network: Network,
  server: Server,
  terminal: Terminal,
  globe: Globe,
  bell: Bell,
  'git-commit': GitCommit,
  search: Search,
  'file-text': FileText,
  square: Square,
};

function resolveIcon(iconName: string): LucideIcon {
  return ICON_MAP[iconName] ?? LayoutGrid;
}

interface WidgetPickerProps {
  /** Called when the user selects a widget type. */
  onSelect: (widgetType: string, defaultSize: WidgetSize) => void;
  /** Widget types that are already on the board (shown as "Added"). */
  existingTypes?: string[];
  /** Disable interaction while a mutation is in flight. */
  disabled?: boolean;
}

export function WidgetPicker({
  onSelect,
  existingTypes = [],
  disabled = false,
}: WidgetPickerProps) {
  const [open, setOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const registryQuery = useWidgetRegistry();
  const registry = registryQuery.data;

  const filteredWidgets = useMemo(() => {
    if (!registry) return [];
    let widgets = registry.widgets;

    if (selectedCategory) {
      widgets = widgets.filter((w) => w.category === selectedCategory);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      widgets = widgets.filter(
        (w) =>
          w.displayName.toLowerCase().includes(q) ||
          w.description.toLowerCase().includes(q) ||
          w.widgetType.toLowerCase().includes(q)
      );
    }

    return widgets;
  }, [registry, selectedCategory, searchQuery]);

  const handleSelect = (widget: WidgetTypeDefinition) => {
    onSelect(widget.widgetType, widget.defaultSize);
    setOpen(false);
    setSearchQuery('');
    setSelectedCategory(null);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" disabled={disabled}>
          <Plus className="mr-2 h-4 w-4" />
          Add Widget
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[640px] max-h-[80vh] flex flex-col bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-foreground">Add Widget</DialogTitle>
          <DialogDescription>
            Choose a widget to add to your dashboard board.
          </DialogDescription>
        </DialogHeader>

        {registryQuery.isLoading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner />
          </div>
        ) : registryQuery.isError ? (
          <div className="text-center py-12 text-sm text-muted-foreground">
            Failed to load widget registry.
          </div>
        ) : registry ? (
          <div className="flex flex-col gap-4 min-h-0">
            {/* Search input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search widgets..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-muted/50 border-border"
              />
            </div>

            {/* Category filter chips */}
            <div className="flex flex-wrap gap-2">
              <Button
                variant={selectedCategory === null ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs"
                onClick={() => setSelectedCategory(null)}
              >
                All ({registry.total})
              </Button>
              {registry.categories.map((cat) => (
                <Button
                  key={cat.id}
                  variant={selectedCategory === cat.id ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() =>
                    setSelectedCategory(selectedCategory === cat.id ? null : cat.id)
                  }
                >
                  {cat.name} ({cat.count})
                </Button>
              ))}
            </div>

            {/* Widget grid */}
            <ScrollArea className="flex-1 -mx-1 max-h-[400px]">
              {filteredWidgets.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground">
                  No widgets match your search.
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3 px-1 pb-1">
                  {filteredWidgets.map((widget) => {
                    const Icon = resolveIcon(widget.icon);
                    const alreadyAdded =
                      !widget.capabilities.repeatable &&
                      existingTypes.includes(widget.widgetType);

                    return (
                      <button
                        key={widget.widgetType}
                        type="button"
                        disabled={alreadyAdded}
                        className={cn(
                          'group relative flex flex-col gap-2 rounded-lg border p-3 text-left transition-colors',
                          'border-border hover:border-primary/50 hover:bg-muted/50',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                          alreadyAdded && 'opacity-50 cursor-not-allowed hover:border-border hover:bg-transparent'
                        )}
                        onClick={() => handleSelect(widget)}
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted group-hover:bg-primary/10 transition-colors">
                            <Icon className="h-4.5 w-4.5 text-primary" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-foreground truncate">
                                {widget.displayName}
                              </span>
                              {alreadyAdded && (
                                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                                  Added
                                </Badge>
                              )}
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                              {widget.description}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                          <span>
                            {widget.defaultSize.w}x{widget.defaultSize.h}
                          </span>
                          <span className="text-border">|</span>
                          <span className="capitalize">{widget.category.replace('-', ' ')}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
