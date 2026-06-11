import { useState, useMemo } from 'react';
import {
  Terminal,
  Play,
  Clock,
  History,
  AlertTriangle,
  GitBranch,
  Server,
  Boxes,
  Bot,
  ShieldCheck,
} from 'lucide-react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import {
  useCommandCatalog,
  useCommandEvents,
  type CommandCategory,
  type CommandDefinitionSummary,
} from '@/api/commands';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { ExecuteCommandDialog } from '@/components/commands/execute-command-dialog';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { HydraIcon } from '@/components/icons/hydra-icon';
import { categoryToCommandKind, getCommandIconDescriptor } from '@/lib/command-icons';
import { commandToken, dangerToken } from '@/lib/design-tokens';
import { cn } from '@/lib/utils';
import { WorkflowList } from './components/workflow-list';
import { ExecutionQueue } from './components/execution-queue';
import { CommandHistory } from './components/command-history';

// ── Category icons ────────────────────────────────────────────────────────
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

/**
 * Fall back to a capitalised, hyphen-split label for plugin categories that
 * the API surfaces beyond the three core types (e.g. "ansible", "home-assistant").
 * Known abbreviations (ha, ssh, k8s) get their full display name instead of
 * being naïvely capitalised.
 */
const PLUGIN_CATEGORY_OVERRIDES: Record<string, string> = {
  ha: 'Home Assistant',
  homeassistant: 'Home Assistant',
  'home-assistant': 'Home Assistant',
  k8s: 'Kubernetes',
  ssh: 'SSH',
};

