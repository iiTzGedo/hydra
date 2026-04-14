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
} from 'lucide-react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import {
  useCommandCatalog,
  type CommandCategory,
  type CommandDefinitionSummary,
} from '@/api/commands';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { ExecuteCommandDialog } from '@/components/commands/execute-command-dialog';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
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

          return (
            <div key={category} className="space-y-3">
              <div className="flex items-center gap-2">
                <CategoryIcon className="h-5 w-5 text-muted-foreground" />
                <h3 className="text-lg font-semibold">
                  {CATEGORY_LABELS[category] ?? category} Commands
                </h3>
                <Badge variant="secondary">{items.length}</Badge>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((def) => (
                  <Card
                    key={def.registryId}
                    className="cursor-pointer transition-colors hover:border-primary/40 hover:bg-muted/30"
                    onClick={() => {
                      setSelectedDef(def);
                      setDialogOpen(true);
                    }}
                  >
                    <CardContent className="p-4 space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="text-sm font-medium leading-tight">
                          {def.displayName}
                        </h4>
                        <Play className="h-4 w-4 text-muted-foreground shrink-0" />
                      </div>
                      {def.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {def.description}
                        </p>
                      )}
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                          {def.minimumRole}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground">
                          {def.timeout}s timeout
                        </span>
                        {def.requiresConfirmation && (
                          <Badge variant="warning" className="text-[10px] px-1.5 py-0">
                            Confirm
                          </Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
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
