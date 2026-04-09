import { useMemo, useState } from 'react';
import {
  Boxes,
  Bot,
  Loader2,
  Plus,
  Search,
  Server,
  Terminal,
} from 'lucide-react';
import {
  useCommandCatalog,
  type CommandCategory,
  type CommandDefinitionSummary,
} from '@/api/commands';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';

// ── Category metadata ──────────────────────────────────────────────────

const CATEGORY_ICONS: Record<CommandCategory, typeof Server> = {
  service: Boxes,
  node: Server,
  agent: Bot,
};

const CATEGORY_LABELS: Record<CommandCategory, string> = {
  service: 'Service',
  node: 'Node',
  agent: 'Agent',
};

const CATEGORY_ORDER: CommandCategory[] = ['node', 'service', 'agent'];

// ── Props ──────────────────────────────────────────────────────────────

interface StepPaletteProps {
  onAddCommand: (definition: CommandDefinitionSummary) => void;
}

// ── Component ──────────────────────────────────────────────────────────

export function StepPalette({ onAddCommand }: StepPaletteProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const { data: catalog, isLoading, error } = useCommandCatalog();

  const grouped = useMemo(() => {
    if (!catalog) return {};

    const query = searchQuery.toLowerCase().trim();
    const groups: Partial<Record<CommandCategory, CommandDefinitionSummary[]>> = {};

    for (const def of catalog) {
      if (def.deprecated) continue;

      // Apply search filter
      if (
        query &&
        !def.displayName.toLowerCase().includes(query) &&
        !def.action.toLowerCase().includes(query) &&
        !def.registryId.toLowerCase().includes(query) &&
        !(def.description?.toLowerCase().includes(query))
      ) {
        continue;
      }

      if (!groups[def.category]) {
        groups[def.category] = [];
      }
      groups[def.category]!.push(def);
    }

    return groups;
  }, [catalog, searchQuery]);

  const categories = useMemo(() => {
    const available = Object.keys(grouped) as CommandCategory[];
    return CATEGORY_ORDER.filter((c) => available.includes(c)).concat(
      available.filter((c) => !CATEGORY_ORDER.includes(c))
    );
  }, [grouped]);

  return (
    <div className="flex h-full flex-col border-r">
      <div className="p-3 pb-2">
        <h3 className="text-sm font-semibold text-muted-foreground mb-2">
          Command Palette
        </h3>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter commands..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 pl-8 text-xs"
          />
        </div>
      </div>

      <Separator />

      <ScrollArea className="flex-1">
        <div className="p-2">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && (
            <p className="px-2 py-4 text-xs text-destructive text-center">
              Failed to load catalog
            </p>
          )}

          {!isLoading && !error && categories.length === 0 && (
            <p className="px-2 py-4 text-xs text-muted-foreground text-center">
              {searchQuery ? 'No commands match your filter' : 'No commands available'}
            </p>
          )}

          {categories.map((category, catIdx) => {
            const CategoryIcon = CATEGORY_ICONS[category] ?? Terminal;
            const items = grouped[category] ?? [];

            return (
              <div key={category} className={catIdx > 0 ? 'mt-3' : undefined}>
                <div className="flex items-center gap-1.5 px-1 py-1">
                  <CategoryIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {CATEGORY_LABELS[category] ?? category}
                  </span>
                  <Badge variant="secondary" className="ml-auto text-[10px] px-1 py-0 h-4">
                    {items.length}
                  </Badge>
                </div>

                <div className="space-y-0.5">
                  {items.map((def) => (
                    <button
                      key={def.registryId}
                      type="button"
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent hover:text-accent-foreground group"
                      onClick={() => onAddCommand(def)}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium">
                          {def.displayName}
                        </div>
                        {def.description && (
                          <div className="truncate text-[10px] text-muted-foreground">
                            {def.description}
                          </div>
                        )}
                      </div>
                      <Plus className="h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