function formatCategoryLabel(category: CommandCategory | string): string {
  if (category in CATEGORY_LABELS) return CATEGORY_LABELS[category as CommandCategory];
  if (PLUGIN_CATEGORY_OVERRIDES[category]) return PLUGIN_CATEGORY_OVERRIDES[category];
  return category
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

const DANGER_LABELS: Record<string, string> = {
  safe: 'Safe',
  low: 'Low risk',
  medium: 'Medium risk',
  high: 'High risk',
  critical: 'Critical',
};

// ── Catalog Tab ───────────────────────────────────────────────────────────
function CatalogTab() {
  const { data: catalog, isLoading, error } = useCommandCatalog();
  const [selectedDef, setSelectedDef] = useState<CommandDefinitionSummary | undefined>();
  const [dialogOpen, setDialogOpen] = useState(false);

  const grouped = useMemo(() => {
    if (!catalog) return {};
    const groups: Partial<Record<CommandCategory, CommandDefinitionSummary[]>> = {};
    for (const def of catalog) {
      if (def.deprecated) continue;
      if (!groups[def.category]) {
        groups[def.category] = [];
      }
      groups[def.category]!.push(def);
    }
    return groups;
  }, [catalog]);

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
          <h3 className="mt-4 text-lg font-semibold">Failed to load catalog</h3>
          <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-3">
            <Skeleton className="h-6 w-32" />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((j) => (
                <Skeleton key={j} className="h-32 rounded-lg" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  const categories = Object.keys(grouped) as CommandCategory[];

  if (categories.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <Terminal className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No commands available</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Command definitions will appear here once registered
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="space-y-6">
        {categories.map((category) => {
          const CategoryIcon = CATEGORY_ICONS[category] ?? Terminal;
          const items = grouped[category] ?? [];
          const kind = categoryToCommandKind(category);
          const isPluginCategory = !(category in CATEGORY_ICONS);
          // For plugin categories (ansible, docker, etc.), resolve the brand
          // icon via HydraIcon instead of the generic Terminal fallback.
          const pluginIconSlug = isPluginCategory ? category : null;

          return (
            <div key={category} className="space-y-3">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'flex h-7 w-7 items-center justify-center rounded-md',
                    commandToken({ kind, surface: 'soft' }),
                  )}
                >
                  {pluginIconSlug ? (
                    <HydraIcon
                      icon={{ source: 'fallback', slug: pluginIconSlug }}
                      fallback="terminal"
                      size={16}
                    />
                  ) : (
                    <CategoryIcon className="h-4 w-4" />
                  )}
                </span>
                <h3 className="text-base font-semibold tracking-tight">
                  {formatCategoryLabel(category)} Commands
                </h3>
                <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
                  {items.length}
                </Badge>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((def) => {
                  const icon = getCommandIconDescriptor({
                    registryId: def.registryId,
                    category: def.category,
                  });
                  const danger = def.dangerLevel ?? 'safe';

                  return (
                    <Card
                      key={def.registryId}
                      className={cn(
                        'group cursor-pointer overflow-hidden transition-all',
                        'hover:border-primary/40 hover:shadow-md hover:-translate-y-0.5',
                        commandToken({ kind, surface: 'rail' }),
                      )}
                      onClick={() => {
                        setSelectedDef(def);
                        setDialogOpen(true);
                      }}
                    >
                      <CardContent className="p-4 space-y-3">
                        <div className="flex items-start gap-3">
                          <div
                            className={cn(
                              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border',
                              commandToken({ kind, surface: 'soft' }),
                            )}
                          >
                            <HydraIcon icon={icon} fallback="terminal" size={20} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <h4 className="truncate text-sm font-semibold leading-tight">
                              {def.displayName}
                            </h4>
                            <p className="mt-0.5 font-mono text-[10px] text-muted-foreground truncate">
                              {def.registryId}
                            </p>
                          </div>
                          <Play className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                        </div>

                        {def.description && (
                          <p className="text-xs text-muted-foreground line-clamp-2">
                            {def.description}
                          </p>
                        )}

                        <div className="flex flex-wrap items-center gap-1.5 pt-1">
                          <span
                            className={cn(
                              'inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium capitalize',
                              dangerToken({ level: danger, surface: 'soft' }),
                            )}
                            title={`Danger level: ${DANGER_LABELS[danger] ?? danger}`}
                          >
                            <span
                              className={cn(
                                'inline-block h-1.5 w-1.5 rounded-full',
                                dangerToken({ level: danger, surface: 'dot' }),
                              )}
                              aria-hidden="true"
                            />
                            {DANGER_LABELS[danger] ?? danger}
                          </span>
                          <Badge
                            variant="outline"
                            className="h-5 px-1.5 text-[10px] font-medium capitalize"
                          >
                            <ShieldCheck className="mr-1 h-3 w-3" />
                            {def.minimumRole}
                          </Badge>
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono tabular-nums text-muted-foreground">
                            <Clock className="h-3 w-3" />
                            {def.timeout}s
                          </span>
                          {def.requiresConfirmation && (
                            <Badge variant="warning" className="h-5 px-1.5 text-[10px]">
                              Confirm
                            </Badge>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <ExecuteCommandDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        definition={selectedDef}
      />
    </>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────
export default function CommandsPage() {
  useDocumentTitle('Command Center');
  const [activeTab, setActiveTab] = useState('catalog');
  // Live command status updates (P2G-T03) via the shared events socket.
  useCommandEvents();

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title="Command Center"
        subtitle="Execute commands, orchestrate workflows, and monitor infrastructure operations"
        showBackButton={false}
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="catalog">
            <Terminal className="h-4 w-4 mr-1.5" />
            Catalog
          </TabsTrigger>
          <TabsTrigger value="workflows">
            <GitBranch className="h-4 w-4 mr-1.5" />
            Workflows
          </TabsTrigger>
          <TabsTrigger value="queue">
            <Clock className="h-4 w-4 mr-1.5" />
            Execution Queue
          </TabsTrigger>
          <TabsTrigger value="history">
            <History className="h-4 w-4 mr-1.5" />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="catalog">
          <CatalogTab />
        </TabsContent>

        <TabsContent value="workflows">
          <WorkflowList />
        </TabsContent>

        <TabsContent value="queue">
          <ExecutionQueue />
        </TabsContent>

        <TabsContent value="history">
          <CommandHistory />
        </TabsContent>
      </Tabs>
    </div>
  );
}
